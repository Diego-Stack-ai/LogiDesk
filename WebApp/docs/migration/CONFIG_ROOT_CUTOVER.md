# CONFIG ROOT CUTOVER

## Obiettivo

Eliminare la raccolta Firestore root `config` senza perdere configurazioni e senza mantenere password in chiaro.

## Destinazioni canoniche

| Legacy | Target |
|---|---|
| `config/email_settings` | `aziende/{aziendaId}/settings/email` |
| `config/permessi_dashboard` | `aziende/{aziendaId}/settings/permissions` |
| `config/system_status` | `aziende/{aziendaId}/settings/system` |
| `config/cattel` | `aziende/{aziendaId}/tenants/{cattelTenantId}/configurazioni/integrazione` |

I primi tre target risultano già migrati. Il documento CATTEL conserva esclusivamente URL, username e il riferimento `CATTEL_PORTAL_PASSWORD`; la password reale deve vivere in Secret Manager.

## Segreti richiesti

- `EMAIL_PASSWORD`
- `CATTEL_PORTAL_PASSWORD`

Nessun valore dei due segreti deve essere scritto in Firestore, nel repository, nei log o nei manifest di migrazione.

## Sequenza

1. Eseguire `tools/migrate_config_cutover.py` in preflight.
2. Creare i due segreti nel progetto Cantiere senza inserirli nella riga di comando o nella cronologia della shell.
3. Eseguire la migrazione CATTEL con `--execute`.
4. Distribuire Functions, Hosting e regole Firestore nel progetto Cantiere.
5. Verificare permessi, amministratori, invio email e accesso al portale CATTEL.
6. Esportare i quattro documenti legacy.
7. Eliminare `config` root.
8. Verificare che nessun processo ricrei la raccolta.

## Gate di cancellazione

La raccolta root non può essere eliminata se manca uno dei due segreti, se una Function usa ancora `config`, se il documento CATTEL canonico non esiste o se i test applicativi non sono stati superati.
