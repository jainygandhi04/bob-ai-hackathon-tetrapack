"""
Investigation Engine — trace, explain, challenge, and compare hypotheses.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Optional

import networkx as nx

from models.investigation import (
    ConfidenceLevel, Finding, FindingType, Hypothesis,
    HypothesisStatus, InvestigationSession, RelationshipType, Severity,
)


def _now() -> str:
    return datetime.utcnow().isoformat()


class InvestigationEngine:

    def trace_money(
        self,
        from_account: str,
        session: InvestigationSession,
        max_depth: int = 6,
    ) -> dict[str, Any]:
        """
        Trace all money paths originating from an account.
        Returns paths, total amounts, and evidence IDs.
        """
        G = self._transaction_graph(session)
        if from_account not in G:
            return {"paths": [], "evidence_ids": [], "total_amount": 0}

        paths: list[dict] = []
        evidence_ids: list[str] = []
        seen_paths: set[tuple] = set()

        for target in G.nodes():
            if target == from_account:
                continue
            try:
                for path in nx.all_simple_paths(G, from_account, target, cutoff=max_depth):
                    key = tuple(path)
                    if key in seen_paths:
                        continue
                    seen_paths.add(key)

                    # Compute amount and collect evidence
                    hops = []
                    total = 0.0
                    for i in range(len(path) - 1):
                        edge = G.get_edge_data(path[i], path[i + 1], {})
                        amount = float(edge.get("amount", 0))
                        total += amount
                        hops.append({
                            "from": path[i],
                            "to": path[i + 1],
                            "amount": amount,
                            "timestamp": edge.get("timestamp", ""),
                            "transaction_id": edge.get("tx_id", ""),
                            "source_file": edge.get("source_file", ""),
                        })

                    # Build evidence references
                    for hop in hops:
                        eid = f"ev-trace-{hop['transaction_id']}"
                        evidence_ids.append(eid)

                    is_suspicious = self._is_suspicious_path(path, session)
                    paths.append({
                        "path": path,
                        "hops": hops,
                        "total_amount": total,
                        "hop_count": len(path) - 1,
                        "suspicious": is_suspicious,
                    })
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                pass

        paths.sort(key=lambda x: (-x["hop_count"], -x["total_amount"]))
        return {
            "from_account": from_account,
            "paths": paths[:10],
            "evidence_ids": list(set(evidence_ids)),
            "total_amount": sum(p["total_amount"] for p in paths),
            "suspicious_paths": sum(1 for p in paths if p["suspicious"]),
        }

    def explain_connection(
        self,
        entity_a: str,
        entity_b: str,
        session: InvestigationSession,
    ) -> dict[str, Any]:
        """Explain why two entities are connected."""
        G = self._full_graph(session)
        explanation_parts: list[str] = []
        path: list[str] = []

        try:
            path = nx.shortest_path(G, entity_a, entity_b)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return {
                "explanation": f"No direct connection found between {entity_a} and {entity_b}",
                "path": [],
                "relationship_chain": [],
            }

        chain: list[dict] = []
        for i in range(len(path) - 1):
            a, b = path[i], path[i + 1]
            ent_a = session.entities.get(a)
            ent_b = session.entities.get(b)
            rel = next(
                (r for r in session.relationships
                 if r.from_entity == a and r.to_entity == b),
                None
            )
            rel_type = rel.relationship_type.value if rel else "LINKED"
            name_a = ent_a.display_name if ent_a else a
            name_b = ent_b.display_name if ent_b else b
            chain.append({
                "from": a, "from_name": name_a,
                "to": b, "to_name": name_b,
                "relationship": rel_type,
                "timestamp": rel.timestamp if rel else None,
            })
            explanation_parts.append(f"{name_a} [{rel_type}] {name_b}")

        explanation = " → ".join(explanation_parts)
        return {
            "explanation": explanation,
            "path": path,
            "relationship_chain": chain,
            "degree_of_separation": len(path) - 1,
        }

    def challenge_finding(
        self,
        finding_id: str,
        session: InvestigationSession,
    ) -> dict[str, Any]:
        """Challenge a finding by identifying supporting and contradicting evidence."""
        finding = session.findings.get(finding_id)
        if not finding:
            return {"error": f"Finding {finding_id} not found"}

        supporting = []
        contradicting = []
        open_questions = list(finding.missing_evidence)

        # Supporting evidence: evidence already attached to the finding
        for eid in finding.evidence_ids:
            ev = session.evidence.get(eid)
            if ev:
                supporting.append({
                    "evidence_id": eid,
                    "description": ev.description,
                    "source_file": ev.source_file,
                    "original_record": ev.original_record,
                })

        # Contradicting evidence from session
        for eid in finding.contradicting_evidence_ids:
            ev = session.evidence.get(eid)
            if ev:
                contradicting.append({
                    "evidence_id": eid,
                    "description": ev.description,
                })

        # Add soft challenges based on finding type
        challenges = self._generate_challenges(finding, session)

        return {
            "finding_id": finding_id,
            "finding_title": finding.title,
            "challenges": challenges,
            "supporting_evidence": supporting,
            "contradicting_evidence": contradicting,
            "open_questions": open_questions,
            "verdict": self._preliminary_verdict(finding, len(supporting), len(contradicting)),
        }

    def generate_hypotheses(
        self, session: InvestigationSession
    ) -> list[Hypothesis]:
        """Generate multiple competing hypotheses from the findings."""
        hypotheses: list[Hypothesis] = []

        finding_types = {f.finding_type for f in session.findings.values()}
        all_finding_ids = list(session.findings.keys())

        # Hypothesis 1: Organised fraud ring
        if (FindingType.CIRCULAR_TRANSACTION in finding_types
                or FindingType.TRANSACTION_CHAIN in finding_types):
            h = Hypothesis(
                title="Organised Money Laundering Ring",
                description=(
                    "Multiple entities are coordinating to move funds in circular or "
                    "layered patterns, suggesting an organised fraud ring. "
                    "The transaction chains and circular flows point to deliberate "
                    "placement, layering, and integration of funds."
                ),
                status=HypothesisStatus.SUPPORTED,
                supporting_finding_ids=[
                    fid for fid, f in session.findings.items()
                    if f.finding_type in (
                        FindingType.CIRCULAR_TRANSACTION,
                        FindingType.TRANSACTION_CHAIN,
                        FindingType.RAPID_FUND_MOVEMENT,
                    )
                ],
                contradicting_finding_ids=[],
                open_questions=[
                    "Who is the ultimate beneficiary of the funds?",
                    "Are there external accounts not in the dataset?",
                    "Is there physical evidence of coordination?",
                ],
                confidence=0.7,
                created_at=_now(),
            )
            hypotheses.append(h)

        # Hypothesis 2: SIM-swap targeted account takeover
        if FindingType.SIM_SWAP_CHAIN in finding_types:
            h = Hypothesis(
                title="SIM-Swap Account Takeover",
                description=(
                    "One or more accounts were accessed after SIM-swap events. "
                    "This could indicate that attackers obtained new SIMs to intercept "
                    "OTPs and gain unauthorised access to banking accounts."
                ),
                status=HypothesisStatus.SUPPORTED,
                supporting_finding_ids=[
                    fid for fid, f in session.findings.items()
                    if f.finding_type == FindingType.SIM_SWAP_CHAIN
                ],
                open_questions=[
                    "Did the SIM swap involve identity impersonation at the carrier?",
                    "Were OTPs intercepted or were credentials stolen separately?",
                    "Did the account holder authorize the SIM swap?",
                ],
                confidence=0.65,
                created_at=_now(),
            )
            hypotheses.append(h)

        # Hypothesis 3: Benign explanation (always include to avoid forcing a conclusion)
        h = Hypothesis(
            title="Legitimate Business Activity",
            description=(
                "The observed transaction patterns may have a legitimate business explanation. "
                "Large, rapid transfers can occur in legitimate supply chain payments, "
                "and SIM swaps are a common carrier service. "
                "This hypothesis requires contradiction through corroborating evidence."
            ),
            status=HypothesisStatus.OPEN,
            contradicting_finding_ids=all_finding_ids[:3],
            open_questions=[
                "Is there a documented business relationship between the entities?",
                "Are there invoices or contracts that explain the transfers?",
                "Did the account holders confirm knowledge of the transactions?",
            ],
            confidence=0.3,
            created_at=_now(),
        )
        hypotheses.append(h)

        # Hypothesis 4: Insider threat
        if FindingType.SHARED_INFRASTRUCTURE in finding_types:
            h = Hypothesis(
                title="Insider-Assisted Fraud",
                description=(
                    "Shared device or infrastructure usage across multiple accounts "
                    "may indicate an insider with privileged access to multiple customers' "
                    "credentials, or a coordinated attack from a single controlled device."
                ),
                status=HypothesisStatus.INCONCLUSIVE,
                supporting_finding_ids=[
                    fid for fid, f in session.findings.items()
                    if f.finding_type == FindingType.SHARED_INFRASTRUCTURE
                ],
                open_questions=[
                    "Was the shared device a bank-operated device or a customer device?",
                    "Are the accounts linked to the same branch or relationship manager?",
                ],
                confidence=0.4,
                created_at=_now(),
            )
            hypotheses.append(h)

        return hypotheses

    # ── helpers ────────────────────────────────────────────────────────────

    def _transaction_graph(self, session: InvestigationSession) -> nx.DiGraph:
        G: nx.DiGraph = nx.DiGraph()
        for rel in session.relationships:
            if rel.relationship_type == RelationshipType.TRANSFERRED_TO:
                G.add_edge(
                    rel.from_entity, rel.to_entity,
                    amount=float(rel.attributes.get("amount", 0)),
                    timestamp=rel.timestamp or "",
                    tx_id=rel.attributes.get("transaction_id", ""),
                    source_file=rel.source_file,
                    source_row=rel.source_row,
                )
        return G

    def _full_graph(self, session: InvestigationSession) -> nx.Graph:
        G: nx.Graph = nx.Graph()
        for rel in session.relationships:
            G.add_edge(rel.from_entity, rel.to_entity,
                       rel_type=rel.relationship_type.value)
        return G

    def _is_suspicious_path(
        self, path: list[str], session: InvestigationSession
    ) -> bool:
        if len(path) >= 4:
            return True
        for finding in session.findings.values():
            if any(e in finding.entity_ids for e in path):
                return True
        return False

    def _generate_challenges(
        self, finding: Finding, session: InvestigationSession
    ) -> list[str]:
        challenges = [
            "Could these transactions reflect legitimate business payments?",
            "Is there a signed contract or invoice that explains this transfer?",
            "Were the account holders contacted and did they confirm or deny knowledge?",
        ]
        if finding.finding_type == FindingType.SIM_SWAP_CHAIN:
            challenges.extend([
                "Did the person initiate the SIM swap through a carrier store with ID verification?",
                "Is the new SIM registered to the same address as the original?",
            ])
        if finding.finding_type == FindingType.CIRCULAR_TRANSACTION:
            challenges.append(
                "Could this be a settlement cycle between business partners?"
            )
        return challenges

    def _preliminary_verdict(
        self,
        finding: Finding,
        supporting_count: int,
        contradicting_count: int,
    ) -> str:
        if contradicting_count > supporting_count:
            return "CHALLENGED — more contradicting evidence than supporting"
        if supporting_count > 0 and contradicting_count == 0:
            return "SUPPORTED — evidence supports finding, but requires human verification"
        return "INCONCLUSIVE — insufficient evidence to determine either way"
