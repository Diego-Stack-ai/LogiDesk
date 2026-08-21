# LOGIDESK CORE V1 MIGRATION PLAN

## PRINCIPIO BASE DELLA MIGRAZIONE
**CORE_V1_MIGRATION_POLICY**: COPY_VERIFY_CUTOVER
**LEGACY_DELETE_ALLOWED**: FALSE

Nessuna collection legacy verra cancellata o modificata sul posto (in-place) durante la fase iniziale. I dati verranno **COPIATI** nei nuovi path.

## REGISTRO DI MIGRAZIONE
Necessario un meccanismo (collection o JSON offline) per tenere traccia del mapping tra:
- `legacy_path` / `legacy_id`
- `target_path` / `target_id`
- `checksum` e `status` (DRY_RUN, COPIED, VERIFIED, SHADOW_WRITE_DESIGNED)

## ORDINE DELLE FASI E STATO
- **M0**: Core Dataset (Azienda, Impostazioni, Clienti) - **[COMPLETE]**
- **M1**: Legacy Settings (Impostazioni App) - **[COMPLETE]**
- **M2**: Legacy Customers (Clienti) - **[COMPLETE]**
- **M3**: Identity (Dipendenti/Utenti) - **[COMPLETE]**
  - **M3_TEST_IDENTITY_CLEANUP**: **[COMPLETE]**
- **M4**: Warehouses (Magazzini) - **[SKIPPED_NOT_REQUIRED]**
  - No standalone canonical Warehouse entity exists in the current live model.
  - Legacy/runtime values are configuration records used by UI/billing flows.
- **M5**: Delivery Points (Punti di Consegna) - **[NEXT RECOMMENDED MIGRATION]**
- **M6**: Vehicles (Mezzi di Trasporto) - **[PENDING]**
- **M7**: Travel Records (Viaggi/DDT) - **[PENDING]**
- **M8**: Invoices (Fatturazione) - **[PENDING]**
- **M9**: Fatturazione Tenant - **[PENDING]**
- **M10**: Ruoli / Capabilities - **[PENDING]**
- **M11**: Code Cutover - **[PENDING]**
- **M12**: Legacy Freeze - **[PENDING]**

## VALIDAZIONI OBBLIGATORIE E REQUISITI SCRIPT
- **DRY_RUN**: Ogni script deve supportare `--dry-run` senza scrivere.
- **IDEMPOTENZA**: Esecuzioni multiple non devono duplicare i target.
- **BATCH/RESUMABLE**: Batch limit per evitare timeout Firestore.
- **VALIDATION MANIFEST**: Produzione report finale count e sample checksum.

## M5: SPLIT PUNTI DI CONSEGNA DNR
**LEGACY_DNR_CODE_SPLIT_RULE**: I record con doppio codice (Frutta e Latte) vengono splittati in due target distinti (`punto_id` separati). I dati fisici vengono duplicati (COPY_TO_BOTH) ma con target indipendenti e un `association_group_id` comune.
**GENERIC_SUBCODE_MODEL**: Utilizzo di `sottocodice` ('FRUTTA', 'LATTE') per marcare il source channel operativo.
**TENANT_SCOPED_SEQUENCE_CODE**: Ogni nuovo punto riceve un codice sequenziale logico (es. `DP000001` - `DP000609`) isolato per tenant.
**DNR_TRANSFORMATION_AWARE_COUNT_VALIDATION**: La validazione M5 non si aspetta count 1:1, ma `TARGET_COUNT = 609`.

## M5: APPROVAZIONE GEO E FINESTRE TEMPORALI
**DELIVERY_TIME_WINDOWS_MODEL**: ARRAY_0_N. Eliminata dipendenza strutturale da mattina/pomeriggio. Array di `{da, a}`.
**GEO_APPROVAL_MODEL**: OPERATOR_VERIFIED. Un punto geolocalizzato non e' approvato finche `stato_verifica` non e' 'OK'.
**DNR_LEGACY_GEO_MIGRATION_POLICY**: CONFIRMED_DATASET. I 453 record DNR consolidati avranno `stato_verifica='OK'` e `fonte='LEGACY_CONFIRMED_DATASET'`, eccetto gli 8 con esplicito `stato='ok'` (fonte `LEGACY_EXPLICIT`).
**DNR_M5_TARGET_COUNT**: 609. Derivante da 453 legacy (236 FRUTTA_ONLY + 61 LATTE_ONLY + 156 FRUTTA_AND_LATTE * 2). (453_TO_453_MODEL is SUPERSEDED, 609_INVALIDATION was REVERTED).
**LEGACY_NOISE**: Campi come `tipo`, `tipologia_grado` ignorati. Valori `False`, `NaN`, vuoti negli orari normalizzati a null/scartati.

## M5 DRY-RUN DESIGN
**DRY_RUN_OUTPUT_FILES**: Vengono generati summary, preview dei target, preview del registry e record da revisionare in JSON locale.
**DNR_ADAPTER_DEFINED**: Utilizzato un pattern Adapter (`LegacyDNRAdapter` -> `CanonicalDeliveryPoint`) per generalizzare il transformer e riutilizzarlo per Cattel, Gran Chef, ecc.
**SIMULATED_ID**: `SIM::{legacy_doc_id}::SOTTOCODICE`.
**MIGRATION_FINGERPRINT_MODEL**: SHA256 dei campi canonical target generati per validazione successiva.

## TERMINOLOGIA CANONICA CORE V1
- **TENANT**: Committente commerciale.
- **PUNTO_CONSEGNA**: Destinazione fisica servita.
- **TERM_CLIENTE_FOR_DELIVERY_POINT**: DEPRECATED nel nuovo modello.
- **LEGACY SOURCE M5**: `clienti/{tenant}/raccolta clienti` (NESSUN RENAME).
- **FUTURE TARGET M5**: `aziende/{azienda_id}/tenants/{tenant_id}/punti_consegna`.
- **M5_DNR_TARGET_COLLECTION**: punti_consegna
- **M5_CURRENT_MODEL**: 453_TO_609_SPLIT
- **M5_453_MODEL**: SUPERSEDED
- **M5_609_LIVE_DRY_RUN_CERTIFIED**: TRUE
- **MULTI_COMPANY_MODEL**: TRUE. L'azienda funge da data isolation boundary.
- **PRODUCT**: LogiDesk
- **DEMO_COMPANY**: LogiDesk Demo
- **DEPLOYMENT_METADATA_NOT_IN_BUSINESS_DOMAIN**: TRUE. (e.g. `tipo_ambiente` is kept in migration registry only, not in canonical payloads).

## WRITE STATUS
- **M0_M1_SHADOW_WRITE**: EXECUTED and CERTIFIED (`NzXaCgyXxZWWehw1tSlo`).
- **M2_VEHICLES_SHADOW_WRITE**: EXECUTED and CERTIFIED (`NzXaCgyXxZWWehw1tSlo`).

## M6 SETTINGS CORE & M6B RESOLUTION
**M6A_CORE_SETTINGS**: Limitato a 47 documenti deterministici. permessi_dashboard, system_status, mail_settings, 3 listini tenant (illing) e 41 import_mappings (codici articoli per DNR). STATUS: SCOPE_CERTIFIED, DESIGN_READY.
**M6B_CLIENTI_FATTURAZIONE**: 14 record legacy in clienti_fatturazione posticipati a causa di ownership non deterministica e duplicati. STATUS: DEFERRED_REVIEW_REQUIRED.
**M7_DRIVER_HR**: L'audit ha confermato che M3 Identity non migra i campi operativi autisti (ruolo, turno, patente, ecc.) a causa del Foundation Schema. Necessaria una migrazione M7 dedicata. STATUS: REVIEW_PENDING.
## M6A WRITE DESIGN
**M6A_LIVE_DRY_RUN_CERTIFIED**: TRUE
**M6A_WRITE_DESIGNED**: TRUE
**M6A_WRITE_EXECUTED**: FALSE
**M6B_STATUS**: DEFERRED_REVIEW_REQUIRED
## M6A SHADOW WRITE
**M6A_WRITE_SCRIPT_IMPLEMENTED**: TRUE
**M6A_LIVE_PREFLIGHT_CERTIFIED**: FALSE
**M6A_WRITE_EXECUTED**: FALSE
