# LOGIDESK CORE V1 MIGRATION PLAN

## PRINCIPIO BASE DELLA MIGRAZIONE
**CORE_V1_MIGRATION_POLICY**: COPY_VERIFY_CUTOVER
**LEGACY_DELETE_ALLOWED**: FALSE

Nessuna collection legacy verra cancellata o modificata sul posto (in-place) durante la fase iniziale. I dati verranno **COPIATI** nei nuovi path.

## REGISTRO DI MIGRAZIONE
Necessario un meccanismo (collection o JSON offline) per tenere traccia del mapping tra:
- `legacy_path` / `legacy_id`
- `target_path` / `target_id`
- `checksum` e `status` (DRY_RUN, COPIED, VERIFIED)

## ORDINE DELLE FASI (PHASES)
- **M0 — Company Shell**: Creazione `aziende/{azienda_id}` vuota (Auto-ID). Nessuna dipendenza.
- **M1 — Tenants Shell**: Creazione `aziende/{azienda_id}/tenants/{tenant_id}` per DNR, CATTEL, GRAN CHEF, BAUER. DAC in review.
- **M2 — Mezzi**: Da `root/mezzi` a `aziende/{a}/mezzi/{id}`. `targa` diventa attributo. (COPY_TRANSFORM)
- **M3 — Dipendenti/Utenti**: Split `root/dipendenti` in `utenti/{uid}` (auth base) e `dipendenti/{legacy_document_id}` (HR base). (COPY_SPLIT) PRESERVE_LEGACY_DOC_ID used for M6/M7 continuity.
- **M4 — Magazzini**: Classificazione ownership (Azienda vs Tenant). Da `root/magazzini_sedi` e `clienti/DNR/magazzini_sedi` ai nuovi path.
- **M5 — Punti Consegna**: Da `clienti/{t}/raccolta clienti` a `aziende/{a}/tenants/{t}/punti_consegna`. ID Auto. Mapping `codice_esterno`.
- **M6 — Presenze**: Da `root/presenze` a `aziende/{a}/presenze/{id}`. Rischio alto, necessita validazione rigorosa per evitare danni fatturazione.
- **M7 — Costi Personale**: Da `clienti/DNR/costi_personale` a `aziende/{a}/costi_personale`.
- **M8 — Costi Flotta**: Da `root/costi_carburante` a `aziende/{a}/costi_flotta`.
- **M9 — Fatturazione Tenant**: Merge e review di `clienti_fatturazione` e collection navette/magazzini_sedi in config Tenant.
- **M10 — Ruoli / Capabilities**: Trasformazione di `permessi_dashboard` in ruoli astratti.
- **M11 — Code Cutover**: Switch flag nel backend/frontend per usare i nuovi path.
- **M12 — Legacy Freeze**: Blocco scritture ai path originali.

## VALIDAZIONI OBBLIGATORIE E REQUISITI SCRIPT
- **DRY_RUN**: Ogni script deve supportare `--dry-run` senza scrivere.
- **IDEMPOTENZA**: Esecuzioni multiple non devono duplicare i target.
- **BATCH/RESUMABLE**: Batch limit per evitare timeout Firestore.
- **VALIDATION MANIFEST**: Produzione report finale count e sample checksum.

## M5: SPLIT PUNTI DI CONSEGNA DNR
**LEGACY_DNR_CODE_SPLIT_RULE**: I record con doppio codice (Frutta e Latte) vengono splittati in due target distinti (`punto_id` separati). I dati fisici vengono duplicati (COPY_TO_BOTH) o smistati (es. orari_frutta al target FRUTTA).
**GENERIC_SUBCODE_MODEL**: Introdotto attributo opzionale `sottocodice` (es. 'FRUTTA', 'LATTE') per marcare la tipologia logistica nel tenant DNR, configurabile per altri tenant.
**TENANT_SCOPED_SEQUENCE_CODE**: Ogni nuovo punto riceve un codice sequenziale logico (es. `DP000001`) isolato per tenant, gestito tramite counter atomico.
**DNR_TRANSFORMATION_AWARE_COUNT_VALIDATION**: La validazione M5 non si aspetta count 1:1, ma `TARGET_COUNT = FRUTTA_ONLY + LATTE_ONLY + 2 * FRUTTA_AND_LATTE`.

## M5: APPROVAZIONE GEO E FINESTRE TEMPORALI
**DELIVERY_TIME_WINDOWS_MODEL**: ARRAY_0_N. Eliminata dipendenza strutturale da mattina/pomeriggio. Array di `{da, a}`.
**GEO_APPROVAL_MODEL**: OPERATOR_VERIFIED. Un punto geolocalizzato non e' approvato finche `stato_verifica` non e' 'OK'.
**DNR_LEGACY_GEO_MIGRATION_POLICY**: CONFIRMED_DATASET. I 453 record DNR consolidati avranno `stato_verifica='OK'` e `fonte='LEGACY_CONFIRMED_DATASET'`, eccetto gli 8 con esplicito `stato='ok'` (fonte `LEGACY_EXPLICIT`).
**DNR_M5_TARGET_COUNT**: 609. Derivante da 453 legacy (236 FRUTTA_ONLY + 61 LATTE_ONLY + 156 FRUTTA_AND_LATTE * 2).
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
- **M5_DNR_DRY_RUN_CERTIFIED**: TRUE
- **M5_DNR_TARGET_COLLECTION**: punti_consegna
- **MULTI_COMPANY_MODEL**: TRUE. L'azienda funge da data isolation boundary.
- **PRODUCT**: LogiDesk
- **DEMO_COMPANY**: LogiDesk Demo
- **DEPLOYMENT_METADATA_NOT_IN_BUSINESS_DOMAIN**: TRUE. (e.g. `tipo_ambiente` is kept in migration registry only, not in canonical payloads).

## WRITE STATUS
- **M0_M1_SHADOW_WRITE**: EXECUTED and CERTIFIED (`NzXaCgyXxZWWehw1tSlo`).
- **M2_VEHICLES_SHADOW_WRITE**: EXECUTED and CERTIFIED (`NzXaCgyXxZWWehw1tSlo`).
