


**Document role**: memoria operativa e punto di ripresa tra task Codex

**Authority scope**: stato dei lavori, evidenze Git, operazioni registrate e prossime verifiche

**Upstream**: `PROJECT_MANIFEST.md`, `README.md`, `AGENTS.md`, `DOMAIN_MODEL.md`, `ARCHITECTURE.md`, `OPERATIONS.md`

**Status**: ACTIVE

**Last reviewed**: 2026-08-31

> Questo documento non sostituisce le fonti autorevoli del progetto. In caso di
> conflitto prevalgono il Manifest, i cinque documenti Core e i documenti di
> dominio pertinenti. Le operazioni su Firebase indicate come "registrate nella
> task" devono essere verificate dal vivo prima di assumere che lo stato remoto
> sia ancora invariato.

## 1. Scopo del progetto

LogiDesk è la nuova generazione dell'app logistica di Loge Solution. Deve
diventare autonoma, ordinata e multi-tenant, mantenendo intatta l'applicazione
legacy di Produzione durante il cantiere di ricostruzione.

Obiettivo immediato: ripulire e normalizzare codice, Firestore e Cloud Storage
del Cantiere prima di riattivare progressivamente le pagine e gli script Python.
Ogni script deve essere controllato prima dell'esecuzione, affinché non ricrei
raccolte legacy o cartelle duplicate.

## 2. Identità tecnica

| Elemento | Valore |
|---|---|
| Repository GitHub | `Diego-Stack-ai/LogiDesk` |
| Repository locale | `C:\Users\Diego\Documents\Codex\2026-08-28\in-chatgpt-c-un-progetto-che\work\LogiDesk` |
| Root applicativa | `WebApp/` |
| Firebase Cantiere | `log-solutions-cantiere` |
| Firebase Produzione legacy | `log-solution-60007` |
| Azienda canonica Cantiere | `aziende/NzXaCgyXxZWWehw1tSlo` |
| Branch corrente al 2026-08-31 | `main` |
| Commit corrente al 2026-08-31 | `c6e6699` |
| Versione frontend nel codice | `6.463` |

Il working tree risultava pulito e `main` allineato a `origin/main` durante la
creazione di questo handoff.

## 3. Regole operative da non perdere

1. Leggere integralmente, nell'ordine, `README.md`, `AGENTS.md`,
   `DOMAIN_MODEL.md`, `ARCHITECTURE.md` e `OPERATIONS.md` prima di intervenire.
2. Produzione e Cantiere sono applicazioni separate. La Produzione è congelata
   salvo hotfix esplicitamente autorizzati.
3. Ogni comando Firebase deve contenere il project ID esplicito. Non utilizzare
   mai un semplice `firebase deploy`: il default del repository può puntare alla
   Produzione.
4. Analisi, modifica, bump versione, commit, push, merge e deploy sono
   autorizzazioni separate.
5. Non lavorare direttamente su `main` per nuove modifiche: creare un branch
   dedicato e mostrare status/diff prima del commit.
6. Il push su `main` può attivare automazioni di deploy: ispezionare sempre il
   workflow e dichiarare il target prima del merge/push.
7. Nessuna cancellazione o migrazione Firestore/Storage senza inventario,
   backup, confronto sorgente-target, gate di cancellazione e conferma esplicita.
8. Il rollback Git non ripristina i dati cancellati da Firestore o Storage.

## 4. Modello dati concordato

- Loge Solution è l'azienda proprietaria e il vettore operativo.
- DNR, CATTEL, GRAN CHEF e gli altri committenti sono tenant paritetici.
- DNR non è una cartella radice, un'azienda o un tenant predefinito.
- `DNR_FRUTTA` e `DNR_LATTE` sono canali dello stesso tenant DNR:
  `tenantId = DNR`, con `sourceChannel = FRUTTA` oppure `LATTE`.
- Se manca `tenantId`, il dato deve essere bloccato o messo in quarantena; è
  vietato assegnarlo automaticamente a DNR.
- I dati aziendali condivisi, come dipendenti e mezzi, appartengono ad
  `aziende/{aziendaId}` e non a un committente.
- L'anagrafica dei committenti deve avere una sola fonte canonica sotto
  l'azienda; non devono esistere liste indipendenti per pagine diverse.
- I dati tenant-specifici devono rimanere isolati sotto il tenant effettivo.
- I percorsi target dei punti di consegna sono
  `aziende/{aziendaId}/tenants/{tenantId}/punti_consegna/{idPunto}`.

## 5. Lavori Git completati e verificati

### 5.1 Cutover mezzi

- Commit `623394f` — `refactor: cut over vehicles to company collection`.
- File principali: `fatturazione_v2.html`, `gestione_mezzi.html`,
  `services/realtime-sync.js`.
- Version bump commit `89cd65b` a `6.461`.
- Integrato in `main` dalla PR #2, merge commit `317af9c`.
- Risultato: il runtime modificato usa la raccolta mezzi aziendale canonica.
- Stato della vecchia raccolta root `mezzi`: da verificare dal vivo prima di
  dichiararla assente o cancellabile.

### 5.2 Cutover config

- Commit `a9251f5` — `refactor: cut over config to canonical settings`.
- Version bump commit `f8a3783` a `6.462`.
- Integrato in `main` dalla PR #3, merge commit `d7c2e38`.
- Specifica: `docs/migration/CONFIG_ROOT_CUTOVER.md`.
- Destinazioni canoniche previste:
  - `config/email_settings` -> `aziende/{aziendaId}/settings/email`;
  - `config/permessi_dashboard` -> `aziende/{aziendaId}/settings/permissions`;
  - `config/system_status` -> `aziende/{aziendaId}/settings/system`;
  - `config/cattel` ->
    `aziende/{aziendaId}/tenants/{cattelTenantId}/configurazioni/integrazione`.
- URL e username CATTEL possono restare nel documento canonico; la password
  reale deve vivere in Secret Manager come `CATTEL_PORTAL_PASSWORD`.
- `EMAIL_PASSWORD` deve anch'essa vivere in Secret Manager.
- Lo script di supporto è `tools/migrate_config_cutover.py`.
- Il cutover del codice è verificato in Git. L'effettiva eliminazione della
  raccolta root `config` non è certificata da questo handoff: controllare
  target, segreti e stato live prima di cancellarla.

### 5.3 Cutover dipendenti

- Commit `5cb3856` — `refactor: cutover dipendenti al percorso aziendale`.
- Integrato in `main` dalla PR #4, merge commit `7d54d6e`.
- Specifica: `docs/migration/DIPENDENTI_ROOT_CUTOVER.md`.
- Percorso dismesso: `/dipendenti/{dipendenteId}`.
- Percorso canonico:
  `/aziende/NzXaCgyXxZWWehw1tSlo/dipendenti/{dipendenteId}`.
- Audit registrato: 25 documenti legacy e 25 canonici, senza ID mancanti o
  aggiuntivi.
- Commit `3eb9a1a` — rimossa la regola Firestore legacy `/dipendenti`.
- Commit `9e1e7b9` — workflow GitHub Actions aggiornato a Node 24.
- I due ultimi commit sono integrati dalla PR #5, merge commit `c6e6699`.
- Nella task precedente l'utente ha autorizzato la cancellazione dei 25
  documenti root `/dipendenti`; l'operazione è stata registrata come eseguita e
  la raccolta canonica come preservata. Trattandosi di stato remoto e
  distruttivo, effettuare comunque una verifica read-only live prima di basare
  nuove decisioni su questo dato.

### 5.4 Versionamento e CI

- Versione frontend corrente verificata nel repository: `6.463`.
- Lo script ufficiale è `WebApp/bump_version.py`; propaga `APP_VERSION`, cache
  del service worker e query string degli asset.
- Il bump non comporta automaticamente commit, push o deploy.
- Il workflow GitHub usa ora azioni compatibili con Node 24.

## 6. Deploy registrati nella task precedente

La task precedente contiene autorizzazioni e resoconti di merge/deploy sul
Cantiere per i cutover effettuati, compreso il deploy delle Firestore Rules dopo
la rimozione della regola legacy dipendenti. Poiché lo stato degli ambienti
remoti può cambiare, all'inizio della nuova task verificare almeno:

1. ultima esecuzione del workflow GitHub;
2. versione effettivamente servita dall'Hosting Cantiere;
3. ruleset Firestore attivo su `log-solutions-cantiere`;
4. assenza di deploy o modifiche involontarie su `log-solution-60007`.

Non assumere che un merge equivalga automaticamente al deploy di tutti i
componenti Firebase: Hosting, Functions, Firestore Rules e Storage Rules sono
componenti distinti.

## 7. Stato della pulizia Firestore

La finalità della pulizia non è cancellare tutto ciò che sembra vecchio, ma
ottenere una struttura unica e inequivocabile. Le raccolte root devono essere
classificate come:

- canoniche aziendali;
- canoniche tenant-scoped;
- cache tecniche ancora utilizzate;
- dati storici/fatturazione conservabili;
- legacy non più lette né scritte;
- stato sconosciuto da analizzare.

Indicazioni maturate nella task:

- `aziende`: radice canonica dell'organizzazione, da mantenere;
- `dipendenti` root: cutover completato; cancellazione registrata, da
  riconfermare read-only;
- `mezzi` root: codice migrato al percorso aziendale; stato live da verificare;
- `config` root: codice migrato; cancellazione live non certificata qui;
- `giustificativi`: dato aziendale usato da Presenze/Impostazioni, da mantenere
  e successivamente collocare nel corretto scope aziendale/settings;
- `distanze`, `percorsi_stradali` e `traffico_cache`: probabili cache tecniche
  coordinate con Storage; non cancellare finché non sono stati tracciati tutti
  i lettori/scrittori e il rapporto con la cartella `caches/`;
- `presenze`: dato HR/fatturazione storico; la decisione di eliminazione deve
  dipendere da uso runtime, obblighi di conservazione e backup, non soltanto
  dall'assenza apparente nella UI;
- `progetti`, `start_monitoring`, `sistema_migrazione`, `viaggi` e le altre root:
  stato ancora da classificare mediante audit completo del codice e dei dati.

Regola pratica: lasciare al loro posto le raccolte non ancora certificate. Prima
si impedisce al runtime di leggerle o ricrearle, poi si collauda l'app, infine si
propone la cancellazione con un gate separato.

## 8. Lavoro aperto prioritario: indipendenza da DNR

Documento di partenza:
`docs/active-plans/DEBT_ISOLAMENTO_TENANT_DNR.md`.

La task precedente ha avviato l'inventario e ha registrato circa 45 riferimenti
legacy/hardcoded distribuiti in 19 file verso logiche o percorsi assimilabili a
`clienti/DNR`. Nessuna modifica DNR è stata applicata prima della creazione di
questo handoff. I conteggi devono essere rigenerati sul commit corrente.

Perimetro da classificare, senza sostituzioni massive:

1. fallback come `activeTenant || 'DNR'`;
2. path Firestore forzati sotto `clienti/DNR/...`;
3. path Storage speciali per DNR, inclusa l'asimmetria `REPORTS/` root;
4. importatori Python e Functions che generano dati senza tenant esplicito;
5. pianificazione, mappe, articoli, rientri DDT e fatturazione;
6. riferimenti storici legittimi, test e backup da non confondere con runtime;
7. dati aziendali erroneamente salvati sotto DNR;
8. compatibilità temporanea necessaria per leggere viaggi storici.

Principio di intervento: ogni occorrenza va prima classificata come
`LEGACY_RUNTIME`, `LEGACY_HISTORY`, `VALID_DNR_SPECIFIC`, `FALLBACK_INVALIDO`,
`TEST/FIXTURE` oppure `DOCUMENTAZIONE`. Solo dopo l'approvazione si modifica il
codice per gruppi funzionali e con test mirati.

## 9. Sequenza consigliata per la nuova task

1. Eseguire il bootstrap documentale completo.
2. Verificare `git status`, branch, commit e remote senza modificare nulla.
3. Rigenerare l'inventario DNR con file, righe, tipo di riferimento, lettura o
   scrittura, ambiente e destinazione target proposta.
4. Analizzare per primi gli ingressi dati: import Python, Functions e creazione
   della pianificazione. Nessun dato nuovo deve nascere sotto DNR per fallback.
5. Presentare un report e un piano a fasi; attendere l'approvazione prima delle
   modifiche architetturali.
6. Lavorare su branch dedicato.
7. Eseguire test locali e, se autorizzato separatamente, collaudi selettivi sul
   solo progetto `log-solutions-cantiere`.
8. Riprendere l'audit delle raccolte Firestore root soltanto con verifiche live
   read-only e una matrice lettori/scrittori/dati/target.

## 10. Prompt breve per aprire la nuova task Codex

Incollare questo testo come primo messaggio nella nuova task del progetto
locale LogiDesk:

```text
Continuiamo il progetto LogiDesk dal precedente cantiere Codex. Prima di fare
qualsiasi analisi o modifica, leggi integralmente WebApp/PROJECT_MANIFEST.md,
i cinque documenti Core indicati in WebApp/README.md e
WebApp/docs/CODEX_HANDOFF_LOGIDESK.md. Verifica Git e distingui sempre tra fatti
verificati nel repository, operazioni Firebase registrate nella task e stato
remoto da ricontrollare. Riprendi in modalità ANALISI dal censimento dei
riferimenti legacy DNR: DNR deve essere trattato come un committente paritetico,
mai come root o fallback. Non modificare codice, Firestore, Storage, Rules,
versione, Git o deploy senza la relativa autorizzazione separata.
```

## 11. Evidenze principali

- `PROJECT_MANIFEST.md`
- `README.md`
- `AGENTS.md`
- `DOMAIN_MODEL.md`
- `ARCHITECTURE.md`
- `OPERATIONS.md`
- `docs/migration/CONFIG_ROOT_CUTOVER.md`
- `docs/migration/DIPENDENTI_ROOT_CUTOVER.md`
- `docs/active-plans/DEBT_ISOLAMENTO_TENANT_DNR.md`
- `docs/data-model/FIRESTORE_TARGET_SCHEMA.md`
- `docs/active-plans/LOGIDESK_DATA_ARCHITECTURE_PLAN.md`
- Git commits `623394f`, `a9251f5`, `5cb3856`, `3eb9a1a`, `9e1e7b9` e
  merge commit `c6e6699`.

## 12. Aggiornamento futuro dell'handoff

Al termine di ogni fase rilevante aggiornare questo documento indicando:

- data e branch;
- commit/PR/merge;
- test e deploy realmente eseguiti;
- progetto Firebase effettivamente toccato;
- backup e rollback disponibili;
- stato delle raccolte remote verificato;
- decisioni ancora aperte.

Non riportare password, token, chiavi di servizio o altri segreti in questo file.

## 13. Aggiornamento 2026-09-02 — cutover dati HR aziendali

- Branch di lavoro: `codex/company-hr-data-cutover`, basato sul commit handoff
  `9bffea6` e quindi su `main` `c6e6699`.
- Il runtime è stato spostato dai path root ai path canonici
  `aziende/{companyId}/giustificativi` e
  `aziende/{companyId}/presenze`; sono state aggiunte le relative regole.
- Le cinque causali sono state copiate nel perimetro aziendale e verificate
  nella UI Cantiere. La raccolta root `giustificativi` non risultava più
  presente alla verifica live del 2026-09-02.
- La raccolta root `presenze` risultava ancora presente e conteneva documenti
  di più mesi. La copia selettiva di luglio 2026 è stata completata il
  2026-09-02: 625 documenti copiati con gli stessi ID in
  `aziende/NzXaCgyXxZWWehw1tSlo/presenze`, zero conflitti e verifica finale di
  625 documenti. La root legacy non è stata cancellata.
- `system_migrations` risultava ancora presente con i marker tecnici delle
  migrazioni core. Non è stato cancellato.
- Hosting e regole erano già stati distribuiti sul solo progetto
  `log-solutions-cantiere`; nessuna operazione è stata eseguita sul progetto
  Produzione.
- Il ramo remoto `copilot/fix-deploy-firebase-hosting` non è compatibile con la
  pipeline corrente: ridurrebbe il rilascio al solo Hosting e riporterebbe
  `actions/checkout` da v5 a v4. Non deve essere unito a `main`.
- I quattro rami `feature/a416-*` risultavano già contenuti in `main`; il ramo
  `docs/codex-handoff-logidesk` viene assorbito dal presente lavoro.
- Esecuzione certificata: GitHub Actions `Migrate Company HR Data`, run
  `33623429433`, tentativo 2. Il ruolo IAM `Cloud Datastore User` è stato
  aggiunto temporaneamente a `github-action-logidesk`, quindi rimosso e
  verificato dopo la migrazione.
- Con conferma esplicita dell'utente, la raccolta root legacy `presenze` è
  stata cancellata integralmente il 2026-09-02. La console Firebase ha
  confermato l'assenza della root e la presenza della subcollection aziendale.
  Anche la relativa regola Firestore legacy è stata rimossa per impedirne la
  ricreazione accidentale.
