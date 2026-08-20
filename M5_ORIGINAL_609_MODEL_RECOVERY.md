# M5 ORIGINAL 609 MODEL RECOVERY

## A. ORIGINAL BUSINESS RULE
DNR remains ONE tenant. FRUTTA and LATTE are source channels within that tenant. 
A physical location in the legacy dataset might have a code for Frutta, Latte, or both.
The original business rule defined that each REAL code implies a distinct operational delivery identity. 
Thus, a physical location with two distinct, real codes expands into TWO canonical points.

## B. PLACEHOLDER P00000 RULE
Values like `P00000`, `p00000`, `None`, `NaN`, `null`, `False`, or empty strings are considered `LEGACY_NULL_CODE`.
A `LEGACY_NULL_CODE` DOES NOT generate a canonical delivery point.
- REAL_FRUTTA + P00000 => 1 FRUTTA point
- P00000 + REAL_LATTE => 1 LATTE point
- REAL_FRUTTA + REAL_LATTE (distinct) => 2 canonical points

## C. SPLIT ALGORITHM (MATHEMATICS)
From the original `build_plan` execution:
- **FRUTTA_ONLY_COUNT**: 236 (generates 236 targets)
- **LATTE_ONLY_COUNT**: 61 (generates 61 targets)
- **BOTH_REAL_DIFFERENT_COUNT**: 156 (generates 312 targets)
- **BOTH_REAL_SAME_COUNT**: Not mapped automatically (raises `SAME_VALID_CODE_BOTH_FIELDS` error requiring review/policy).
- **NO_REAL_CODE_COUNT**: Not mapped automatically (raises `NO_VALID_CODE` error).

**TOTAL**: 236 + 61 + 312 = 609 TARGETS.

## D. EXACT CANONICAL FIELDS
The original adapter logic (`LegacyDNRAdapter`) generated the following exact canonical fields per point:
- `codice_punto` (e.g. DP000001)
- `codice_esterno` (mapped from the valid `codice_frutta` or `codice_latte`)
- `sottocodice` (mapped as `"FRUTTA"` or `"LATTE"`) - acting as sourceChannel.
- `nome` (from legacy `cliente`)
- `indirizzo`
- `cap`
- `citta`
- `provincia`
- `codice_zona`
- `geolocalizzazione` (`lat`, `lon`, `stato_verifica`, `verification_source`)
- `attivo` (True)
- `finestre_consegna` (Array of `{ "da": tmin, "a": tmax }`)
- `association_group_id` (e.g. `ASSOC::{legacy_doc_id}`) for dual points linking them without mutable bidirectionality.

## E. EXACT REMOVED LEGACY FIELDS
- `codice_frutta` (removed, replaced by `codice_esterno` and `sottocodice = "FRUTTA"`)
- `codice_latte` (removed, replaced by `codice_esterno` and `sottocodice = "LATTE"`)
- `tipo` (discarded as noise)
- `tipologia_grado` (discarded as noise)

## F. EXACT ID STRATEGY
- **STRATEGY**: Sequence Generation (`DP000001` through `DP000609`).
- **SORT KEY**: `(legacy_document_id, sottocodice)` to ensure deterministic ordering between split points from the same legacy document.

## G. EXACT FINGERPRINT & IDEMPOTENCY
- **Idempotency Key**: Not explicitly designed in dry-run, but implied as `CORE_V1::DELIVERY_POINT::DNR::{legacy_doc_id}::{sottocodice}`.
- **Fingerprint Model**: SHA256 of JSON payload including `legacy_doc_id`, `codice_esterno`, `sottocodice`, `nome`, `indirizzo`, `finestre_consegna`, `association_group_id`, `lat`, and `lon`.

## H. ORIGINAL COMMIT SHAs
- **Original Split Logic Commits**: 
  - `7a16840 docs: define DNR delivery point split and subcode model`
  - `8ee8435 docs: design M5 delivery point migration dry run`
  - `e90b8df feat: add M5 delivery point migration dry run`
  - `0c48715 fix: complete M5 Firestore read-only dry run`
- **Invalidation Commit**: 
  - `e561291 fix: finalize M5 live reconciliation` (and earlier `f45d212 feat: add M5 live reconciliation audit`).
- **Invalidation Reason**: AI assumption. The script incorrectly assumed a physical delivery point maps 1:1 regardless of operational channels, treating `consegna_frutta`/`consegna_latte` as boolean flags instead of distinct delivery identities. It was NOT user approved.

## I. MODEL COMPARISON
- **ORIGINAL_CORRECT_MODEL**: 453 legacy documents -> 609 canonical points (based on operational codes).
- **CURRENT_SUPERSEDED_453_MODEL**: 453 legacy documents -> 453 canonical points (merging operational codes, losing `codice_esterno` distinction). STATUS: `SUPERSEDED_PENDING_REWORK`.
