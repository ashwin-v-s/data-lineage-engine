# Spike Report D-17: Graph Visualization Library Selection

**Author**: Member 5 (API & UI Lead)  
**Date**: 2026-09-23  
**Status**: COMPLETED / RECOMMENDATION SUBMITTED FOR TEAM REVIEW  
**Scope**: Decision D-17 in `docs/FINAL_ARCHITECTURE_AND_RESEARCH_EXECUTION_PACK.md`  

---

## 1. Executive Summary & Context

Kairos Stage 1 UI requires a responsive, high-precision forensic lineage cockpit. The visual representation must support:
- Multi-state visual redundancy (OBSERVED, REFUTED_FOR_RUN, POSSIBLE, UNKNOWN) with border patterns, fill textures, SVG badges, and directional arrows.
- Dual-axis historical time-travel (Valid at $T_v$ vs Known as of $T_k$) with dynamic edge and node transitions.
- Interactive expansion affordances (Atlan / Neo4j Bloom style directional expansion popovers).
- Crisp performance on graphs ranging from single-hop incident subgraphs (5–15 nodes) to complete multi-tenant pipeline DAGs (100–300 nodes).
- Strict accessibility compliance without relying on color alone, and zero numeric confidence artifacts.

This spike rigorously compares the two shortlisted candidates: **React Flow (@xyflow/react)** and **Cytoscape.js**.

---

## 2. Head-to-Head Comparison Matrix

| Evaluation Criteria | React Flow (@xyflow/react) | Cytoscape.js | Winner / Assessment |
|---|---|---|---|
| **Custom Node Architecture** | Pure React DOM components. Full flexibility for Tailwind CSS, badges, action buttons, popovers, and inputs. | Canvas/WebGL based. Complex HTML inside nodes requires overlays (`cytoscape-node-html-label`) which desync during high-velocity pan/zoom. | **React Flow**: Native React integration allows seamless component embedding (e.g. expansion popover, column tables). |
| **Directed Edge Styling** | SVG path generation with custom markers, animated dashes (`stroke-dasharray`), and inline edge badges (e.g. D-14 hazard pill). | Rich edge styling via stylesheet selectors, native arrowheads and bezier curving. | **Tie**: Both support custom stroke patterns and arrow markers cleanly. |
| **Bitemporal State Transitions** | React state drives DOM diffing directly. Nodes and edges re-render reactively with smooth CSS transitions. | Requires imperatively mutating graph elements (`cy.batch()`, `ele.style()`). Fast, but requires manual sync with React lifecycle. | **React Flow**: Declarative state binding matches Kairos bitemporal slider model cleanly. |
| **Layout Algorithms** | Does not bundle layout engines. Requires external integration with Dagre (`@dagrejs/dagre`) or ELK (`elkjs`). | Bundles grid, circle, breadthfirst, and supports extensions for CoSE, Dagre, Kola, and Euler. | **Cytoscape.js**: Superior built-in layout suite and automated force-directed physics. |
| **Large Graph Performance (>300 nodes)** | Canvas rendered via DOM elements. At >500 nodes, DOM node count can degrade frame rates unless virtualized. | WebGL/Canvas multi-buffering. Can effortlessly render 10,000+ elements at 60 FPS. | **Cytoscape.js**: Clear winner for massive enterprise graphs; however, Kairos Stage 1 scopes traversal depth to $\le 10$ hops. |
| **Developer Ergonomics & Learning Curve** | High. Any standard React developer can build custom nodes in minutes. | Moderate. Requires learning Cytoscape's jQuery-like imperative selector API. | **React Flow**: Drastically reduces initial implementation time for Stage 1. |
| **Licensing** | MIT (React Flow v11/v12 Pro features are optional; core is open source). | MIT. | **Tie**: Both are fully MIT and enterprise-friendly. |

---

## 3. Benchmark Observations on Prototype Graph (14 Nodes / 18 Edges)

Testing against the Kairos forensic topology (`orders_fact` anchor + upstream sources + downstream consumers):

1. **Custom Node Complexity**:
   The `stg_customer_orders` node contains a header badge, a column descriptor table (`gross_amount NUMERIC`), an embedded downstream directional expansion trigger, and an interactive popover.
   - In React Flow: Built in ~40 lines of JSX using Tailwind classes.
   - In Cytoscape: Required complex canvas bounding box calculations and secondary DOM absolute positioning.

2. **D-14 Warning Pill**:
   The D-14 Hazard Pill anchored to the center of edge `stg_customer_orders -> orders_fact` renders natively as an `EdgeLabelRenderer` in React Flow with standard CSS z-index and click events.

3. **Performance at Bounded Depth**:
   At default depth (1 to 3 hops, ~15–30 nodes), React Flow maintained a constant 60 FPS during pinch-zoom and pan interactions on standard hardware.

---

## 4. Final Recommendation (D-17 Resolution)

**Adopt React Flow (`@xyflow/react` + `@dagrejs/dagre`) for Stage 1 Lineage Explorer.**

### Rationale:
1. **Focus on Semantics, Not Mega-Graphs**: Kairos is an execution-conditioned reasoning engine, not a global web crawler. The UI's mission is deep forensic inspection of specific causal edges (R1–R5 rules, evidence dossiers, bitemporal divergence), which demands rich DOM nodes.
2. **Rapid Delivery for Four-Day Checkpoint**: React Flow directly supports our interactive HTML/Tailwind mockup without needing to recreate complex HTML interfaces inside Canvas/WebGL shaders.
3. **Escalation Path**: If future benchmarks require rendering >1,000 nodes without depth bounds, Cytoscape.js can be introduced as an alternate layout projection backend.

---

## 5. Decision Record Entry

- **Decision ID**: `D-17`
- **Topic**: Frontend Graph Visualization Library
- **Decision**: Adopt React Flow with Dagre layout for Stage 1.
- **Reviewers**: M5 (Author), M4 (Architecture Review), Team Lead
