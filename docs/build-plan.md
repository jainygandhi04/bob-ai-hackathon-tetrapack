# Module-wise Build Plan

Each module is independently testable and only depends on modules above it.

| # | Module | Folder | Depends on | "Done" means | Status |
|---|---|---|---|---|---|
| 1 | Temporal graph + mock data + evidence registry | `graph/`, `mock_data/` | - | `python -m mock_data.load` builds graph; tests green | DONE |
| 2 | Entity Engine: normalisation, Hinglish/Devanagari extraction, entity resolution | `engines/entity/` | 1 | Rakesh Mandal / R. Mandal / राकेश मंडल merge into 1 person; complaints yield edges | DONE |
| 3 | Fraud Engine: SIM-swap chain detector, mule scoring, pattern typing, hierarchy ranking | `engines/fraud/` | 1, 2 | Detects SWAP-001..003, ignores decoy SWAP-004; ranks kingpin top with reasons | next |
| 4 | Action Engine: betweenness, min-cut freeze/block set, before/after simulation | `engines/action/` | 1, 3 | Freeze set + "capacity reduced by X%" | |
| 5 | Evidence Engine: confidence, contradictions, challenge mode | `engines/evidence/` | 1-3 | `challenge()` returns counter-evidence and what would change the ranking | |
| 6 | Legal layer + Brief generator | `legal/`, `brief/` | 1-5 | Markdown/PDF FIR-ready brief with evidence IDs, hashes, BSA Sec 63 checklist | |
| 7 | MCP server (Bob tool surface) | `mcp_server/` | 1-6 | All 12 tools from architecture.md callable from Bob | |
| 8 | Investigator UI | `ui/` | 7 | Graph, SIM-swap lane, Disrupt before/after, Generate brief, chat | |
| 9 | Case memory, polish, submission | `graph/`, `demo/` | all | Cross-case linking, screenshots, demo video, submission.yaml filled | |

Rule: engines stay deterministic (no LLM calls inside them). Bob does language + planning; engines do the maths.
