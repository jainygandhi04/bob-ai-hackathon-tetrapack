"""
Case Brief Engine — generates a structured case brief from investigation state.
Every claim links back to evidence.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from models.investigation import CaseBrief, InvestigationSession


def _now() -> str:
    return datetime.utcnow().isoformat()


class CaseBriefEngine:

    def generate(self, session: InvestigationSession) -> CaseBrief:
        """Generate a complete case brief from the session state."""
        findings_summary = self._summarise_findings(session)
        hypotheses_summary = self._summarise_hypotheses(session)
        legal_refs = self._summarise_legal(session)
        timeline = self._build_timeline(session)
        network_summary = self._network_summary(session)
        sim_chains = self._sim_swap_chains(session)
        proposed_actions = self._summarise_actions(session)
        outstanding = self._outstanding_questions(session)

        supporting_ev = [
            eid for f in session.findings.values()
            for eid in f.evidence_ids
        ]
        contradicting_ev = [
            eid for f in session.findings.values()
            for eid in f.contradicting_evidence_ids
        ]

        high_findings = [
            f for f in session.findings.values()
            if f.severity.value == "HIGH"
        ]

        sim_count = sum(
            1 for f in session.findings.values()
            if f.finding_type.value == "SIM_SWAP_CHAIN"
        )

        summary = (
            f"Investigation '{session.name}' analysed {len(session.source_files)} data source(s), "
            f"identified {len(session.entities)} entities, "
            f"detected {len(session.findings)} finding(s) "
            f"({len(high_findings)} high severity), "
            f"generated {len(session.hypotheses)} hypothesis/hypotheses, "
            f"and mapped {len(session.legal_mappings)} legal reference(s). "
        )
        if sim_count:
            summary += f"{sim_count} SIM-swap chain(s) detected. "
        summary += (
            "All findings are UNVERIFIED and require human investigator review. "
            "This brief is an AI-assisted investigation aid only."
        )

        brief = CaseBrief(
            session_id=session.session_id,
            title=f"Case Brief: {session.name}",
            summary=summary,
            timeline=timeline,
            entity_network_summary=network_summary,
            sim_swap_chains=sim_chains,
            findings_summary=findings_summary,
            hypotheses_summary=hypotheses_summary,
            supporting_evidence=list(set(supporting_ev)),
            contradicting_evidence=list(set(contradicting_ev)),
            legal_references=legal_refs,
            proposed_actions=proposed_actions,
            outstanding_questions=outstanding,
            generated_at=_now(),
        )
        return brief

    # ── section builders ──────────────────────────────────────────────────

    def _summarise_findings(self, session: InvestigationSession) -> list[dict]:
        summaries = []
        for f in session.findings.values():
            summaries.append({
                "finding_id": f.finding_id,
                "type": f.finding_type.value,
                "title": f.title,
                "severity": f.severity.value,
                "confidence": f.confidence.value,
                "explanation": f.explanation,
                "entity_ids": f.entity_ids,
                "evidence_ids": f.evidence_ids,
                "missing_evidence": f.missing_evidence,
                "timeline_events": len(f.timeline),
            })
        # Sort by severity
        order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        summaries.sort(key=lambda x: order.get(x["severity"], 3))
        return summaries

    def _summarise_hypotheses(self, session: InvestigationSession) -> list[dict]:
        return [
            {
                "hypothesis_id": h.hypothesis_id,
                "title": h.title,
                "status": h.status.value,
                "confidence": h.confidence,
                "description": h.description,
                "open_questions": h.open_questions,
            }
            for h in session.hypotheses.values()
        ]

    def _summarise_legal(self, session: InvestigationSession) -> list[dict]:
        return [
            {
                "mapping_id": m.mapping_id,
                "finding_id": m.finding_id,
                "legal_reference": m.legal_reference,
                "statute": m.statute,
                "section": m.section,
                "description": m.description,
                "evidence_ids": m.evidence_ids,
                "status": m.status.value,
                "disclaimer": m.disclaimer,
            }
            for m in session.legal_mappings.values()
        ]

    def _summarise_actions(self, session: InvestigationSession) -> list[dict]:
        return [
            {
                "action_id": a.action_id,
                "action_type": a.action_type,
                "title": a.title,
                "description": a.description,
                "target_entities": a.target_entity_ids,
                "status": a.status,
                "risk_level": a.risk_level.value,
                "disclaimer": a.disclaimer,
            }
            for a in session.proposed_actions.values()
        ]

    def _build_timeline(self, session: InvestigationSession) -> list[dict]:
        events: list[dict] = []
        for finding in session.findings.values():
            events.extend(finding.timeline)
        events.sort(key=lambda x: x.get("timestamp", ""))
        return events

    def _network_summary(self, session: InvestigationSession) -> dict:
        from collections import Counter
        type_counts = Counter(
            e.entity_type.value for e in session.entities.values()
        )
        return {
            "total_entities": len(session.entities),
            "total_relationships": len(session.relationships),
            "entity_type_breakdown": dict(type_counts),
            "total_findings": len(session.findings),
        }

    def _sim_swap_chains(self, session: InvestigationSession) -> list[dict]:
        chains = []
        for finding in session.findings.values():
            if finding.finding_type.value == "SIM_SWAP_CHAIN":
                chains.append({
                    "finding_id": finding.finding_id,
                    "title": finding.title,
                    "pattern": finding.pattern_data,
                    "timeline": finding.timeline,
                    "evidence_ids": finding.evidence_ids,
                })
        return chains

    def _outstanding_questions(self, session: InvestigationSession) -> list[str]:
        questions: list[str] = []
        seen: set[str] = set()
        for finding in session.findings.values():
            for q in finding.missing_evidence:
                if q not in seen:
                    questions.append(q)
                    seen.add(q)
        for hyp in session.hypotheses.values():
            for q in hyp.open_questions:
                if q not in seen:
                    questions.append(q)
                    seen.add(q)
        return questions
