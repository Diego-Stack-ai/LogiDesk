# LogiDesk — piano agente di ingestione e archivio storico

Stato: `PROTOTYPE_IMPLEMENTED / LOCAL_DRY_RUN_VERIFIED / NO_REMOTE_WRITES`  
Data: 2026-09-04

## 1. Scopo e confini

Questo documento fissa le decisioni emerse sul nuovo ingresso documentale e sul ciclo di vita dei file. Non certifica lo stato remoto di Firebase e non autorizza migrazioni, cancellazioni, deploy o modifiche ai dati.

LogiDesk è un prodotto multi-azienda. L'azienda che usa il prodotto non è una radice globale del modello; i committenti sono tenant paritetici. In particolare DNR non deve mai essere usato come root, default o fallback. Il viaggio operativo finale è composto dall'utente dell'azienda e può comprendere consegne appartenenti a tenant diversi.

## 2. Principio operativo: l'app non dipende dall'AI

Il funzionamento quotidiano deve rimanere disponibile con PC tecnico spento e con AI disabilitata:

1. un formato già riconosciuto viene affidato a un parser deterministico certificato;
2. il parser può essere eseguito dal worker cloud già previsto dall'app;
3. PC, tablet e telefono inviano il job e consultano il risultato;
4. l'AI non partecipa alla normale elaborazione di un formato certificato.

Modalità previste:

- `AI_DISABLED`: soltanto parser certificati; un formato sconosciuto richiede intervento tecnico;
- `AI_LOCAL_TECHNICAL`: l'agente locale assiste il personale tecnico nella conoscenza di un nuovo formato;
- `AI_CLOUD_OPTIONAL`: possibile servizio futuro, esplicitamente abilitabile e con costo separato.

È inoltre prevista `CHATGPT_FREE_MANUAL_BRIDGE`, destinata a chi usa ChatGPT
gratuitamente: LogiDesk genera una rappresentazione testuale anonimizzata,
l'operatore la copia manualmente in ChatGPT e incolla in LogiDesk la risposta
JSON. Non esiste login condiviso, automazione del sito ChatGPT o chiamata API;
limiti e disponibilità del servizio esterno restano estranei a LogiDesk.

L'AI locale non modifica autonomamente uno script attivo. Può proporre mapping, regole, test e una nuova versione del parser; pubblicazione e certificazione richiedono verifica umana.

Il primo contratto applicativo del ponte manuale è implementato in
`functions/services/manual_ai_bridge.py`. Il componente non salva dati e non
effettua traffico di rete: produce il testo copiabile, anonimizza i campioni e
rifiuta mapping verso campi non appartenenti allo schema canonico.

Il prototipo UI è disponibile in `frontend/importazione_assistita.html` e usa
il contratto browser `frontend/services/manual-ai-bridge.js`. Legge localmente
Excel, PDF, CSV e testo. Le immagini vengono lette nel browser tramite OCR
Tesseract italiano/inglese, con limiti differenti per telefono e desktop e
avviso obbligatorio sulla fallibilità di codici, quantità e date. Il motore e i
modelli OCR vengono scaricati alla prima esecuzione, ma l'immagine non viene
inviata a Firebase o a ChatGPT. Il tenant è obbligatorio e non esiste un valore
di default. La risposta validata resta una proposta e non viene scritta su
Firestore.

Il client `functions/services/local_ai_agent.py` collega il contratto a un
endpoint Ollama esclusivamente locale. Il primo collaudo con `qwen3.5:9b` ha
normalizzato correttamente nove intestazioni anonime e rilevato l'ambiguità
della fascia oraria. Una prima risposta conteneva un errore formale ed è stata
rifiutata; il tentativo unico di riparazione guidato dal validatore ha poi
prodotto un contratto valido. Il tempo osservato su CPU è circa 55 secondi e
impone una coda con concorrenza uno.

Lo stesso OCR viene applicato come fallback alle pagine PDF che contengono meno
di 30 caratteri di testo digitale. Il worker OCR viene riutilizzato per tutte
le pagine del documento e terminato al termine; il limite è 6 pagine OCR su
telefono e 20 su desktop. Le pagine eccedenti restano censite con stato
`ocr_skipped_limit` e non devono essere considerate lette.

Il prototipo genera inoltre una `source_signature` dalla struttura selezionata:
tipo sorgente, nomi di fogli/pagine, colonne, metodo di estrazione e indicatori
documentali. Un profilo JSON precedente può essere ricaricato e confrontato
localmente. La coincidenza vale soltanto come `candidate_only`: azienda, tenant
e impronta devono coincidere, ma la firma non certifica da sola il parser e non
autorizza un'elaborazione automatica.

Per i file Excel il mapping revisionato può essere applicato localmente a tutte
le righe dei fogli selezionati. Il risultato è soltanto
`NORMALIZED_PREVIEW_NOT_PERSISTED`: conserva foglio e riga sorgente, mostra un
campione e può essere scaricato come JSON. Prima dell'esportazione vengono
segnalati duplicati candidati interni per codice punto, codice articolo o DDT
nello stesso tenant. Il controllo non sostituisce ancora la riconciliazione con
le anagrafiche Firestore.

## 3. Flusso di conoscenza e certificazione di un formato

Ogni sorgente viene descritta da un `ingestion_profile` versionato, contenente almeno:

- azienda, tenant e famiglia documentale;
- firma strutturale del formato, distinta dall'hash del singolo file;
- fogli/pagine/sezioni da leggere o ignorare;
- regole di estrazione, normalizzazione e raggruppamento;
- versione del parser e set di file campione;
- test attesi, soglie di confidenza e stato di certificazione.

Flusso:

`UPLOAD -> INVENTARIO -> RICONOSCIMENTO PROFILO -> PARSER CERTIFICATO -> NORMALIZZAZIONE -> RICONCILIAZIONE -> REVISIONE -> COMMIT DATI`

Se la firma differisce dal profilo noto (colonna nuova, intestazione spostata, foglio aggiunto, layout PDF cambiato), il job si ferma in revisione. L'operatore vede i campi trovati e li associa tramite una scheda con selettore al campo canonico, può dichiararli non rilevanti oppure proporre un nuovo campo di dominio.

## 4. Dialogo obbligatorio dell'importazione

Per ogni file o gruppo di file il sistema deve registrare e, quando non deducibile con sicurezza, chiedere:

- azienda proprietaria;
- committente/tenant; un tenant sconosciuto non viene creato implicitamente;
- data operativa del viaggio, scelta all'importazione e non confusa con data file o data elaborazione;
- quantità di giri proposta: un file può contenere uno o più giri;
- regola di lettura dei fogli Excel: tutti, lista inclusa/esclusa, solo riepilogo o fogli separati;
- regola documentale PDF: una pagina per DDT oppure DDT multipagina;
- regola di denominazione dei documenti separati, per esempio `{numero_ddt}_{data_ddt}.pdf`.

Per `ReportPianificazione.xlsx` l'inventario deve comprendere tutte le linguette. L'operatore può scegliere il riepilogo, che contiene più giri riconoscibili da una colonna, oppure i fogli di dettaglio evitando doppie importazioni.

## 5. DDT, punti di consegna e articoli

L'originale va preservato durante il periodo operativo. Se il PDF contiene più DDT, la separazione deve avvenire per identità documentale, non assumendo senza verifica che ogni pagina sia sempre un documento completo.

Identità e riconciliazione dei punti di consegna:

1. chiave primaria funzionale: `tenant_id + codice_punto_committente`;
2. confronto secondario su alias, denominazione e indirizzo normalizzato;
3. differenze presentate campo per campo: `mantieni`, `aggiungi`, `sostituisci`, `ignora`;
4. nessuna duplicazione silenziosa in presenza di un codice già noto.

Per gli articoli vanno distinti e conservati:

- codice base assegnato dal committente;
- codice operativo aggiuntivo, anche se stampato sulla stessa riga o su righe successive;
- lotto/intervallo/scadenza o periodo di distribuzione;
- quantità, unità, confezionamento e porzioni per collo, senza inferenze irreversibili.

Una regola come `D4110` è specifica del profilo: si conserva il valore originale, `D` può rappresentare l'agente commerciale, mentre `4110` è la zona usata per il raggruppamento logistico. La trasformazione si applica solo dopo conferma e test, evitando omissioni come la perdita delle cifre `110`.

## 6. Tracciabilità dei viaggi

Sono entità distinte:

- documento sorgente e relativa impronta;
- sessione/job di importazione;
- DDT e righe DDT;
- proposta di giro importata;
- punto di consegna e articolo canonici;
- viaggio operativo finale, deciso dall'utente;
- decisioni di riconciliazione e revisione.

Ogni consegna deve conservare tenant, documento e righe d'origine, peso, colli, quantità, data e fotografia economica applicabile. In questo modo un viaggio aziendale multi-tenant rimane ricostruibile e fatturabile per viaggio, consegna o DDT.

## 7. Classificazione Storage

I contenuti non hanno tutti la stessa durata:

| Classe | Esempi | Regola proposta |
|---|---|---|
| Operativo caldo | PDF originali e separati, report, memorandum, output e link di percorso | Firebase Storage durante il periodo operativo configurabile, indicativamente 1-3 mesi |
| Strategico derivato | cache distanze e asset indispensabili al calcolo | conservazione e backup dedicati; non cancellare con l'archivio mensile |
| Asset aziendale | foto mezzi, documenti mezzi | ciclo legato al mezzo e agli obblighi documentali, non al mese fatturato |
| Storico freddo | pacchetti mensili chiusi e relativi originali | archivio esterno configurabile: Google Drive condiviso, storage alternativo o archivio locale gestito |

Google Drive è un archivio esterno, non un filesystem operativo né un sostituto trasparente di Firebase Storage. L'integrazione deve usare API, identità e permessi dedicati. Per installazioni Google Workspace è preferibile un Drive condiviso aziendale, così la proprietà resta dell'organizzazione e non di una persona.

## 8. Chiusura mensile e pacchetto di archivio

Un mese può essere archiviato solo dopo chiusura della fatturazione. Stati minimi:

`HOT -> FINALIZED -> ARCHIVING -> ARCHIVED`

Stati di servizio: `RESTORE_REQUIRED`, `RESTORED`, `ERROR`.

Il pacchetto mensile deve includere:

- `manifest.json`: schema version, azienda, periodo, tenant coinvolti, elenco file, dimensioni, checksum, origine e destinazione;
- snapshot normalizzati JSON/JSONL e, dove utile, CSV o Parquet;
- fatti economici e operativi: viaggi, consegne, DDT, km, peso, colli, mezzo, carburante, pedaggi, imposte/costi, tariffa e risultato di fatturazione congelati;
- decisioni di riconciliazione necessarie a interpretare i dati;
- documenti originali richiesti dalla policy aziendale o normativa.

In Firestore rimane un indice leggero con `archive_id`, periodo, provider, locator opaco, checksum del manifest, schema version, stato, data archiviazione e stato dell'ultima prova di ripristino.

La copia calda si elimina soltanto dopo:

1. mese finalizzato;
2. upload completato;
3. verifica dei checksum;
4. prova di lettura/ripristino;
5. scadenza della retention configurata;
6. assenza di vincoli legali o amministrativi.

## 9. Analisi annuale

Le analisi annuali non devono dipendere dalla rilettura di centinaia di PDF. I fatti strutturati compatti restano interrogabili o vengono consolidati in dataset annuali; i PDF e gli altri documenti freddi servono come prova e approfondimento recuperabile.

Questo consente domande future su costo e ricavo per mezzo, tenant, giro o DDT, utilizzo della flotta, km, peso, carburante, tasse e scostamenti. I campi economici definitivi verranno estesi progressivamente senza distruggere le versioni storiche dello schema.

## 10. Decisioni ancora aperte

- durata predefinita e limiti minimi/massimi della retention per classe di dato;
- obblighi fiscali, privacy e conservazione documentale per tipo di allegato;
- Drive condiviso, Cloud Storage a classe fredda o archivio locale/NAS per ciascuna installazione;
- cifratura, gestione chiavi, responsabilità dell'account archivio e procedura di disaster recovery;
- schema definitivo del fact table annuale e gestione dei costi caricati successivamente;
- politica commerciale e tecnica della modalità AI cloud opzionale.

## 11. Stato delle evidenze

### Fatti verificati nel repository

- il piano dati prevedeva già retention configurabile, metadati persistenti e futuro offload verso Drive;
- la pipeline corrente comprende parser Python specifici e un worker cloud; il loro inventario dettagliato resta oggetto del refactoring;
- il repository contiene ancora materiale legacy da trattare come fonte di regole, non come architettura canonica.

### Operazioni Firebase registrate nella task precedente

Restano valide soltanto come registro storico le migrazioni e i deploy annotati in `docs/CODEX_HANDOFF_LOGIDESK.md`.

### Stato remoto Firebase da ricontrollare

Il contenuto effettivo attuale di Firestore e Firebase Storage, le relative quantità e lo stato live del worker non sono stati verificati durante questa attività documentale. Le descrizioni di PDF, link, report, foto e documenti mezzi sono requisiti comunicati dall'utente, non un inventario remoto certificato.
