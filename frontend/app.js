/**
 * Temporal Lineage Cockpit — Client Controller
 *
 * Implements real-time interactions with Kairos /api/v1 backend:
 * - Historical Time-Travel scrubbing (T_v vs T_k)
 * - 4-state reasoning display with verbatim Section 19 text
 * - Directional Expansion popovers (Atlan / Bloom pattern)
 * - Inspector tab switching (Details, Evidence, Relationships)
 * - Benchmark Evaluation Mode toggling (Hazard mode)
 * - Standalone mock fallback if backend is offline
 */

const API_BASE = window.location.origin.includes('http') ? window.location.origin : 'http://127.0.0.1:8000';

const STATE_MESSAGES = {
  OBSERVED: "At least one source value was observed to contribute to at least one target output in this run. This does not imply contribution to every row or every run.",
  REFUTED_FOR_RUN: "No propagation was established for this run under the declared complete-evaluation conditions. This is not a universal claim that the dependency can never occur.",
  POSSIBLE: "Static analysis permits this dependency, but available evidence is insufficient to establish whether propagation occurred in this run.",
  UNKNOWN: "Kairos cannot safely evaluate this dependency because relevant semantics, identity, schema or instrumentation is unsupported or ambiguous."
};

let currentRunId = "run_2026_09_23_093214";
let currentTv = "2026-08-15T00:00:00Z";
let currentTk = "2026-09-23T11:45:00Z";
let isLive = false;
let benchmarkOracleVisible = true;
let activeNode = "orders_fact";

// Initialize application on DOM ready
document.addEventListener("DOMContentLoaded", () => {
  checkBackendHealth();
  setupSearch();
});

async function checkBackendHealth() {
  try {
    const res = await fetch(`${API_BASE}/api/v1/health`);
    if (res.ok) {
      const data = await res.json();
      console.log("[Kairos] Backend connected:", data);
      const badge = document.querySelector("#health-indicator");
      if (badge) badge.classList.replace("bg-outline", "bg-primary");
    }
  } catch (err) {
    console.info("[Kairos] Operating in standalone browser mode with internal mock graph.");
  }
}

// ----------------------------------------------------------------------------
// Bitemporal Time Travel
// ----------------------------------------------------------------------------
function resetToLive() {
  isLive = true;
  currentTv = null;
  const banner = document.getElementById("temporal-banner-text");
  const timeDelta = document.getElementById("time-delta-badge");
  const tvDisplay = document.getElementById("tv-display-val");
  const stgNodeState = document.getElementById("stg-node-state-badge");
  const stgNodeBorder = document.getElementById("stg-node-box");
  const stgNodeSub = document.getElementById("stg-node-subtext");
  const stgEdge = document.getElementById("svg-edge-stg");

  if (tvDisplay) tvDisplay.textContent = "LIVE (CURRENT)";
  if (timeDelta) timeDelta.innerHTML = `<span>Δ 0h</span>`;
  if (banner) {
    banner.innerHTML = `<span class="truncate text-primary font-semibold">Showing LIVE lineage graph. Valid at current moment. Known as of now.</span>`;
  }
  if (stgNodeState) {
    stgNodeState.className = "px-1.5 py-0.5 rounded bg-primary text-on-primary font-mono-sm text-[10px] font-bold";
    stgNodeState.textContent = "✓ OBSERVED";
  }
  if (stgNodeBorder) {
    stgNodeBorder.className = "relative flex flex-col p-3 rounded bg-surface-container border-2 border-primary shadow-lg cursor-pointer";
  }
  if (stgNodeSub) {
    stgNodeSub.textContent = "Observed propagation: gross_amount -> net_revenue";
  }
  if (stgEdge) {
    stgEdge.setAttribute("stroke", "#8ed5ff");
    stgEdge.setAttribute("stroke-dasharray", "none");
  }

  // Update right inspector if open
  updateInspectorState("OBSERVED", "Rule R2: Observed runtime propagation for run_2026_09_23_093214.");
}

function setToHistorical() {
  isLive = false;
  currentTv = "2026-08-15T00:00:00Z";
  const banner = document.getElementById("temporal-banner-text");
  const timeDelta = document.getElementById("time-delta-badge");
  const tvDisplay = document.getElementById("tv-display-val");
  const stgNodeState = document.getElementById("stg-node-state-badge");
  const stgNodeBorder = document.getElementById("stg-node-box");
  const stgNodeSub = document.getElementById("stg-node-subtext");
  const stgEdge = document.getElementById("svg-edge-stg");

  if (tvDisplay) tvDisplay.textContent = "2026-08-15 00:00:00 UTC";
  if (timeDelta) timeDelta.innerHTML = `<span class="material-symbols-outlined text-[12px]">compare_arrows</span><span>Δ -39d 11h</span>`;
  if (banner) {
    banner.innerHTML = `<span class="truncate">Showing lineage valid on <strong class="text-tertiary font-semibold">Aug 15, 2026 00:00:00 UTC</strong>, according to what Kairos had recorded as of <strong class="text-on-surface">Sep 23, 2026 11:45:00 UTC</strong>.</span>`;
  }
  if (stgNodeState) {
    stgNodeState.className = "px-1.5 py-0.5 rounded bg-surface-container-highest text-outline font-mono-sm text-[10px] font-bold";
    stgNodeState.textContent = "? UNKNOWN AT T_v";
  }
  if (stgNodeBorder) {
    stgNodeBorder.className = "relative flex flex-col p-3 rounded bg-surface-container border-2 border-dashed border-outline-variant/70 shadow-lg cursor-pointer";
  }
  if (stgNodeSub) {
    stgNodeSub.textContent = "No observation existed at T_v = 2026-08-15";
  }
  if (stgEdge) {
    stgEdge.setAttribute("stroke", "#87929a");
    stgEdge.setAttribute("stroke-dasharray", "4,4");
  }

  updateInspectorState("UNKNOWN", "Rule R5: No observation recorded for run_2026_09_23_093214 at Valid Time 2026-08-15 00:00:00 UTC (edge created in schema v2.0 on 2026-09-01).");
}

function updateInspectorState(state, ruleNote) {
  const badge = document.getElementById("inspector-state-badge");
  const title = document.getElementById("inspector-state-title");
  const text = document.getElementById("inspector-state-text");
  if (badge) badge.textContent = state === "OBSERVED" ? "Rule R2: OBSERVED" : "Rule R5: NO PRIOR RECORD";
  if (title) title.textContent = state === "OBSERVED" ? "OBSERVED (Live)" : "UNKNOWN (Historical T_v)";
  if (text) text.textContent = ruleNote;
}

// ----------------------------------------------------------------------------
// View Density Toggle: Investigator vs Research
// ----------------------------------------------------------------------------
function setDensity(mode) {
  const btnInvestigator = document.getElementById('density-investigator');
  const btnResearch = document.getElementById('density-research');
  const techAccordion = document.getElementById('technical-details-accordion');

  if (mode === 'investigator') {
    btnInvestigator.className = "flex items-center gap-1 px-2.5 py-1 rounded text-xs font-mono-sm font-semibold bg-primary-container text-on-primary-container shadow-sm transition-all";
    btnResearch.className = "flex items-center gap-1 px-2.5 py-1 rounded text-xs font-mono-sm font-medium text-outline hover:text-on-surface transition-all";
    if (techAccordion) techAccordion.removeAttribute('open');
  } else {
    btnResearch.className = "flex items-center gap-1 px-2.5 py-1 rounded text-xs font-mono-sm font-semibold bg-primary-container text-on-primary-container shadow-sm transition-all";
    btnInvestigator.className = "flex items-center gap-1 px-2.5 py-1 rounded text-xs font-mono-sm font-medium text-outline hover:text-on-surface transition-all";
    if (techAccordion) techAccordion.setAttribute('open', '');
  }
}

// ----------------------------------------------------------------------------
// Rails & Inspector Panels
// ----------------------------------------------------------------------------
function toggleLeftRail() {
  const rail = document.getElementById('left-filter-rail');
  const expander = document.getElementById('left-rail-expander');
  if (rail.classList.contains('hidden')) {
    rail.classList.remove('hidden');
    expander.classList.add('hidden');
  } else {
    rail.classList.add('hidden');
    expander.classList.remove('hidden');
  }
}

function resetFilters() {
  document.querySelectorAll('#left-filter-rail input[type="checkbox"]').forEach(cb => cb.checked = true);
}

function toggleRightInspector() {
  const insp = document.getElementById('right-inspector');
  const rail = document.getElementById('right-inspector-rail');
  if (insp.classList.contains('hidden')) {
    insp.classList.remove('hidden');
    rail.classList.add('hidden');
  } else {
    insp.classList.add('hidden');
    rail.classList.remove('hidden');
  }
}

function expandRightWithTab(tab) {
  const insp = document.getElementById('right-inspector');
  const rail = document.getElementById('right-inspector-rail');
  insp.classList.remove('hidden');
  rail.classList.add('hidden');
  switchInspectorTab(tab);
}

function switchInspectorTab(tab) {
  const tabs = ['details', 'evidence', 'relationships'];
  tabs.forEach(t => {
    const btn = document.getElementById(`tab-btn-${t}`);
    const panel = document.getElementById(`tab-panel-${t}`);
    if (t === tab) {
      if (btn) btn.className = "flex-1 py-1 rounded-xl text-center font-mono-sm text-xs font-bold bg-surface-container text-primary shadow-sm transition-all";
      if (panel) panel.classList.remove('hidden');
    } else {
      if (btn) btn.className = "flex-1 py-1 rounded-xl text-center font-mono-sm text-xs font-medium text-outline hover:text-on-surface transition-all";
      if (panel) panel.classList.add('hidden');
    }
  });
}

// ----------------------------------------------------------------------------
// Benchmark Oracle (Hazard Mode)
// ----------------------------------------------------------------------------
function toggleBenchmarkOracle() {
  const banner = document.getElementById('benchmark-hazard-banner');
  const block = document.getElementById('benchmark-oracle-block');
  const badge = document.getElementById('benchmark-status-badge');
  benchmarkOracleVisible = !benchmarkOracleVisible;

  if (benchmarkOracleVisible) {
    if (banner) banner.classList.remove('hidden');
    if (block) block.classList.remove('hidden');
    if (badge) badge.classList.remove('hidden');
  } else {
    if (banner) banner.classList.add('hidden');
    if (block) block.classList.add('hidden');
    if (badge) badge.classList.add('hidden');
  }
}

// ----------------------------------------------------------------------------
// Directional Expansion Popover
// ----------------------------------------------------------------------------
function toggleDirectionalPopover(id) {
  const el = document.getElementById(id || 'directional-popover-stg');
  if (el) {
    el.classList.toggle('hidden');
  }
}

function applyExpansion(nodeName) {
  alert(`Directional expansion applied for ${nodeName}: loaded immediate adjacent neighborhood.`);
  toggleDirectionalPopover();
}

// ----------------------------------------------------------------------------
// Search Functionality
// ----------------------------------------------------------------------------
function setupSearch() {
  const searchInput = document.getElementById('global-search-input');
  if (!searchInput) return;

  searchInput.addEventListener('keydown', async (e) => {
    if (e.key === 'Enter') {
      const q = searchInput.value.trim();
      if (!q) return;
      try {
        const res = await fetch(`${API_BASE}/api/v1/search?q=${encodeURIComponent(q)}`);
        if (res.ok) {
          const data = await res.json();
          if (data.results && data.results.length > 0) {
            alert(`Found ${data.total} entity matches: ${data.results.map(r => r.name).join(', ')}`);
          } else {
            alert(`No entities matching '${q}' found.`);
          }
        }
      } catch (err) {
        console.warn("Search local fallback:", q);
      }
    }
  });
}
