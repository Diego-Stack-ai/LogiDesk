# M3 IDENTITY MIGRATION AUDIT (DIPENDENTI / UTENTI)

## 1. SOURCE DISCOVERY
- `root/dipendenti` is the main legacy collection.
- Firebase Auth contains the identities.

## 2. DOCUMENT COUNTS
- **Legacy Dipendenti Count**: 45
- **Legacy User Doc Count**: 0 (no separate `utenti` collection)
- **Firebase Auth User Count**: 42

## 3. IDENTITY MODEL
- **Document ID Model**: MIXED (Some use Firebase UID, some use AUTO_ID).
- **Employee Only**: 5
- **User Only**: 2
- **Employee and User**: 40

## 4. AUTH LINKAGE
- **Explicit Links (uid field)**: 40
- **No Auth Account**: 5
- **Ambiguous Link**: 0

## 5. EMAIL AUDIT
- **Missing Email**: 5 (Employees without account)
- **Duplicate Email**: 0

## 6. ROLE & PERMISSION MODEL
- **Roles Found**: `[amministratore, autista, impiegata, fornitore]`
- **Role Source**: Document field `ruolo`.
- **Permissions**: Global configuration in `permessi_dashboard`.

## 7. DEPENDENCIES
- **M5 (Punti Consegna)**: `verificato_da` uses name or UID. Requires canonical user mapping.
- **M6 (Presenze)**: Uses dipendente `doc.id`.
- **M7 (Costi)**: Uses dipendente `doc.id`.

## 8. CANONICAL STRATEGY
- **Utente ID**: Firebase Auth UID (Guarantees 1:1 with Auth).
- **Dipendente ID**: AUTO_ID (Decoupled from Auth, enables employees without access).

## 9. BLOCKERS
- None currently identified.

## 10. DRY-RUN READINESS
- **SAFE TO DESIGN M3 DRY RUN**: TRUE.
