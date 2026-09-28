"""
Action Engine — proposes and simulates interventions.
NEVER automatically executes real-world actions.
"""
from __future__ import annotations

from typing import Any

import networkx as nx

from models.investigation import (
    InvestigationSession, ProposedAction, RelationshipType, Severity,
)


class ActionEngine:
    """
    Generates proposed interventions and runs simulations.
    All actions remain PROPOSED — no real-world execution.
    """

    def propose_actions(
        self, session: InvestigationSession
    ) -> list[ProposedAction]:
        actions: list[ProposedAction] = []
        for finding in session.findings.values():
            # One or more proposed actions per finding type
            for action in self._actions_for_finding(finding, session):
                actions.append(action)
        return actions

    def simulate_graph_cut(
        self,
        session: InvestigationSession,
        source: str,
        sink: str,
    ) -> dict[str, Any]:
        """
        Simulate removing the minimum-cut edges between source and sink.
        Does NOT modify the original session graph.
        """
        G = self._transaction_graph(session)

        before_paths: list[list[str]] = []
        after_paths: list[list[str]] = []
        cut_edges: list[tuple] = []

        if source not in G or sink not in G:
            return {
                "removed_edges": [],
                "before_paths": [],
                "after_paths": [],
                "remaining_suspicious": [],
            }

        # Enumerate paths before cut
        try:
            before_paths = list(nx.all_simple_paths(G, source, sink, cutoff=6))
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            pass

        # Compute minimum cut
        try:
            cut_value, partition = nx.minimum_cut(G, source, sink, capacity="amount")
            reachable, non_reachable = partition
            cut_edges = [
                (u, v)
                for u in reachable
                for v in G.successors(u)
                if v in non_reachable
            ]
        except Exception:
            cut_edges = []

        # Simulate removal on a copy
        G_cut = G.copy()
        for u, v in cut_edges:
            if G_cut.has_edge(u, v):
                G_cut.remove_edge(u, v)

        try:
            after_paths = list(nx.all_simple_paths(G_cut, source, sink, cutoff=6))
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            pass

        # Find remaining suspicious paths in the cut graph (other routes)
        remaining_suspicious: list[list[str]] = []
        for s in G_cut.nodes():
            for t in G_cut.nodes():
                if s == t or s == source or t == sink:
                    continue
                try:
                    for p in nx.all_simple_paths(G_cut, s, t, cutoff=5):
                        if len(p) >= 3:
                            remaining_suspicious.append(p)
                            if len(remaining_suspicious) >= 5:
                                break
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    pass
                if len(remaining_suspicious) >= 5:
                    break

        return {
            "source": source,
            "sink": sink,
            "removed_edges": [{"from": u, "to": v} for u, v in cut_edges],
            "before_paths": [{"path": p, "length": len(p)} for p in before_paths],
            "after_paths": [{"path": p, "length": len(p)} for p in after_paths],
            "remaining_suspicious": [{"path": p} for p in remaining_suspicious],
            "paths_eliminated": len(before_paths) - len(after_paths),
            "disclaimer": (
                "SIMULATION ONLY — No accounts or transactions have been blocked. "
                "This is a planning tool for investigators."
            ),
        }

    # ── helpers ────────────────────────────────────────────────────────────

    def _actions_for_finding(
        self, finding: Any, session: InvestigationSession
    ) -> list[ProposedAction]:
        actions: list[ProposedAction] = []
        from models.investigation import FindingType

        if finding.finding_type == FindingType.CIRCULAR_TRANSACTION:
            accounts = [
                e for e in finding.entity_ids
                if session.entities.get(e) and
                session.entities[e].entity_type.value == "ACCOUNT"
            ]
            if accounts:
                actions.append(ProposedAction(
                    action_type="FREEZE_ACCOUNT",
                    title=f"Freeze {len(accounts)} accounts in circular chain",
                    description=(
                        f"Propose freezing accounts {accounts} "
                        "to stop circular fund movement. "
                        "Requires court order or regulatory approval before execution."
                    ),
                    target_entity_ids=accounts,
                    finding_id=finding.finding_id,
                    status="PROPOSED",
                    risk_level=Severity.HIGH,
                ))

        elif finding.finding_type == FindingType.SIM_SWAP_CHAIN:
            accounts = [
                e for e in finding.entity_ids
                if session.entities.get(e) and
                session.entities[e].entity_type.value == "ACCOUNT"
            ]
            actions.append(ProposedAction(
                action_type="ENHANCED_VERIFICATION",
                title="Require enhanced verification on affected accounts",
                description=(
                    "Propose enabling step-up authentication on accounts "
                    "linked to the SIM-swap event. "
                    "This is a soft block that does not prevent legitimate access."
                ),
                target_entity_ids=accounts,
                finding_id=finding.finding_id,
                status="PROPOSED",
                risk_level=Severity.MEDIUM,
            ))

        elif finding.finding_type == FindingType.TRANSACTION_CHAIN:
            actions.append(ProposedAction(
                action_type="INVESTIGATE_CHAIN",
                title="Issue information request for multi-hop chain",
                description=(
                    "Request transaction justification from each entity in the chain. "
                    "Attach regulatory information request under applicable AML rules."
                ),
                target_entity_ids=finding.entity_ids,
                finding_id=finding.finding_id,
                status="PROPOSED",
                risk_level=Severity.MEDIUM,
            ))

        return actions

    def _transaction_graph(self, session: InvestigationSession) -> nx.DiGraph:
        G: nx.DiGraph = nx.DiGraph()
        for rel in session.relationships:
            if rel.relationship_type == RelationshipType.TRANSFERRED_TO:
                amount = float(rel.attributes.get("amount", 0))
                G.add_edge(
                    rel.from_entity, rel.to_entity,
                    amount=amount if amount > 0 else 1,
                    timestamp=rel.timestamp or "",
                    tx_id=rel.attributes.get("transaction_id", ""),
                )
        return G
