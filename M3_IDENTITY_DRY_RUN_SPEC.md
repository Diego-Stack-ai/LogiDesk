# M3 IDENTITY DRY-RUN SPEC

## 1. SOURCE & TARGET
- **Company ID**: `NzXaCgyXxZWWehw1tSlo`
- **Employee Source**: `root/dipendenti` (26 docs)
- **User Source**: Firebase Auth (24 users)
- **Employee Target**: `aziende/{company_id}/dipendenti/{legacy_document_id}`
- **User Target**: `aziende/{company_id}/utenti/{firebase_uid}`
- **Registry Path**: `system_migrations/core_v1_m3_identity`

## 2. ID STRATEGY
- **Employee ID**: PRESERVE_LEGACY_DOC_ID. We preserve the legacy document ID to prevent massive foreign key rewrites in M6 (Presenze) and M7 (Costi Personale).
- **User ID**: Firebase Auth UID.

## 3. CANONICAL MODELS
### Employee Model
```json
{
  "nome": "string",
  "cognome": "string",
  "telefono": "string",
  "attivo": "boolean (false only if legacy is exactly False)",
  "schema_version": 1
}
```

### User Model
```json
{
  "uid": "string",
  "email": "string",
  "ruolo": "string (preserved exactly as legacy)",
  "attivo": "boolean (same as employee)",
  "schema_version": 1,
  "dipendente_id": "string (legacy_document_id)"
}
```

## 4. RESOLUTION POLICIES
- **Role Policy**: `PRESERVE_ROLE_AS_IS` (autista, impiegata, fornitore, soel, amministratore).
- **Active Mapping**: `(legacy_attivo === false) ? false : true`.
- **Duplicate IDs**: Preserve both `Ws6G1rYXMpPPHEydxa3VkgJ4Weg2` and `jDA7dUlEYEQ3XGDlGPh0gvm3vHb2` as distinct identities. Log warning in registry.
- **Test Record**: Exclude `qtQWKWaJRMZNv0UzhOETC0t2`.

## 5. MAPPING AND DEPENDENCIES
- **M5 Verifier**: Resolvable via M3 mapping.
- **M6/M7 References**: No translation needed since we preserve the legacy `doc.id`.

## 6. VALIDATION GATES
- EXPECTED_EMPLOYEE_TARGET_COUNT = 25
- EXPECTED_USER_TARGET_COUNT = 24
- AUTH_LINKAGE = 24/24

## 7. DRY-RUN EXPECTED OUTPUT
- `M3_IDENTITY_DRYRUN_SUMMARY.json`
- `M3_EMPLOYEES_TARGET_PREVIEW.json`
- `M3_USERS_TARGET_PREVIEW.json`
- `M3_IDENTITY_MAPPING_REGISTRY_PREVIEW.json`
- `M3_IDENTITY_REVIEW_REQUIRED.json`
- `M3_IDENTITY_FIELD_COVERAGE.json`
- `M3_IDENTITY_VALIDATION_MANIFEST.json`
