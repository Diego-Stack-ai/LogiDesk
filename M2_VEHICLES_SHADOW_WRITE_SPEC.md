# M2 VEHICLES SHADOW WRITE SPEC
# FIRST VEHICLE CANONICAL WRITE (DESIGN ONLY)

## 1. SCOPE AND PRINCIPLE
- **WRITE_MODE**: SHADOW (Legacy consumer impact = NONE)
- **SOURCE**: `mezzi/{legacy_document_id}`
- **TARGET**: `aziende/NzXaCgyXxZWWehw1tSlo/mezzi/{vehicle_id}` (Firestore AUTO_ID)
- Creates the 24 vehicle documents inside the target company without touching legacy data. No consumer is migrated in this phase.
- Excludes `_patenti` and `_tipologie` configuration documents.

## 2. HARD GATES & EXECUTION
- **TARGET_PROJECT_HARD_GATE**: `log-solutions-cantiere`
- **COMPANY_ID_HARD_GATE**: `NzXaCgyXxZWWehw1tSlo`
- Pre-requisite: M0/M1 must be COMPLETE and company document must exist.
- **EXECUTION_CONFIRMATION_MODEL**: Requires `--execute` and `--confirm-shadow-write LOGIDESK_M2_VEHICLES`. Defaults to PREFLIGHT READ ONLY without these flags.

## 3. BUSINESS FIELDS VS DEFERRED FIELDS
**BUSINESS_WRITE_FIELDS**:
- targa, attivo, schema_version, tipo, marca, modello, portata, patente_richiesta, temperatura, note, immatricolazione, scadenza_revisione, scadenza_atp, scadenza_assicurazione, scadenza_tachigrafo, tessera_carburante, pin_tessera (PRESERVE_AS_STRING), storico_manutenzioni, proprietario, assicurazione, inUso, stato.

**DEFERRED_STORAGE_FIELDS**:
- fotoUrls, documentiUrls, copertinaUrl.
- Registered in migration registry but explicitly NOT copied to target documents.

**DEFERRED_CONFIGURATION_DOCUMENTS**:
- `_patenti`, `_tipologie`.

## 4. AUTO_IDS AND IDEMPOTENCY
- 24 `vehicle_id`s will be pre-generated via `company_ref.collection("mezzi").document()`.
- **M2_IDEMPOTENCY_MODEL**: `CORE_V1::VEHICLE::{legacy_document_id}`
- **M2_REGISTRY_PATH**: `system_migrations/core_v1_m2_vehicles`

## 5. PRE-WRITE STATE DISCOVERY
The script must classify the environment before writing:
- **CLEAN_START**: No M2 registry exists, 0 target vehicles exist. (Safe to proceed)
- **ALREADY_APPLIED**: Registry COMPLETE + 24 valid vehicles + hash parity.
- **PARTIAL_STATE**: Registry or targets incomplete.
- **CONFLICT**: Inconsistent documents exist.

## 6. WRITE PLAN & ATOMICITY
- **ATOMIC_WRITE_RECOMMENDED**: TRUE
- **ATOMIC_WRITE_MODEL**: SINGLE_ATOMIC_BATCH
- **BUSINESS_DOCUMENT_COUNT**: 24
- **TECHNICAL_DOCUMENT_COUNT**: 1 (registry)
- **TOTAL_ATOMIC_DOCUMENT_COUNT**: 25
- **CREATE_ONLY_GUARD_REQUIRED**: TRUE. Uses `batch.create()` for registry to prevent concurrent execution overwrites.

## 7. FINGERPRINT & POST-WRITE VALIDATION
- **POST_WRITE_HASH_PARITY_REQUIRED**: TRUE
- **POST_WRITE_FIELD_PARITY_REQUIRED**: TRUE
Post-write validations must confirm:
- Target count == 24
- Duplicate target == 0, Missing targa == 0
- Fingerprints match 24/24
- Registry status == COMPLETE
- Configuration docs not created
- Storage fields not written.

## 8. LEGACY & STORAGE GUARDS
- **DEFERRED_STORAGE_FIELD_WRITE_COUNT_EXPECTED**: 0
- **LEGACY_WRITE_COUNT_EXPECTED**: 0 (No touches to `mezzi`, `presenze`, `costi_carburante`, etc.)

## 9. ROLLBACK DESIGN
- Rollback only targets the 24 newly created vehicles and the registry.
- Rollback blocked if fingerprints don't match (meaning docs were manually modified).
- **AUTOMATIC_ROLLBACK**: FALSE.

## 10. GO / NO-GO GATES
- GATE_PROJECT
- GATE_COMPANY
- GATE_M0_M1_COMPLETE
- GATE_M2_DRY_RUN_CERTIFIED
- GATE_REAL_VEHICLE_COUNT_24
- GATE_REVIEW_ZERO
- GATE_ERROR_ZERO
- GATE_PRE_STATE_CLEAN
- GATE_TARGA_UNIQUE
- GATE_FIELD_COVERAGE_ZERO_UNKNOWN
- GATE_STORAGE_WRITE_ZERO
- GATE_LEGACY_WRITE_ZERO
- GATE_ATOMIC_PLAN_VALID
- GATE_ROLLBACK_MANIFEST_READY

## 11. MAPPING SOURCE OF TRUTH
`system_migrations/core_v1_m2_vehicles` becomes the technical source of truth for resolving `legacy_document_id` -> `vehicle_id`.

## 12. STATUS
- DESIGN ONLY.
- WRITE NOT IMPLEMENTED.
- WRITE NOT AUTHORIZED.
