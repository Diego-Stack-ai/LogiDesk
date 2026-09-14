"""Contratto comune dei due binari di ingestion, privo di persistenza."""

from __future__ import annotations

from typing import Any


SCHEMA_VERSION = "logidesk.ingestion-candidates/1.0"
PRODUCERS = {"CURRENT_APP_PARSER", "DETERMINISTIC_CANDIDATE", "LOCAL_AI"}


def validate_candidate_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    if bundle.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Versione contratto candidati non valida")
    if bundle.get("producer") not in PRODUCERS:
        raise ValueError("Producer non riconosciuto")
    context = bundle.get("context")
    if not isinstance(context, dict) or not context.get("tenant_id"):
        raise ValueError("tenant_id esplicito obbligatorio")
    if not context.get("source_file") or not context.get("source_page"):
        raise ValueError("Provenienza file/pagina obbligatoria")
    for group in ("delivery_points", "travel_notes", "articles"):
        if not isinstance(bundle.get(group), list):
            raise ValueError(f"{group} deve essere una lista")
    if bundle.get("writes_performed") != 0:
        raise ValueError("Il bundle di collaudo non può dichiarare scritture")
    return bundle
