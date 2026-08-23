# M4 WAREHOUSES MIGRATION AUDIT (UPDATED: RECONCILIATION)

## 1. M4 SCOPE
- **M4_ID**: M4
- **M4_NAME**: Magazzini
- **Source Assumption**: `root/magazzini_sedi`, `clienti/{tenant}/magazzini_sedi`
- **Real Live Source Found**: `clienti/DNR/fatturazione_magazzini_sedi` and various `clienti/DNR/fatturazione_navette_*` collections.
- **Dataset Nature**: Configuration strings for UI dropdowns, NOT Canonical Warehouse Entities.

## 2. DISCOVERY LIVE FIRESTORE
- The original assumed collections (`root/magazzini_sedi`) do not exist or are empty.
- The actual data feeding the UI (e.g. `window.appData.lista_magazzini_sedi`) is sourced dynamically from `clienti/DNR/fatturazione_magazzini_sedi`.

## 3. DATA STRUCTURE
- Documents in `fatturazione_magazzini_sedi` contain a single primary field: `{ nome: "..." }`.
- They are UI/billing configuration values managed directly from `fatturazione_clienti.html` via `aggiungiNuovaAnagrafica` and `eliminaAnagrafica`.

## 4. CROSS REFERENCES & LIVE RECONCILIATION
- `lista_magazzini_sedi` appears in 18 codebase references (primarily as an in-memory array for UI population).
- `fatturazione_magazzini_sedi` appears in 6 references (Firestore collection path).
- All 20 "live reference samples" observed previously were merely reading/writing these string values for the UI or attaching them as text to other documents.

## 5. M4 NECESSITY & RELATION TO M5
- **M4 Dataset Status**: `CONFIGURATION_ONLY`
- There are no genuine "Warehouse" business entities (with addresses, coordinates, configurations) in the legacy system.
- Therefore, there is NO canonical warehouse dataset to migrate.
- **M4 Migration**: `NOT REQUIRED` (Autonomy as a migration phase is unjustified, this data should be handled during M5 Punti Consegna or left as UI Config).
- **M5 Relation**: M5 (Punti Consegna) may or may not depend on these strings, but it does NOT depend on a discrete M4 Warehouse entity. `M5_DEPENDS_ON_M4 = FALSE`.
