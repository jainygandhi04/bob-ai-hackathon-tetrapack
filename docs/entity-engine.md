# Entity Engine (Module 2)

Deterministic: no LLM calls inside. Bob does the language work and hands structured JSON to the engine.

## Pipeline
`resolve_entities()` -> for each complaint: `extract_entities()` -> `ingest_extraction()` -> graph

| File | Job |
|---|---|
| `normalize.py` | phones (+91/0 prefixes), Indian-grouped amounts (1,22,500), Devanagari transliteration, name similarity, clock times (`12:40 raat` = 00:40; unmarked times keep both AM/PM candidates) |
| `extract.py` | rule-based complaint extraction + `validate_extraction()` for Bob's JSON (confidence capped at 0.9) |
| `resolve.py` | person merging with explicit tiers and corroboration; non-destructive, auditable |
| `link.py` | complaint claims -> `ALLEGES` edges with confidence, `needs_review`, conflicts and ambiguity reports |
| `engine.py` | facade the MCP server will expose to Bob |

## Merge rules
* Tier A: name score >= 0.92 (not initial-only) -> merge.
* Tier B: 0.80-0.92 or initial-only ("R. Mandal") -> merge only with corroboration (shared phone, shared IMEI, same bank + account-opening date).
* Otherwise listed under `possible_matches`; never guessed.
* Same surname alone never merges (Imran Ansari != Bablu Ansari).
* Old node ids keep working through `graph.canonical_id()`; every merge is in `graph.graph["merge_log"]`.

## Link confidence ladder (mention -> person)
0.95 name + phone anchor | 0.90 first name + phone anchor | 0.85 full name | 0.55 unique first name (needs review) | ambiguous -> not linked | name/phone mismatch -> `conflicts`.

## Bob payload (what `ingest_extraction` accepts)
```json
{"evidence_id": "EV-0007",
 "complainant": {"name": "Sunil Verma", "account_id": "A-VIC-02"},
 "phones": [{"raw": "+91 90000 20001", "role": "suspect_phone"}],
 "mentions": [{"text": "Imran Ansari", "kind": "full_name", "role": "caller_claimed", "phones": ["9000020001"]}],
 "amounts": [{"raw": "1,55,000 rupaye", "role": "claimed_loss"}],
 "times": [{"raw": "2:40", "kind": "network_loss", "candidates": ["2026-03-14T02:40:00"]}]}
```

## Known limitations
* Pairwise O(n^2) resolution; production needs blocking (e.g. by phonetic surname).
* Devanagari matching is transliteration-based, so heavy spelling drift can be missed.
* "Same bank + opening date" is weak evidence on its own; it is only ever used to back a name match.
