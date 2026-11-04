import { db } from "hatchable";

export const access = "admin";
export const methods = ["GET", "POST"];

// ---------------------------------------------------------------------------
// POST /api/v1/runtime-evidence
//   Body: { run_id?: string }   — process one run or all unprocessed events
//
// GET  /api/v1/runtime-evidence
//   ?run_id=<id>  — list evidence for a specific run
//   ?case_id=<id> — list evidence for a benchmark case
//   (no params)   — list all evidence records, latest first
// ---------------------------------------------------------------------------

async function sha256hex(value) {
  const bytes = new TextEncoder().encode(
    typeof value === "string" ? value : JSON.stringify(value)
  );
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), b => b.toString(16).padStart(2, "0")).join("");
}

// Normalize one raw OpenLineage event payload into evidence record(s).
// Returns array of evidence objects ready to upsert.
// RULE: missing events are never converted to negative evidence.
async function normalizeToEvidence(raw) {
  const payload  = raw.payload;
  const runId    = String(payload?.run?.runId   || "").trim();
  const jobName  = String(payload?.job?.name    || "").trim();
  const eventType = String(payload?.eventType   || "UNKNOWN").toUpperCase();
  const eventTime = raw.event_time;
  const caseId   = String(payload?.kairos_case_id || "").trim() || null;

  if (!runId)   return [];   // malformed — skip, not negative evidence
  if (eventType !== "COMPLETE") return [];  // only COMPLETE events are positive observations

  const inputs  = Array.isArray(payload?.inputs)  ? payload.inputs  : [];
  const outputs = Array.isArray(payload?.outputs) ? payload.outputs : [];

  if (!inputs.length || !outputs.length) return [];

  const evidenceRecords = [];

  for (const inp of inputs) {
    const sourceName = [inp.namespace, inp.name].filter(Boolean).join("/");
    for (const out of outputs) {
      const targetName = [out.namespace, out.name].filter(Boolean).join("/");

      // Dataset-level positive observation — job read sourceName and wrote targetName
      // This is NOT proof of column-level dependency; it is a dataset boundary observation.
      const fingerprint = await sha256hex({ run_id: runId, source: sourceName, target: targetName, type: "RUNTIME_OBSERVED" });
      const evidenceId  = "m2-evidence:" + fingerprint;

      const coverage = JSON.stringify({
        mode: "RUNTIME_DATASET_BOUNDARY",
        complete: true,
        granularity: "DATASET",
        note: "COMPLETE event observed. Dataset boundary coverage only — column-level coverage not available from this event."
      });

      const metadata = JSON.stringify({
        source_system: "openlineage",
        job_name: jobName,
        event_type: eventType,
        raw_event_id: raw.id,
        kairos_case_id: caseId,
        producer: payload?.producer || null,
        semantics: "Positive runtime observation. Absence of an event is NOT stored as negative evidence."
      });

      evidenceRecords.push({
        id: evidenceId,
        source_name: sourceName,
        target_name: targetName,
        state: "OBSERVED",
        evidence_type: "RUNTIME_OBSERVED",
        run_id: runId,
        coverage,
        rule_name: "R_RUNTIME_COMPLETE",
        explanation: `COMPLETE event for run ${runId}: job ${jobName} read ${sourceName} and wrote ${targetName}. Dataset-level observation only.`,
        valid_from: eventTime,
        metadata,
        case_id: caseId
      });
    }
  }

  return evidenceRecords;
}

export default async function (req, res) {
  // ---- GET: query stored evidence ----------------------------------------
  if (req.method === "GET") {
    try {
      const runId  = String(req.query?.run_id  || "").trim().slice(0, 400) || null;
      const caseId = String(req.query?.case_id || "").trim().slice(0, 200) || null;
      const limit  = Math.min(500, Math.max(1, parseInt(req.query?.limit || "100", 10) || 100));

      let rows;
      if (runId) {
        const r = await db.query(
          `SELECT id, source_name, target_name, state, evidence_type, run_id,
                  coverage, rule_name, explanation, valid_from, recorded_from, metadata
           FROM kairos_evidence
           WHERE run_id = $1
           ORDER BY recorded_from DESC LIMIT $2`,
          [runId, limit]
        );
        rows = r.rows;
      } else if (caseId) {
        const r = await db.query(
          `SELECT id, source_name, target_name, state, evidence_type, run_id,
                  coverage, rule_name, explanation, valid_from, recorded_from, metadata
           FROM kairos_evidence
           WHERE metadata->>'kairos_case_id' = $1
           ORDER BY recorded_from DESC LIMIT $2`,
          [caseId, limit]
        );
        rows = r.rows;
      } else {
        const r = await db.query(
          `SELECT id, source_name, target_name, state, evidence_type, run_id,
                  coverage, rule_name, explanation, valid_from, recorded_from, metadata
           FROM kairos_evidence
           WHERE evidence_type = 'RUNTIME_OBSERVED'
           ORDER BY recorded_from DESC LIMIT $1`,
          [limit]
        );
        rows = r.rows;
      }

      const total = await db.query(
        `SELECT COUNT(*)::int AS n FROM kairos_evidence WHERE evidence_type = 'RUNTIME_OBSERVED'`
      );

      return res.json({
        ok: true,
        source: "postgresql",
        count: rows.length,
        total_runtime_observed: total.rows[0].n,
        evidence: rows,
        semantics: {
          OBSERVED: "A COMPLETE runtime event was received for this run/dataset pair.",
          missing_event: "Missing events are never stored as REFUTED_FOR_RUN. Absence of evidence is not evidence of absence."
        }
      });
    } catch (err) {
      return res.status(500).json({ ok: false, error: "query_failed", message: String(err.message) });
    }
  }

  // ---- POST: normalize raw OpenLineage events → evidence -----------------
  if (req.method === "POST") {
    try {
      const runIdFilter = String(req.body?.run_id || "").trim() || null;

      let rawRows;
      if (runIdFilter) {
        const r = await db.query(
          `SELECT id, event_time, payload FROM kairos_raw_events
           WHERE source_system = 'openlineage'
             AND payload->>'eventType' = 'COMPLETE'
             AND payload->'run'->>'runId' = $1`,
          [runIdFilter]
        );
        rawRows = r.rows;
      } else {
        // Process all COMPLETE openlineage events not yet in kairos_evidence
        const r = await db.query(
          `SELECT r.id, r.event_time, r.payload
           FROM kairos_raw_events r
           WHERE r.source_system = 'openlineage'
             AND r.payload->>'eventType' = 'COMPLETE'
             AND NOT EXISTS (
               SELECT 1 FROM kairos_evidence e
               WHERE e.metadata->>'raw_event_id' = r.id
             )
           ORDER BY r.event_time ASC
           LIMIT 200`
        );
        rawRows = r.rows;
      }

      if (!rawRows.length) {
        return res.json({ ok: true, message: "No unprocessed COMPLETE events found.", evidence_created: 0 });
      }

      let created = 0, skipped = 0;

      for (const raw of rawRows) {
        const records = await normalizeToEvidence(raw);
        for (const ev of records) {
          const r = await db.query(
            `INSERT INTO kairos_evidence
               (id, source_name, target_name, state, evidence_type, run_id,
                coverage, rule_name, explanation, valid_from, recorded_from, metadata)
             VALUES
               ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, now(), $11::jsonb)
             ON CONFLICT (id) DO NOTHING
             RETURNING id`,
            [
              ev.id, ev.source_name, ev.target_name,
              ev.state, ev.evidence_type, ev.run_id,
              ev.coverage, ev.rule_name, ev.explanation,
              ev.valid_from, ev.metadata
            ]
          );
          if (r.rows?.length) created++;
          else skipped++;
        }
      }

      return res.json({
        ok: true,
        raw_events_processed: rawRows.length,
        evidence_created: created,
        evidence_skipped_duplicates: skipped,
        semantics: {
          OBSERVED: "Stored for every COMPLETE event with valid input/output datasets.",
          missing_event: "Missing or failed events produce no evidence records. Absence is not refutation.",
          granularity: "Dataset-level only. Column-level coverage requires the columnLineage facet which is not present in these events."
        }
      });
    } catch (err) {
      return res.status(500).json({ ok: false, error: "normalization_failed", message: String(err.message) });
    }
  }

  return res.status(405).json({ ok: false, error: "method_not_allowed" });
}
