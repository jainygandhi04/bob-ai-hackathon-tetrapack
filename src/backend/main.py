"""
FraudLens FastAPI backend.
All investigation state is held in an in-process store keyed by session_id.
"""
from __future__ import annotations

import io
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# engine imports
import sys
sys.path.insert(0, str(Path(__file__).parent))

from engines.entity_engine import EntityEngine
from engines.fraud_engine import FraudEngine
from engines.evidence_engine import EvidenceEngine
from engines.investigation_engine import InvestigationEngine
from engines.action_engine import ActionEngine
from engines.legal_engine import LegalEngine
from engines.case_brief_engine import CaseBriefEngine
from models.investigation import InvestigationSession

app = FastAPI(
    title="FraudLens API",
    description="Evidence-first fraud investigation platform",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-process session store ───────────────────────────────────────────────
_sessions: dict[str, InvestigationSession] = {}


def _get_session(session_id: str) -> InvestigationSession:
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return session


# ── Upload & Session Management ────────────────────────────────────────────

# ── Known entity type keywords (order matters: more specific first) ───────────
_ENTITY_KEYWORDS: list[tuple[str, str]] = [
    ("sim_swap", "sim_swaps"),
    ("simswap",  "sim_swaps"),
    ("sim",      "sims"),
    ("people",   "people"),
    ("person",   "people"),
    ("account",  "accounts"),
    ("transaction", "transactions"),
    ("transfer",    "transactions"),
    ("phone",    "phones"),
    ("mobile",   "phones"),
    ("device",   "devices"),
    ("imei",     "devices"),
    ("call",     "calls"),
    ("cdr",      "calls"),
    ("location", "locations"),
    ("loc",      "locations"),
    ("tower",    "locations"),
]

# Fallback: detect entity type by inspecting CSV column names
_COLUMN_SIGNATURES: list[tuple[frozenset, str]] = [
    (frozenset({"person_id", "full_name"}),       "people"),
    (frozenset({"account_id", "account_number"}),  "accounts"),
    (frozenset({"transaction_id", "from_account"}), "transactions"),
    (frozenset({"phone_id", "phone_number"}),      "phones"),
    (frozenset({"sim_id", "iccid"}),               "sims"),
    (frozenset({"swap_id", "old_sim_id"}),         "sim_swaps"),
    (frozenset({"device_id", "imei"}),             "devices"),
    (frozenset({"call_id", "from_phone"}),         "calls"),
    (frozenset({"location_id", "latitude"}),       "locations"),
]


def _detect_entity_type(stem: str, content: bytes) -> str:
    """
    Detect entity type from filename stem, then fall back to column sniffing.
    Returns the canonical key used by EntityEngine.build_session().
    """
    clean = stem.lower().replace("-", "_").replace(" ", "_")

    # 1. Exact match
    canonical_keys = {v for _, v in _ENTITY_KEYWORDS}
    if clean in canonical_keys:
        return clean

    # 2. Keyword substring match (most-specific keyword wins)
    for keyword, canonical in _ENTITY_KEYWORDS:
        if keyword in clean:
            return canonical

    # 3. Column-header sniffing
    try:
        first_line = content.split(b"\n")[0].decode("utf-8", errors="ignore").strip().lower()
        cols = frozenset(c.strip() for c in first_line.split(","))
        for required_cols, canonical in _COLUMN_SIGNATURES:
            if required_cols.issubset(cols):
                return canonical
    except Exception:
        pass

    # 4. Return the raw stem so the engine can still attempt extraction
    return clean


@app.post("/api/upload")
async def upload_csvs(
    files: list[UploadFile] = File(...),
    session_name: str = Form(default="Investigation"),
):
    """
    Upload multiple CSV files and build an investigation session.
    Entity type is auto-detected from filename (fuzzy match) then CSV column headers.
    Supported: people, accounts, transactions, phones, sims, devices, calls, locations, sim_swaps.
    Any filename containing those keywords works (e.g. my_people_export.csv → people).
    """
    import tempfile, os
    csv_files: dict[str, str] = {}
    tmp_dir = tempfile.mkdtemp()

    for upload in files:
        fname = upload.filename or f"file_{uuid.uuid4()}.csv"
        content = await upload.read()
        key = _detect_entity_type(Path(fname).stem, content)
        dest = os.path.join(tmp_dir, fname)
        with open(dest, "wb") as f:
            f.write(content)
        csv_files[key] = dest

    entity_engine = EntityEngine()
    session = entity_engine.build_session(session_name, csv_files)

    # Auto-run all engines
    fraud_engine = FraudEngine()
    findings = fraud_engine.detect_all(session)
    for f in findings:
        session.findings[f.finding_id] = f

    ev_engine = EvidenceEngine()
    session.evidence = ev_engine.build_evidence_map(session)

    inv_engine = InvestigationEngine()
    for h in inv_engine.generate_hypotheses(session):
        session.hypotheses[h.hypothesis_id] = h

    legal_engine = LegalEngine()
    for m in legal_engine.map_findings(session):
        session.legal_mappings[m.mapping_id] = m

    action_engine = ActionEngine()
    for a in action_engine.propose_actions(session):
        session.proposed_actions[a.action_id] = a

    _sessions[session.session_id] = session

    return {
        "session_id": session.session_id,
        "name": session.name,
        "entity_count": len(session.entities),
        "relationship_count": len(session.relationships),
        "finding_count": len(session.findings),
        "hypothesis_count": len(session.hypotheses),
        "legal_mapping_count": len(session.legal_mappings),
        "source_files": list(csv_files.keys()),
        "detected_types": {
            fname: key for fname, key in
            zip([f.filename or "" for f in files], csv_files.keys())
        },
    }


@app.post("/api/sessions/demo")
async def load_demo_session():
    """Load the bundled mock data as a demo investigation session."""
    mock_dir = Path(__file__).parent.parent.parent / "data" / "mock"
    csv_map = {
        "people": str(mock_dir / "people.csv"),
        "accounts": str(mock_dir / "accounts.csv"),
        "phones": str(mock_dir / "phones.csv"),
        "sims": str(mock_dir / "sims.csv"),
        "devices": str(mock_dir / "devices.csv"),
        "transactions": str(mock_dir / "transactions.csv"),
        "calls": str(mock_dir / "calls.csv"),
        "locations": str(mock_dir / "locations.csv"),
        "sim_swaps": str(mock_dir / "sim_swaps.csv"),
    }
    # Filter to existing files only
    csv_map = {k: v for k, v in csv_map.items() if Path(v).exists()}

    entity_engine = EntityEngine()
    session = entity_engine.build_session("Demo Investigation", csv_map)

    fraud_engine = FraudEngine()
    for f in fraud_engine.detect_all(session):
        session.findings[f.finding_id] = f

    ev_engine = EvidenceEngine()
    session.evidence = ev_engine.build_evidence_map(session)

    inv_engine = InvestigationEngine()
    for h in inv_engine.generate_hypotheses(session):
        session.hypotheses[h.hypothesis_id] = h

    legal_engine = LegalEngine()
    for m in legal_engine.map_findings(session):
        session.legal_mappings[m.mapping_id] = m

    action_engine = ActionEngine()
    for a in action_engine.propose_actions(session):
        session.proposed_actions[a.action_id] = a

    _sessions[session.session_id] = session

    return {
        "session_id": session.session_id,
        "name": session.name,
        "entity_count": len(session.entities),
        "finding_count": len(session.findings),
        "hypothesis_count": len(session.hypotheses),
    }


@app.get("/api/sessions")
def list_sessions():
    return [
        {"session_id": s.session_id, "name": s.name,
         "created_at": s.created_at, "status": s.status}
        for s in _sessions.values()
    ]


# ── Entities ───────────────────────────────────────────────────────────────

@app.get("/api/sessions/{session_id}/entities")
def get_entities(session_id: str, entity_type: Optional[str] = None):
    session = _get_session(session_id)
    entities = list(session.entities.values())
    if entity_type:
        entities = [e for e in entities if e.entity_type.value == entity_type.upper()]
    return [e.model_dump() for e in entities]


@app.get("/api/sessions/{session_id}/entities/{entity_id}")
def get_entity(session_id: str, entity_id: str):
    session = _get_session(session_id)
    ent = session.entities.get(entity_id)
    if not ent:
        raise HTTPException(404, f"Entity {entity_id} not found")
    rels = [r.model_dump() for r in session.relationships
            if r.from_entity == entity_id or r.to_entity == entity_id]
    return {**ent.model_dump(), "relationships": rels}


# ── Graph ──────────────────────────────────────────────────────────────────

@app.get("/api/sessions/{session_id}/graph")
def get_graph(session_id: str):
    session = _get_session(session_id)
    nodes = [
        {
            "id": e.canonical_id,
            "label": e.display_name,
            "type": e.entity_type.value,
            "data": e.attributes,
        }
        for e in session.entities.values()
    ]
    edges = [
        {
            "id": r.relationship_id,
            "source": r.from_entity,
            "target": r.to_entity,
            "type": r.relationship_type.value,
            "timestamp": r.timestamp,
            "attributes": r.attributes,
        }
        for r in session.relationships
    ]
    return {"nodes": nodes, "edges": edges}


# ── Findings ───────────────────────────────────────────────────────────────

@app.get("/api/sessions/{session_id}/findings")
def get_findings(session_id: str):
    session = _get_session(session_id)
    return [f.model_dump() for f in session.findings.values()]


@app.get("/api/sessions/{session_id}/findings/{finding_id}")
def get_finding(session_id: str, finding_id: str):
    session = _get_session(session_id)
    finding = session.findings.get(finding_id)
    if not finding:
        raise HTTPException(404, f"Finding {finding_id} not found")

    evidence = [
        session.evidence[eid].model_dump()
        for eid in finding.evidence_ids
        if eid in session.evidence
    ]
    entities = [
        session.entities[eid].model_dump()
        for eid in finding.entity_ids
        if eid in session.entities
    ]
    return {
        **finding.model_dump(),
        "evidence": evidence,
        "entities": entities,
    }


@app.get("/api/sessions/{session_id}/findings/{finding_id}/challenge")
def challenge_finding(session_id: str, finding_id: str):
    session = _get_session(session_id)
    engine = InvestigationEngine()
    return engine.challenge_finding(finding_id, session)


# ── Evidence ───────────────────────────────────────────────────────────────

@app.get("/api/sessions/{session_id}/evidence")
def get_evidence(session_id: str):
    session = _get_session(session_id)
    return [e.model_dump() for e in session.evidence.values()]


@app.get("/api/sessions/{session_id}/evidence/{evidence_id}")
def get_evidence_item(session_id: str, evidence_id: str):
    session = _get_session(session_id)
    ev = session.evidence.get(evidence_id)
    if not ev:
        raise HTTPException(404, f"Evidence {evidence_id} not found")
    return ev.model_dump()


# ── Hypotheses ─────────────────────────────────────────────────────────────

@app.get("/api/sessions/{session_id}/hypotheses")
def get_hypotheses(session_id: str):
    session = _get_session(session_id)
    return [h.model_dump() for h in session.hypotheses.values()]


# ── Investigation tools ────────────────────────────────────────────────────

@app.get("/api/sessions/{session_id}/trace/{entity_id}")
def trace_money(session_id: str, entity_id: str):
    session = _get_session(session_id)
    engine = InvestigationEngine()
    return engine.trace_money(entity_id, session)


@app.get("/api/sessions/{session_id}/explain")
def explain_connection(
    session_id: str, entity_a: str, entity_b: str
):
    session = _get_session(session_id)
    engine = InvestigationEngine()
    return engine.explain_connection(entity_a, entity_b, session)


# ── Actions ────────────────────────────────────────────────────────────────

@app.get("/api/sessions/{session_id}/actions")
def get_actions(session_id: str):
    session = _get_session(session_id)
    return [a.model_dump() for a in session.proposed_actions.values()]


@app.post("/api/sessions/{session_id}/simulate-cut")
def simulate_cut(session_id: str, source: str, sink: str):
    session = _get_session(session_id)
    engine = ActionEngine()
    return engine.simulate_graph_cut(session, source, sink)


# ── Legal ──────────────────────────────────────────────────────────────────

@app.get("/api/sessions/{session_id}/legal")
def get_legal_mappings(session_id: str):
    session = _get_session(session_id)
    return [m.model_dump() for m in session.legal_mappings.values()]


# ── Timeline ───────────────────────────────────────────────────────────────

@app.get("/api/sessions/{session_id}/timeline")
def get_timeline(session_id: str):
    session = _get_session(session_id)
    events: list[dict] = []
    for finding in session.findings.values():
        for event in finding.timeline:
            events.append({
                **event,
                "finding_id": finding.finding_id,
                "finding_type": finding.finding_type.value,
                "severity": finding.severity.value,
            })
    events.sort(key=lambda x: x.get("timestamp", ""))
    return events


# ── Case Brief ─────────────────────────────────────────────────────────────

@app.post("/api/sessions/{session_id}/brief")
def generate_brief(session_id: str):
    session = _get_session(session_id)
    engine = CaseBriefEngine()
    brief = engine.generate(session)
    return brief.model_dump()


# ── Bob Integration ────────────────────────────────────────────────────────

class BobQuery(BaseModel):
    query: str
    session_id: str


@app.post("/api/bob")
def bob_query(payload: BobQuery):
    """
    Bob AI integration endpoint.
    Routes natural-language investigation queries to backend engines.
    Bob calls actual investigation tools — this is not cosmetic.
    """
    session = _get_session(payload.session_id)
    query = payload.query.lower()

    # Route to appropriate engine based on query intent
    if any(kw in query for kw in ["trace", "money", "follow", "path", "flow"]):
        # Extract account/entity reference from query
        account_id = _extract_entity_ref(query, session)
        if account_id:
            engine = InvestigationEngine()
            result = engine.trace_money(account_id, session)
            return {
                "tool_called": "trace_money",
                "entity": account_id,
                "result": result,
                "narrative": _narrate_trace(account_id, result, session),
            }

    if any(kw in query for kw in ["sim", "swap", "sim swap", "sim-swap"]):
        sim_findings = [
            f for f in session.findings.values()
            if f.finding_type.value == "SIM_SWAP_CHAIN"
        ]
        timeline_events = []
        for f in sim_findings:
            timeline_events.extend(f.timeline)
        timeline_events.sort(key=lambda x: x.get("timestamp", ""))
        return {
            "tool_called": "get_sim_swap_findings",
            "finding_count": len(sim_findings),
            "findings": [f.model_dump() for f in sim_findings],
            "timeline": timeline_events,
            "narrative": _narrate_sim_swaps(sim_findings, session),
        }

    if any(kw in query for kw in ["why", "connect", "related", "link", "relation"]):
        entities = _extract_two_entities(query, session)
        if len(entities) >= 2:
            engine = InvestigationEngine()
            result = engine.explain_connection(entities[0], entities[1], session)
            return {
                "tool_called": "explain_connection",
                "entity_a": entities[0],
                "entity_b": entities[1],
                "result": result,
            }

    if any(kw in query for kw in ["finding", "fraud", "suspicious", "pattern", "detect"]):
        return {
            "tool_called": "get_findings",
            "finding_count": len(session.findings),
            "findings": [f.model_dump() for f in session.findings.values()],
            "narrative": f"Found {len(session.findings)} fraud pattern(s) in this investigation.",
        }

    if any(kw in query for kw in ["brief", "summary", "case", "report"]):
        engine = CaseBriefEngine()
        brief = engine.generate(session)
        return {
            "tool_called": "generate_brief",
            "brief": brief.model_dump(),
        }

    if any(kw in query for kw in ["hypothes", "theory", "scenario"]):
        return {
            "tool_called": "get_hypotheses",
            "hypotheses": [h.model_dump() for h in session.hypotheses.values()],
        }

    if any(kw in query for kw in ["evidence", "proof", "record", "source"]):
        return {
            "tool_called": "get_evidence",
            "evidence_count": len(session.evidence),
            "evidence": [e.model_dump() for e in list(session.evidence.values())[:20]],
        }

    if any(kw in query for kw in ["legal", "law", "statute", "section", "act"]):
        return {
            "tool_called": "get_legal_mappings",
            "mappings": [m.model_dump() for m in session.legal_mappings.values()],
        }

    if any(kw in query for kw in ["action", "block", "freeze", "interven"]):
        return {
            "tool_called": "get_proposed_actions",
            "actions": [a.model_dump() for a in session.proposed_actions.values()],
        }

    # Default: return session overview
    return {
        "tool_called": "session_overview",
        "session_id": session.session_id,
        "name": session.name,
        "entity_count": len(session.entities),
        "finding_count": len(session.findings),
        "hypothesis_count": len(session.hypotheses),
        "narrative": (
            f"Session '{session.name}' has {len(session.entities)} entities, "
            f"{len(session.findings)} findings, "
            f"and {len(session.hypotheses)} hypotheses. "
            "Try asking: 'trace money from ACC001', 'what happened after the SIM swap?', "
            "'why are P001 and P003 connected?', or 'generate a case brief'."
        ),
    }


# ── Bob helpers ────────────────────────────────────────────────────────────

def _extract_entity_ref(query: str, session: InvestigationSession) -> Optional[str]:
    """Find an entity canonical_id mentioned in the query."""
    for eid in session.entities:
        if eid.lower() in query:
            return eid
    return None


def _extract_two_entities(query: str, session: InvestigationSession) -> list[str]:
    """Find up to two entity IDs mentioned in the query."""
    found: list[str] = []
    for eid in session.entities:
        if eid.lower() in query:
            found.append(eid)
        if len(found) == 2:
            break
    return found


def _narrate_trace(
    account_id: str, result: dict, session: InvestigationSession
) -> str:
    paths = result.get("paths", [])
    suspicious = result.get("suspicious_paths", 0)
    total = result.get("total_amount", 0)
    return (
        f"Traced money flows from {account_id}. "
        f"Found {len(paths)} path(s), {suspicious} suspicious. "
        f"Total amount in traced paths: {total:.2f} INR."
    )


def _narrate_sim_swaps(findings: list, session: InvestigationSession) -> str:
    if not findings:
        return "No SIM-swap chains detected in this investigation."
    msgs = []
    for f in findings:
        pid = f.pattern_data.get("person_id", "unknown")
        tx_count = f.pattern_data.get("transactions_after_swap", 0)
        msgs.append(
            f"Person {pid}: SIM swap followed by {tx_count} transaction(s) within 72 hours."
        )
    return " | ".join(msgs)


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "1.0.0"}
