# Demo — Cyber Fraud Analyzer

This directory documents the demonstration walkthrough for the JAMTARA-001 built-in case and for uploading a fresh case via the investigator wizard.

---

## Quick start

```bash
# 1. Install Python deps
cd src && pip install -r requirements.txt

# 2. Start the backend
uvicorn ui.backend:app --reload --port 8000

# 3. Start the frontend (new terminal)
cd src/ui && npm install && npm run dev
# → opens at http://localhost:5173
```

---

## Demo walkthrough — JAMTARA-001 (built-in)

JAMTARA-001 is a synthetic but realistic Jharkhand SIM-swap fraud case modelled on publicly reported gang structures.

### Step 1 — Open the app

Navigate to `http://localhost:5173`.  The sidebar starts on the **Case** step.  Under *Demo Cases* you will see **JAMTARA-001**.  Click it.

### Step 2 — Skip upload (data pre-loaded)

The wizard advances to **Upload**.  Click **Continue to Pipeline →** — the demo case data is already present.

### Step 3 — Run the pipeline

Click **⚙ Run Analysis Pipeline**.  The backend ingests the CSVs and complaint text, builds the knowledge graph, runs entity resolution across Hinglish/Devanagari aliases, and computes the fraud pattern.

Expected result: ≥ 35 nodes · ≥ 60 edges.

### Step 4 — Explore

Use the **Jump To** buttons or the top tab bar:

| Tab | What to show |
|---|---|
| 🕸 Graph | Knowledge graph — click any node to see raw attributes |
| 📡 SIM-Swap Lane | 3-lane SVG timeline: SIM swap → OTP → fund transfer |
| 👑 Hierarchy | Ranked suspect table — KINGPIN at top with reasons |
| ⚡ Disrupt | Click *Compute Disruption Plan* — see freeze set + before/after capacity bar |
| 📄 Brief | Click *Generate Brief* — download the FIR-ready Markdown |
| 💬 Bob Chat | Ask Bob: *"Who is the kingpin?"* or *"What charges apply?"* |

---

## Demo walkthrough — uploading a new case

### Prepare evidence files

Create CSV files matching the schemas below and a free-text `.txt` complaint:

| Kind | Required columns |
|---|---|
| `bank_accounts` | account_id, bank, holder_name, linked_phone, opened_on, kyc |
| `subscribers` | number, holder_name, iccid, activated_on |
| `sim_events` | event_id, ts, number, old_iccid, new_iccid, new_imei, request_channel |
| `transactions` | txn_id, ts, from_account, to_account, amount, channel, device_imei, location |
| `cdr` | call_id, ts, from_number, to_number, duration_sec, imei, tower |
| `complaint` | free-text `.txt` — any language (English, Hindi, Hinglish) |

### Step 1 — Create case

In the sidebar wizard, click **＋ Create New Case**, enter a Case ID (e.g. `PUNE-2025-01`) and optional title.  Click **Create & Continue →**.

### Step 2 — Upload evidence

Drop or browse to your prepared files.  The kind is auto-detected from the filename; use the dropdown to override.  Click **⬆ Upload N file(s)**.  Each file shows a per-file status indicator (● pending → ↑ uploading → ✓ ok).

### Step 3 — Run pipeline

Click **⚙ Run Analysis Pipeline**.  The backend builds the knowledge graph for your case.

### Step 4 — Done

View node/edge counts and use the **Jump To** buttons to explore the graph, hierarchy, and brief for your case.

---

## Bob MCP tools

The following 12 tools are registered in `.mcp.json` and callable from Bob:

| Tool | Description |
|---|---|
| `build_graph` | Build / reload knowledge graph for a case |
| `graph_summary` | Node and edge counts |
| `detect_pattern` | Fraud pattern classification + confidence |
| `detect_simswap_chains` | All SIM-swap → OTP → transaction chains |
| `score_mules` | Mule account scores |
| `rank_hierarchy` | Kingpin-to-mule ranking with reasons |
| `plan_disruption` | Min-cut freeze/block set |
| `score_confidence` | Case-level evidence confidence |
| `detect_contradictions` | Timeline / amount contradictions |
| `challenge` | Challenge a hypothesis — returns counter-evidence |
| `map_legal` | IT Act / BNS / PMLA / TRAI section mapping |
| `generate_brief` | FIR-ready Markdown brief |

Example Bob conversation:

> **You:** Who is the kingpin in JAMTARA-001 and what charges apply?
>
> **Bob:** *calls `rank_hierarchy` and `map_legal`*
>
> The top suspect is **Rakesh Mandal** (confidence 0.87).  He appears as the
> coordinator across three SIM-swap chains.  Applicable charges: IT Act Sec 66C
> (identity theft), 66D (cheating by impersonation), BNS Sec 318 (cheating),
> PMLA Sec 3/4 (money laundering).

---

## Cross-case memory

After ingesting any case the backend automatically indexes every person, phone, account, SIM, and IMEI into a cross-case memory store (`data/case_memory/index.json`).

Use the memory API to find repeat offenders:

```
GET /api/memory/query?identifier=9876543210
GET /api/memory/linked/JAMTARA-001
GET /api/memory/summary
```

---

## Test suite

```bash
cd src && python -m pytest tests/ -q
# 313 passed
```
