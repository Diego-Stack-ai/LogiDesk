# M0 / M1 SHADOW WRITE DESIGN SPEC

## 1. SCOPE AND PRINCIPLES
This document outlines the design for the first canonical Firestore write for M0 (Company Shell) and M1 (Tenants Shell) in LogiDesk.

**PRINCIPLE:** SHADOW WRITE ONLY
- **M0_M1_WRITE_MODE:** SHADOW
- The new canonical structure is created, but no runtime is shifted.
- No legacy data is deleted, modified, or synced (no dual-write).
- **M0_M1_RUNTIME_IMPACT:** NONE
- **LEGACY_WRITE_COUNT_EXPECTED:** 0
- **PUNTI_CONSEGNA_CREATED_EXPECTED:** 0

## 2. PROJECT HARD GATE & ENABLEMENT
- The execution must enforce a hard stop if `--project` is not exactly `log-solutions-cantiere`.
- Implicit booleans for execution are banned. It must require an explicit, exact string confirmation flag, e.g., `--confirm-shadow-write LOGIDESK_M0_M1`.
- **EXECUTION_ENVIRONMENT:** Google Cloud Shell with ADC (`gcloud config set project log-solutions-cantiere`). No hardcoded JSON service accounts.

## 3. M0 COMPANY & M1 TENANT MODELS
**M0 Target:** `aziende/{azienda_id}` (Firestore AUTO_ID)
Canonical payload must NOT contain migration metadata (like `migration_status`, `idempotency_key`, `tipo_ambiente`).
```json
{
  "nome": "LogiDesk Demo",
  "attiva": true,
  "schema_version": 1
}
```

**M1 Target:** `aziende/{azienda_id}/tenants/{tenant_id}` (Firestore AUTO_ID for each of the 4 tenants: DNR, CATTEL, GRAN CHEF, BAUER).
*DNR gets `{ sottocodice_attivo: true, valori_ammessi: ["FRUTTA", "LATTE"] }` while others get empty code configs.*
*DAC is NOT created (status: PENDING_RECONCILIATION).*

## 4. MIGRATION REGISTRY SEPARATION
Migration metadata will live in a dedicated system registry, e.g., `system_migrations/core_v1_m0_m1` (or under a migration ID).
It must track: `migration_version`, `migration_name`, `project_id`, `executed_at`, `company_id`, `company_idempotency_key`, `tenant_mapping`, `fingerprints`, `status`.

**MAPPING_SOURCE_OF_TRUTH:** This migration registry (and the written canonical documents) will be the future technical source of truth for all mappings (no manual PC files).

## 5. IDEMPOTENCY & DISCOVERY
Before writing, the script must perform a **PRE-WRITE DISCOVERY** to check `system_migrations/core_v1_m0_m1` and existing documents using keys:
- `CORE_V1::COMPANY::PRIMARY`
- `CORE_V1::TENANT::DNR` (etc.)

Classifications:
- `CLEAN_START` -> Proceed
- `ALREADY_APPLIED` -> Verify-only, no write
- `PARTIAL_STATE` -> STOP + MANUAL REVIEW (no auto-resume for the first version)
- `CONFLICT` -> STOP

## 6. ATOMICITY & PRE-GENERATED IDs
**ATOMIC_WRITE_RECOMMENDED:** TRUE
Rationale: M0 + M1 + registry involves 1 company + 4 tenants + 1 registry doc = 6 documents. This is well within Firestore's 500 document batch limit. Doing this in a single atomic batch avoids `PARTIAL_STATE` almost entirely.

- **Pre-generated Auto IDs:** The script will call `db.collection(...).document()` to obtain `company_id` and `tenant_ids` before batch execution, allowing the registry to be built and committed atomically with the data.

## 7. FINGERPRINTS & VALIDATION
**FINGERPRINT PRE-WRITE:** Canonical payload fingerprints (excluding generated IDs) are calculated before execution.
**POST_WRITE_HASH_PARITY_REQUIRED:** TRUE. After the batch commit, the documents are read back and fingerprints recalculated to ensure 5/5 match.

Post-Write Checks:
- Company exists with `LogiDesk Demo`.
- 4 tenants exist (names: DNR, CATTEL, GRAN CHEF, BAUER).
- DNR config is correct, DAC is absent.
- Registry is `COMPLETE`.

## 8. ROLLBACK DESIGN
Rollback targets ONLY the documents created by this specific script (tracked in the registry).
It must NOT recursively delete `aziende/`.
**Guard:** Rollback is BLOCKED (manual review required) if the post-write hashes of the documents no longer match the registry (i.e., someone modified them after the migration).

## 9. GO / NO-GO GATES
Execution is authorized ONLY if:
1. `GATE_PROJECT` = PASS
2. `GATE_DRY_RUN` = PASS
3. `GATE_COMPANY_CERTIFIED` = PASS
4. `GATE_TENANTS_CERTIFIED` = PASS
5. `GATE_DAC_EXCLUDED` = PASS
6. `GATE_PRE_STATE_CLEAN` = PASS
7. `GATE_ATOMIC_PLAN_VALID` = PASS
8. `GATE_LEGACY_WRITE_ZERO` = PASS
9. `GATE_M5_WRITE_DISABLED` = PASS
10. `GATE_ROLLBACK_MANIFEST_READY` = PASS

## 10. AUTH & RULES IMPLICATION
- `AUTH_CHANGED_EXPECTED` = FALSE
- `RULES_CHANGED_EXPECTED` = FALSE
*Note: Server admin ADC write bypasses client rules. The new structure remains inaccessible to frontend clients.*

## 11. OUTPUT FILES
The write execution will produce local reporting:
- `M0_M1_WRITE_SUMMARY.json`
- `M0_M1_WRITE_REGISTRY.json`
- `M0_M1_POST_WRITE_VALIDATION.json`
## 12. EXECUTION STATUS
- **SCRIPT IMPLEMENTED**: YES (`scripts/migrations/core_v1/m0_m1_foundation_write.py`)
- **LIVE WRITE AUTHORIZED**: NO

**Preflight Command (Cloud Shell / ADC):**
```bash
python scripts/migrations/core_v1/m0_m1_foundation_write.py \
  --project log-solutions-cantiere \
  --output-dir ./migration_output/m0_m1_write
```
