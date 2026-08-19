# M5 DELIVERY POINT MIGRATION SPECIFICATION (DRY-RUN)

## 1. OBIETTIVO
Progettare la simulazione deterministica (dry-run) della trasformazione dei punti di consegna legacy (DNR) verso il Core Data Model V1.

## 2. MODELLO IDENTIFICATIVO E SEQUENCE
- **SIMULATED_POINT_ID**: `SIM::{legacy_doc_id}::FRUTTA` o `SIM::{legacy_doc_id}::LATTE`.
- **DRY_RUN_SEQUENCE_SORT_KEY**: Ordinamento lessicografico per `legacy_doc_id`.
- **DELIVERY_POINT_SEQUENCE**: Codici generati in RAM in ordine (DP000001, DP000002...).
- **ASSOCIATION_GROUP_ID**: `ASSOC::{legacy_doc_id}` per tracciare la parentela senza cicli bidirezionali mutabili.

## 3. ARCHITETTURA (ADAPTER PATTERN)
La logica deve essere separata in due layer:
1. **LegacyDNRAdapter**: Legge il doc legacy, normalizza campi (time, geocoding), risolve la regola Frutta/Latte/Dual, emette 1 o 2 `CanonicalDeliveryPointPayload`.
2. **CanonicalDeliveryPointTransformer**: Riceve payload agnostici e crea il record formale con validation standard e calcolo fingerprint (SHA256).

## 4. VALIDATION E OUTPUT FILES
Output generati (JSON locale):
- `M5_DNR_DRYRUN_SUMMARY.json` (Source: 453, Target: 609, Review Time: 4)
- `M5_DNR_TARGET_PREVIEW.json`
- `M5_DNR_MIGRATION_REGISTRY_PREVIEW.json`
- `M5_DNR_REVIEW_REQUIRED.json`
- `M5_DNR_VALIDATION_MANIFEST.json`

## 5. ESECUZIONE DRY-RUN
Lo script si trova in `scripts/migrations/core_v1/m5_delivery_points_dry_run.py`.
Deve essere lanciato ESCLUSIVAMENTE in modalita `--dry-run`:
```bash
python3 m5_delivery_points_dry_run.py \
  --project log-solutions-cantiere \
  --tenant DNR \
  --dry-run \
  --output-dir "$HOME/LOGIDESK_M5_DNR_DRYRUN"
```

**NOTA**: Questo script deve essere eseguito da Cloud Shell, sfruttando l'Application Default Credentials (ADC) dell'utente per l'accesso in sola lettura a Firestore.
