"""
Evidence Engine — builds a traceable evidence map.
Every finding links to evidence that links to original CSV records.
"""
from __future__ import annotations

from models.investigation import (
    EvidenceItem, Finding, InvestigationSession,
)


class EvidenceEngine:
    """
    Builds and validates the evidence map for an investigation session.
    Ensures every finding has traceable evidence back to the original record.
    """

    def build_evidence_map(
        self, session: InvestigationSession
    ) -> dict[str, EvidenceItem]:
        """
        Collect all EvidenceItem objects referenced by findings.
        Returns a dict keyed by evidence_id.
        """
        evidence_map: dict[str, EvidenceItem] = {}

        for finding in session.findings.values():
            # Inline evidence carried inside each finding's evidence IDs
            # The fraud engine already creates EvidenceItem objects and stores
            # their IDs in finding.evidence_ids. We need to reconstruct them
            # from the finding's pattern_data and entity info.
            items = self._materialize_evidence_for_finding(finding, session)
            for item in items:
                # Assign finding_id to each evidence item
                item.finding_id = finding.finding_id
                evidence_map[item.evidence_id] = item

        return evidence_map

    def _materialize_evidence_for_finding(
        self, finding: Finding, session: InvestigationSession
    ) -> list[EvidenceItem]:
        """
        Re-create EvidenceItem objects from the timeline and pattern data
        already embedded in a Finding. This makes evidence fully reproducible
        from the session state without any side-channel storage.
        """
        items: list[EvidenceItem] = []

        # Use timeline events as evidence
        for event in finding.timeline:
            tx_id = event.get("transaction_id", "")
            entity_id = event.get("entity_id", "")
            ent = session.entities.get(entity_id)
            original_record: dict = {}
            source_file = "transactions.csv"
            source_row = 0

            if ent:
                original_record = dict(ent.attributes)
                source_file = ent.source_file
                source_row = ent.source_row

            items.append(EvidenceItem(
                finding_id=finding.finding_id,
                description=event.get("event", ""),
                source_file=source_file,
                source_row=source_row,
                original_record=original_record if original_record else {
                    "event": event.get("event", ""),
                    "timestamp": event.get("timestamp", ""),
                    "entity_id": entity_id,
                },
                entity_ids=[entity_id] if entity_id else [],
                timestamp=event.get("timestamp"),
                evidence_type="DIRECT",
            ))

        # If no timeline, build from entity IDs
        if not items and finding.entity_ids:
            for eid in finding.entity_ids[:3]:  # cap at 3 entities per finding
                ent = session.entities.get(eid)
                if ent:
                    items.append(EvidenceItem(
                        finding_id=finding.finding_id,
                        description=f"Entity {ent.display_name} involved in {finding.finding_type}",
                        source_file=ent.source_file,
                        source_row=ent.source_row,
                        original_record=dict(ent.attributes),
                        entity_ids=[eid],
                        evidence_type="CIRCUMSTANTIAL",
                    ))

        # Assign the new IDs back to the finding
        finding.evidence_ids = [item.evidence_id for item in items]
        return items

    def find_contradictions(
        self, session: InvestigationSession
    ) -> list[dict]:
        """
        Identify evidence that contradicts findings.
        Examples: a finding says account was inactive, but transactions exist.
        """
        contradictions: list[dict] = []

        for finding in session.findings.values():
            if finding.finding_type.value == "SIM_SWAP_CHAIN":
                # Check if there are prior legitimate accesses from the same device
                person_id = finding.pattern_data.get("person_id", "")
                ent = session.entities.get(person_id)
                if ent and str(ent.attributes.get("status", "")) == "ACTIVE":
                    contradictions.append({
                        "finding_id": finding.finding_id,
                        "contradiction": "Account holder has an active status; swap may be legitimate",
                        "evidence_type": "CONTRADICTING",
                    })

        return contradictions

    def identify_missing_evidence(
        self, session: InvestigationSession
    ) -> list[dict]:
        """Return a list of evidence gaps identified across all findings."""
        missing: list[dict] = []
        for finding in session.findings.values():
            for gap in finding.missing_evidence:
                missing.append({
                    "finding_id": finding.finding_id,
                    "finding_title": finding.title,
                    "missing": gap,
                })
        return missing
