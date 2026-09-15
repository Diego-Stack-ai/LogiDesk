# INGESTION ENTRY CONTRACT — IMPLEMENTATION PLAN

**Stato**: fase 2A implementata localmente; collaudo Cantiere in attesa di approvazione
**Ambiente previsto**: Cantiere (`log-solutions-cantiere`)
**Produzione**: esclusa
**Riferimenti Core**: `DOMAIN_MODEL.md`, `ARCHITECTURE.md`, `AGENTS.md`

## 1. Obiettivo

Mettere in sicurezza la nascita dei nuovi job di importazione prima di introdurre classificazione AI, nuovi parser o migrazioni dei path. Ogni job deve avere un tenant valido, un canale esplicito e una data di lavoro autorevole; nessun valore sconosciuto può essere trasformato in DNR.

## 2. Decisioni approvate

- DNR è un tenant paritetico e vive nel path tenant DNR; non è un fallback.
- `FRUTTA` e `LATTE` sono canali di DNR.
- Per un tenant valido, un canale non specializzato può essere `ALTRO`, con conferma dell'operatore.
- Un tenant non censito o una chiave di ingresso sconosciuta arrestano la procedura.
- L'importazione classica usa pulsanti/profili noti e non invoca l'AI.
- Un nuovo pulsante separato avvierà in futuro l'importazione AI per sorgenti incerte o nuovi formati.
- L'AI opera per proposta e richiede conferma; non crea tenant automaticamente.
- Il file sorgente è temporaneo e viene cancellato solo dopo certificazione; restano dati canonici e metadati minimi di audit.

## 3. Perimetro della prima implementazione

### Incluso

1. Registry chiusa degli ingressi classici:
   - `FRUTTA` → `tenantId=DNR`, `sourceChannel=FRUTTA`;
   - `LATTE` → `tenantId=DNR`, `sourceChannel=LATTE`;
   - `GRAN_CHEF` → tenant configurato, canale configurato o `ALTRO`;
   - `CATTEL` → tenant configurato, canale configurato o `ALTRO`;
   - `DAC` → tenant configurato, canale configurato o `ALTRO`.
2. Validazione fail-closed delle chiavi di ingresso.
3. Scrittura di `tenantId`, `sourceChannel`, `data_lavoro`, metadati file e versione del contratto nel nuovo job.
4. Validazione backend dello stesso contesto senza default DNR/FRUTTA.
5. Compatibilità di lettura esplicita e isolata per i job legacy esistenti.
6. Test unitari o di caratterizzazione per combinazioni valide e invalide.

### Escluso

- migrazione dei path Firestore o Storage;
- modifica dei dati di Produzione;
- cancellazione automatica dei file;
- nuovo agente AI e relativa UI;
- modifica dei parser PDF/Excel;
- modifica di reporting, routing, viaggi o fatturazione;
- modifica delle Security Rules.

## 4. Contratto proposto per i nuovi job

```json
{
  "contract_version": "2.0",
  "status": "uploaded",
  "tenantId": "DNR",
  "sourceChannel": "FRUTTA",
  "data_lavoro": "15-09-2026",
  "source": {
    "originalFilename": "consegne.pdf",
    "storagePath": "input_pdf_fornitore/...",
    "fileType": "application/pdf",
    "fileSize": 123456
  },
  "classification": {
    "mode": "CLASSIC",
    "operatorConfirmedSource": true,
    "ingestionProfileId": "dnr-frutta-ddt-pdf",
    "ingestionProfileVersion": 1
  }
}
```

`ingestionProfileId` identifica la famiglia di regole di lettura e non coincide con il nome del file.

## 5. Gate di validazione

La procedura si arresta prima del parsing se:

- la chiave del pulsante non è registrata;
- `tenantId` è assente, vuoto o non censito;
- `sourceChannel` è assente quando richiesto;
- la combinazione tenant/canale non è ammessa;
- `data_lavoro` è assente o invalida;
- il file non rispetta il tipo consentito dal profilo.

`sourceChannel=ALTRO` è valido soltanto per un tenant già valido e non può essere usato come fallback per tenant o sorgente sconosciuti.

## 6. Strategia di compatibilità

- I nuovi job usano `contract_version=2.0` e campi espliciti.
- I job senza `contract_version` sono classificati come legacy.
- Il reader legacy può tradurre temporaneamente `DNR_FRUTTA`/`DNR_LATTE` in memoria, senza riscrivere i documenti storici.
- Nessun nuovo job viene creato con il vecchio contratto.
- Nessuna sostituzione massiva di stringhe DNR.

## 7. Test richiesti

| Caso | Esito atteso |
| --- | --- |
| DNR + FRUTTA | accettato |
| DNR + LATTE | accettato |
| tenant valido + ALTRO | accettato dopo conferma |
| chiave pulsante sconosciuta | hard stop |
| tenant mancante | hard stop |
| tenant non censito | hard stop/onboarding |
| DNR_FRUTTA usato come tenant | rifiutato |
| CATTEL + FRUTTA | rifiutato salvo configurazione esplicita |
| data lavoro mancante | hard stop |
| job legacy | letto dal compatibility adapter |

## 8. Criteri di ingresso

- working tree pulito;
- branch dedicato non `main`;
- approvazione esplicita dell'implementazione;
- file da modificare concordati;
- baseline dei test esistenti registrata;
- nessun accesso a Produzione.

## 9. Criteri di uscita

- nessun fallback automatico DNR/FRUTTA nel nuovo percorso;
- tutti i nuovi job contengono tenant e canale espliciti;
- combinazioni sconosciute bloccate prima dell'upload o parsing;
- importazione classica priva di chiamate AI;
- compatibilità legacy coperta da test;
- nessuna modifica ai path o ai dati esistenti;
- diff e risultati dei test presentati prima della fase successiva.

## 10. Rollback

Il rollback della prima implementazione avviene tramite `git revert` del commit applicativo. Poiché la fase non migra dati e non cambia path, non è previsto rollback Firestore/Storage. Gli eventuali job v2 creati in Cantiere durante il collaudo devono essere inventariati e rimossi separatamente prima del rollback applicativo.

## 11. Fasi successive, non ancora autorizzate

### Completata localmente — Fase 2A

- rimossa la pulizia distruttiva pre-upload;
- contabilizzate le pagine PDF riconosciute e non riconosciute;
- zero DDT produce `failed_no_documents`, non un falso successo;
- nuovi punti, articoli, orari o pagine non riconosciute producono `awaiting_domain_review`;
- un'estrazione pulita produce `ready_for_certification`, non ancora `certified`.
- i profili DNR FRUTTA/LATTE leggono i punti e gli articoli dal Master Data canonico tenant-scoped; il matching usa `codice_esterno` filtrato per `sottocodice`.
- i tenant non ancora migrati mantengono una sorgente Master Data legacy dichiarata dal profilo, senza fallback automatico.

### Ancora non autorizzate

1. Comando e transazione di certificazione/sostituzione controllata.
2. Pulsante e workflow di importazione AI.
3. Ingestion profile versionati e configurabili da database.
4. Retention e cancellazione automatica del file certificato.
5. Hardening Security Rules e verifica cross-tenant tramite Emulator.

## 12. Approvazione richiesta

La prima implementazione locale ha introdotto il contratto v2 in `frontend/elaborazione.html`, la validazione fail-closed in `functions/services/pdf_service.py` e un modulo di contratto coperto da test. È richiesta approvazione separata prima di qualsiasi deploy o collaudo sul progetto Cantiere. Nessun deploy è stato eseguito.
