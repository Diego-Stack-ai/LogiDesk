# M3 IDENTITY SHADOW WRITE SPECIFICATION

## OBJECTIVE
Execute a completely safe, create-only, atomic shadow write of the certified M3 canonical identities into the new Core V1 Firestore paths.

## SCOPE
- **EMPLOYEE_TARGET**: `aziende/NzXaCgyXxZWWehw1tSlo/dipendenti/{legacy_document_id}`
- **USER_TARGET**: `aziende/NzXaCgyXxZWWehw1tSlo/utenti/{firebase_uid}`
- **REGISTRY_TARGET**: `system_migrations/core_v1_m3_identity`
- **TOTAL ATOMIC DOCUMENTS**: 49 (25 employees + 23 users + 1 registry)

## SAFETY & GUARDRAILS
1. **DEFAULT_MODE**: `PREFLIGHT`
2. **EXECUTE CONDITION**: Must run explicitly with `--execute` and `--confirm-shadow-write LOGIDESK_M3_IDENTITY`
3. **HARD GATES**:
   - `PROJECT` = `log-solutions-cantiere`
   - `COMPANY_ID` = `NzXaCgyXxZWWehw1tSlo`
4. **DEPENDENCY GATES**:
   - `M0_M1` = `COMPLETE`
   - `M2` = `COMPLETE`
   - `M3_DRY_RUN` = `CERTIFIED`
5. **PRE-WRITE STATE CLASSIFICATION**:
   - `CLEAN_START`: Allowed
   - `ALREADY_APPLIED`: Allowed (if idempotent)
   - `PARTIAL_STATE`: `STOP`
   - `CONFLICT`: `STOP`

## ATOMIC WRITE GUARANTEES
- **SINGLE ATOMIC BATCH**: All 49 documents must be written in a single Firestore batch.
- **CREATE-ONLY**: No overwrites. Guard against existing non-empty paths.
- **CONCURRENCY GUARD**: Implementation required to prevent parallel runs.
- **IDEMPOTENCY**: Required. Repeated runs must yield the same clean outcome.

## IMMUTABILITY
- **FIRESTORE_CHANGED**: ONLY target business collections. Legacy `root/dipendenti` remains UNCHANGED.
- **AUTH_CHANGED**: FALSE (No Auth modifications, creates, deletes, or claims).
- **STORAGE_CHANGED**: FALSE.
- **RULES_CHANGED**: FALSE.

## POST-WRITE VALIDATION
- EMPLOYEE_TARGET_COUNT_25
- USER_TARGET_COUNT_23
- EMPLOYEE_IDS_PRESERVED
- USER_IDS_EQUAL_FIREBASE_UID
- AUTHENTICATED_EMPLOYEE_COUNT_23
- EMPLOYEE_ONLY_COUNT_2
- NO_TEST_EMPLOYEE_TARGET
- NO_TEST_USER_TARGET
- NO_DUPLICATE_USER_UID
- IDENTITY_REVIEW_CASE_PRESERVED
- EMPLOYEE_FINGERPRINT_MATCH
- USER_FINGERPRINT_MATCH
- EMPLOYEE_FIELD_PARITY
- USER_FIELD_PARITY
- PASSWORD_ABSENT_FROM_TARGET
- PASSWORD_ABSENT_FROM_REPORTS
- LEGACY_UNCHANGED
- AUTH_UNCHANGED
- STORAGE_UNCHANGED
- REGISTRY_COMPLETE

## ROLLBACK PLAN
- **Scope**: Only the 49 generated documents (25 canonical employees, 23 canonical users, 1 registry document).
- **Guard**: Must use fingerprint verification before deletion.
- **Prohibited**: Touching legacy dipendenti, Firebase Auth, M0/M1, M2, or Storage.
- **Automation**: `AUTOMATIC_ROLLBACK = FALSE`
