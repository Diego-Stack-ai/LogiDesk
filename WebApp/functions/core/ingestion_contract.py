"""Validation helpers for the versioned ingestion entry contract."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping


CONTRACT_VERSION = "2.0"


@dataclass(frozen=True)
class ClassicImportProfile:
    tenant_id: str
    source_channel: str
    file_kind: str
    profile_id: str
    profile_version: int = 1
    master_data_source: str = "LEGACY"


CLASSIC_IMPORT_PROFILES: dict[str, ClassicImportProfile] = {
    "FRUTTA": ClassicImportProfile(
        "DNR", "FRUTTA", "PDF", "dnr-frutta-ddt-pdf", master_data_source="CANONICAL"
    ),
    "LATTE": ClassicImportProfile(
        "DNR", "LATTE", "PDF", "dnr-latte-ddt-pdf", master_data_source="CANONICAL"
    ),
    "GRAN_CHEF": ClassicImportProfile("GRAN CHEF", "ALTRO", "XLSX", "gran-chef-consegne-xlsx"),
    "CATTEL": ClassicImportProfile("CATTEL", "ALTRO", "XLSX", "cattel-consegne-xlsx"),
    "DAC": ClassicImportProfile("DAC", "ALTRO", "XLSX", "dac-consegne-xlsx"),
}


class IngestionContractError(ValueError):
    """Raised when a new ingestion job has an invalid or ambiguous context."""


def determine_ingestion_outcome(
    deliveries_count: int,
    new_delivery_points: int = 0,
    new_articles: int = 0,
    new_time_windows: int = 0,
    skipped_pages: int = 0,
) -> tuple[str, list[str]]:
    """Return the non-certified terminal state and its blocking reasons."""
    if deliveries_count <= 0:
        return "failed_no_documents", ["NO_DOCUMENTS_EXTRACTED"]

    reasons = []
    if new_delivery_points > 0:
        reasons.append("NEW_DELIVERY_POINTS")
    if new_articles > 0:
        reasons.append("NEW_ARTICLES")
    if new_time_windows > 0:
        reasons.append("NEW_TIME_WINDOWS")
    if skipped_pages > 0:
        reasons.append("UNRECOGNIZED_PAGES")

    if reasons:
        return "awaiting_domain_review", reasons
    return "ready_for_certification", []


def build_canonical_delivery_point_index(
    points: list[Mapping[str, Any]], source_channel: str
) -> dict[str, dict[str, Any]]:
    """Index canonical delivery points by the external code used in source files."""
    expected_channel = str(source_channel or "").strip().upper()
    indexed: dict[str, dict[str, Any]] = {}
    for point in points:
        point_channel = str(point.get("sottocodice") or "").strip().upper()
        if expected_channel != "ALTRO" and point_channel != expected_channel:
            continue

        external_code = str(point.get("codice_esterno") or "").strip().lower()
        if not external_code or external_code in {"p00000", "nan", "false"}:
            continue
        if external_code in indexed:
            raise IngestionContractError(
                f"Codice esterno duplicato nel canale {expected_channel}: {external_code}"
            )
        indexed[external_code] = dict(point)
    return indexed


def normalize_import_key(value: Any) -> str:
    key = str(value or "").strip().upper().replace("-", "_").replace(" ", "_")
    if key in {"GRAND_CHEF", "GRANCHEF"}:
        return "GRAN_CHEF"
    return key


def get_classic_import_profile(value: Any) -> ClassicImportProfile:
    key = normalize_import_key(value)
    try:
        return CLASSIC_IMPORT_PROFILES[key]
    except KeyError as exc:
        raise IngestionContractError(f"Sorgente di importazione non riconosciuta: {value!r}") from exc


def _require_text(job: Mapping[str, Any], field: str) -> str:
    value = job.get(field)
    if not isinstance(value, str) or not value.strip():
        raise IngestionContractError(f"{field} mancante o non valido.")
    return value.strip()


def validate_v2_job(job: Mapping[str, Any], request_tenant: Any) -> ClassicImportProfile:
    """Validate a classic v2 job without inventing tenant or channel values."""
    if job.get("contract_version") != CONTRACT_VERSION:
        raise IngestionContractError("Versione contratto ingestion non supportata.")

    tenant_id = _require_text(job, "tenantId")
    source_channel = _require_text(job, "sourceChannel")
    data_lavoro = _require_text(job, "data_lavoro")
    try:
        datetime.strptime(data_lavoro, "%d-%m-%Y")
    except ValueError as exc:
        raise IngestionContractError("data_lavoro non valida: formato atteso DD-MM-YYYY.") from exc

    if not isinstance(request_tenant, str) or not request_tenant.strip():
        raise IngestionContractError("tenant mancante nella richiesta.")
    if request_tenant.strip() != tenant_id:
        raise IngestionContractError("Il tenant della richiesta non coincide con il tenant del job.")

    classification = job.get("classification")
    if not isinstance(classification, Mapping):
        raise IngestionContractError("classification mancante o non valida.")
    if classification.get("mode") != "CLASSIC":
        raise IngestionContractError("Modalità ingestion non supportata da questo endpoint.")
    if classification.get("operatorConfirmedSource") is not True:
        raise IngestionContractError("La sorgente non è stata confermata dall'operatore.")

    profile = get_classic_import_profile(job.get("type"))
    if tenant_id != profile.tenant_id or source_channel != profile.source_channel:
        raise IngestionContractError("Combinazione tenant/canale non ammessa per la sorgente selezionata.")
    if classification.get("ingestionProfileId") != profile.profile_id:
        raise IngestionContractError("Profilo ingestion non coerente con la sorgente selezionata.")
    if classification.get("ingestionProfileVersion") != profile.profile_version:
        raise IngestionContractError("Versione del profilo ingestion non supportata.")

    actual_file_kind = "XLSX" if job.get("is_excel") is True else "PDF"
    if actual_file_kind != profile.file_kind:
        raise IngestionContractError("Formato file non coerente con il profilo ingestion.")

    source = job.get("source")
    if not isinstance(source, Mapping):
        raise IngestionContractError("Metadati source mancanti o non validi.")
    for field in ("originalFilename", "storagePath", "fileType"):
        _require_text(source, field)
    if source.get("storagePath") != job.get("storage_path"):
        raise IngestionContractError("storagePath non coerente con il percorso legacy del job.")

    return profile
