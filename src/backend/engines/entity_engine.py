"""
Entity Engine — extracts, normalizes, and resolves entities from CSV files.
Builds relationships with timestamps, source records, source files, and confidence.
Works with any investigator-provided CSV data.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from models.investigation import (
    Entity, EntityType, InvestigationSession,
    Relationship, RelationshipType,
)


def _now() -> str:
    return datetime.utcnow().isoformat()


class EntityEngine:
    """
    Extracts and resolves entities from CSV DataFrames.
    All logic is driven by column names — never by hardcoded entity values.
    """

    # ── public entry point ─────────────────────────────────────────────────

    def build_session(
        self,
        name: str,
        csv_files: dict[str, str],   # {"people": "/path/to/people.csv", ...}
    ) -> InvestigationSession:
        session = InvestigationSession(name=name, created_at=_now(), updated_at=_now())
        session.source_files = list(csv_files.values())

        loader_map: dict[str, callable] = {
            "people":       (self.extract_people,       self._link_people),
            "accounts":     (self.extract_accounts,     self._link_accounts),
            "phones":       (self.extract_phones,       None),
            "sims":         (self.extract_sims,         self._link_sims),
            "devices":      (self.extract_devices,      self._link_devices),
            "transactions":  (self.extract_transactions, self._link_transactions),
            "calls":        (self.extract_calls,        None),
            "locations":    (self.extract_locations,    None),
            "sim_swaps":    (self.extract_sim_swaps,    self._link_sim_swaps),
        }

        dfs: dict[str, pd.DataFrame] = {}
        for key, path in csv_files.items():
            if Path(path).exists():
                df = pd.read_csv(path, keep_default_na=False)
                dfs[key] = df
                extractor, _ = loader_map.get(key, (None, None))
                if extractor:
                    entities = extractor(df, Path(path).name)
                    for e in entities:
                        session.entities[e.canonical_id] = e

        # Second pass: build relationships (needs entities to exist)
        for key, df in dfs.items():
            _, linker = loader_map.get(key, (None, None))
            if linker:
                rels = linker(df, Path(csv_files[key]).name, session)
                session.relationships.extend(rels)

        session.updated_at = _now()
        return session

    # ── extractor methods ──────────────────────────────────────────────────

    def extract_people(
        self, df: pd.DataFrame, source_file: str
    ) -> list[Entity]:
        seen: set[str] = set()
        entities: list[Entity] = []
        for row_idx, row in df.iterrows():
            cid = str(row.get("person_id", "")).strip()
            if not cid or cid in seen:
                continue
            seen.add(cid)
            entities.append(Entity(
                entity_type=EntityType.PERSON,
                canonical_id=cid,
                display_name=str(row.get("full_name", cid)).strip(),
                attributes={k: str(v) for k, v in row.items()},
                source_file=source_file,
                source_row=int(row_idx),
                confidence=1.0,
            ))
        return entities

    def extract_accounts(
        self, df: pd.DataFrame, source_file: str
    ) -> list[Entity]:
        seen: set[str] = set()
        entities: list[Entity] = []
        for row_idx, row in df.iterrows():
            cid = str(row.get("account_id", "")).strip()
            if not cid or cid in seen:
                continue
            seen.add(cid)
            bank = str(row.get("bank_name", "")).strip()
            acc_num = str(row.get("account_number", "")).strip()
            entities.append(Entity(
                entity_type=EntityType.ACCOUNT,
                canonical_id=cid,
                display_name=f"{bank} ···{acc_num[-4:]}",
                attributes={k: str(v) for k, v in row.items()},
                source_file=source_file,
                source_row=int(row_idx),
                confidence=1.0,
            ))
        return entities

    def extract_phones(
        self, df: pd.DataFrame, source_file: str
    ) -> list[Entity]:
        seen: set[str] = set()
        entities: list[Entity] = []
        for row_idx, row in df.iterrows():
            cid = str(row.get("phone_id", "")).strip()
            if not cid or cid in seen:
                continue
            seen.add(cid)
            entities.append(Entity(
                entity_type=EntityType.PHONE,
                canonical_id=cid,
                display_name=str(row.get("phone_number", cid)).strip(),
                attributes={k: str(v) for k, v in row.items()},
                source_file=source_file,
                source_row=int(row_idx),
                confidence=1.0,
            ))
        return entities

    def extract_sims(
        self, df: pd.DataFrame, source_file: str
    ) -> list[Entity]:
        seen: set[str] = set()
        entities: list[Entity] = []
        for row_idx, row in df.iterrows():
            cid = str(row.get("sim_id", "")).strip()
            if not cid or cid in seen:
                continue
            seen.add(cid)
            carrier = str(row.get("carrier", "")).strip()
            iccid = str(row.get("iccid", "")).strip()
            entities.append(Entity(
                entity_type=EntityType.SIM,
                canonical_id=cid,
                display_name=f"SIM {carrier} ···{iccid[-6:]}",
                attributes={k: str(v) for k, v in row.items()},
                source_file=source_file,
                source_row=int(row_idx),
                confidence=1.0,
            ))
        return entities

    def extract_devices(
        self, df: pd.DataFrame, source_file: str
    ) -> list[Entity]:
        seen: set[str] = set()
        entities: list[Entity] = []
        for row_idx, row in df.iterrows():
            cid = str(row.get("device_id", "")).strip()
            if not cid or cid in seen:
                continue
            seen.add(cid)
            entities.append(Entity(
                entity_type=EntityType.DEVICE,
                canonical_id=cid,
                display_name=str(row.get("model", cid)).strip(),
                attributes={k: str(v) for k, v in row.items()},
                source_file=source_file,
                source_row=int(row_idx),
                confidence=1.0,
            ))
        return entities

    def extract_transactions(
        self, df: pd.DataFrame, source_file: str
    ) -> list[Entity]:
        seen: set[str] = set()
        entities: list[Entity] = []
        for row_idx, row in df.iterrows():
            cid = str(row.get("transaction_id", "")).strip()
            if not cid or cid in seen:
                continue
            seen.add(cid)
            amount = str(row.get("amount", "")).strip()
            currency = str(row.get("currency", "INR")).strip()
            entities.append(Entity(
                entity_type=EntityType.TRANSACTION,
                canonical_id=cid,
                display_name=f"TX {amount} {currency}",
                attributes={k: str(v) for k, v in row.items()},
                source_file=source_file,
                source_row=int(row_idx),
                confidence=1.0,
            ))
        return entities

    def extract_calls(
        self, df: pd.DataFrame, source_file: str
    ) -> list[Entity]:
        seen: set[str] = set()
        entities: list[Entity] = []
        for row_idx, row in df.iterrows():
            cid = str(row.get("call_id", "")).strip()
            if not cid or cid in seen:
                continue
            seen.add(cid)
            entities.append(Entity(
                entity_type=EntityType.CALL,
                canonical_id=cid,
                display_name=f"Call {row.get('from_phone', '')} → {row.get('to_phone', '')}",
                attributes={k: str(v) for k, v in row.items()},
                source_file=source_file,
                source_row=int(row_idx),
                confidence=1.0,
            ))
        return entities

    def extract_locations(
        self, df: pd.DataFrame, source_file: str
    ) -> list[Entity]:
        seen: set[str] = set()
        entities: list[Entity] = []
        for row_idx, row in df.iterrows():
            cid = str(row.get("location_id", "")).strip()
            if not cid or cid in seen:
                continue
            seen.add(cid)
            entities.append(Entity(
                entity_type=EntityType.LOCATION,
                canonical_id=cid,
                display_name=str(row.get("name", cid)).strip(),
                attributes={k: str(v) for k, v in row.items()},
                source_file=source_file,
                source_row=int(row_idx),
                confidence=1.0,
            ))
        return entities

    def extract_sim_swaps(
        self, df: pd.DataFrame, source_file: str
    ) -> list[Entity]:
        # SIM swaps are events; we record them as special entities
        seen: set[str] = set()
        entities: list[Entity] = []
        for row_idx, row in df.iterrows():
            cid = str(row.get("swap_id", "")).strip()
            if not cid or cid in seen:
                continue
            seen.add(cid)
            entities.append(Entity(
                entity_type=EntityType.SIM,   # tagged as SIM event
                canonical_id=cid,
                display_name=f"SIM Swap: {row.get('old_sim_id', '')} → {row.get('new_sim_id', '')}",
                attributes={k: str(v) for k, v in row.items()},
                source_file=source_file,
                source_row=int(row_idx),
                confidence=1.0,
                aliases=["SIM_SWAP_EVENT"],
            ))
        return entities

    # ── relationship linkers ───────────────────────────────────────────────

    def _link_people(
        self, df: pd.DataFrame, source_file: str, session: InvestigationSession
    ) -> list[Relationship]:
        return []  # people are root nodes

    def _link_accounts(
        self, df: pd.DataFrame, source_file: str, session: InvestigationSession
    ) -> list[Relationship]:
        rels: list[Relationship] = []
        for row_idx, row in df.iterrows():
            pid = str(row.get("person_id", "")).strip()
            aid = str(row.get("account_id", "")).strip()
            if pid and aid and pid in session.entities and aid in session.entities:
                rels.append(Relationship(
                    from_entity=pid,
                    to_entity=aid,
                    relationship_type=RelationshipType.OWNS,
                    timestamp=str(row.get("opened_at", "")),
                    attributes={"account_type": str(row.get("account_type", ""))},
                    source_file=source_file,
                    source_row=int(row_idx),
                    confidence=1.0,
                ))
        return rels

    def _link_sims(
        self, df: pd.DataFrame, source_file: str, session: InvestigationSession
    ) -> list[Relationship]:
        rels: list[Relationship] = []
        for row_idx, row in df.iterrows():
            pid = str(row.get("person_id", "")).strip()
            sid = str(row.get("sim_id", "")).strip()
            ph_id = str(row.get("phone_id", "")).strip()
            ts = str(row.get("activated_at", ""))
            if pid and sid and pid in session.entities and sid in session.entities:
                rels.append(Relationship(
                    from_entity=pid,
                    to_entity=sid,
                    relationship_type=RelationshipType.USES,
                    timestamp=ts,
                    source_file=source_file,
                    source_row=int(row_idx),
                ))
            if ph_id and sid and ph_id in session.entities and sid in session.entities:
                rels.append(Relationship(
                    from_entity=ph_id,
                    to_entity=sid,
                    relationship_type=RelationshipType.USES,
                    timestamp=ts,
                    source_file=source_file,
                    source_row=int(row_idx),
                ))
        return rels

    def _link_devices(
        self, df: pd.DataFrame, source_file: str, session: InvestigationSession
    ) -> list[Relationship]:
        rels: list[Relationship] = []
        for row_idx, row in df.iterrows():
            pid = str(row.get("person_id", "")).strip()
            did = str(row.get("device_id", "")).strip()
            if pid and did and pid in session.entities and did in session.entities:
                rels.append(Relationship(
                    from_entity=pid,
                    to_entity=did,
                    relationship_type=RelationshipType.USES,
                    timestamp=str(row.get("first_seen_at", "")),
                    source_file=source_file,
                    source_row=int(row_idx),
                ))
        return rels

    def _link_transactions(
        self, df: pd.DataFrame, source_file: str, session: InvestigationSession
    ) -> list[Relationship]:
        rels: list[Relationship] = []
        for row_idx, row in df.iterrows():
            tx_id = str(row.get("transaction_id", "")).strip()
            from_acc = str(row.get("from_account", "")).strip()
            to_acc = str(row.get("to_account", "")).strip()
            ts = str(row.get("timestamp", ""))
            amount = str(row.get("amount", ""))

            if from_acc and to_acc and from_acc in session.entities and to_acc in session.entities:
                rels.append(Relationship(
                    from_entity=from_acc,
                    to_entity=to_acc,
                    relationship_type=RelationshipType.TRANSFERRED_TO,
                    timestamp=ts,
                    attributes={"transaction_id": tx_id, "amount": amount,
                                "currency": str(row.get("currency", "INR"))},
                    source_file=source_file,
                    source_row=int(row_idx),
                    confidence=1.0,
                ))
            # Link transaction entity to accounts
            if tx_id in session.entities:
                if from_acc in session.entities:
                    rels.append(Relationship(
                        from_entity=from_acc,
                        to_entity=tx_id,
                        relationship_type=RelationshipType.LINKED_TO,
                        timestamp=ts,
                        source_file=source_file,
                        source_row=int(row_idx),
                    ))
        return rels

    def _link_sim_swaps(
        self, df: pd.DataFrame, source_file: str, session: InvestigationSession
    ) -> list[Relationship]:
        rels: list[Relationship] = []
        for row_idx, row in df.iterrows():
            swap_id = str(row.get("swap_id", "")).strip()
            pid = str(row.get("person_id", "")).strip()
            old_sim = str(row.get("old_sim_id", "")).strip()
            new_sim = str(row.get("new_sim_id", "")).strip()
            old_dev = str(row.get("old_device_id", "")).strip()
            new_dev = str(row.get("new_device_id", "")).strip()
            ts = str(row.get("completed_at", ""))

            pairs = [
                (old_sim, new_sim, RelationshipType.SIM_SWAPPED),
                (old_dev, new_dev, RelationshipType.DEVICE_CHANGED),
                (pid, swap_id, RelationshipType.LINKED_TO),
            ]
            for from_e, to_e, rel_type in pairs:
                if (from_e and to_e
                        and from_e in session.entities
                        and to_e in session.entities):
                    rels.append(Relationship(
                        from_entity=from_e,
                        to_entity=to_e,
                        relationship_type=rel_type,
                        timestamp=ts,
                        attributes={"swap_id": swap_id},
                        source_file=source_file,
                        source_row=int(row_idx),
                    ))
        return rels
