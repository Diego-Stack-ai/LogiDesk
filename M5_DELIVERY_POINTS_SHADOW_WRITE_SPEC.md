# M5 DELIVERY POINTS SHADOW WRITE SPECIFICATION

## 1. OBJECTIVE
Execute a read-only migration simulation (preflight) followed by a live shadow write of legacy delivery points to the Core Data Model V1.
The shadow write MUST be `CREATE ONLY` without overwriting or merging, and it MUST NOT impact the current runtime legacy data or consumers.

## 2. SCOPE AND TARGETS
- **PROJECT**: `log-solutions-cantiere`
- **COMPANY_ID**: `NzXaCgyXxZWWehw1tSlo`
- **TENANT_ID**: `AgvcnbuUMu7YhzSuUKTY` (DNR ONLY)
- **SOURCE**: `clienti/DNR/raccolta clienti`
- **TARGET_COLLECTION**: `aziende/NzXaCgyXxZWWehw1tSlo/tenants/AgvcnbuUMu7YhzSuUKTY/punti_consegna`
- **REGISTRY_PATH**: `system_migrations/core_v1_m5_delivery_points_dnr`

## 3. IDENTIFICATION STRATEGY
- **SOURCE_COUNT**: 453
- **TARGET_COUNT**: 453
- **ID_SORT_KEY**: Lexicographical ascending sort of legacy `id`.
- **ID_STRATEGY**: Deterministic Sequence Generation (`DP000001` to `DP000453`).
- **FRUTTA_LATTE_EXPANSION_ALLOWED**: FALSE. One physical location equals one canonical delivery point (1:1 mapping). The previous 609 expansion model is INVALIDATED.

## 4. DUPLICATE AND VERIFIER POLICY
- **DUPLICATES**: 3 semantic duplicate cases exist. Policy is `PRESERVE_ALL` (blocking = false). No automatic deduplication or merge.
- **VERIFICATO_DA**: All 453 legacy records have `verificato_da = EMPTY`. Therefore, `M5_VERIFIER_MAPPING_REQUIRED_COUNT = 0` and `M5_VERIFIER_UNRESOLVED_COUNT = 0`. No default verifiers will be assigned.

## 5. WRITE ARCHITECTURE
- **TOTAL DOCUMENTS**: 453 business + 1 technical registry = 454 documents.
- **ATOMIC_WRITE_RECOMMENDED**: TRUE. 454 documents is below the Firestore batch limit (500). The write will be executed as a `SINGLE ATOMIC BATCH`.
- **IDEMPOTENCY**: 
  - Canonical Idempotency Key: `CORE_V1::DELIVERY_POINT::DNR::{legacy_document_id}`
  - Registry Idempotency Key: `CORE_V1::M5::DNR::DELIVERY_POINTS`
- **CONCURRENCY GUARD**: Registry will be created using a create precondition or equivalent check to ensure atomic failure and zero partial state for concurrent execution attempts.
- **LEGACY_FIELDS**: `tipo` and `tipologia_grado` are classified as `LEGACY_ONLY` and MUST be excluded from the canonical payload.

## 6. VALIDATION AND FINGERPRINTING
- **FINGERPRINT_MODEL**: SHA256 of the deterministic canonical payload.
- **FIELD_PARITY**: Post-write validation must perform explicit verification of field mapping and fingerprint parity.
- **SOURCE IMMUTABILITY**: Legacy source dataset will be snapped pre-write. After write, the source state must be completely unchanged (`LEGACY_SOURCE_UNCHANGED = TRUE`).

## 7. EXECUTION MODEL
- The script operates in `PREFLIGHT` mode by default.
- Execute write only with `--execute` and `--confirm-shadow-write LOGIDESK_M5_DNR`.
- Hard gating prevents execution against non-Logidesk environments, other companies, or other tenants.
- All preflight/execute reports must be written before exit, even upon failure.

## 8. ROLLBACK DESIGN
- Rollback will target the exact 454 paths identified by the preflight.
- Automatic rollback on execution failure is `FALSE`.
- Rollback fingerprint guard is required to ensure no accidental deletion of independently modified records.
