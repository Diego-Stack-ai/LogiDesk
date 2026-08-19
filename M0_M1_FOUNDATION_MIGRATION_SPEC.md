# M0 / M1 FOUNDATION MIGRATION SPEC (DRY-RUN DESIGN)

## 1. SCOPE
This document defines the design for the M0 (Company Shell) and M1 (Tenants Shell) migration scripts for LogiDesk.
**MODE:** SHADOW ONLY
- Creates the new foundation structure.
- Legacy runtime reads from legacy paths.
- No consumer shifted.
- No legacy data deleted.
- No dual write.
- No mandatory new rules yet.
- IMPACT ON RUNTIME: NONE

## 2. M0: COMPANY SHELL
- **Target:** `aziende/{azienda_id}`
- **ID Strategy:** Auto-ID in the future.
- **Dry-run ID:** `COMPANY_ID_PREVIEW = "COMPANY_ID_LOGIDESK_001"`
- **Minimum Model:**
  ```json
  {
    "nome": "REVIEW_REQUIRED", 
    "attiva": true,
    "schema_version": "1.0.0"
  }
  ```
  *(Note: LogiDesk is the product name. The operating company name must be configured/certified; hence REVIEW_REQUIRED by default in the script).*

## 3. M1: TENANTS SHELL
- **Target:** `aziende/{azienda_id}/tenants/{tenant_id}`
- **Initial Certified Tenants:** DNR, CATTEL, GRAN CHEF, BAUER.
- **DAC:** Status is `PENDING_RECONCILIATION`. No shell tenant will be created yet.
- **ID Strategy:** Auto-ID in the future.
- **Dry-run IDs:** 
  - `TENANT_ID_DNR`
  - `TENANT_ID_CATTEL`
  - `TENANT_ID_GRAN_CHEF`
  - `TENANT_ID_BAUER`
- **Minimum Model:**
  ```json
  {
    "nome": "Tenant Name",
    "legacy_name": "LEGACY_NAME",
    "attivo": true,
    "schema_version": "1.0.0",
    "configurazione_codici": {},
    "capabilities": {}
  }
  ```

### Tenant Specifics
- **DNR Code Configuration:**
  ```json
  "configurazione_codici": {
      "sottocodice_attivo": true,
      "valori_ammessi": ["FRUTTA", "LATTE"]
  }
  ```
- **Other Tenants Code Configuration:**
  ```json
  "configurazione_codici": {
      "sottocodice_attivo": false,
      "valori_ammessi": []
  }
  ```
- **Capabilities:** Only configured if certified.

## 4. REGISTRY AND IDEMPOTENCY

### Tenant Mapping Registry
Maps legacy names to future targets.
Fields: `legacy_name`, `target_preview_id`, `future_target_id`, `status`.

### Migration Registry (M0/M1 Local Dry-Run)
Fields: `migration_version`, `entity_type`, `legacy_identifier`, `target_preview_id`, `target_path`, `status`, `fingerprint`.

### Idempotency
- Same input = same preview output.
- In execute phase: No duplicate companies, tenants, or mappings.
- Rely on deterministic mapping/registry keys rather than commercial names.

## 5. VALIDATIONS (DRY-RUN)
- `COMPANY_PREVIEW_COUNT = 1`
- `TENANT_PREVIEW_COUNT = 4` (DNR, CATTEL, GRAN CHEF, BAUER)
- `DAC_CREATED = FALSE`
- `duplicate_tenant_name = 0`, `duplicate_preview_id = 0`, `missing_tenant_name = 0`

## 6. DEPENDENCIES
- **M5:** Depends on M0 (Company Created) and M1 (Tenant Created).
  Future write for M5 targets `aziende/{azienda_id}/tenants/{tenant_id_DNR}/punti_consegna/{punto_id}` and must not auto-create the company or tenant.
- **Authorization:** `aziende/{a}/utenti`, roles, capabilities authorization deferred. M0/M1 must precede authorization migration.

## 7. OUTPUT OF M0/M1 SCRIPT
- `M0_M1_DRYRUN_SUMMARY.json`
- `M0_COMPANY_PREVIEW.json`
- `M1_TENANTS_PREVIEW.json`
- `M0_M1_MIGRATION_REGISTRY_PREVIEW.json`
- `M0_M1_VALIDATION_MANIFEST.json`
