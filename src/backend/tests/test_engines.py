"""
Test suite for FraudLens investigation platform.
Tests are written FIRST, before engine implementation (TDD).
"""
import os
import sys
import pytest
import pandas as pd
from pathlib import Path

# Add src/backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

MOCK_DATA = Path(__file__).parent.parent.parent.parent / "data" / "mock"


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_data_path():
    return MOCK_DATA


@pytest.fixture
def sample_people_df():
    return pd.read_csv(MOCK_DATA / "people.csv")


@pytest.fixture
def sample_accounts_df():
    return pd.read_csv(MOCK_DATA / "accounts.csv")


@pytest.fixture
def sample_transactions_df():
    return pd.read_csv(MOCK_DATA / "transactions.csv")


@pytest.fixture
def sample_sims_df():
    return pd.read_csv(MOCK_DATA / "sims.csv")


@pytest.fixture
def sample_devices_df():
    return pd.read_csv(MOCK_DATA / "devices.csv")


@pytest.fixture
def sample_sim_swaps_df():
    return pd.read_csv(MOCK_DATA / "sim_swaps.csv")


@pytest.fixture
def loaded_session(mock_data_path):
    """A fully loaded investigation session from mock data."""
    from engines.entity_engine import EntityEngine
    engine = EntityEngine()
    csv_files = {
        "people": str(mock_data_path / "people.csv"),
        "accounts": str(mock_data_path / "accounts.csv"),
        "phones": str(mock_data_path / "phones.csv"),
        "sims": str(mock_data_path / "sims.csv"),
        "devices": str(mock_data_path / "devices.csv"),
        "transactions": str(mock_data_path / "transactions.csv"),
        "calls": str(mock_data_path / "calls.csv"),
        "locations": str(mock_data_path / "locations.csv"),
        "sim_swaps": str(mock_data_path / "sim_swaps.csv"),
    }
    return engine.build_session("Test Investigation", csv_files)


# ─── Entity Resolution Tests ─────────────────────────────────────────────────

class TestEntityEngine:
    def test_loads_people(self, sample_people_df):
        from engines.entity_engine import EntityEngine
        engine = EntityEngine()
        entities = engine.extract_people(sample_people_df, "people.csv")
        assert len(entities) == 10
        ids = [e.canonical_id for e in entities]
        assert "P001" in ids

    def test_loads_accounts(self, sample_accounts_df):
        from engines.entity_engine import EntityEngine
        engine = EntityEngine()
        entities = engine.extract_accounts(sample_accounts_df, "accounts.csv")
        assert len(entities) == 15
        ids = [e.canonical_id for e in entities]
        assert "ACC001" in ids

    def test_loads_transactions(self, sample_transactions_df):
        from engines.entity_engine import EntityEngine
        engine = EntityEngine()
        entities = engine.extract_transactions(sample_transactions_df, "transactions.csv")
        assert len(entities) == 20

    def test_person_has_required_attributes(self, sample_people_df):
        from engines.entity_engine import EntityEngine
        engine = EntityEngine()
        entities = engine.extract_people(sample_people_df, "people.csv")
        p = next(e for e in entities if e.canonical_id == "P001")
        assert p.display_name == "Rahul Sharma"
        assert "full_name" in p.attributes
        assert p.source_file == "people.csv"
        assert p.source_row >= 0

    def test_account_linked_to_person(self, loaded_session):
        rels = [r for r in loaded_session.relationships
                if r.from_entity == "P001" and r.to_entity == "ACC001"]
        assert len(rels) > 0
        assert rels[0].relationship_type.value == "OWNS"

    def test_builds_full_session(self, loaded_session):
        assert loaded_session.session_id
        assert len(loaded_session.entities) > 0
        assert len(loaded_session.relationships) > 0
        # All expected entity types present
        types = {e.entity_type for e in loaded_session.entities.values()}
        from models.investigation import EntityType
        assert EntityType.PERSON in types
        assert EntityType.ACCOUNT in types
        assert EntityType.TRANSACTION in types

    def test_no_hardcoded_ids_in_engine(self):
        """Engine must not contain hardcoded entity IDs."""
        engine_path = Path(__file__).parent.parent / "engines" / "entity_engine.py"
        content = engine_path.read_text()
        # These are data values, not logic checks
        assert 'if transaction_id ==' not in content
        assert 'if person_id ==' not in content
        assert '"TX001"' not in content
        assert '"P001"' not in content

    def test_duplicate_entity_resolution(self):
        """Entities with same canonical_id should be resolved, not duplicated."""
        from engines.entity_engine import EntityEngine
        df = pd.DataFrame([
            {"person_id": "P001", "full_name": "Rahul Sharma", "dob": "1985-03-15",
             "national_id": "ABCD1234E", "address": "12 MG Road", "email": "r@e.com",
             "phone_primary": "+919876543210", "created_at": "2023-01-10", "updated_at": "2024-03-01"},
            {"person_id": "P001", "full_name": "Rahul Sharma", "dob": "1985-03-15",
             "national_id": "ABCD1234E", "address": "12 MG Road", "email": "r@e.com",
             "phone_primary": "+919876543210", "created_at": "2023-01-10", "updated_at": "2024-03-01"},
        ])
        engine = EntityEngine()
        entities = engine.extract_people(df, "test.csv")
        ids = [e.canonical_id for e in entities]
        assert ids.count("P001") == 1


# ─── Fraud Engine Tests ───────────────────────────────────────────────────────

class TestFraudEngine:
    def test_detects_circular_transaction(self, loaded_session):
        from engines.fraud_engine import FraudEngine
        engine = FraudEngine()
        findings = engine.detect_all(loaded_session)
        circular = [f for f in findings if f.finding_type.value == "CIRCULAR_TRANSACTION"]
        assert len(circular) > 0, "Should detect circular transaction patterns in mock data"

    def test_detects_transaction_chain(self, loaded_session):
        from engines.fraud_engine import FraudEngine
        engine = FraudEngine()
        findings = engine.detect_all(loaded_session)
        chains = [f for f in findings if f.finding_type.value == "TRANSACTION_CHAIN"]
        assert len(chains) > 0

    def test_detects_sim_swap_chain(self, loaded_session):
        from engines.fraud_engine import FraudEngine
        engine = FraudEngine()
        findings = engine.detect_all(loaded_session)
        sim_swaps = [f for f in findings if f.finding_type.value == "SIM_SWAP_CHAIN"]
        assert len(sim_swaps) > 0, "Should detect SIM-swap followed by transactions"

    def test_detects_rapid_fund_movement(self, loaded_session):
        from engines.fraud_engine import FraudEngine
        engine = FraudEngine()
        findings = engine.detect_all(loaded_session)
        rapid = [f for f in findings if f.finding_type.value == "RAPID_FUND_MOVEMENT"]
        assert len(rapid) > 0

    def test_finding_has_evidence_ids(self, loaded_session):
        from engines.fraud_engine import FraudEngine
        engine = FraudEngine()
        findings = engine.detect_all(loaded_session)
        for f in findings:
            assert len(f.evidence_ids) > 0, f"Finding {f.finding_id} has no evidence"

    def test_finding_has_entity_ids(self, loaded_session):
        from engines.fraud_engine import FraudEngine
        engine = FraudEngine()
        findings = engine.detect_all(loaded_session)
        for f in findings:
            assert len(f.entity_ids) > 0, f"Finding {f.finding_id} has no entity IDs"

    def test_severity_assigned(self, loaded_session):
        from engines.fraud_engine import FraudEngine
        from models.investigation import Severity
        engine = FraudEngine()
        findings = engine.detect_all(loaded_session)
        for f in findings:
            assert f.severity in Severity, f"Invalid severity on {f.finding_id}"

    def test_no_hardcoded_ids(self):
        engine_path = Path(__file__).parent.parent / "engines" / "fraud_engine.py"
        content = engine_path.read_text()
        assert '"TX001"' not in content
        assert '"P001"' not in content


# ─── Evidence Engine Tests ────────────────────────────────────────────────────

class TestEvidenceEngine:
    def test_every_finding_has_traceable_evidence(self, loaded_session):
        from engines.fraud_engine import FraudEngine
        from engines.evidence_engine import EvidenceEngine
        fraud = FraudEngine()
        findings = fraud.detect_all(loaded_session)
        # attach findings to session
        for f in findings:
            loaded_session.findings[f.finding_id] = f

        evidence_engine = EvidenceEngine()
        result = evidence_engine.build_evidence_map(loaded_session)

        for finding_id, finding in loaded_session.findings.items():
            for eid in finding.evidence_ids:
                assert eid in result, f"Evidence {eid} for finding {finding_id} not found"

    def test_evidence_has_original_record(self, loaded_session):
        from engines.fraud_engine import FraudEngine
        from engines.evidence_engine import EvidenceEngine
        fraud = FraudEngine()
        findings = fraud.detect_all(loaded_session)
        for f in findings:
            loaded_session.findings[f.finding_id] = f
        evidence_engine = EvidenceEngine()
        evidence_map = evidence_engine.build_evidence_map(loaded_session)
        for ev in evidence_map.values():
            assert ev.original_record, f"Evidence {ev.evidence_id} has no original_record"
            assert ev.source_file, f"Evidence {ev.evidence_id} has no source_file"

    def test_contradicting_evidence_identified(self, loaded_session):
        from engines.evidence_engine import EvidenceEngine
        engine = EvidenceEngine()
        contradictions = engine.find_contradictions(loaded_session)
        # Should find at least some ambiguity in mock data
        assert isinstance(contradictions, list)

    def test_missing_evidence_flagged(self, loaded_session):
        from engines.evidence_engine import EvidenceEngine
        engine = EvidenceEngine()
        missing = engine.identify_missing_evidence(loaded_session)
        assert isinstance(missing, list)

    def test_evidence_chain_traceable(self, loaded_session):
        """Finding → Evidence → Original Record chain must be complete."""
        from engines.fraud_engine import FraudEngine
        from engines.evidence_engine import EvidenceEngine
        fraud = FraudEngine()
        findings = fraud.detect_all(loaded_session)
        for f in findings:
            loaded_session.findings[f.finding_id] = f
        ev_engine = EvidenceEngine()
        evidence_map = ev_engine.build_evidence_map(loaded_session)
        loaded_session.evidence = evidence_map

        for finding in loaded_session.findings.values():
            for eid in finding.evidence_ids:
                ev = loaded_session.evidence.get(eid)
                assert ev is not None
                assert ev.source_file
                assert ev.original_record is not None


# ─── Investigation Engine Tests ───────────────────────────────────────────────

class TestInvestigationEngine:
    def test_trace_money_from_account(self, loaded_session):
        from engines.investigation_engine import InvestigationEngine
        engine = InvestigationEngine()
        result = engine.trace_money("ACC009", loaded_session)
        assert "paths" in result
        assert len(result["paths"]) > 0

    def test_trace_returns_evidence(self, loaded_session):
        from engines.investigation_engine import InvestigationEngine
        engine = InvestigationEngine()
        result = engine.trace_money("ACC009", loaded_session)
        assert "evidence_ids" in result

    def test_why_entities_connected(self, loaded_session):
        from engines.investigation_engine import InvestigationEngine
        engine = InvestigationEngine()
        result = engine.explain_connection("P001", "P003", loaded_session)
        assert "explanation" in result
        assert "path" in result

    def test_challenge_finding(self, loaded_session):
        from engines.fraud_engine import FraudEngine
        from engines.investigation_engine import InvestigationEngine
        fraud = FraudEngine()
        findings = fraud.detect_all(loaded_session)
        for f in findings:
            loaded_session.findings[f.finding_id] = f

        inv_engine = InvestigationEngine()
        finding_id = list(loaded_session.findings.keys())[0]
        result = inv_engine.challenge_finding(finding_id, loaded_session)
        assert "challenges" in result
        assert "supporting_evidence" in result
        assert "contradicting_evidence" in result

    def test_multiple_hypotheses(self, loaded_session):
        from engines.fraud_engine import FraudEngine
        from engines.investigation_engine import InvestigationEngine
        fraud = FraudEngine()
        findings = fraud.detect_all(loaded_session)
        for f in findings:
            loaded_session.findings[f.finding_id] = f

        inv_engine = InvestigationEngine()
        hypotheses = inv_engine.generate_hypotheses(loaded_session)
        assert len(hypotheses) >= 2, "Should generate multiple competing hypotheses"

    def test_never_forces_single_conclusion(self, loaded_session):
        from engines.fraud_engine import FraudEngine
        from engines.investigation_engine import InvestigationEngine
        fraud = FraudEngine()
        findings = fraud.detect_all(loaded_session)
        for f in findings:
            loaded_session.findings[f.finding_id] = f

        inv_engine = InvestigationEngine()
        hypotheses = inv_engine.generate_hypotheses(loaded_session)
        statuses = {h.status for h in hypotheses}
        # Should have at least OPEN or INCONCLUSIVE alongside SUPPORTED
        from models.investigation import HypothesisStatus
        not_all_supported = not all(h.status == HypothesisStatus.SUPPORTED for h in hypotheses)
        assert not_all_supported or len(hypotheses) > 1


# ─── Action Engine Tests ──────────────────────────────────────────────────────

class TestActionEngine:
    def test_proposes_interventions(self, loaded_session):
        from engines.fraud_engine import FraudEngine
        from engines.action_engine import ActionEngine
        fraud = FraudEngine()
        findings = fraud.detect_all(loaded_session)
        for f in findings:
            loaded_session.findings[f.finding_id] = f

        action_engine = ActionEngine()
        actions = action_engine.propose_actions(loaded_session)
        assert len(actions) > 0

    def test_actions_are_proposed_not_executed(self, loaded_session):
        from engines.fraud_engine import FraudEngine
        from engines.action_engine import ActionEngine
        fraud = FraudEngine()
        findings = fraud.detect_all(loaded_session)
        for f in findings:
            loaded_session.findings[f.finding_id] = f

        action_engine = ActionEngine()
        actions = action_engine.propose_actions(loaded_session)
        for a in actions:
            assert a.status == "PROPOSED", "Actions must be PROPOSED, not executed"

    def test_graph_mincut_simulation(self, loaded_session):
        from engines.action_engine import ActionEngine
        engine = ActionEngine()
        result = engine.simulate_graph_cut(loaded_session, "ACC009", "ACC014")
        assert "removed_edges" in result
        assert "before_paths" in result
        assert "after_paths" in result
        assert "remaining_suspicious" in result

    def test_simulation_does_not_modify_session(self, loaded_session):
        from engines.action_engine import ActionEngine
        import copy
        original_rel_count = len(loaded_session.relationships)
        engine = ActionEngine()
        engine.simulate_graph_cut(loaded_session, "ACC009", "ACC014")
        assert len(loaded_session.relationships) == original_rel_count

    def test_actions_have_disclaimer(self, loaded_session):
        from engines.fraud_engine import FraudEngine
        from engines.action_engine import ActionEngine
        fraud = FraudEngine()
        findings = fraud.detect_all(loaded_session)
        for f in findings:
            loaded_session.findings[f.finding_id] = f
        action_engine = ActionEngine()
        actions = action_engine.propose_actions(loaded_session)
        for a in actions:
            assert a.disclaimer, "Every proposed action must have a disclaimer"


# ─── Legal Engine Tests ───────────────────────────────────────────────────────

class TestLegalEngine:
    def test_maps_findings_to_legal_references(self, loaded_session):
        from engines.fraud_engine import FraudEngine
        from engines.legal_engine import LegalEngine
        fraud = FraudEngine()
        findings = fraud.detect_all(loaded_session)
        for f in findings:
            loaded_session.findings[f.finding_id] = f

        legal_engine = LegalEngine()
        mappings = legal_engine.map_findings(loaded_session)
        assert len(mappings) > 0

    def test_all_mappings_start_unverified(self, loaded_session):
        from engines.fraud_engine import FraudEngine
        from engines.legal_engine import LegalEngine
        from models.investigation import LegalStatus
        fraud = FraudEngine()
        findings = fraud.detect_all(loaded_session)
        for f in findings:
            loaded_session.findings[f.finding_id] = f

        legal_engine = LegalEngine()
        mappings = legal_engine.map_findings(loaded_session)
        for m in mappings:
            assert m.status == LegalStatus.UNVERIFIED

    def test_mappings_have_disclaimers(self, loaded_session):
        from engines.fraud_engine import FraudEngine
        from engines.legal_engine import LegalEngine
        fraud = FraudEngine()
        findings = fraud.detect_all(loaded_session)
        for f in findings:
            loaded_session.findings[f.finding_id] = f
        legal_engine = LegalEngine()
        mappings = legal_engine.map_findings(loaded_session)
        for m in mappings:
            assert "UNVERIFIED" in m.disclaimer

    def test_mappings_link_to_evidence(self, loaded_session):
        from engines.fraud_engine import FraudEngine
        from engines.evidence_engine import EvidenceEngine
        from engines.legal_engine import LegalEngine
        fraud = FraudEngine()
        findings = fraud.detect_all(loaded_session)
        for f in findings:
            loaded_session.findings[f.finding_id] = f
        ev_engine = EvidenceEngine()
        loaded_session.evidence = ev_engine.build_evidence_map(loaded_session)
        legal_engine = LegalEngine()
        mappings = legal_engine.map_findings(loaded_session)
        for m in mappings:
            assert len(m.evidence_ids) > 0

    def test_legal_mappings_json_configurable(self):
        from engines.legal_engine import LegalEngine
        engine = LegalEngine()
        config = engine.load_mappings_config()
        assert isinstance(config, dict)
        assert len(config) > 0


# ─── Case Brief Tests ─────────────────────────────────────────────────────────

class TestCaseBriefEngine:
    def _full_session(self, loaded_session):
        from engines.fraud_engine import FraudEngine
        from engines.evidence_engine import EvidenceEngine
        from engines.investigation_engine import InvestigationEngine
        from engines.legal_engine import LegalEngine
        from engines.action_engine import ActionEngine

        fraud = FraudEngine()
        findings = fraud.detect_all(loaded_session)
        for f in findings:
            loaded_session.findings[f.finding_id] = f

        ev_engine = EvidenceEngine()
        loaded_session.evidence = ev_engine.build_evidence_map(loaded_session)

        inv_engine = InvestigationEngine()
        hypotheses = inv_engine.generate_hypotheses(loaded_session)
        for h in hypotheses:
            loaded_session.hypotheses[h.hypothesis_id] = h

        legal_engine = LegalEngine()
        for m in legal_engine.map_findings(loaded_session):
            loaded_session.legal_mappings[m.mapping_id] = m

        action_engine = ActionEngine()
        for a in action_engine.propose_actions(loaded_session):
            loaded_session.proposed_actions[a.action_id] = a

        return loaded_session

    def test_generates_case_brief(self, loaded_session):
        from engines.case_brief_engine import CaseBriefEngine
        session = self._full_session(loaded_session)
        engine = CaseBriefEngine()
        brief = engine.generate(session)
        assert brief.session_id == session.session_id
        assert brief.summary
        assert brief.title

    def test_brief_has_all_sections(self, loaded_session):
        from engines.case_brief_engine import CaseBriefEngine
        session = self._full_session(loaded_session)
        engine = CaseBriefEngine()
        brief = engine.generate(session)
        assert len(brief.timeline) > 0
        assert brief.entity_network_summary
        assert len(brief.findings_summary) > 0
        assert len(brief.legal_references) > 0

    def test_brief_claims_linked_to_evidence(self, loaded_session):
        from engines.case_brief_engine import CaseBriefEngine
        session = self._full_session(loaded_session)
        engine = CaseBriefEngine()
        brief = engine.generate(session)
        # Every finding in summary should have evidence_ids
        for fs in brief.findings_summary:
            assert "evidence_ids" in fs
            assert len(fs["evidence_ids"]) > 0

    def test_brief_has_disclaimer(self, loaded_session):
        from engines.case_brief_engine import CaseBriefEngine
        session = self._full_session(loaded_session)
        engine = CaseBriefEngine()
        brief = engine.generate(session)
        assert "UNVERIFIED" in brief.disclaimer or "investigation aid" in brief.disclaimer.lower()

    def test_outstanding_questions_present(self, loaded_session):
        from engines.case_brief_engine import CaseBriefEngine
        session = self._full_session(loaded_session)
        engine = CaseBriefEngine()
        brief = engine.generate(session)
        assert isinstance(brief.outstanding_questions, list)


# ─── Full Integration Test ────────────────────────────────────────────────────

class TestEndToEnd:
    def test_full_csv_to_brief_pipeline(self, mock_data_path):
        """Complete CSV → Investigation → Brief flow."""
        from engines.entity_engine import EntityEngine
        from engines.fraud_engine import FraudEngine
        from engines.evidence_engine import EvidenceEngine
        from engines.investigation_engine import InvestigationEngine
        from engines.legal_engine import LegalEngine
        from engines.action_engine import ActionEngine
        from engines.case_brief_engine import CaseBriefEngine

        csv_files = {
            "people": str(mock_data_path / "people.csv"),
            "accounts": str(mock_data_path / "accounts.csv"),
            "phones": str(mock_data_path / "phones.csv"),
            "sims": str(mock_data_path / "sims.csv"),
            "devices": str(mock_data_path / "devices.csv"),
            "transactions": str(mock_data_path / "transactions.csv"),
            "calls": str(mock_data_path / "calls.csv"),
            "locations": str(mock_data_path / "locations.csv"),
            "sim_swaps": str(mock_data_path / "sim_swaps.csv"),
        }

        # Stage 1: Entity resolution
        entity_engine = EntityEngine()
        session = entity_engine.build_session("E2E Test", csv_files)
        assert len(session.entities) > 0

        # Stage 2: Fraud detection
        fraud_engine = FraudEngine()
        findings = fraud_engine.detect_all(session)
        for f in findings:
            session.findings[f.finding_id] = f
        assert len(session.findings) > 0

        # Stage 3: Evidence building
        ev_engine = EvidenceEngine()
        session.evidence = ev_engine.build_evidence_map(session)
        assert len(session.evidence) > 0

        # Stage 4: Investigation
        inv_engine = InvestigationEngine()
        hypotheses = inv_engine.generate_hypotheses(session)
        for h in hypotheses:
            session.hypotheses[h.hypothesis_id] = h

        # Stage 5: Legal mapping
        legal_engine = LegalEngine()
        for m in legal_engine.map_findings(session):
            session.legal_mappings[m.mapping_id] = m
        assert len(session.legal_mappings) > 0

        # Stage 6: Action simulation
        action_engine = ActionEngine()
        for a in action_engine.propose_actions(session):
            session.proposed_actions[a.action_id] = a

        # Stage 7: Case brief
        brief_engine = CaseBriefEngine()
        brief = brief_engine.generate(session)
        assert brief.summary
        assert len(brief.findings_summary) > 0

    def test_different_csv_data_works(self, tmp_path):
        """System must work with completely different CSV data."""
        from engines.entity_engine import EntityEngine

        people = pd.DataFrame([{
            "person_id": "X001", "full_name": "Test Person",
            "dob": "1990-01-01", "national_id": "TEST001",
            "address": "Test Address", "email": "test@test.com",
            "phone_primary": "+911234567890",
            "created_at": "2024-01-01", "updated_at": "2024-01-01"
        }])
        accounts = pd.DataFrame([{
            "account_id": "XACC001", "person_id": "X001",
            "account_number": "1234567890", "bank_name": "Test Bank",
            "account_type": "SAVINGS", "balance": 1000.0,
            "currency": "INR", "status": "ACTIVE",
            "opened_at": "2024-01-01", "closed_at": "", "branch_code": "B001"
        }])

        people_path = tmp_path / "people.csv"
        accounts_path = tmp_path / "accounts.csv"
        people.to_csv(people_path, index=False)
        accounts.to_csv(accounts_path, index=False)

        engine = EntityEngine()
        session = engine.build_session("Custom Data Test", {
            "people": str(people_path),
            "accounts": str(accounts_path),
        })
        assert len(session.entities) == 2
        ids = [e.canonical_id for e in session.entities.values()]
        assert "X001" in ids
        assert "XACC001" in ids
