# Collaudo campioni ingestion — 2026-09-04

Modalità: `READ_ONLY_DRY_RUN`. Nessuna scrittura Firestore o Storage.

## Esito verificato

- 15 file censiti: 4 Excel, 10 PDF e 1 immagine.
- DDT Frutta: 90 pagine, 90 DDT e 90 punti di consegna strutturalmente completi; 133 occorrenze articolo.
- DDT Latte: 58 pagine, 58 DDT e 58 punti di consegna strutturalmente completi; 179 occorrenze articolo.
- Test puntuale `FNS17765`: il codice zona originale `D4110` resta integro; agente `D` e zona logistica `4110` sono campi distinti.
- `ReportPianificazione.xlsx`: quattro fogli; tre fogli-giro e un `Riepilogo`. La scelta fra fogli analitici e riepilogo richiede conferma dell'operatore.
- Tre Excel `OrdineCarico_Ragg` condividono la stessa struttura candidata e richiedono una prima mappatura certificata.
- Otto PDF giro appartengono a famiglie strutturali riconoscibili, ma non sono ancora certificati come parser di punti di consegna.
- L'immagine di un foglio Excel richiede OCR e controllo operatore.

## Valutazione per punti di consegna

I 148 DDT digitali sono tecnicamente idonei a produrre una **proposta** di confronto con i punti di consegna del committente. Non sono ancora autorizzati alla scrittura: prima servono confronto read-only con l'anagrafica Firebase Dev, risoluzione dei record `NEW/MODIFIED/AMBIGUOUS` e approvazione umana campo per campo.

Gli Excel e i PDF giro possono alimentare la stessa pipeline dopo la certificazione del mapping della rispettiva struttura. Un file con firma variata torna sempre in revisione e non usa automaticamente il parser precedente.

## Limiti del collaudo

- Il confronto remoto Firebase Dev non è stato eseguito dal terminale perché non sono presenti credenziali ADC locali. La pagina applicativa lo esegue in sola lettura tramite l'utente autenticato.
- Ollama `0.33.3` è installato. È stato collaudato il modello locale già presente `qwen3.5:9b`: nove mapping coerenti, una corretta ambiguità sulla fascia oraria e contratto valido dopo un solo tentativo di riparazione formale. Tempo CPU osservato: circa 55 secondi. Questo collaudo usa intestazioni anonime e non sostituisce i parser deterministici.
- Nessun profilo è marcato `CERTIFIED`: la transizione richiede revisione umana e regressione completa superata.

## Confronto reale a tre vie — 2026-09-05

Sono stati confrontati in locale, sugli stessi DDT, il parser attuale dell'app,
il parser deterministico candidato e `qwen3.5:9b`:

- `FNS17765` (Latte): i tre sistemi concordano sui sei campi principali del
  punto. AI e candidato aggiungono telefono e referente. Il candidato rileva
  sei righe articolo; l'AI ne rileva cinque, perde una seconda occorrenza e
  associa erroneamente un codice articolo al record `10-GEL`. L'AI conserva
  `D4110` ma interpreta erroneamente `H10` come zona e non ricava `07:30`.
- `FNS62295` (Frutta): concordanza sui dati principali, telefono, referente e
  articolo, incluso il codice operativo spezzato `7-3-250526`. L'AI conserva
  `D3110` ma scambia `745` per codice agente e perde zona `3110` e orario
  `07:45`.

Conclusione: l'AI locale è utile per scoprire campi e interpretare descrizioni,
ma non è certificabile come estrattore autonomo di codici zona, orari e
occorrenze articolo. Questi elementi devono essere vincolati da regole
deterministiche e test di regressione. Tutti gli output restano privati sotto
`test-data/ingestion-private/derived/comparisons`; scritture remote zero.
