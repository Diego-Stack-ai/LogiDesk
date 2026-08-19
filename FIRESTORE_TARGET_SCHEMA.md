# LOGIDESK FIRESTORE TARGET SCHEMA (CORE V1)
Ultimo aggiornamento: Agosto 2026

## 1. RADICE MULTI-AZIENDA
Tutto il dominio LogiDesk e racchiuso sotto la root:
`/aziende/{azienda_id}`
- **Strategia ID**: AUTO_ID generato da Firestore.
- **Campi**: nome, ragione_sociale, partita_iva, attiva, created_at

## 2. ASSET AZIENDALI (COMPANY_SCOPED)
### 2.1 UTENTI
`/aziende/{azienda_id}/utenti/{uid}`
- **ID**: Firebase Auth uid
- **Campi**: attivo, ruolo_id, dipendente_id, tenant_access_mode (ALL / SELECTED), tenant_ids (array), created_at

### 2.2 DIPENDENTI
`/aziende/{azienda_id}/dipendenti/{dipendente_id}`
- **ID**: AUTO_ID
- **Campi**: nome, cognome, codice_fiscale, ruolo_hr, attivo

### 2.3 MEZZI
`/aziende/{azienda_id}/mezzi/{mezzo_id}`
- **ID**: AUTO_ID (La targa puo cambiare)
- **Campi**: targa, modello, portata, attivo

### 2.4 MAGAZZINI AZIENDALI
`/aziende/{azienda_id}/magazzini/{magazzino_id}`
- **ID**: AUTO_ID
- **Campi**: nome, indirizzo, lat, lon, tipo (PROPRIO, AFFITTO, HUB), attivo

### 2.5 COSTI (PERSONALE E FLOTTA)
`/aziende/{azienda_id}/costi_personale/{id}`
`/aziende/{azienda_id}/costi_flotta/{id}`
- **ID**: AUTO_ID
- **Campi**: riferimento_id, mese, importo, tipo

### 2.6 PRESENZE (INCLUSO nel Core V1)
`/aziende/{azienda_id}/presenze/{id}`
- **ID**: AUTO_ID
- **Campi**: dipendente_id, data, mezzo_id, ore, tenant_id

### 2.7 CONFIGURAZIONE (RUOLI E CAPABILITY)
`/aziende/{azienda_id}/config/ruoli_capabilities`
- **Campi**: Mappa per ruolo es. amministratore: ['manage_users', 'manage_tenants']

## 3. DOMINIO TENANT (TENANT_SCOPED)
`/aziende/{azienda_id}/tenants/{tenant_id}`
- **ID**: AUTO_ID
- **Campi Base**: nome, codice_esterno, attivo
- **Capabilities (Embedded Map)**: ddt_digitale, routing_ottimizzato, split_pdf_ddt
- **Fatturazione (Embedded Map)**: metodo_fatturazione, prezzo_viaggio

### 3.1 PUNTI DI CONSEGNA
`/aziende/{azienda_id}/tenants/{tenant_id}/punti_consegna/{punto_id}`
- **ID**: AUTO_ID
- **Campi**: codice_esterno, nome, indirizzo, lat, lon, zona
- **Finestre**: finestre_consegna: { mattina: {da, a}, pomeriggio: {da, a} }
- **Associazione**: associazione: { linked_point_id, rule: 'RESTRICTIVE_WINDOW' }

### 3.2 MAGAZZINI TENANT
`/aziende/{azienda_id}/tenants/{tenant_id}/magazzini/{magazzino_id}`
- **ID**: AUTO_ID
- **Campi**: nome, indirizzo, lat, lon
