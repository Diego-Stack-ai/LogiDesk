# LOGIDESK FIRESTORE TARGET SCHEMA (CORE V1)
Ultimo aggiornamento: Agosto 2026

## 1. RADICE MULTI-AZIENDA (M0)
Tutto il dominio LogiDesk e racchiuso sotto la root:
`/aziende/{azienda_id}`
- **Strategia ID**: AUTO_ID generato da Firestore. (Demo ID: `NzXaCgyXxZWWehw1tSlo`)
- **Campi Base**: `nome`, `attiva`, `schema_version`

## 2. ASSET AZIENDALI (COMPANY_SCOPED)
### 2.1 MEZZI (M2)
`/aziende/{azienda_id}/mezzi/{mezzo_id}`
- **ID**: AUTO_ID
- **Campi Base**: `targa`, `attivo`, `schema_version`, `tipo`, `marca`, `modello`, `portata`, `patente_richiesta`, `temperatura`, `note`, `immatricolazione`, `scadenza_revisione`, `scadenza_atp`, `scadenza_assicurazione`, `scadenza_tachigrafo`, `tessera_carburante`, `pin_tessera`, `storico_manutenzioni`, `proprietario`, `assicurazione`, `inUso`, `stato`
- **Campi Storage (Deferred)**: `fotoUrls`, `documentiUrls`, `copertinaUrl` (Migrati in fase successiva)
- **Owner**: Azienda (Non tenant)

### 2.2 UTENTI
`/aziende/{azienda_id}/utenti/{uid}`
- **ID**: Firebase Auth uid
- **Campi Base**: `uid`, `email`, `ruolo`, `attivo`, `schema_version`, `dipendente_id`

### 2.3 DIPENDENTI
`/aziende/{azienda_id}/dipendenti/{legacy_document_id}`
- **ID**: PRESERVED LEGACY DOC ID
- **Campi Base**: `nome`, `cognome`, `telefono`, `cellulare`, `attivo`, `schema_version`



### 2.4 MAGAZZINI AZIENDALI
`/aziende/{azienda_id}/magazzini/{magazzino_id}`
- **ID**: AUTO_ID
- **Campi Base**: `codice_punto` (interno sequenziale, es. DP000001), `codice_esterno`, `sottocodice` (es. FRUTTA/LATTE), `nome`, `indirizzo`, `cap`, `citta`, `provincia`, `codice_zona`, `note_anagrafiche`, `attivo`

### 2.5 COSTI (PERSONALE E FLOTTA)
`/aziende/{azienda_id}/costi_personale/{id}`
`/aziende/{azienda_id}/costi_flotta/{id}`
- **ID**: AUTO_ID
- **Campi Base**: `codice_punto` (interno sequenziale, es. DP000001), `codice_esterno`, `sottocodice` (es. FRUTTA/LATTE), `nome`, `indirizzo`, `cap`, `citta`, `provincia`, `codice_zona`, `note_anagrafiche`, `attivo`

### 2.6 PRESENZE (INCLUSO nel Core V1)
`/aziende/{azienda_id}/presenze/{id}`
- **ID**: AUTO_ID
- **Campi Base**: `codice_punto` (interno sequenziale, es. DP000001), `codice_esterno`, `sottocodice` (es. FRUTTA/LATTE), `nome`, `indirizzo`, `cap`, `citta`, `provincia`, `codice_zona`, `note_anagrafiche`, `attivo`

### 2.7 CONFIGURAZIONE (RUOLI E CAPABILITY)
`/aziende/{azienda_id}/config/ruoli_capabilities`
- **Campi Base**: `codice_punto` (interno sequenziale, es. DP000001), `codice_esterno`, `sottocodice` (es. FRUTTA/LATTE), `nome`, `indirizzo`, `cap`, `citta`, `provincia`, `codice_zona`, `note_anagrafiche`, `attivo`

## 3. DOMINIO TENANT (TENANT_SCOPED) (M1)
`/aziende/{azienda_id}/tenants/{tenant_id}`
- **ID**: AUTO_ID (e.g. DNR: `AgvcnbuUMu7YhzSuUKTY`)
- **Campi Base**: `nome`, `legacy_name`, `attivo`, `schema_version`
- **Configurazione Codici**: `{ sottocodice_attivo: bool, valori_ammessi: [...] }`
- **Capabilities (Embedded Map)**: Configurable per tenant
- **Fatturazione (Embedded Map)**: NON ANCORA MIGRATA (Futuro: metodo_fatturazione, prezzo_viaggio)

### 3.1 PUNTI DI CONSEGNA
`/aziende/{azienda_id}/tenants/{tenant_id}/punti_consegna/{punto_id}`
- **ID**: SEQUENTIAL_ID (es. DP000001)
- **Campi Base**: `codice_punto` (interno sequenziale, es. DP000001), `codice_esterno`, `nome`, `indirizzo`, `cap`, `citta`, `provincia`, `codice_zona`, `note_anagrafiche`, `attivo`
- **Campi Tenant Specifici (DNR)**: `codice_frutta`, `codice_latte`, `orario_min_frutta`, `orario_max_frutta`, `orario_min_latte`, `orario_max_latte`
- **Geolocalizzazione**: `geolocalizzazione: { lat, lon, stato_verifica (PENDING/OK/REJECTED/NEEDS_REVIEW), fonte, verificato_da, verificato_at }`
- **Finestre**: `finestre_consegna: [ { da: 'HH:MM', a: 'HH:MM' } ]` (Nessuna semantica mattina/pomeriggio obbligatoria)
- **Associazione**: associazione: { linked_point_id, rule: 'RESTRICTIVE_WINDOW' }

### 3.2 MAGAZZINI TENANT
`/aziende/{azienda_id}/tenants/{tenant_id}/magazzini/{magazzino_id}`
- **ID**: AUTO_ID
- **Campi Base**: `codice_punto` (interno sequenziale, es. DP000001), `codice_esterno`, `sottocodice` (es. FRUTTA/LATTE), `nome`, `indirizzo`, `cap`, `citta`, `provincia`, `codice_zona`, `note_anagrafiche`, `attivo`
