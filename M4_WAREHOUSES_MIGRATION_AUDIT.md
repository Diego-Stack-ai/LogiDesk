# M4 WAREHOUSES MIGRATION AUDIT

## 1. M4 SCOPE
- **M4_ID**: M4
- **M4_NAME**: Magazzini
- **Source**: `root/magazzini_sedi`, `clienti/{tenant}/magazzini_sedi`
- **Target**: `aziende/{azienda_id}/magazzini/{id}`, `aziende/{azienda_id}/tenants/{tenant_id}/magazzini/{id}`

## 2. DISCOVERY LIVE FIRESTORE
*(PENDING LIVE AUDIT - ADC Credentials missing in execution context)*
- **root/magazzini_sedi exists**: TBD
- **root/magazzini_sedi count**: TBD
- **Tenant warehouses**: TBD

## 3. TENANT RECONCILIATION
- M0/M1 canonical tenants: DNR, CATTEL, GRAN CHEF, BAUER
- **Ownership Classification**: TBD (requires live data evaluation)

## 4. FIELD AUDIT
*(PENDING LIVE AUDIT)*
- **Fields Discovered**: TBD

## 5. CANONICAL MODEL CANDIDATE
*(PENDING LIVE AUDIT)*
- TBD

## 6. ID STRATEGY AUDIT
*(PENDING LIVE AUDIT)*
- Legacy IDs: TBD
- Recommended Strategy: PRESERVE_ID / AUTO_ID / MIXED (Pending data review)

## 7. CROSS REFERENCES
*(Based on codebase search)*
- `lista_magazzini_sedi` is heavily referenced in frontend (`pianificazione.html`, `presenze.html`, `script.js`).
- `fatturazione_magazzini_sedi` is used in Sync scripts.

## 8. DUPLICATES & INVALID RECORDS
*(PENDING LIVE AUDIT)*
- Duplicates: TBD
- Invalid: TBD

## 9. M4 DEPENDENCIES
- **M0_M1_COMPLETE**: TRUE
- **M2, M3**: No direct business dependency, M3 for identity/audit only.
- **M4_REAL_DEPENDENCIES**: M0, M1

## 10. RUNTIME IMPACT
- **M4_RUNTIME_IMPACT**: NONE_SHADOW (Must remain shadow, frontend currently reads from legacy global/tenant appData).

## 11. M5 RELATION
- **M5_DEPENDS_ON_M4**: TBD (Pending confirmation of Punti Consegna referencing magazzini).
