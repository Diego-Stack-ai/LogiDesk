# DIPENDENTI ROOT CUTOVER

## Obiettivo

Disattivare il percorso Firestore legacy:

`/dipendenti/{dipendente_id}`

e usare esclusivamente il percorso aziendale canonico:

`/aziende/NzXaCgyXxZWWehw1tSlo/dipendenti/{dipendente_id}`

Ambiente coinvolto: `log-solutions-cantiere`.

## Evidenze dati (30 agosto 2026)

- documenti nella raccolta legacy: `25`;
- documenti nella raccolta canonica: `25`;
- identificativi mancanti nel target canonico: `0`;
- identificativi aggiuntivi nel target canonico: `0`.

La verifica certifica la parita degli identificativi. La raccolta legacy non deve
essere cancellata prima del collaudo applicativo successivo al deploy.

## Cutover runtime

- `frontend/services/dipendentiService.js` legge il percorso restituito da
  `CompanyContext.getEmployeesPath()`;
- `frontend/services/realtime-sync.js` legge e scrive gia il percorso canonico;
- `frontend/core/auth-service.js` usa gia `CompanyContext.getEmployeesPath()`;
- la regola Firestore dedicata a `/dipendenti/{userId}` resta temporaneamente
  attiva durante il primo rilascio, per proteggere le sessioni frontend in cache;
- la regola per `/aziende/{companyId}/dipendenti/{dipendenteId}` resta attiva.

Le sottocollezioni denominate `dipendenti` appartenenti ad altri domini, ad esempio
`clienti/DNR/costi_personale/{mese}/dipendenti`, non sono la raccolta HR legacy e
sono fuori dal perimetro di questo cutover.

## Criteri per la cancellazione della raccolta legacy

La cancellazione di `/dipendenti` e consentita solo dopo:

1. deploy del nuovo Hosting su `log-solutions-cantiere`;
2. apertura e verifica della pagina Pianificazione;
3. verifica del caricamento degli autisti attivi;
4. verifica della pagina Impostazioni e del listener dipendenti;
5. ricerca finale senza lettori o scrittori runtime verso `/dipendenti`;
6. secondo rilascio con rimozione della regola Firestore legacy;
7. conferma esplicita dell'utente per la cancellazione.

## Rollback

- ripristinare il lettore legacy in `dipendentiService.js`;
- ripristinare la regola Firestore legacy dal commit precedente;
- eseguire deploy selettivi di Hosting e Firestore Rules esclusivamente su
  `log-solutions-cantiere`.

Il rollback Git non ripristina dati Firestore gia cancellati.
