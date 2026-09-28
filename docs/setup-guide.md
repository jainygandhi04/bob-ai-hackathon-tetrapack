# Setup Guide

> Status: commands below are the target workflow and will be finalised as code lands in `src/`. Re-test on a clean machine before submission.

## Prerequisites
| Tool | Version |
|---|---|
| Python | 3.11+ |
| Node.js | 20+ |
| IBM Bob (CLI or IDE) | Access provided by hackathon |
| Git | any recent |

## Environment variables
Copy `src/.env.example` to `src/.env` and fill in:
| Variable | Description |
|---|---|
| `BOB_API_KEY` | IBM Bob access key |
| `BOB_MCP_SERVER_NAME` | Name Bob uses for our MCP server |
| `WATSONX_API_KEY`, `WATSONX_PROJECT_ID`, `WATSONX_URL` | watsonx.ai credentials (if used) |
| `BACKEND_HOST`, `BACKEND_PORT`, `FRONTEND_PORT` | Local ports |
| `GRAPH_DB_PATH`, `CASE_MEMORY_PATH` | Local persistence paths |
| `SIMSWAP_WINDOW_HOURS`, `MULE_SCORE_THRESHOLD` | Detection thresholds |

## Install
```bash
git clone https://github.com/<your-username>/bob-ai-hackathon-<team-name>.git
cd bob-ai-hackathon-<team-name>/src
cp .env.example .env
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd ui && npm install && cd ..
```

## Run
```bash
# 1. Load mock case data
python -m mock_data.load --case JAMTARA-001
# 2. Start backend + MCP server
python -m mcp_server.main
# 3. Start UI
cd ui && npm run dev
# 4. Register the MCP server with Bob and open a Bob session (see Bob docs)
```

## Verify it works
1. Open `http://localhost:5173`; the graph for `JAMTARA-001` renders.
2. Ask Bob: "Detect SIM-swap chains in JAMTARA-001". The SIM-swap lane highlights at least one chain.
3. Click **Disrupt**; a freeze set and before/after capacity number appear.
4. Click **Generate brief**; an FIR-ready document is produced.

## Troubleshooting
| Problem | Fix |
|---|---|
| Bob cannot see tools | Confirm MCP server is running and registered under `BOB_MCP_SERVER_NAME` |
| `ModuleNotFoundError` | Activate the venv and reinstall requirements |
| Empty graph | Re-run the mock data loader |
| Port in use | Change `BACKEND_PORT` / `FRONTEND_PORT` in `.env` |
