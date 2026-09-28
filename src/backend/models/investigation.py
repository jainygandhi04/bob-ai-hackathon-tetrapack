"""
Data models for FraudLens investigation platform.
All models use Pydantic for validation and serialization.
"""
from __future__ import annotations
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field
import uuid


def new_id() -> str:
    return str(uuid.uuid4())


# ─── Enumerations ────────────────────────────────────────────────────────────

class EntityType(str, Enum):
    PERSON = "PERSON"
    ACCOUNT = "ACCOUNT"
    PHONE = "PHONE"
    SIM = "SIM"
    DEVICE = "DEVICE"
    TRANSACTION = "TRANSACTION"
    CALL = "CALL"
    LOCATION = "LOCATION"


class RelationshipType(str, Enum):
    OWNS = "OWNS"
    USES = "USES"
    TRANSFERRED_TO = "TRANSFERRED_TO"
    CALLED = "CALLED"
    LOCATED_AT = "LOCATED_AT"
    LINKED_TO = "LINKED_TO"
    SIM_SWAPPED = "SIM_SWAPPED"
    DEVICE_CHANGED = "DEVICE_CHANGED"
    SHARED_DEVICE = "SHARED_DEVICE"
    SHARED_IP = "SHARED_IP"


class FindingType(str, Enum):
    CIRCULAR_TRANSACTION = "CIRCULAR_TRANSACTION"
    TRANSACTION_CHAIN = "TRANSACTION_CHAIN"
    SIM_SWAP_CHAIN = "SIM_SWAP_CHAIN"
    SHARED_INFRASTRUCTURE = "SHARED_INFRASTRUCTURE"
    TEMPORAL_ANOMALY = "TEMPORAL_ANOMALY"
    RAPID_FUND_MOVEMENT = "RAPID_FUND_MOVEMENT"
    LAYERING = "LAYERING"


class Severity(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class HypothesisStatus(str, Enum):
    OPEN = "OPEN"
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    INCONCLUSIVE = "INCONCLUSIVE"


class LegalStatus(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    UNDER_REVIEW = "UNDER_REVIEW"
    VERIFIED = "VERIFIED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


# ─── Core Data Models ────────────────────────────────────────────────────────

class Entity(BaseModel):
    entity_id: str = Field(default_factory=new_id)
    entity_type: EntityType
    canonical_id: str                     # original CSV ID (e.g. "P001", "ACC001")
    display_name: str
    attributes: dict[str, Any] = Field(default_factory=dict)
    source_file: str
    source_row: int
    confidence: float = 1.0
    aliases: list[str] = Field(default_factory=list)


class Relationship(BaseModel):
    relationship_id: str = Field(default_factory=new_id)
    from_entity: str                      # canonical_id
    to_entity: str                        # canonical_id
    relationship_type: RelationshipType
    timestamp: Optional[str] = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    source_file: str
    source_row: int
    confidence: float = 1.0


class EvidenceItem(BaseModel):
    evidence_id: str = Field(default_factory=new_id)
    finding_id: Optional[str] = None
    description: str
    source_file: str
    source_row: int
    original_record: dict[str, Any]
    entity_ids: list[str] = Field(default_factory=list)
    timestamp: Optional[str] = None
    evidence_type: str = "DIRECT"         # DIRECT | CIRCUMSTANTIAL | CONTRADICTING


class Finding(BaseModel):
    finding_id: str = Field(default_factory=new_id)
    finding_type: FindingType
    title: str
    explanation: str
    severity: Severity
    confidence: ConfidenceLevel
    entity_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    pattern_data: dict[str, Any] = Field(default_factory=dict)
    detected_at: str = ""


class Hypothesis(BaseModel):
    hypothesis_id: str = Field(default_factory=new_id)
    title: str
    description: str
    status: HypothesisStatus = HypothesisStatus.OPEN
    supporting_finding_ids: list[str] = Field(default_factory=list)
    contradicting_finding_ids: list[str] = Field(default_factory=list)
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    confidence: float = 0.5
    created_at: str = ""


class LegalMapping(BaseModel):
    mapping_id: str = Field(default_factory=new_id)
    finding_id: str
    legal_reference: str
    statute: str
    section: str
    description: str
    evidence_ids: list[str] = Field(default_factory=list)
    status: LegalStatus = LegalStatus.UNVERIFIED
    disclaimer: str = (
        "UNVERIFIED — This is an investigation aid only, not definitive legal advice. "
        "All mappings require review by a qualified legal professional."
    )


class ProposedAction(BaseModel):
    action_id: str = Field(default_factory=new_id)
    action_type: str
    title: str
    description: str
    target_entity_ids: list[str] = Field(default_factory=list)
    finding_id: str
    simulation_result: Optional[dict[str, Any]] = None
    status: str = "PROPOSED"             # PROPOSED | SIMULATED — never EXECUTED
    risk_level: Severity = Severity.HIGH
    disclaimer: str = (
        "PROPOSED ONLY — No action has been taken. "
        "This simulation is for investigative planning only."
    )


class InvestigationSession(BaseModel):
    session_id: str = Field(default_factory=new_id)
    name: str
    source_files: list[str] = Field(default_factory=list)
    entities: dict[str, Entity] = Field(default_factory=dict)
    relationships: list[Relationship] = Field(default_factory=list)
    findings: dict[str, Finding] = Field(default_factory=dict)
    evidence: dict[str, EvidenceItem] = Field(default_factory=dict)
    hypotheses: dict[str, Hypothesis] = Field(default_factory=dict)
    legal_mappings: dict[str, LegalMapping] = Field(default_factory=dict)
    proposed_actions: dict[str, ProposedAction] = Field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    status: str = "ACTIVE"


class CaseBrief(BaseModel):
    brief_id: str = Field(default_factory=new_id)
    session_id: str
    title: str
    summary: str
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    entity_network_summary: dict[str, Any] = Field(default_factory=dict)
    sim_swap_chains: list[dict[str, Any]] = Field(default_factory=list)
    findings_summary: list[dict[str, Any]] = Field(default_factory=list)
    hypotheses_summary: list[dict[str, Any]] = Field(default_factory=list)
    supporting_evidence: list[str] = Field(default_factory=list)
    contradicting_evidence: list[str] = Field(default_factory=list)
    legal_references: list[dict[str, Any]] = Field(default_factory=list)
    proposed_actions: list[dict[str, Any]] = Field(default_factory=list)
    outstanding_questions: list[str] = Field(default_factory=list)
    generated_at: str = ""
    disclaimer: str = (
        "This case brief is an AI-assisted investigation aid. "
        "All findings, legal mappings, and proposed actions are UNVERIFIED "
        "and require review by qualified investigators and legal professionals."
    )
