# M5 DELIVERY POINTS LIVE RECONCILIATION AUDIT

## 1. SOURCE RECONCILIATION
- **Legacy Source**: `clienti/DNR/raccolta clienti`
- **Expected Legacy Source Count**: 453
- **Expected Canonical Target Count**: 453
- **Expansion Logic**: The previous expected target count of 609 was INVALIDATED. It was based on a stale assumption that points needed duplication for Frutta and Latte separately. In reality, a physical delivery point is a single location (1:1 mapping).

## 2. M3 VERIFIER BRIDGE (verificato_da)
A live audit script has been designed to resolve legacy `verificato_da` strings via the `system_migrations/core_v1_m3_identity` registry.
Classifications:
- `RESOLVED_CANONICAL_USER`: Maps directly to one of the 23 canonical users.
- `EMPLOYEE_ONLY_NO_USER`: Known employees without user accounts (e.g., `YS6bw0Wedla6Z1Px5bWsZy1om8z1`).
- `TEST_USER_REMOVED`: Legacy `qtQWKWaJRMZNv0UzhOETC0t2hdU2` (Requires manual review since the test identity was deleted).
- `NAME_BASED_LEGACY`: E.g. "Mario Rossi", unresolvable without manual mapping.
- `UNKNOWN_UID` / `EMPTY`: Unresolvable or missing data.

*(Actual numbers pending Cloud Shell ADC live execution of `scripts/migrations/core_v1/m5_delivery_points_live_audit.py`)*

## 3. ID STRATEGY
- **M5_ID_STRATEGY**: Deterministic Sequence Generation (`DP000001`, `DP000002`) based on lexicographical sort of legacy IDs.
- **Dry-run alias**: `SIM::{legacy_id}::SOTTOCODICE`
- **Fingerprint Model**: SHA256 of the transformed Canonical Payload excluding runtime metadata.

## 4. TENANT ISOLATION
- The script strictly targets the DNR tenant only. `NON_DNR_RECORD_COUNT` must equal 0. `DAC_RECORD_COUNT` must equal 0.

## 5. RUNTIME IMPACT
- **M5_RUNTIME_IMPACT**: NONE_SHADOW
- The legacy `raccolta clienti` collection and its associated frontend usages remain untouched. Target writes will strictly populate `aziende/{azienda_id}/tenants/{tenant_id}/punti_consegna`.
