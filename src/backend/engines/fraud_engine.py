"""
Fraud Engine — detects fraud patterns from graph and temporal data.
All patterns are derived from data; no hardcoded entity IDs.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Optional

import networkx as nx

from models.investigation import (
    ConfidenceLevel, EntityType, EvidenceItem, Finding, FindingType,
    InvestigationSession, RelationshipType, Severity,
)


def _now() -> str:
    return datetime.utcnow().isoformat()


class FraudEngine:
    """
    Detects fraud patterns by analysing the entity graph and transaction timelines.
    Pattern detection is data-driven; entity IDs are never hardcoded.
    """

    def detect_all(self, session: InvestigationSession) -> list[Finding]:
        findings: list[Finding] = []
        G = self._build_transaction_graph(session)
        findings.extend(self._detect_circular_transactions(G, session))
        findings.extend(self._detect_transaction_chains(G, session))
        findings.extend(self._detect_sim_swap_chains(session))
        findings.extend(self._detect_rapid_fund_movement(G, session))
        findings.extend(self._detect_shared_infrastructure(session))
        return findings

    # ── graph construction ─────────────────────────────────────────────────

    def _build_transaction_graph(
        self, session: InvestigationSession
    ) -> nx.DiGraph:
        G: nx.DiGraph = nx.DiGraph()
        for rel in session.relationships:
            if rel.relationship_type == RelationshipType.TRANSFERRED_TO:
                amount = float(rel.attributes.get("amount", 0))
                G.add_edge(
                    rel.from_entity,
                    rel.to_entity,
                    timestamp=rel.timestamp,
                    amount=amount,
                    relationship_id=rel.relationship_id,
                    source_file=rel.source_file,
                    source_row=rel.source_row,
                    tx_id=rel.attributes.get("transaction_id", ""),
                )
        return G

    # ── pattern detectors ──────────────────────────────────────────────────

    def _detect_circular_transactions(
        self, G: nx.DiGraph, session: InvestigationSession
    ) -> list[Finding]:
        findings: list[Finding] = []
        try:
            cycles = list(nx.simple_cycles(G))
        except Exception:
            return findings

        for cycle in cycles:
            if len(cycle) < 2:
                continue
            evidence_items = self._evidence_for_cycle(cycle, G, session)
            ev_ids = [ev.evidence_id for ev in evidence_items]
            entity_ids = list(cycle)

            # Collect timeline
            timeline = self._timeline_for_path(cycle, G)

            finding = Finding(
                finding_type=FindingType.CIRCULAR_TRANSACTION,
                title=f"Circular transaction chain involving {len(cycle)} accounts",
                explanation=(
                    f"Funds flow in a closed loop: "
                    f"{' → '.join(cycle)} → {cycle[0]}. "
                    "This pattern is consistent with money layering or circular fraud. "
                    "Each hop may indicate an attempt to obscure the source of funds."
                ),
                severity=Severity.HIGH if len(cycle) >= 3 else Severity.MEDIUM,
                confidence=ConfidenceLevel.HIGH,
                entity_ids=entity_ids,
                evidence_ids=ev_ids,
                timeline=timeline,
                pattern_data={"cycle": cycle, "length": len(cycle)},
                detected_at=_now(),
            )
            findings.append(finding)
        return findings

    def _detect_transaction_chains(
        self, G: nx.DiGraph, session: InvestigationSession
    ) -> list[Finding]:
        findings: list[Finding] = []
        if G.number_of_nodes() == 0:
            return findings

        # Find chains of length >= 3 hops (non-circular)
        # Use DFS to find all paths longer than threshold
        threshold = 3
        long_paths: list[list[str]] = []
        for source in G.nodes():
            for target in G.nodes():
                if source == target:
                    continue
                try:
                    paths = list(nx.all_simple_paths(G, source, target, cutoff=6))
                    for p in paths:
                        if len(p) >= threshold + 1:
                            long_paths.append(p)
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    pass

        # Deduplicate: keep only paths not subsumed by a longer one
        unique_paths = self._deduplicate_paths(long_paths)

        for path in unique_paths[:5]:   # cap at 5 findings
            evidence_items = self._evidence_for_path(path, G, session)
            ev_ids = [ev.evidence_id for ev in evidence_items]
            timeline = self._timeline_for_path(path, G)
            total_amount = sum(
                G[path[i]][path[i+1]].get("amount", 0)
                for i in range(len(path)-1)
                if G.has_edge(path[i], path[i+1])
            )
            finding = Finding(
                finding_type=FindingType.TRANSACTION_CHAIN,
                title=f"Multi-hop transaction chain: {len(path)-1} hops",
                explanation=(
                    f"Funds moved through a chain of {len(path)-1} accounts: "
                    f"{' → '.join(path)}. "
                    f"Total amount in chain: {total_amount:.2f}. "
                    "Multi-hop chains are a common layering technique."
                ),
                severity=Severity.HIGH if len(path) >= 5 else Severity.MEDIUM,
                confidence=ConfidenceLevel.HIGH,
                entity_ids=list(path),
                evidence_ids=ev_ids,
                timeline=timeline,
                pattern_data={"path": path, "total_amount": total_amount},
                detected_at=_now(),
            )
            findings.append(finding)
        return findings

    def _detect_sim_swap_chains(
        self, session: InvestigationSession
    ) -> list[Finding]:
        """
        Detect SIM-swap → device-change → account-access → transaction chains.
        Looks for swap events followed by transactions within a temporal window.
        """
        findings: list[Finding] = []

        # Collect all SIM swap events (tagged as SIM_SWAP_EVENT alias)
        swap_events = [
            e for e in session.entities.values()
            if "SIM_SWAP_EVENT" in e.aliases
        ]

        for swap in swap_events:
            pid = str(swap.attributes.get("person_id", "")).strip()
            new_sim = str(swap.attributes.get("new_sim_id", "")).strip()
            new_dev = str(swap.attributes.get("new_device_id", "")).strip()
            completed_at = str(swap.attributes.get("completed_at", ""))

            # Find accounts owned by same person
            owned_accounts = [
                r.to_entity for r in session.relationships
                if r.from_entity == pid and r.relationship_type == RelationshipType.OWNS
            ]

            # Find transactions from those accounts AFTER the swap
            post_swap_txs = []
            for rel in session.relationships:
                if rel.relationship_type != RelationshipType.TRANSFERRED_TO:
                    continue
                if rel.from_entity not in owned_accounts:
                    continue
                if completed_at and rel.timestamp:
                    try:
                        swap_ts = datetime.fromisoformat(completed_at)
                        tx_ts = datetime.fromisoformat(str(rel.timestamp))
                        hours_after = (tx_ts - swap_ts).total_seconds() / 3600
                        if 0 < hours_after <= 72:   # within 72 hours
                            post_swap_txs.append((rel, hours_after))
                    except ValueError:
                        pass

            if not post_swap_txs:
                continue

            # Build evidence
            evidence_items: list[EvidenceItem] = []
            for e_id in [swap.canonical_id, new_sim, new_dev] + owned_accounts:
                if e_id in session.entities:
                    ent = session.entities[e_id]
                    evidence_items.append(EvidenceItem(
                        description=f"Entity involved in SIM-swap chain: {ent.display_name}",
                        source_file=ent.source_file,
                        source_row=ent.source_row,
                        original_record=ent.attributes,
                        entity_ids=[e_id],
                        timestamp=completed_at,
                        evidence_type="DIRECT",
                    ))

            for rel, hours in post_swap_txs:
                tx_ent = session.entities.get(rel.attributes.get("transaction_id", ""))
                evidence_items.append(EvidenceItem(
                    description=(
                        f"Transaction {rel.attributes.get('transaction_id', '')} "
                        f"occurred {hours:.1f} hours after SIM swap"
                    ),
                    source_file=rel.source_file,
                    source_row=rel.source_row,
                    original_record=rel.attributes,
                    entity_ids=[rel.from_entity, rel.to_entity],
                    timestamp=rel.timestamp,
                    evidence_type="DIRECT",
                ))

            ev_ids = [ev.evidence_id for ev in evidence_items]
            entity_ids = (
                [pid, swap.canonical_id, new_sim, new_dev]
                + owned_accounts
                + [r.from_entity for r, _ in post_swap_txs]
            )

            timeline = sorted([
                {"timestamp": completed_at, "event": "SIM Swap completed", "entity_id": swap.canonical_id},
            ] + [
                {"timestamp": r.timestamp, "event": f"Transaction {r.attributes.get('amount','')} post-swap",
                 "entity_id": r.from_entity}
                for r, _ in post_swap_txs
            ], key=lambda x: x.get("timestamp", ""))

            finding = Finding(
                finding_type=FindingType.SIM_SWAP_CHAIN,
                title=f"SIM-swap chain: {len(post_swap_txs)} transactions within 72h",
                explanation=(
                    f"Person {pid} performed a SIM swap on {completed_at}. "
                    f"Within 72 hours, {len(post_swap_txs)} transaction(s) were made "
                    "from the same person's accounts using the new device/SIM. "
                    "This sequence — SIM swap → device change → account access → transaction — "
                    "is a known SIM-swap fraud pattern."
                ),
                severity=Severity.HIGH,
                confidence=ConfidenceLevel.MEDIUM,
                entity_ids=list(set(entity_ids)),
                evidence_ids=ev_ids,
                timeline=timeline,
                missing_evidence=[
                    "Verification method used during SIM swap",
                    "Credential change events (password reset, PIN change)",
                    "Login attempts from new device before transactions",
                ],
                pattern_data={
                    "swap_id": swap.canonical_id,
                    "person_id": pid,
                    "transactions_after_swap": len(post_swap_txs),
                },
                detected_at=_now(),
            )
            findings.append(finding)
        return findings

    def _detect_rapid_fund_movement(
        self, G: nx.DiGraph, session: InvestigationSession
    ) -> list[Finding]:
        """Detect funds moving through multiple accounts within a short time window."""
        findings: list[Finding] = []

        # Group transfers by timestamp proximity
        timed_transfers: list[tuple[str, str, str, float]] = []
        for u, v, data in G.edges(data=True):
            ts = data.get("timestamp", "")
            amount = data.get("amount", 0)
            if ts:
                timed_transfers.append((u, v, ts, amount))

        timed_transfers.sort(key=lambda x: x[2])

        # Find clusters of transfers within 4 hours
        window_hours = 4
        for i, (u1, v1, ts1, amt1) in enumerate(timed_transfers):
            cluster = [(u1, v1, ts1, amt1)]
            try:
                t1 = datetime.fromisoformat(str(ts1))
            except ValueError:
                continue
            for j, (u2, v2, ts2, amt2) in enumerate(timed_transfers):
                if i == j:
                    continue
                try:
                    t2 = datetime.fromisoformat(str(ts2))
                    if abs((t2 - t1).total_seconds()) <= window_hours * 3600:
                        cluster.append((u2, v2, ts2, amt2))
                except ValueError:
                    pass

            # Significant rapid movement: >= 3 transfers in window
            if len(cluster) >= 3:
                involved_accounts = list({u for u, v, _, _ in cluster} |
                                         {v for _, v, _, _ in cluster})
                if len(involved_accounts) >= 3:
                    total = sum(a for _, _, _, a in cluster)
                    ev_items = []
                    for u, v, ts, amt in cluster:
                        edge_data = G.get_edge_data(u, v, {})
                        ev_items.append(EvidenceItem(
                            description=f"Transfer {amt:.2f} from {u} to {v} at {ts}",
                            source_file=edge_data.get("source_file", "transactions.csv"),
                            source_row=edge_data.get("source_row", 0),
                            original_record={"from": u, "to": v, "amount": amt, "timestamp": ts},
                            entity_ids=[u, v],
                            timestamp=ts,
                            evidence_type="DIRECT",
                        ))
                    ev_ids = [e.evidence_id for e in ev_items]
                    finding = Finding(
                        finding_type=FindingType.RAPID_FUND_MOVEMENT,
                        title=f"Rapid fund movement: {len(cluster)} transfers in {window_hours}h",
                        explanation=(
                            f"{len(cluster)} transfers totalling {total:.2f} INR "
                            f"occurred within {window_hours} hours across "
                            f"{len(involved_accounts)} accounts. "
                            "Rapid sequential transfers are a common indicator of layering."
                        ),
                        severity=Severity.HIGH if total > 100000 else Severity.MEDIUM,
                        confidence=ConfidenceLevel.MEDIUM,
                        entity_ids=involved_accounts,
                        evidence_ids=ev_ids,
                        timeline=[
                            {"timestamp": ts, "event": f"Transfer {amt:.2f} from {u} to {v}",
                             "entity_id": u}
                            for u, v, ts, amt in sorted(cluster, key=lambda x: x[2])
                        ],
                        pattern_data={
                            "transfer_count": len(cluster),
                            "total_amount": total,
                            "window_hours": window_hours,
                        },
                        detected_at=_now(),
                    )
                    # Avoid duplicate findings (same account set)
                    acc_key = frozenset(involved_accounts)
                    if not any(
                        frozenset(f.entity_ids) == acc_key
                        and f.finding_type == FindingType.RAPID_FUND_MOVEMENT
                        for f in findings
                    ):
                        findings.append(finding)
        return findings

    def _detect_shared_infrastructure(
        self, session: InvestigationSession
    ) -> list[Finding]:
        """Detect multiple entities sharing the same device or IP address."""
        findings: list[Finding] = []

        # Find accounts using the same device
        device_users: dict[str, set[str]] = defaultdict(set)
        for ent in session.entities.values():
            if ent.entity_type == EntityType.TRANSACTION:
                dev = str(ent.attributes.get("device_id", "")).strip()
                acc = str(ent.attributes.get("from_account", "")).strip()
                if dev and acc:
                    device_users[dev].add(acc)

        for dev_id, accounts in device_users.items():
            if len(accounts) < 2:
                continue
            account_owners: set[str] = set()
            for rel in session.relationships:
                if rel.to_entity in accounts and rel.relationship_type == RelationshipType.OWNS:
                    account_owners.add(rel.from_entity)

            if len(account_owners) >= 2:
                ev_items = [
                    EvidenceItem(
                        description=f"Accounts {list(accounts)} shared device {dev_id}",
                        source_file="transactions.csv",
                        source_row=0,
                        original_record={"device_id": dev_id, "accounts": list(accounts)},
                        entity_ids=[dev_id] + list(accounts),
                        evidence_type="CIRCUMSTANTIAL",
                    )
                ]
                finding = Finding(
                    finding_type=FindingType.SHARED_INFRASTRUCTURE,
                    title=f"Shared device used by {len(accounts)} accounts",
                    explanation=(
                        f"Device {dev_id} was used to initiate transactions "
                        f"from {len(accounts)} different accounts owned by "
                        f"{len(account_owners)} different persons. "
                        "Shared device usage across unrelated accounts suggests coordination."
                    ),
                    severity=Severity.MEDIUM,
                    confidence=ConfidenceLevel.MEDIUM,
                    entity_ids=[dev_id] + list(accounts) + list(account_owners),
                    evidence_ids=[e.evidence_id for e in ev_items],
                    missing_evidence=["Confirm physical device ownership", "Check IP address correlation"],
                    pattern_data={"device_id": dev_id, "account_count": len(accounts)},
                    detected_at=_now(),
                )
                findings.append(finding)

        return findings

    # ── helpers ────────────────────────────────────────────────────────────

    def _evidence_for_cycle(
        self, cycle: list[str], G: nx.DiGraph, session: InvestigationSession
    ) -> list[EvidenceItem]:
        items: list[EvidenceItem] = []
        for i, node in enumerate(cycle):
            next_node = cycle[(i + 1) % len(cycle)]
            if G.has_edge(node, next_node):
                edge = G[node][next_node]
                items.append(EvidenceItem(
                    description=f"Transfer from {node} to {next_node}: {edge.get('amount', 0):.2f}",
                    source_file=edge.get("source_file", "transactions.csv"),
                    source_row=edge.get("source_row", 0),
                    original_record={
                        "from": node,
                        "to": next_node,
                        "amount": edge.get("amount", 0),
                        "timestamp": edge.get("timestamp", ""),
                        "transaction_id": edge.get("tx_id", ""),
                    },
                    entity_ids=[node, next_node],
                    timestamp=edge.get("timestamp"),
                    evidence_type="DIRECT",
                ))
        return items

    def _evidence_for_path(
        self, path: list[str], G: nx.DiGraph, session: InvestigationSession
    ) -> list[EvidenceItem]:
        items: list[EvidenceItem] = []
        for i in range(len(path) - 1):
            node, next_node = path[i], path[i + 1]
            if G.has_edge(node, next_node):
                edge = G[node][next_node]
                items.append(EvidenceItem(
                    description=f"Transfer hop {i+1}: {node} → {next_node} ({edge.get('amount', 0):.2f})",
                    source_file=edge.get("source_file", "transactions.csv"),
                    source_row=edge.get("source_row", 0),
                    original_record={
                        "from": node, "to": next_node,
                        "amount": edge.get("amount", 0),
                        "timestamp": edge.get("timestamp", ""),
                        "transaction_id": edge.get("tx_id", ""),
                    },
                    entity_ids=[node, next_node],
                    timestamp=edge.get("timestamp"),
                    evidence_type="DIRECT",
                ))
        return items

    def _timeline_for_path(
        self, path: list[str], G: nx.DiGraph
    ) -> list[dict]:
        events = []
        for i in range(len(path) - 1):
            n, m = path[i], path[(i + 1) % len(path)] if i + 1 < len(path) else path[0]
            if G.has_edge(n, m):
                edge = G[n][m]
                events.append({
                    "timestamp": edge.get("timestamp", ""),
                    "event": f"Transfer {edge.get('amount', 0):.2f} from {n} to {m}",
                    "entity_id": n,
                    "transaction_id": edge.get("tx_id", ""),
                })
        return sorted(events, key=lambda x: x.get("timestamp", ""))

    @staticmethod
    def _deduplicate_paths(paths: list[list[str]]) -> list[list[str]]:
        """Remove paths that are subsets of longer paths."""
        unique = []
        path_sets = [frozenset(p) for p in paths]
        for i, p in enumerate(paths):
            if any(
                i != j and path_sets[i].issubset(path_sets[j]) and len(paths[i]) < len(paths[j])
                for j in range(len(paths))
            ):
                continue
            if p not in unique:
                unique.append(p)
        return unique
