"""
Legal Engine — maps findings to potentially relevant legal references.
All mappings start as UNVERIFIED. This is an investigation aid, not legal advice.
"""
from __future__ import annotations

import json
from pathlib import Path

from models.investigation import (
    InvestigationSession, LegalMapping, LegalStatus,
)


MAPPINGS_FILE = Path(__file__).parent.parent / "legal_mappings.json"


class LegalEngine:
    """
    Maps fraud findings to potentially relevant legal statutes and sections.
    All mappings are UNVERIFIED by default.
    """

    def load_mappings_config(self) -> dict:
        """Load the configurable legal mappings from JSON."""
        if MAPPINGS_FILE.exists():
            with open(MAPPINGS_FILE) as f:
                return json.load(f)
        return {}

    def map_findings(
        self, session: InvestigationSession
    ) -> list[LegalMapping]:
        """Map all findings in the session to legal references."""
        config = self.load_mappings_config()
        mappings: list[LegalMapping] = []

        for finding in session.findings.values():
            finding_key = finding.finding_type.value
            legal_refs = config.get(finding_key, [])

            for ref in legal_refs:
                mapping = LegalMapping(
                    finding_id=finding.finding_id,
                    legal_reference=ref["legal_reference"],
                    statute=ref["statute"],
                    section=ref["section"],
                    description=ref["description"],
                    evidence_ids=list(finding.evidence_ids),
                    status=LegalStatus.UNVERIFIED,
                    disclaimer=(
                        "UNVERIFIED — This is an investigation aid only, "
                        "not definitive legal advice. All mappings require "
                        "review by a qualified legal professional."
                    ),
                )
                mappings.append(mapping)

        return mappings
