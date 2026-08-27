# LOGIDESK DATA ARCHITECTURE PLAN

**DOCUMENT ROLE**: Domain authority (Authoritative within Data Architecture scope)
**Authority Scope**: Target Data Architecture, Master/Operational Data, Firestore/Storage target, Migration data policy
**Upstream**: PROJECT_MANIFEST.md, DOMAIN_MODEL.md
**Downstream**: LOGIDESK_INGESTION_AI_PLAN.md, LOGIDESK_JOURNEY_ARCHITECTURE.md, LOGIDESK_COMPANY_TENANT_MODEL.md
**Related Agents**: IngestionAgent, PlanningAgent, ProjectOrchestratorAgent
**Status**: ACTIVE
**Version**: 1.0
**Last Reviewed**: 24/08/2026

Questo documento definisce la futura fondazione dati di LogiDesk. Stabilisce i principi, la terminologia, la struttura dati target, le politiche di migrazione, il ciclo di vita dei viaggi e il ruolo dell'AI, fungendo da bussola architetturale per le fasi implementative successive.

> **NOTA ALIGNMENT**: `DOCUMENTATION_ALIGNMENT_REQUIRED`
> Alcuni documenti precedenti (come `FIRESTORE_TARGET_SCHEMA.md` o porzioni di `ARCHITECTURE.md`) potrebbero presentare schemi target o nomenclature non perfettamente allineate con questa specifica, specialmente riguardo all'isolamento assoluto del nodo `aziende/{azienda_id}` rispetto alla root. Questo piano ha la precedenza gerarchica.

## 1. PRINCIPI ARCHITETTURALI

1. **Company First**
   L'azienda utilizzatrice di LogiDesk è il livello superiore e radice di ogni architettura dati. Tutto appartiene a un'azienda.
2. **Tenant Symmetry**
   I committenti (DNR, CATTEL, GRAN CHEF, DAC e futuri tenant) usano esattamente lo stesso schema logico e fisico. Nessun tenant gode di percorsi preferenziali o hardcoding.
3. **Configuration over Hardcoding**
   Le differenze di business logic tra i tenant devono vivere esclusivamente nei profili di configurazione (database), e non in strutture dati differenziate o regole cablate nel codice.
4. **Master Data vs Operational Data**
   Le anagrafiche permanenti (punti di consegna, magazzini, vettori) sono strettamente separate dai dati operativi giornalieri (fermate, colli, pesi).
5. **Immutable History**
   Un viaggio definitivo deve rappresentare ciò che è avvenuto operativamente. Non può essere alterato retroattivamente da future modifiche anagrafiche o tariffarie.
6. **Billing Snapshot**
   La regola economica applicata al momento della prestazione deve essere "congelata" all'interno del viaggio definitivo.
7. **AI Assisted, Deterministic Core**
   L'AI interpreta i formati e propone mapping. Tuttavia, le decisioni strutturali, le scritture anagrafiche permanenti e i calcoli economici devono restare deterministici e verificabili, sottomessi ad approvazione umana (operator-in-the-loop).
8. **Migrate Primary Data, Rebuild Derived Data**
   Si migrano solo master data e asset strategici (es. anagrafiche pulite e dataset cache Google). Non si migrano i vecchi viaggi storici o i vecchi report derivati per popolare il nuovo schema.

## 2. TERMINOLOGIA CANONICA

Per evitare ogni ambiguità all'interno del codice e del business, si adotta la seguente terminologia tassativa:
- **AZIENDA**: L'azienda utilizzatrice di LogiDesk (es. AppLogSolutions) che acquista o usa il software.
- **TENANT / COMMITTENTE**: L'entità che affida i trasporti all'Azienda (es. DNR, Cattel, Gran Chef, DAC). È un cliente dell'Azienda.
- **CLIENTE**: Il cliente finale (es. il ristorante, l'hotel, il supermercato) che riceve la merce. Non è il tenant.
- **PUNTO_DI_CONSEGNA**: Il record anagrafico canonico e stabile che definisce una singola destinazione fisica di recapito (Master Data).
- **DOCUMENTO_SORGENTE**: Il file originale o flusso dati in entrata (PDF, Excel, API) da cui si estraggono le spedizioni giornaliere.
- **FERMATA_GIORNALIERA**: L'istanza operativa di una consegna in un dato giorno, che referenzia un `PUNTO_DI_CONSEGNA` e contiene i dati volatili del documento (Operational Data).
- **VIAGGIO**: L'aggregazione temporanea o in lavorazione di una sequenza di fermate assegnata a un mezzo/autista.
- **VIAGGIO_DEFINITIVO**: Lo snapshot immutabile di un viaggio consolidato e completato.
- **CONFIGURAZIONE_TENANT**: Le regole di business (tariffe, orari, eccezioni) specifiche di un singolo committente.
- **CONFIGURAZIONE_AZIENDA**: Le regole applicative globali dell'Azienda utilizzatrice.
- **INGESTION_PROFILE**: La firma strutturale e le regole di mapping che permettono all'engine di riconoscere e parsare automaticamente un `DOCUMENTO_SORGENTE`.
- **BILLING_SNAPSHOT**: L'istantanea immutabile della configurazione di fatturazione nel momento in cui il viaggio viene consolidato.

## 3. MODELLO AZIENDA

Il dominio `AZIENDA` è il contenitore top-level:

```text
AZIENDA
├── dati_azienda
│   ├── ragione_sociale
│   ├── nome_commerciale
│   ├── piva
│   ├── codice_fiscale
│   ├── indirizzo
│   ├── cap
│   ├── citta
│   ├── provincia
│   ├── nazione
│   ├── email
│   ├── pec
│   ├── telefono
│   ├── sito
│   └── branding/logo
│
├── configurazioni_azienda
│   ├── impostazioni_generali
│   ├── moduli_abilitati
│   ├── preferenze_operative
│   └── future_configurazioni
│
├── magazzini
├── mezzi
├── dipendenti
├── autisti
├── utenti_software
└── tenants
```

## 4. MODELLO TENANT

Ogni Tenant è strutturalmente identico. Una nuova configurazione introdotta in LogiDesk deve esistere per tutti i tenant (eventualmente con flag di disabilitazione), senza schemi asimmetrici.

```text
TENANT
├── anagrafica
├── configurazioni
│   ├── ingestion
│   ├── logistica
│   ├── orari
│   ├── fatturazione
│   ├── report
│   ├── resi
│   ├── notifiche
│   └── future_configurazioni
├── punti_consegna
└── documenti_sorgente
```

## 5. MODELLO PUNTO DI CONSEGNA

Il punto di consegna, in quanto Master Data, non deve mai essere contaminato da dati temporanei della spedizione odierna.

**A. DATI STABILI**
- id canonico (`pointUUID`)
- tenant
- nome/ragione sociale
- indirizzo normalizzato
- CAP
- città
- provincia
- coordinate
- codici sorgente

**B. DATI PERSISTENTI AGGIORNABILI**
- telefono
- contatti
- note permanenti
- orari standard

**C. DATI TEMPORANEI/GIORNALIERI (NON INCLUSI NEL MASTER)**
NON devono risiedere qui: DDT, colli, peso, bancali, note di giornata, override orari, priorità del giorno, vincoli della singola consegna.

## 6. MODELLO FERMATA GIORNALIERA

La fermata giornaliera funge da Operational Data e referenzia il master data.

```text
FERMATA_GIORNALIERA
├── stop_id
├── data
├── tenant_id
├── punto_id (Reference al PUNTO_DI_CONSEGNA)
├── documento_sorgente
├── ddt
├── colli
├── peso
├── bancali
├── note_giornaliere
├── override_orari
├── priorita
├── vincoli_temporanei
└── source_lineage
```

## 7. INGESTION & AI AGENT

L'agente futuro (`INGESTION & TENANT ONBOARDING AGENT`) agirà come smart funnel per i flussi in ingresso.

**Responsabilità:**
1. TENANT RESOLUTION
2. FORMAT RECOGNITION
3. DATA NORMALIZATION
4. TENANT ONBOARDING
5. INGESTION PROFILE MANAGEMENT
6. ANOMALY DETECTION

**Flusso:**
1. **FILE IMPORTATO**
2. Riconoscimento tenant
3. Riconoscimento formato
   - **Se FORMATO CONOSCIUTO**: Carica `ingestion_profile` → Normalizza → Valida.
   - **Se FORMATO NUOVO**: AI analizza il documento → Mostra i campi individuati all'operatore → Propone il mapping → **Fa domande per risolvere ambiguità** → Operatore conferma → Salva un nuovo `ingestion_profile` → Normalizza.

*IMPORTANTE*: L'AI agisce in modalità proposal. Non deve creare silenziosamente tenant o mapping anagrafici permanenti senza la conferma esplicita dell'operatore.

## 8. INGESTION PROFILE

Consente al sistema di disaccoppiare la logica di estrazione dall'estensione fisica del file. Un formato noto verrà riconosciuto a prescindere da variazioni marginali del nome file.

```text
INGESTION_PROFILE
├── profile_id
├── tenant_id
├── source_signature (Hash/Header fingerprint)
├── file_type
├── expected_fields
├── mappings
├── extraction_rules
├── field_policies
├── validation_rules
├── version
├── status
└── approved_by
```

## 9. POLICY CAMPI VARIABILI

La propagazione dei dati dai documenti in ingresso segue policy ferree per proteggere le anagrafiche:

- **TELEFONO**: Se il nuovo documento contiene un valore ritenuto valido → Aggiorna il Master. Se assente → Conserva il precedente.
- **ORARI STANDARD**: Se si rileva una nuova informazione stabile e dichiarata come permanente → Aggiorna il Master.
- **OVERRIDE GIORNALIERO** (es: "domani consegnare 7-8 invece di 7-11"): → NON aggiornare il Master. Salvare il constraint direttamente nella `FERMATA_GIORNALIERA`.
- **COLLI / PESO / DDT / BANCALI**: → Esclusivamente dati di fermata/viaggio. Mai scritti sul master punto consegna.

## 10. VIAGGIO LIFECYCLE

Il flusso vitale di una spedizione in LogiDesk è lineare e tracciato end-to-end:
`NUOVO IMPORT` → `NORMALIZED DATA` → `FERMATE GIORNALIERE` → `PIANIFICAZIONE` → `MAPPA / DIVISIONE VIAGGI` → `MODIFICA OPERATORE / AI ASSIST` → `VIAGGI DEFINITIVI` → `LINK AUTISTI` → `ESECUZIONE` → `CONSUNTIVO` → `FATTURAZIONE`

## 11. VIAGGIO DEFINITIVO E BILLING MODEL

Un viaggio consolidato diventa uno snapshot storico inalterabile.

```text
VIAGGIO_DEFINITIVO
├── viaggio_id
├── tenant_id
├── data
├── magazzino
├── autista
├── mezzo
├── sequenza_fermate[]
├── totale_colli
├── totale_peso
├── totale_bancali
├── km_previsti
├── km_effettivi
├── tempi_previsti
├── tempi_effettivi
├── stato
├── eventi_operativi
└── billing_snapshot
```

**BILLING MODEL**
La fatturazione è un modulo dinamicamente configurabile per tenant. Può supportare scenari ibridi (es. `PER_VIAGGIO`, `PER_CONSEGNA`, `PER_DDT`, `PER_KG`, `PER_QUINTALE`, `PER_KM`, `PER_FASCIA_KM`, `MINIMO_VIAGGIO`, `EXTRA`, `MODELLO_MISTO`).
- `billing_configuration`: è la regola attiva nel profilo corrente del tenant.
- `billing_snapshot`: è la regola "congelata" (clonata) sul viaggio definitivo al momento della sua chiusura, a prova di futuri ritocchi tariffari. (Es. Se `PER_DDT`, ogni ddt conserva il suo prezzo storico e il viaggio aggrega il totale).

## 12. STRATEGIC DISTANCE DATASETS

I seguenti dataset rappresentano un forte valore aziendale in quanto accumulano onerosi calcoli geospaziali derivati da API a pagamento (Google Maps). Vengono classificati come `STRATEGIC_DERIVED_ASSET` e vanno scrupolosamente preservati:
- `distanze_reali_cache.json`
- `directions_cache.json`
- `distanze_traffico_cache.json`

*(Nota: Il loro percorso finale nella gerarchia Storage verrà sancito al momento del physical design design).*

## 13. MIGRATION POLICY

**Cosa MIGRARE:**
- Dati azienda
- Configurazioni azienda
- Tenant e configurazioni tenant
- Punti di consegna master
- Mezzi
- Dipendenti/Autisti
- Magazzini
- Dataset distanze Google (Strategic Assets)

**Cosa NON MIGRARE (Drop & Fresh Start):**
- Vecchi viaggi (storico in formato legacy)
- Vecchie fermate / pianificazioni
- Vecchi report
- Billing derivato storico
- Output temporanei
- Processing jobs storici

**USO LEGACY CONSENTITO:**
Il vecchio schema resta disponibile in modalità *Strict Read-Only* per procedure di fallback e lookup intelligente (es. recupero di coordinate perse, vecchi alias, contatti o info mancanti non estraibili direttamente dai nuovi flussi).

## 14. STATO MIGRAZIONE ATTUALE (BASELINE)

- **DNR**: 609 punti estratti (392 FRUTTA, 217 LATTE). **Stato**: COMPLETE.
- **CATTEL**: Punti legacy presenti nello schema `clienti/`, 0 nel nuovo schema. **Stato**: NOT_MIGRATED.
- **GRAN_CHEF**: Punti legacy presenti nello schema `clienti/`, 0 nel nuovo schema. **Stato**: NOT_MIGRATED.
- **DAC**: Punti legacy presenti nello schema `clienti/`, 0 nel nuovo schema. **Stato**: NOT_MIGRATED.
- **Mezzi**: Da verificare e allineare al nuovo schema Azienda.
- **Dipendenti / Autisti**: Da verificare e allineare al nuovo schema Azienda.
- **3 Dataset Google**: Trasferiti e al sicuro; si attende conferma path target definitivo.
- **Azienda, Tenant, Magazzini, Fatturazione**: Architetture da istanziare e completare.

## 15. FIRESTORE TARGET TREE (CONCEPTUAL)

Il dettaglio tecnico delle collection e sub-collection sarà validato fisicamente in Fase A3.

```text
aziende/{azienda_id}
├── profilo
├── configurazioni
├── magazzini
├── mezzi
├── dipendenti
├── utenti
└── tenants/{tenant_id}
    ├── anagrafica
    ├── configurazioni
    ├── punti_consegna
    ├── documenti_sorgente
    └── ...
```

## 16. STORAGE TARGET TREE (CONCEPTUAL)

L'alberatura rifletterà concettualmente il segregamento dei permessi:
- `company-scoped/`
- `tenant-scoped/`
- `strategic-assets/`
- `source-documents/`
- `branding/`
- `temporary-processing/`

*(Nessun path fisico definitivo approvato finora).*

## 17. READINESS MATRIX

| DOMINIO | PRESENTE | PARZIALE | MANCA | AZIONE |
|---|---|---|---|---|
| azienda | | | X | Inizializzare Master Data |
| configurazioni_azienda | | | X | Definire schema config |
| tenant | | | X | Creare radici tenants |
| configurazioni_tenant | | | X | Standardizzare schema config |
| fatturazione | | | X | Sviluppare modello fatturazione |
| punti_DNR | X | | | Promuovere schema M5 in A |
| punti_CATTEL | | | X | Migrazione da legacy/excel |
| punti_GRAN_CHEF | | | X | Migrazione da legacy/pdf |
| punti_DAC | | | X | Migrazione da legacy |
| mezzi | | X | | Allineamento nuovo schema |
| dipendenti | | X | | Allineamento nuovo schema |
| magazzini | | X | | Consolidamento tenant vs globale |
| 3_dataset_Google | X | | | Assegnazione path definitivo |

## 18. FUTURE PHASES

Il piano esecutivo che prosegue l'architettura LogiDesk sarà declinato in:
- **A3** — Target Firestore/Storage physical design
- **A4** — Baseline data readiness
- **A5** — Missing master data migration
- **A6** — New ingestion engine
- **A7** — Stops/Journey model
- **A8** — Planning & Maps
- **A9** — Driver execution
- **A10** — Billing
- **A11** — End-to-end validation



## A3 — PHYSICAL FIRESTORE & STORAGE DESIGN

### 1. FIRESTORE: INVENTARIO STATO REALE (AS-IS)
Sulla base dei tracciati di migrazione e dell'analisi runtime, lo stato logico-fisico attuale si articola come segue:

| PATH | ENTITY | SCOPE | STATUS | RECORD_COUNT (stima) | NOTES |
|---|---|---|---|---|---|
| `punti_consegna/` | Delivery Points | Tenant (DNR) | TARGET_ONLY | 609 | Migrazione M5 Completata |
| `clienti/{tenant}/raccolta clienti`| Punti Consegna | Tenant | TO_DEPRECATE | - | Legacy (CATTEL, GRAN CHEF, DAC) |
| `viaggi/` | Viaggi e fermate | Global/Mixed | TO_DEPRECATE | Molteplici | Storico legacy monolitico |
| `users/` | Utenti | Global | LEGACY_ACTIVE | - | Gestione accessi legacy |
| `autisti/` | Autisti | Global | LEGACY_ACTIVE | - | Da normalizzare sotto Azienda |
| `mezzi/` | Automezzi | Global | LEGACY_ACTIVE | - | Da normalizzare sotto Azienda |
| `aziende/` | Company profile | Global | TARGET_READY | - | Radice strutturale target |
| `clienti/{tenant}/processing_jobs` | Job temporanei | Tenant | TO_DEPRECATE | - | Gestito dai frontend legacy |

*(Nota: Altre collection collaterali come `presenze`, `permessi`, `fatturazione` e `resi` sono state identificate in stato ibrido o cablate nei viaggi).*

### 2. FIRESTORE TARGET PHYSICAL TREE
L'architettura definitiva assume il paradigma Company-First. Ogni entità appartiene rigidamente all'Azienda (Loge Solution) e, ove pertinente, viene partizionata per Tenant (Committente).

```text
aziende/{azienda_id}
│
├── profilo (Documento singolo o subcollection di metadati base)
├── configurazioni (Subcollection per isolamento moduli)
├── magazzini/{magazzino_id}
├── mezzi/{mezzo_id}
├── dipendenti/{dipendente_id}
├── utenti/{uid} (Utenti software company-scoped)
│
└── tenants/{tenant_id}
    │
    ├── anagrafica (Documento descrittivo del committente)
    ├── configurazioni/
    │   ├── ingestion (es. `tenants/123/configurazioni/ingestion`)
    │   ├── logistica
    │   ├── orari
    │   ├── fatturazione
    │   └── ...
    │
    ├── punti_consegna/{punto_id}
    ├── documenti_sorgente/{documento_id}
    ├── fermate_giornaliere/{stop_id}
    └── viaggi/{viaggio_id}
```
*Raccomandazione:* Gli `utenti` restano company-scoped per permettere al vettore di assegnare un driver a più tenant. `mezzi` e `magazzini` sono company-scoped (Loge Solution) in quanto asset logistici trasversali.

### 3. CONFIGURATION MODEL PHYSICAL DESIGN
Per permettere un'estendibilità orizzontale e un isolamento sicuro, la configurazione deve seguire il **MODEL B**: *Subcollection con documenti per modulo*.
- **MODEL B (Raccomandato):** `tenants/{tenant_id}/configurazioni/{modulo}` (es. `fatturazione`, `ingestion`).
- **Motivazione (Rationale):** Atomicità delle letture, limiti stringenti dei permessi (es. il billing accessibile solo ad Admin, l'ingestion accessibile agli Agenti AI), facile versioning senza sforare i limiti di 1MB per documento (che affliggerebbero un ipotetico MODEL A monolitico).

### 4. DELIVERY POINT PHYSICAL MODEL
Il `Punto di Consegna` rappresenta esclusivamente Master Data.
- **DELIVERY_POINT_INTERNAL_CODE_PATTERN**: Approvata la convenzione `DP + 6 cifre progressive`. (es. `DP000001`, `DP000002` ... `DP000609`).
  - Campo di riferimento Firestore: `codice_punto`.
  - Progressivo e *tenant-scoped*: ogni tenant possiede il proprio progressivo indipendente e riparte da `DP000001` (es. DNR: `DP000001`, CATTEL: `DP000001`, GRAN_CHEF: `DP000001`, DAC: `DP000001`).
  - NON è globalmente univoco da solo tra tenant. L'identità logica completa è: `azienda_id` + `tenant_id` + `codice_punto`.
  - *Baseline Esistente:* DNR ha già 609 record migrati (`DP000001` → `DP000609`). La struttura deve preservare questi codici senza rinominarli.
  - *Nuovi Tenant:* CATTEL, GRAN_CHEF, DAC e futuri partiranno dal proprio `DP000001`.
  - *Requisito Implementativo Futuro:* Ogni tenant deve possedere un meccanismo sicuro e atomico (es. transaction / counter document `next_delivery_point_sequence = N`) per determinare il prossimo codice disponibile ed evitare collisioni concorrenti. Modalità tecnica da definire.
- **Identity (Firestore Document ID):** Approvato
  - Il `codice_punto` viene utilizzato ESATTAMENTE come Firestore Document ID all'interno della subcollection tenant-scoped.
  - Esempio: `aziende/{azienda_id}/tenants/DNR/punti_consegna/DP000001`
  - Esempio: `aziende/{azienda_id}/tenants/CATTEL/punti_consegna/DP000001`
  - Sono documenti distinti perché appartengono a path tenant differenti.
  - UUID tecnico separato: `NOT_REQUIRED_CURRENTLY`.
- **Data Shape Target:** Indirizzo normalizzato, CAP, città, provincia, coordinate (GeoPoint), Contatti, Orari Standard.
- **Esclusioni Tassative:** Nessun dato temporaneo, nessun riferimento a colli, pesi, bancali, DDT od override di orari giornalieri.

### 5. STOP / DAILY DELIVERY PHYSICAL MODEL
La entità **Fermata Giornaliera** (`fermate_giornaliere/{stop_id}`) funge da Operational Data e deve vivere nello scope del tenant (sotto `tenants/{tenant_id}/fermate_giornaliere/{stop_id}`).
- **Data Shape Target:** `tenant_id`, `punto_id` (reference), `source_document_id` (lineage), dati merce (ddt, colli, peso, bancali), `note_giornaliere`, `override_orari`, `priority`, `planning_status`.
- **Pro/Contro Posizionamento:** Collocandola come entità indipendente sotto tenant, si facilita la ricerca e l'aggregazione pre-viaggio. Aggregarla dentro il viaggio renderebbe complessa la fase di routing.

### 6. JOURNEY PHYSICAL MODEL (STRUTTURA BASE)
I nuovi viaggi vivranno sotto: `aziende/{azienda_id}/tenants/{tenant_id}/viaggi/{viaggio_id}`.
- **Regola iniziale (`SINGLE_TENANT_JOURNEY`):** Fino a delibera architetturale contraria nel modulo Journey Engine, ogni viaggio appartiene a un singolo tenant.
- Se in futuro emergesse l'esigenza forte di "viaggi multi-tenant" reali (navette miste), l'entità verrà elevata a `aziende/{azienda_id}/viaggi/{viaggio_id}` referenziando fermate cross-tenant. Al momento la raccomandazione è Tenant-Scoped.

### 7. BILLING CONFIG PHYSICAL MODEL
Collocato in `tenants/{tenant_id}/configurazioni/fatturazione`:
- **Campi minimi:** `enabled` (boolean), `model` (enum: PER_VIAGGIO, PER_CONSEGNA, PER_DDT, PER_KG, ecc.), `currency` (string), `rules` (map/array di regole), `effective_from` (timestamp), `version` (int), `status` (string).

### 8. COMPANY PROFILE PHYSICAL MODEL
Collocato in `aziende/{azienda_id}/profilo` (documento flat):
- Ragione sociale, PIVA, indirizzo, contatti.
- **Branding Metadata:** `logo_storage_path` (string reference), `branding_version`. Nessun file base64 in Firestore.

### 9. STORAGE: INVENTARIO STATO REALE (AS-IS)
| PATH | PURPOSE | SCOPE | STATUS | MIGRATION_ACTION |
|---|---|---|---|---|
| `/REPORTS` | Export viaggi storici DNR | Legacy Global | TO_DEPRECATE | DO_NOT_MIGRATE |
| `/CATTEL/REPORTS`| Export viaggi storici Cattel | Tenant-Scoped | TO_DEPRECATE | DO_NOT_MIGRATE |
| `/split_ddt` | Documenti temporanei | Mixed | TO_DEPRECATE | DO_NOT_MIGRATE |
| `/caches/` | Cache Dataset Google Maps | Strategic Asset| TO_MOVE | COPY_VERIFY_CUTOVER |
| `/{tenant}/uploads`| File originali | Tenant | TO_DEPRECATE | DO_NOT_MIGRATE |

### 10. STORAGE TARGET PHYSICAL TREE
L'alberatura fisica Storage seguirà lo stesso segregamento Company-First:
```text
companies/{company_id}/
├── branding/
│   └── logo.* (permanente, public-read)
├── strategic-assets/
│   ├── distance-matrices/
│   ├── directions/
│   └── traffic/
├── tenants/{tenant_id}/
│   ├── source-documents/{yyyy}/{mm}/{dd}/... (permanente per tracciabilità)
│   ├── processing/ (temporaneo, eliminabile dopo ETL)
│   ├── reports/ (permanente per auditing)
│   └── exports/ (temporaneo)
└── temporary/
    └── processing-jobs/ (TTL 7 giorni)
```

### 11. TRE DATASET GOOGLE (STRATEGIC_DERIVED_ASSET)
- **File:** `distanze_reali_cache.json`, `directions_cache.json`, `distanze_traffico_cache.json`
- **Classificazione:** Confermati esplicitamente come `STRATEGIC_DERIVED_ASSET`.
- **Policy Backup & Restore:**
  - Esiste già nell'applicazione una procedura attiva per il backup, la conservazione e il ripristino/ricaricamento di questi dati.
  - Il nuovo target NON deve sostituire questa capacità ma **documentarla e preservarla**, verificandone solo la compatibilità con il nuovo path. Mantenere backup+restore come requisito obbligatorio senza introdurre meccanismi non necessari.
- **Current Location:** Storage root (`/caches/`)
- **Target Location:** `companies/{company_id}/strategic-assets/{tipo}/`

### 12. SOURCE DOCUMENT STORAGE
Ogni documento di origine (PDF, Excel, CSV) va preservato seguendo la policy formale:
**`SOURCE_DOCUMENT_RETENTION = CONFIGURABLE_POLICY`**
- **Conservazione Temporanea**: Firebase Storage NON è un archivio perpetuo obbligatorio.
- **Durata Configurabile**: La durata (es. 1, 2 o 3 mesi) sarà configurabile a livello azienda/tenant.
- **Auto-cancellazione**: I file saranno eliminabili automaticamente a scadenza.
- **Offload Futuro**: Prevista la possibilità di un'archiviazione a lungo termine su Google Drive o storage alternativo a minor costo.
- **Metadati su Firestore**: Rimarranno persistenti per garantire il lineage (`tenants/{tenant_id}/documenti_sorgente/{documento_id}`). Campi: `document_id`, `tenant_id`, `company_id`, `original_filename`, `storage_path`, `file_type`, `source_signature`, `ingestion_profile_id`, `imported_at`, `status`, `checksum`.

### 13. DATA READINESS MATRIX

| DOMAIN | AS_IS | TARGET_PATH | STATUS | ACTION |
|---|---|---|---|---|
| Azienda | - | `aziende/{id}/profilo` | MISSING | Inizializzare |
| Configurazioni | - | `aziende/{id}/configurazioni` | MISSING | Definire e popolare |
| Tenant | - | `aziende/{id}/tenants` | MISSING | Creare |
| Config Tenant | Ibrido in `clienti` | `tenants/{id}/configurazioni` | NEEDS_ALIGNMENT| Standardizzare |
| Fatturazione | Assente | `.../configurazioni/fatturazione` | MISSING | Sviluppare modello |
| Punti DNR | `punti_consegna`| `tenants/DNR/punti_consegna` | READY | Promuovere schema M5 |
| Punti CATTEL | `clienti/CATTEL`| `tenants/CATTEL/punti_consegna`| LEGACY_ONLY | Migrazione da legacy |
| Punti GRAN CHEF| `clienti/GC` | `tenants/GC/punti_consegna` | LEGACY_ONLY | Migrazione da legacy |
| Punti DAC | `clienti/DAC` | `tenants/DAC/punti_consegna` | LEGACY_ONLY | Migrazione da legacy |
| Mezzi/Autisti | root global | `aziende/{id}/mezzi` | NEEDS_ALIGNMENT| Spostare sotto Azienda |
| Magazzini | misto | `aziende/{id}/magazzini` | NEEDS_ALIGNMENT| Consolidare su Azienda |
| Google Dataset | root Storage | `companies/{id}/strategic-assets`| PARTIAL | Move & Cutover |

### 14. MIGRATION DECISION MATRIX
- **Master Data (Azienda, Tenant, Punti, Mezzi, Dipendenti):** `MOVE` (Migrazione attiva / Consolidamento).
- **Google Strategic Datasets:** `COPY_VERIFY_CUTOVER`.
- **Vecchi Viaggi (Legacy Journeys):** `DO_NOT_MIGRATE` (Consultabili storicamente).
- **Vecchi Report / Planning:** `DO_NOT_MIGRATE`.

### 15. SECURITY BOUNDARIES
Linee guida per Firestore/Storage Rules:
- **COMPANY_ISOLATION:** Accesso limitato all'Azienda d'appartenenza.
- **TENANT_ISOLATION:** Un operatore Tenant X non può leggere Tenant Y.
- **COMPANY_ADMIN:** Read/Write completo sui tenant della propria azienda.
- **DRIVER_ACCESS:** Accesso Read-Only sulle fermate/viaggi a lui assegnati e Update limitato allo `status` o firma digitale.
- **SERVICE_ACCOUNT_ACCESS (Backend/AI):** Pieni permessi operativi segregati per token.

### 16. DESIGN DECISION REGISTER (A3)

| DECISION_ID | TOPIC | OPTIONS | RECOMMENDATION | RATIONALE | STATUS |
|---|---|---|---|---|---|
| A3-D01 | Company root structure | Misto vs `aziende/` strict | `aziende/{id}/` strict | Sicurezza e gerarchia universale | APPROVED_BY_EXISTING_POLICY |
| A3-D02 | Config document vs subcoll | Model A (Doc) vs Model B (Coll) | Model B (Subcollection) | Atomicità, query security e limiti 1MB | PROPOSED |
| A3-D03 | Delivery Point Canonical Identity | UUID generico vs DP+6 digits | tenant-scoped DP + 6-digit sequence | Firestore Document ID: `codice_punto`. UUID separato: not currently required. | APPROVED |
| A3-D04 | Stop physical location | Root vs Viaggio vs Tenant | Tenant-Scoped | Flessibilità in pre-routing | PROPOSED |
| A3-D05 | Journey scope | Company-Scoped vs Tenant-Scoped | Tenant-Scoped | Fino a validazione Multi-Tenant reale | REQUIRES_HUMAN_DECISION |
| A3-D06 | Strategic asset location & Backup | Nuovo meccanismo vs Uso esistente | Preservare backup esistente | Procedura già testata e funzionante. Classificato come STRATEGIC_DERIVED_ASSET. | APPROVED_BY_EXISTING_POLICY |
| A3-D07 | Source doc retention | Conservazione Perpetua vs `CONFIGURABLE_POLICY` | `CONFIGURABLE_POLICY` | Firebase Storage temporaneo (es. 1-3 mesi), offload Drive futuro | APPROVED_BY_EXISTING_POLICY |
| A3-D08 | Branding storage model | Base64 DB vs Storage Bucket | Storage Bucket + DB Link | Prevenzione gonfiaggio Firestore | PROPOSED |

### 17. OPEN HUMAN DECISIONS
1. **Decisione su Multi-Tenant Journeys (A3-D05):** Stabilire se i furgoni trasporteranno merce promiscua di tenant diversi nel medesimo `Viaggio_Definitivo`. Se sì, i Viaggi devono scalare allo scope Azienda e non Tenant.

## A4 - BILLING SOURCE OF TRUTH CONSOLIDATION

### 1. AS-IS (SPLIT-BRAIN)
La logica commerciale per i tenant attualmente presenta un'inconsistenza architetturale grave (Split-Brain):
- **FRONTEND V2:** Utilizza una root collection globale fuori standard `clienti_fatturazione/{doc_id}` per configurare e calcolare mensilmente.
- **BACKEND OPERATIVO:** Utilizza la collection legacy tenant-scoped `clienti/{tenant}/impostazioni/listino` (es. `routing_service.py`).
- **FALLBACK CODE:** Valori Python usati *solo* in assenza di configurazione DB (`FALLBACK_DEFAULT`). Non sono costanti hardcoded assolute.
- **Classificazione:** `CURRENT_STATE = SPLIT_BRAIN`

### 2. TARGET SOURCE OF TRUTH
Si approva formalmente come **UNICA FONTE CANONICA FUTURA**:
`aziende/{azienda_id}/tenants/{tenant_id}/configurazioni/fatturazione`

### 3. CONSUMER TARGET
Ogni consumer dovrà leggere esclusivamente la nuova configurazione unica.
- Journey/Routing Engine
- Billing Engine
- Fatturazione mensile
- UI Fatturazione
- Report economici

Nessun consumer futuro è autorizzato a mantenere tariffe o engine separati.

### 4. CONFIG SHAPE (TARGET)
La struttura dati per la fatturazione supporterà nativamente configurazioni flessibili:
```json
{
  "enabled": true,
  "model": "MODELLO_MISTO",
  "currency": "EUR",
  "version": "1.0",
  "effective_from": "2026-01-01T00:00:00Z",
  "status": "ACTIVE",
  "rules": {
    "tariffa_viaggio": 350.00,
    "tariffa_ddt": 16.50
  }
}
```
*Modelli previsti per il futuro:* `PER_VIAGGIO`, `PER_DDT`, `PER_CONSEGNA`, `PER_KG`, `PER_QUINTALE`, `PER_KM`, `PER_FASCIA_KM`, `MINIMO_VIAGGIO`, `EXTRA`, `MODELLO_MISTO`.

### 5. MIGRATION SOURCES
Durante la migrazione tenant, le fonti di estrazione dovranno essere consultate nel seguente ordine (Priorità Proposta):
1. Valore configurato esplicitamente e modificabile dall'utente (`clienti_fatturazione`).
2. Listino backend, se ancora operativo (`clienti/{tenant}/impostazioni/listino`).
3. Fallback Python (solo come estrema evidenza legacy).

### 6. CONFLICT HANDLING
In caso di divergenza tra la fonte Frontend (A) e Backend (B):
- `BILLING_CONFIG_CONFLICT = TRUE`
- Il sistema di migrazione **NON** dovrà tentare di risolvere automaticamente il conflitto.
- Mostrare entrambi i valori e richiedere una decisione umana esplicita.

### 7. FALLBACK POLICY TARGET
Nel target finale viene abolito il concetto di tariffa dedotta implicitamente dal codice.
- `SILENT_BILLING_FALLBACK = DISALLOWED`

Se manca una configurazione obbligatoria per il modello scelto:
- Bloccare il calcolo definitivo (es. throw error / suspend execution).
- Segnalare visivamente in UI la configurazione mancante.
- Richiedere completamento all'utente prima di calcolare i viaggi.
*I fallback legacy (come i listini default Python) possono esistere esclusivamente durante l'attuale fase transitoria.*

### 8. BILLING SNAPSHOT
Si conferma la validità irrevocabile dei viaggi consolidati:
- Configurazione tenant corrente → Calcolo Viaggio → **`billing_snapshot`** congelato all'interno del documento viaggio definitivo.
Modifiche future alla `configurazione/fatturazione` **NON** alterano e non dovranno mai ricalcolare viaggi pregressi chiusi, garantendo immutabilità dello storico.

### 9. REGISTRO FATTURAZIONE E CORREZIONI
Alla luce dell'audit A4.1, si ufficializza il seguente stato:
- `ACTIVE_HARDCODED_BILLING_VALUES = 0`
- `FALLBACK_DEFAULT_VALUES = 5`
- `CURRENT_BILLING_SOURCE = MIXED` (Split-Brain)
- `TARGET_BILLING_SOURCE = CANONICAL_TENANT_CONFIG`
