# Solution Overview

## Core mechanism
**IBM Bob is the investigator's copilot and the system's orchestrator.** The investigator talks to Bob in plain language ("Who received money from the victims within an hour of the SIM swap?"). Bob decides which tools to call through our **MCP server** and composes the results. Without Bob there is no entry point to the analytics; every capability is a Bob tool.

Pipeline: unstructured evidence -> entities and relations -> temporal knowledge graph -> pattern detection -> disruption plan -> legal-mapped case brief.

## What makes it different from naive alternatives
| Naive approach | Ours |
|---|---|
| Upload CSVs, draw a graph | Ingest raw text and mixed evidence; Bob extracts and resolves entities |
| Single "kingpin" answer | Ranked hypotheses with confidence and "what evidence would change this" |
| Insight only | **Action**: min-cut freeze/block set and before/after capacity |
| Generic summary | FIR-ready brief with sections, evidence IDs, Sec 63 BSA checklist |

## Key design decisions
1. **Bob as orchestrator, deterministic engines as tools.** Bob handles language and planning; graph maths (centrality, min-cut, SIM-swap rules) stays deterministic and testable, so results are reproducible in court.
2. **Temporal graph.** Every edge carries timestamps and a source, enabling SIM-swap chain detection and freeze-window logic.
3. **Provenance everywhere.** Each node/edge links to an evidence ID and confidence; contradictions are surfaced, not hidden.
4. **Suggest, don't decide, on law.** Legal mapping is advisory with a mandatory "verify with legal officer" note.

## Three headline features
1. **SIM-Swap Chain Detector**: SIM replaced -> new IMEI on same number -> OTP-linked UPI transactions within a window. Shown as a three-lane timeline.
2. **Disruption Planner (Action Engine)**: betweenness ranking + min-cut yields the smallest freeze/block set, with a before/after simulation ("network capacity reduced by X%").
3. **Legal & Compliance Layer**: maps findings to IT Act 66C/66D and BNS provisions, attaches evidence IDs, and emits a Sec 63 BSA certificate checklist.

## User experience
1. Investigator uploads mock case files (transactions, CDRs, device logs, complaints).
2. Graph and timeline appear; Bob narrates the pattern type and hierarchy.
3. SIM-swap lane highlights the swap and the fraud that followed.
4. Investigator clicks **Disrupt** (or asks Bob) and sees the network collapse.
5. **Generate brief** produces an FIR-ready document with recommended actions: freeze now, telecom requests, bank requests, field verification.
