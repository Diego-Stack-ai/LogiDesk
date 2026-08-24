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


