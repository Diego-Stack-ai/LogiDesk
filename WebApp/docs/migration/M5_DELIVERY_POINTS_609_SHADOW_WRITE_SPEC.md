# M5 DELIVERY POINTS 609 SHADOW WRITE SPECIFICATION

## 1. OBJECTIVE
Execute a live shadow write of legacy delivery points to the Core Data Model V1 using the restored 453 -> 609 split model.
The shadow write MUST be `CREATE ONLY` and it MUST NOT impact current runtime legacy data.

## 2. SOURCE AND TARGET
- **SOURCE**: `clienti/DNR/raccolta clienti` (453 documents)
- **TARGET**: `aziende/{company}/tenants/{tenant}/punti_consegna/{DP000001-DP000609}` (609 documents)
- **REGISTRY**: `system_migrations/core_v1_m5_delivery_points_dnr`

## 3. FIRESTORE LIMITS AND ATOMICITY
- **EXPECTED WRITE COUNT**: 610 (609 business + 1 technical registry)
- **FIRESTORE BATCH LIMIT**: 500 operations
- **SINGLE BATCH ALLOWED**: FALSE
- **WRITE EXECUTION MODEL**: MULTI-BATCH STATE MACHINE

### State Machine Model
1. **PREPARED**: Registry created indicating `status=WRITING`, containing all fingerprints and target mappings. (Batch 1: 1 document)
2. **WRITING**: Business targets are chunked into 2 or more batches (e.g., 2 chunks of 305 ops). Each batch is committed independently using resume-safe `CREATE-ONLY` logic based on target path existence.
3. **COMPLETE**: Final update to registry setting `status=COMPLETE`. (Final single operation).

If a chunk fails, the process stops leaving a `PARTIAL_STATE`. A subsequent run will detect the registry in `WRITING`, verify existing targets by fingerprint, and only write missing targets.

## 4. CANONICAL MODEL
**Fields**:
`codice_punto`, `codice_esterno`, `sottocodice`, `nome`, `indirizzo`, `cap`, `citta`, `provincia`, `codice_zona`, `geolocalizzazione`, `attivo`, `finestre_consegna`, `association_group_id`.

**Forbidden Fields**:
`codice_frutta`, `codice_latte`, `tipo`, `tipologia_grado`.

**Values**:
- `sottocodice` is exactly `FRUTTA` or `LATTE`.
- `codice_esterno` is derived from valid `codice_frutta` or `codice_latte`.

## 5. SPLIT RULES & PLACEHOLDER POLICY
- **FRUTTA ONLY**: 236 targets
- **LATTE ONLY**: 61 targets
- **BOTH REAL DIFFERENT**: 156 * 2 = 312 targets. Both share the same `association_group_id` = `ASSOC::{legacy_doc_id}`.
- **PLACEHOLDERS**: `P00000`, `p00000`, `False`, `NaN`, `null`, `blank` generate 0 targets.

## 6. DELIVERY WINDOWS
Windows are strictly isolated by channel:
- FRUTTA targets only get `orario_min_frutta` / `orario_max_frutta`.
- LATTE targets only get `orario_min_latte` / `orario_max_latte`.

## 7. IDENTIFIERS & MAPPING
- **ID STRATEGY**: `SEQUENCE_GENERATION`
- **SORT KEY**: `[legacy_document_id, sottocodice]`
- **ONE-TO-MANY MAPPING**: The registry must support a 1 -> 1 or 1 -> 2 array of canonical targets per legacy document.
- **IDEMPOTENCY KEY**: `CORE_V1::DELIVERY_POINT::DNR::{legacy_doc_id}::{sottocodice}`

## 8. PRE-WRITE GATES
- `GATE_PROJECT`, `GATE_COMPANY`, `GATE_TENANT`
- `GATE_M0_M1_COMPLETE`, `GATE_M3_COMPLETE`, `GATE_M4_NOT_REQUIRED`
- `GATE_SOURCE_COUNT_453`
- `GATE_FRUTTA_ONLY_236`, `GATE_LATTE_ONLY_61`, `GATE_BOTH_REAL_156`, `GATE_SAME_CODE_ZERO`, `GATE_NO_VALID_CODE_ZERO`
- `GATE_TARGET_COUNT_609`
- `GATE_FIRST_ID_DP000001`, `GATE_LAST_ID_DP000609`, `GATE_UNIQUE_IDS_609`
- `GATE_ONE_TO_MANY_MAPPING_VALID`
- `GATE_PLACEHOLDER_TARGET_ZERO`, `GATE_LEGACY_CODE_FIELDS_ZERO`, `GATE_UNKNOWN_FIELD_ZERO`, `GATE_VERIFIER_UNRESOLVED_ZERO`
- `GATE_NON_DNR_ZERO`, `GATE_DAC_ZERO`
- `GATE_PRE_STATE_CLEAN`
- `GATE_WRITE_MODEL_VALID`, `GATE_CONCURRENCY_MODEL_VALID`
- `GATE_ROLLBACK_MANIFEST_READY`

## 9. POST-WRITE VALIDATION
- Registry `COMPLETE`.
- Target count 609, unique targets 609.
- Fingerprint parity 609/609.
- Field parity 609/609 (no legacy fields present).
- Association parity (156 pairs sharing `association_group_id`).
- Legacy unchanged, Auth unchanged, Storage unchanged.

## 10. ROLLBACK
Automatic rollback is FALSE. Rollback targets exactly the 609 generated business documents and the registry coordination document, guarded by fingerprints.
