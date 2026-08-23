# M6A SETTINGS SHADOW WRITE SPECIFICATION

## 1. M6A SCOPE E TARGET
**Source**: 47 documenti (3 company, 3 tenant listino, 41 import_mappings)
**Business Target**: 47 documenti unici
**Registry**: 1 documento
**Total Atomic Documents**: 48 documenti

Essendo 48 < 500 (limite batch Firestore), la scrittura verra eseguita in un **SINGOLO BATCH ATOMICO**.

## 2. MODALITA DI SCRITTURA (SHADOW)
*   La scrittura NON andra a modificare le collection legacy config/, clienti/.
*   Tutti i documenti target (inclusi quelli di registry) verranno scritti in modalita **CREATE_ONLY**. Nessun fallback a set, update o merge.
*   La collection legacy **clienti_fatturazione** e rigorosamente **ESCLUSA** (M6B).
*   Se un documento (business o registry) esiste gia, l'operazione in batch fallira garantendo protezione contro concorrenza e conflitti.
*   Il batch atomico da 48 documenti garantisce una transizione di stato deterministica (Tutto o Niente).

## 3. TARGET PATHS E IDEMPOTENCY
### Company Settings (3 documenti)
*   **Path**: aziende/NzXaCgyXxZWWehw1tSlo/settings/{domain}
*   **Idempotency**: CORE_V1::M6A::COMPANY::{domain}

### Tenant Billing Settings (3 documenti)
*   **Path**: aziende/NzXaCgyXxZWWehw1tSlo/tenants/{tenant_id}/settings/billing
*   **Idempotency**: CORE_V1::M6A::TENANT::{tenant_id}::billing

### Import Mappings (41 documenti)
*   **Path**: aziende/NzXaCgyXxZWWehw1tSlo/tenants/{tenant_id}/import_mappings/{source_id}
*   **Idempotency**: CORE_V1::M6A::IMPORT::{tenant_id}::{source_id}

## 4. REGISTRY
*   **Path**: system_migrations/core_v1_m6a_settings
*   **Contenuto**: Metadata dell'esecuzione del batch, timestamps, numero di record.
*   **Status Model**:
    *   PLANNED (In modalita preflight)
    *   COMPLETE (Al momento della scrittura atomica in produzione)

## 5. SECRET GUARD E SICUREZZA
*   Il campo email_password proveniente da config/email_settings DEVE essere droppato.
*   **GATE_EMAIL_PASSWORD_WRITE_ZERO**: Deve essere applicato per assicurare che il secret non entri mai nei payload target, nel registry, nel rollback manifest o nei log.

## 6. VALIDAZIONI E GO / NO-GO GATES
L'esecuzione del write script (preflight ed execute) valutera i seguenti gates prima di procedere:
1.  **GATE_PROJECT**: Il progetto deve essere log-solutions-cantiere
2.  **GATE_COMPANY**: Il company ID deve essere NzXaCgyXxZWWehw1tSlo
3.  **GATE_M0_M1_COMPLETE**, **GATE_M3_COMPLETE**, **GATE_M5_COMPLETE**: Prerequisiti architetturali
4.  **GATE_SOURCE_COUNT_47**: Il totale dei source deve essere esattamente 47
5.  **GATE_COMPANY_TARGET_3**, **GATE_TENANT_SETTINGS_TARGET_3**, **GATE_IMPORT_MAPPING_TARGET_41**: I conteggi dei target devono corrispondere
6.  **GATE_TOTAL_TARGET_47**: Totale business target generati deve essere 47
7.  **GATE_EMAIL_PASSWORD_WRITE_ZERO**: Nessun field secret presente in output
8.  **GATE_CLIENTI_FATTURAZIONE_ZERO**: Zero source o target da clienti_fatturazione
9.  **GATE_UNKNOWN_FIELD_ZERO**, **GATE_UNRESOLVED_OWNER_ZERO**, **GATE_TARGET_COLLISION_ZERO**: Sicurezza dati e ID
10. **GATE_IDEMPOTENCY_UNIQUE**, **GATE_FINGERPRINT_DETERMINISTIC**: Conformita crittografica e batch
11. **GATE_PRE_STATE_CLEAN**: Lo stato Firestore target deve essere CLEAN_START
12. **GATE_ATOMIC_PLAN_48**, **GATE_ROLLBACK_MANIFEST_48**: Verifica corretta pianificazione del batch atomico.

## 7. STATE DISCOVERY
Lo script dovra supportare CLEAN_START, ALREADY_APPLIED, PARTIAL_STATE, CONFLICT.
*   Solo CLEAN_START puo eseguire la scrittura.
*   Se ALREADY_APPLIED, esegue in modalita sola lettura (--verify-existing).
*   In caso di PARTIAL_STATE o CONFLICT, l'operazione abortisce.

## 8. ROLLBACK E RIPRISTINO
*   **Manuale soltanto**. L'auto-rollback non e implementato per ridurre la superficie d'errore del codice runtime.
*   Il manifest M6A_ROLLBACK_MANIFEST.json conterra i 48 path e i rispettivi fingerprints.
*   I legacy source non verranno mai toccati.

## 9. VERIFY EXISTING (--verify-existing)
La verifica a posteriori accertera:
*   47 business docs + 1 registry COMPLETE.
*   Parita 47/47 sui campi.
*   Parita 47/47 sui fingerprint (utilizzando lo stesso SHA256 esatto dell'M6A dry-run).
*   Assenza del campo secret in Firestore.
