# M6 SETTINGS SCOPE CERTIFICATION (M6A & M6B)

## 1. STRATEGIA DI NORMALIZZAZIONE (SPLIT M6A / M6B)
Il dominio Settings (Impostazioni) presenta una natura ibrida tra configurazioni deterministiche (Global e Tenant) e configurazioni di fatturazione legacy (clienti_fatturazione) che soffrono di ownership non deterministica, duplicati e incoerenze strutturali.

Per non bloccare l'evoluzione del sistema, l'isolamento dal legacy è diviso in due tranche:
* **M6A**: Core Settings deterministici e Import Mappings. (PRONTO PER DRY-RUN)
* **M6B**: Disambiguazione e riconciliazione di clienti_fatturazione. (REVIEW PENDING - POSTICIPATO)

## 2. M6A: CORE SETTINGS (SCOPE E TARGET)

L'ambito M6A è rigorosamente limitato a 47 documenti sorgente accertati.

### 2.1 COMPANY SETTINGS (3 Documenti)
Path Target: ziende/{company_id}/settings/{domain}

| Source Path | Target Domain | Action / Field Classification |
|---|---|---|
| config/permessi_dashboard | permissions | **MIGRATE**. Configura accessi per pagina e operazione basati sui ruoli. Non duplica dati identitari M3. |
| config/system_status | system | **MIGRATE**. Configurazione globale di sistema (es. array dmins). |
| config/email_settings | mail | **MIGRATE_MINUS_SECRETS**. Vengono migrati i parametri SMTP/IMAP (imap_host, smtp_host, mail_user, etc.). Il campo mail_password (1 secret field) sarà DROPPATO dal payload in chiaro e richiederà una futura esternalizzazione su Secret Manager. |

### 2.2 TENANT SETTINGS (3 Documenti)
Path Target: ziende/{company_id}/tenants/{tenant_id}/settings/{domain}

| Legacy Tenant | Core Tenant ID | Target Domain | Field Classification |
|---|---|---|---|
| DNR | AgvcnbuUMu7YhzSuUKTY | illing | 	ariffa_ddt, 	ipo_fatturazione, 	ariffa_viaggio_una_tantum (Tutti i field sono BILLING. Nessuno split necessario). |
| GRAN CHEF | UZC65YbnIbXsei88xNBX | illing | 	ipo_fatturazione, 	ariffa_viaggio |
| CATTEL | SomOWB7pieGNej2KdJA | illing | 	ariffa_patente_c, 	ipo_fatturazione, 	ariffa_patente_b |

*Nota: I tenant BAUER e DAC non presentano file listino legacy e non riceveranno documenti mock vuoti.*

### 2.3 IMPORT MAPPINGS (41 Documenti)
Path Target: ziende/{company_id}/tenants/AgvcnbuUMu7YhzSuUKTY/import_mappings/{id}

La collection legacy clienti/DNR/codici articoli (41 record) viene migrata 1:1 come import_mappings associata al tenant DNR.
* **Strategia ID**: PRESERVE_SOURCE_ID (Gli ID, es. 10-AT-01, sono codici articolo reali usati dai parser PDF per il matching, generare un UUID causerebbe la rottura del motore di importazione).

## 3. M6B: CLIENTI FATTURAZIONE (FUORI SCOPE)

I 14 record presenti in clienti_fatturazione contengono mismatch di nomenclatura (es. GRAN CHEF vs BENCARNI), owner unresolved e duplicati. 
* **Write Autorizzato**: FALSE
* **Status**: DEFERRED_REVIEW_REQUIRED

La loro riconciliazione e migrazione saranno oggetto di un intervento M6B dedicato per non contaminare i settings deterministici.

## 4. RELAZIONE CON I DRIVER (M7 DEFERRED)

L'audit ha confermato che M3 Identity è **COMPLETE** (25 utenti/dipendenti migrati 1:1 rispetto allo schema concordato).
Tuttavia, i campi operativi per l'esecuzione del runtime (es. uolo, 	ipoTurno, patente, codice_fiscale, in_presenze, ecc.) non sono stati inclusi nel payload M3 per rispettare il Foundation Schema.
Pertanto, sarà necessaria una successiva migrazione **M7** dedicata ad estendere M3 o a creare record HR/Driver operativi. I Driver Fields **non** sono Settings globali.

## 5. STATO TARGET ATTUALE
Il target candidate si presenta come **CLEAN_START**. Non ci sono collisioni.
M6A è pronto per la fase di progettazione DRY RUN.
