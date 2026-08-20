# M2 VEHICLES MIGRATION DESIGN SPEC
# LEGACY root/mezzi -> aziende/{company_id}/mezzi/{mezzo_id}

## 1. SCOPE AND PRINCIPLES
This document outlines the design for the M2 migration of vehicles from the legacy schema to the canonical Core V1 multi-azienda schema.

**PRINCIPLE:** COPY / TRANSFORM / VERIFY
- **M2_SOURCE**: `root/mezzi` (Legacy `mezzi/{legacy_mezzo_id}`)
- **M2_TARGET**: `aziende/NzXaCgyXxZWWehw1tSlo/mezzi/{mezzo_id}`
- Legacy data remains untouched.
- **M2_RUNTIME_IMPACT**: NONE (Runtime continues using `root/mezzi`).
- **VEHICLE_OWNER**: AZIENDA (Not tenant).

## 2. PROJECT HARD GATE & DEPENDENCIES
- **PROJECT**: `log-solutions-cantiere` (No fallbacks).
- **M2_REQUIRES_M0_M1_COMPLETE**: TRUE (Depends on the real company ID from M0/M1 execution: `NzXaCgyXxZWWehw1tSlo`).
- `system_migrations/core_v1_m0_m1` status must be `COMPLETE`.

## 3. DATASET AUDIT (VIRTUAL)
- **LEGACY_VEHICLE_REFERENCE_MODEL**: Mixed, but mostly `targa` in operational tables like `presenze`.
- **LEGACY_VEHICLE_ID_USED_BY_RUNTIME**: Partially, likely for simple references.
- **LEGACY_TARGA_USED_BY_RUNTIME**: YES (`presenze` uses `targa`).
- **LEGACY_VEHICLE_FIELDS_DISCOVERED**: `targa`, `attivo`, `tipo`, `marca`, `modello`, `portata`, `patente_richiesta`, `temperatura`, `note`.
- **DUPLICATE_AUDIT_REQUIRED**: TRUE. Need to measure missing/duplicate `targa` before writing.

## 4. CANONICAL VEHICLE MODEL & TARGA
**VEHICLE_ID_STRATEGY**: AUTO_ID

**CANONICAL_VEHICLE_MODEL_CANDIDATE**:
```json
{
  "targa": "AB123CD",
  "attivo": true,
  "schema_version": 1,
  "tipo": "...",
  "marca": "...",
  "modello": "...",
  "portata": 3500,
  "patente_richiesta": "B",
  "temperatura": "REFRIGERATO",
  "note": "..."
}
```
**TARGA_NORMALIZATION_MODEL**: Uppercase, stripped string. `legacy_targa_raw` stored in registry if different.

## 5. DEPENDENCIES & CROSS-REFERENCES
- **PRESENCE_VEHICLE_REFERENCE_MODEL**: Uses `targa`. M2 does NOT modify `presenze`.
- **FLEET_COST_VEHICLE_REFERENCE_MODEL**: Uses `targa` or `mezzo_id`. M2 does NOT migrate costs, just prepares mapping.

## 6. M2 MAPPING REGISTRY
- **M2_MAPPING_REGISTRY_TARGET**: `system_migrations/core_v1_m2_vehicles`
- Contains:
  - `legacy_document_id`
  - `legacy_targa`
  - `normalized_targa`
  - `target_vehicle_id`
  - `target_path`
  - `fingerprint`
  - `status`

## 7. IDEMPOTENCY
- **M2_IDEMPOTENCY_MODEL**: `CORE_V1::VEHICLE::{legacy_document_id}`

## 8. DRY-RUN SCRIPT DESIGN
- **M2_DRY_RUN_SCRIPT_PLANNED**: `scripts/migrations/core_v1/m2_vehicles_dry_run.py`
- Operates in READ ONLY on Firestore.
- Target path uses simulated ID: `SIM::VEHICLE::{legacy_document_id}`
- Output Files:
  - `M2_VEHICLES_DRYRUN_SUMMARY.json`
  - `M2_VEHICLES_TARGET_PREVIEW.json`
  - `M2_VEHICLES_MAPPING_REGISTRY_PREVIEW.json`
  - `M2_VEHICLES_REVIEW_REQUIRED.json`
  - `M2_VEHICLES_VALIDATION_MANIFEST.json`

## 9. REVIEW REQUIRED ITEMS
- `MISSING_TARGA`
- `DUPLICATE_NORMALIZED_TARGA`
- `MISSING_REQUIRED_FIELDS`
- `DISMISSED_VEHICLES`

## 10. EXECUTION STATUS
- **SAFE_TO_IMPLEMENT_M2_DRY_RUN**: TRUE
- **SAFE_TO_EXECUTE_M2_WRITE**: FALSE
- **SAFE_TO_EXECUTE_M5_WRITE**: FALSE
