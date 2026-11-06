import { db } from "hatchable";

export const access = "admin";
export const methods = ["GET"];

// ---------------------------------------------------------------------------
// GET /api/v1/ground-truth
//   ?case_id=<id>                              — ground truth for one corpus case
//   ?case_id=<id>&source=<col>&target=<col>    — single pair lookup
//   (no params)                                — all ground truth records
//
// INDEPENDENCE RULE: This endpoint reads only the corpus fixture data.
// It never reads kairos_evidence, the reasoning engine, or prediction outputs.
// Ground truth must remain independent of the prediction path.
// Mirrors: research/ground_truth/reference_interpreter.py
// ---------------------------------------------------------------------------

const CORPUS_GROUND_TRUTH = [
  {
    case_id: "W03_case_when",
    sql: "SELECT CASE WHEN country = 'US' THEN salary ELSE 0 END AS adjusted_salary FROM employees",
    source_dataset: "employees",
    target_output: "out_adjusted_salary",
    granularity: "COLUMN",
    propagated_pairs: [
      { source_column: "employees.country", target_column: "adjusted_salary",
        label: "PROPAGATED",
        reason: "country appears in the CASE WHEN condition — INDIRECT/CONDITIONAL dependency" },
      { source_column: "employees.salary",  target_column: "adjusted_salary",
        label: "PROPAGATED",
        reason: "salary is the THEN branch value — DIRECT/TRANSFORMATION dependency" }
    ],
    run_specific_note: "In a run with NO US rows, salary is NOT read for any row. Static analysis says POSSIBLE; runtime truth says NOT_PROPAGATED for that run. This is the core Kairos research case."
  },
  {
    case_id: "W04_aggregate_sum",
    sql: "SELECT SUM(amount) AS total_amount FROM orders",
    source_dataset: "orders",
    target_output: "out_total_amount",
    granularity: "COLUMN",
    propagated_pairs: [
      { source_column: "orders.amount", target_column: "total_amount",
        label: "PROPAGATED",
        reason: "SUM(amount) directly aggregates the amount column — DIRECT/AGGREGATION" }
    ],
    run_specific_note: "SUM on an empty table produces NULL, not 0. If the table is empty, amount is never read."
  },
  {
    case_id: "W05_join_alias",
    sql: "SELECT o.order_id, c.name FROM orders o INNER JOIN customers c ON o.customer_id = c.id",
    source_dataset: "orders",
    target_output: "out_order_customer",
    granularity: "COLUMN",
    propagated_pairs: [
      { source_column: "orders.order_id",    target_column: "order_id",
        label: "PROPAGATED", reason: "DIRECT/IDENTITY — order_id passes through unchanged" },
      { source_column: "customers.name",     target_column: "name",
        label: "PROPAGATED", reason: "DIRECT/IDENTITY — customer name passes through unchanged" },
      { source_column: "orders.customer_id", target_column: "order_id",
        label: "PROPAGATED", reason: "INDIRECT/JOIN — customer_id is the join key; controls which rows appear" },
      { source_column: "customers.id",       target_column: "name",
        label: "PROPAGATED", reason: "INDIRECT/JOIN — customers.id is the join key on the right side" }
    ],
    run_specific_note: "If there are no matching join pairs, no rows are produced. Join key columns are INDIRECT dependencies."
  },
  {
    case_id: "W06_count_star",
    sql: "SELECT COUNT(*) AS row_count FROM orders",
    source_dataset: "orders",
    target_output: "out_row_count",
    granularity: "DATASET",
    propagated_pairs: [],
    dataset_level_dependency: {
      source_dataset: "orders",
      target_column: "row_count",
      label: "PROPAGATED",
      reason: "COUNT(*) depends on the dataset as a whole — no specific column. Granularity=DATASET."
    },
    run_specific_note: "COUNT(*) never reads individual column values. Dataset-level evidence only."
  },
  {
    case_id: "W07_select_star",
    sql: "SELECT * FROM employees",
    source_dataset: "employees",
    target_output: "out_all_employees",
    granularity: "COLUMN",
    propagated_pairs: [
      { source_column: "employees.id",      target_column: "id",      label: "PROPAGATED", reason: "DIRECT/IDENTITY — SELECT *" },
      { source_column: "employees.name",    target_column: "name",    label: "PROPAGATED", reason: "DIRECT/IDENTITY — SELECT *" },
      { source_column: "employees.salary",  target_column: "salary",  label: "PROPAGATED", reason: "DIRECT/IDENTITY — SELECT *" },
      { source_column: "employees.country", target_column: "country", label: "PROPAGATED", reason: "DIRECT/IDENTITY — SELECT *" }
    ],
    run_specific_note: "SELECT * propagates every column. Schema expansion must happen at parse time using the declared schema."
  },
  {
    case_id: "W08_where_filter",
    sql: "SELECT salary FROM employees WHERE country = 'US'",
    source_dataset: "employees",
    target_output: "out_us_salary",
    granularity: "COLUMN",
    propagated_pairs: [
      { source_column: "employees.salary",  target_column: "salary",
        label: "PROPAGATED", reason: "DIRECT/IDENTITY — salary is the selected column" },
      { source_column: "employees.country", target_column: "salary",
        label: "PROPAGATED", reason: "INDIRECT/FILTER — country controls which rows appear in output" }
    ],
    run_specific_note: "WHERE clause columns are INDIRECT dependencies. If no rows satisfy country='US', salary is still read for filtering."
  },
  {
    case_id: "W09_coalesce",
    sql: "SELECT COALESCE(email, phone, 'unknown') AS contact FROM users",
    source_dataset: "users",
    target_output: "out_contact",
    granularity: "COLUMN",
    propagated_pairs: [
      { source_column: "users.email", target_column: "contact",
        label: "PROPAGATED", reason: "DIRECT/CONDITIONAL — email is the first COALESCE argument; used when non-NULL" },
      { source_column: "users.phone", target_column: "contact",
        label: "PROPAGATED", reason: "DIRECT/CONDITIONAL — phone is the second COALESCE argument; used when email is NULL" }
    ],
    run_specific_note: "In a run where all users have a non-null email, phone is never actually read. Static says POSSIBLE; runtime truth depends on data."
  }
];

function hashForRecord(caseId, source, target) {
  return `gt:${caseId}:${source}:${target}`;
}

export default async function (req, res) {
  const caseId       = String(req.query?.case_id || "").trim() || null;
  const sourceFilter = String(req.query?.source  || "").trim() || null;
  const targetFilter = String(req.query?.target  || "").trim() || null;

  try {
    let records = CORPUS_GROUND_TRUTH;

    if (caseId) {
      records = records.filter(r => r.case_id === caseId);
      if (!records.length) {
        return res.status(404).json({
          ok: false,
          error: "case_not_found",
          message: `No ground truth found for case_id '${caseId}'. Valid cases: ${CORPUS_GROUND_TRUTH.map(r => r.case_id).join(", ")}`
        });
      }
    }

    const pairs = [];
    for (const rec of records) {
      for (const pair of (rec.propagated_pairs || [])) {
        if (sourceFilter && pair.source_column !== sourceFilter) continue;
        if (targetFilter && pair.target_column !== targetFilter) continue;
        pairs.push({
          id: hashForRecord(rec.case_id, pair.source_column, pair.target_column),
          case_id: rec.case_id,
          source_dataset: rec.source_dataset,
          target_output: rec.target_output,
          source_column: pair.source_column,
          target_column: pair.target_column,
          granularity: "COLUMN",
          label: pair.label,
          reason: pair.reason,
          run_specific_note: rec.run_specific_note,
          provider: "reference_interpreter",
          version: "kairos-corpus-1.0"
        });
      }
      if (rec.dataset_level_dependency && !sourceFilter && !targetFilter) {
        const d = rec.dataset_level_dependency;
        pairs.push({
          id: hashForRecord(rec.case_id, d.source_dataset, d.target_column),
          case_id: rec.case_id,
          source_dataset: rec.source_dataset,
          target_output: rec.target_output,
          source_column: null,
          target_column: d.target_column,
          granularity: "DATASET",
          label: d.label,
          reason: d.reason,
          run_specific_note: rec.run_specific_note,
          provider: "reference_interpreter",
          version: "kairos-corpus-1.0"
        });
      }
    }

    // Single-pair exact lookup
    if (sourceFilter && targetFilter && caseId) {
      if (!pairs.length) {
        return res.json({
          ok: true,
          source: "reference_interpreter",
          query: { case_id: caseId, source: sourceFilter, target: targetFilter },
          result: {
            label: "NOT_PROPAGATED",
            reason: "This source→target pair does not appear in the corpus expected mappings for this case.",
            provider: "reference_interpreter",
            version: "kairos-corpus-1.0"
          },
          independence_note: "Ground truth is computed independently of the evidence and reasoning paths."
        });
      }
      return res.json({
        ok: true,
        source: "reference_interpreter",
        query: { case_id: caseId, source: sourceFilter, target: targetFilter },
        result: pairs[0],
        independence_note: "Ground truth is computed independently of the evidence and reasoning paths."
      });
    }

    const summary = CORPUS_GROUND_TRUTH.map(r => ({
      case_id: r.case_id,
      sql: r.sql,
      source_dataset: r.source_dataset,
      granularity: r.granularity,
      propagated_count: r.propagated_pairs?.length || 0,
      has_dataset_level: !!r.dataset_level_dependency,
      run_specific_note: r.run_specific_note
    }));

    return res.json({
      ok: true,
      source: "reference_interpreter",
      provider: "reference_interpreter",
      version: "kairos-corpus-1.0",
      total_cases: CORPUS_GROUND_TRUTH.length,
      total_pairs: pairs.length,
      pairs,
      corpus_summary: caseId ? undefined : summary,
      independence_note: "Ground truth is derived from hand-verified corpus expected mappings. It is computed independently of the evidence table, the reasoning engine, and any runtime prediction."
    });

  } catch (err) {
    return res.status(500).json({ ok: false, error: "ground_truth_failed", message: String(err.message) });
  }
}
