# M5 DELIVERY POINTS CURRENT STATE AUDIT

## 1. M5 STATUS & DEPENDENCIES
- **M5_DNR_DRY_RUN_CERTIFIED**: TRUE (from previous phase)
- **M5_WRITE_EXECUTED**: FALSE
- **M5_WRITE_AUTHORIZED**: FALSE

**Dependencies**:
- **M0**: COMPLETE (PASS)
- **M1**: COMPLETE (PASS)
- **M3**: COMPLETE (PASS)
- **M4**: SKIPPED_NOT_REQUIRED (PASS - Dependency Not Required)

## 2. SCOPE & TARGETS
- **M5_REAL_COMPANY_ID**: `NzXaCgyXxZWWehw1tSlo`
- **M5_REAL_DNR_TENANT_ID**: `AgvcnbuUMu7YhzSuUKTY`
- **Target Path**: `aziende/NzXaCgyXxZWWehw1tSlo/tenants/AgvcnbuUMu7YhzSuUKTY/punti_consegna/{punto_id}`

## 3. COUNTS & TRANSFORMATIONS
- **M5_CURRENT_SOURCE_COUNT**: 453 (from legacy DNR dataset `raccolta clienti`)
- **M5_CURRENT_TARGET_COUNT_EXPECTED**: 609 (After split logic for Frutta/Latte/Dual)

## 4. VERIFIER RECONCILIATION (`verificato_da`)
*Note: Pending live ADC to verify UID -> Canonical User mapping against `system_migrations/core_v1_m3_identity`.*
- **M5_VERIFIER_MAPPING_TOTAL**: PENDING_LIVE_AUDIT
- **M5_VERIFIER_RESOLVED_COUNT**: PENDING_LIVE_AUDIT
- **M5_VERIFIER_UNRESOLVED_COUNT**: PENDING_LIVE_AUDIT

## 5. MIGRATION STRATEGY RECAP
- **ID Strategy**: `SIM::{legacy_doc_id}::SOTTOCODICE` (for Dry Run), generated sequence `DP000001` (for Live).
- **Fingerprint Model**: SHA256 of the generated canonical payload.
- **Duplicate Policy**: Exact legacy ID mapping, dual records generated deterministically via subcode.

## 6. RUNTIME IMPACT
- **M5_RUNTIME_IMPACT**: NONE_SHADOW
- Legacy structures (`raccolta clienti`) will NOT be deleted.
- Frontend consumers remain untouched in this phase.
