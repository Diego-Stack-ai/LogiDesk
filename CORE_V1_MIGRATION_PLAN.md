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
- **M3 — Dipendenti/Utenti**: Split `root/dipendenti` in `utenti/{uid}` (auth base) e `dipendenti/{id}` (HR base). (COPY_SPLIT)
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
