# Cyber Fraud Network Analyzer (Bob-powered)

An IBM Bob-driven investigation tool that turns unstructured cyber-fraud intelligence into a temporal knowledge graph, exposes the ring's hierarchy, tells investigators exactly what to freeze, and drafts an FIR-ready case brief.

## Team
- **Team:** TODO
- **Track:** AI
- **Lead:** TODO
- **Members:** TODO

## Problem Statement
Rings like the Jamtara SIM-swap network spread money across bank accounts, SIMs and devices. Investigators trace links by hand for weeks while funds are cashed out in minutes, and most of the 95,000+ UPI fraud cases in FY2023 went unsolved.

## Solution
IBM Bob orchestrates the investigation: it reads messy (Hinglish-friendly) evidence, calls our MCP tools to build a temporal graph, detects the fraud pattern and kingpin-to-mule hierarchy, plans the minimum freeze/block set, and drafts a legally-mapped brief.

## Key Features
- Bob-orchestrated natural-language investigation
- SIM-Swap Chain Detector with timeline lane
- Disruption Planner (min-cut freeze/block set, before/after capacity)
- Legal & Compliance layer (IT Act, BNS, Sec 63 BSA checklist)
- Explainable mule scoring and confidence-ranked kingpin hypotheses

## Architecture
See [docs/architecture.md](docs/architecture.md).

## Tech Stack
Python, NetworkX, MCP, React, Cytoscape.js, SQLite. IBM technologies: IBM Bob (orchestrator), watsonx.ai (optional).

## How to Run
See [docs/setup-guide.md](docs/setup-guide.md).

## Demo
- Video: `demo/demo-video-link.txt`
- Live demo: `demo/live-demo-url.txt`
- Screenshots: `demo/screenshots/`

## Known Limitations
- Mock data only; no live bank, telecom or NCRP integration.
- Legal mapping is advisory and must be verified by a legal officer.

## What We're Most Proud Of
Bob as the load-bearing orchestrator, and turning analysis into action: the Disruption Planner plus SIM-swap detection feeding an FIR-ready brief.
