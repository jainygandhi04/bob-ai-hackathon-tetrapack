# 🚀 Fraud Lens


---

## 👥 Team

| Field | Value |
|---|---|
| **Team Name** | TetraPack |
| **Track** | Cyber Forensics|
| **Team Lead** | Jainy Gandhi — jainy.mscs25@gj.nfsu.edu.in |
| **Members** | Aanal Dobariya, Om Dave, Rahul Bothra |

---

## 🎯 Problem Statement

> India recorded 13.42 lakh UPI fraud incidents worth ₹1,087 crore in FY2023-24 (Finance Ministry, Lok Sabha), and the Home Ministry's I4C treats Jamtara as one of seven national cyber-fraud hotspots. Jamtara-style rings combine vishing calls, bulk SIM cards, and chains of mule accounts, and investigators still trace the links between accounts, SIMs, and devices by hand, which is slow and leaves rings hard to see as a network. Cyber cell officers, bank nodal officers, and police drafting FIRs feel this pain every day. See docs/problem-statement.md for sources.

## 💡 Solution

Fraud Lens is a Bob-powered investigation tool that turns unstructured cyber fraud intelligence (transaction records, call logs, device IDs, accused names) into a temporal knowledge graph of people, accounts, SIMs, devices and calls. It detects the fraud pattern (including SIM-swap chains), maps the kingpin → mule → victim hierarchy, and lets investigators ask Bob questions in plain language instead of tracing links by hand over weeks. It ends with an FIR-ready case brief that has evidence IDs, mapped legal sections and concrete freeze, telecom, bank and field actions.

---

## ✨ Key Features

- **Feature 1:Entity and relationship extraction**The Entity Engine pulls people, accounts, SIMs, phones and devices/IMEI out of raw records. It resolves and normalizes duplicates into one temporal knowledge graph.
- **Feature 2:Fraud pattern and SIM-swap detection** The Fraud Engine uses temporal patterns, centrality and community analysis to identify the pattern type. Its SIM-swap Chain Detector links swap events, IMEI changes and OTP calls into a per-victim timeline.
- **Feature 3:Hierarchy mapping and Bob Chat.** Kingpin → mule → victim structure is shown on an interactive graph and timeline. Investigators can trace, explain, challenge, compare and simulate through Bob, without writing queries.

---

## 🛠️ Tech Stack

| Category | Technologies |
|---|---|
| **Languages** | [e.g., Python, TypeScript] |
| **Frameworks** | [e.g., FastAPI, React] |
| **IBM Technologies** | [e.g., watsonx.ai, IBM Bob, IBM Cloud] |
| **Databases** | [e.g., PostgreSQL, Redis] |
| **Other** | [e.g., Docker, GitHub Actions] |

---

## 📁 Repository Structure

```
├── src/                  # All source code
├── docs/                 # Written documentation
│   ├── problem-statement.md
│   ├── solution-overview.md
│   ├── architecture.md
│   └── setup-guide.md
├── demo/                 # Demo artifacts
│   ├── screenshots/      # App screenshots
│   └── demo-video-link.txt  # Link to demo video
├── presentation/         # Slide deck
└── submission.yaml       # Structured submission metadata
```

---

## ⚡ How to Run

> **Copy these exact steps from your [`docs/setup-guide.md`](docs/setup-guide.md)**

```bash
# 1. Clone the repo
git clone https://github.com/jainygandhi04/bob-ai-hackathon-tetrapack.git
cd bob-ai-hackathon-tetrapack

# 2. Install dependencies
pip -r requirement.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your values

# 4. Run the project

```

---

## 🖥️ Demo

| Artifact | Link |
|---|---|
| 📹 Demo Video | [See demo/demo-video-link.txt](demo/demo-video-link.txt) |
| 🌐 Live Demo | [See demo/live-demo-url.txt](demo/live-demo-url.txt) |
| 🖼️ Screenshots | [See demo/screenshots/](demo/screenshots/) |
| 📊 Presentation | [See presentation/FraudLens_TetraPack.pptx](presentation/) |

---

## ⚠️ Known Limitations

> Be honest — judges appreciate transparency over overclaiming.

- [Limitation 1: e.g., "Authentication is mocked — not production-ready"]
- [Limitation 2: e.g., "Only tested on Chrome"]
- [Limitation 3: e.g., "Feature X is scaffolded but not fully implemented"]

---

## 🏅 What We're Most Proud Of

[Tell the judges what part of your submission is strongest and worth paying close attention to.]

---
