"""Contratto offline per il ponte manuale fra LogiDesk e un assistente esterno.

Il modulo non effettua chiamate di rete e non conosce credenziali ChatGPT.
Produce un pacchetto testuale copiabile e valida la risposta JSON restituita
manualmente dall'operatore. Nessun risultato validato viene salvato da qui.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping


BRIDGE_SCHEMA_VERSION = "logidesk.manual-ai-bridge/1.0"

CANONICAL_FIELDS = frozenset(
    {
        "tipo_documento",
        "data_viaggio",
        "numero_ddt",
        "codice_punto_committente",
        "denominazione_punto",
        "indirizzo",
        "numero_civico",
        "cap",
        "localita",
        "provincia",
        "telefono",
        "note_consegna",
        "orario_da",
        "orario_a",
        "codice_zona_originale",
        "codice_zona_logistica",
        "codice_articolo_committente",
        "codice_articolo_operativo",
        "descrizione_articolo",
        "lotto",
        "scadenza_da",
        "scadenza_a",
        "quantita",
        "unita_misura",
        "colli",
        "porzioni_per_collo",
        "peso",
        "giro_sorgente",
    }
)

_SENSITIVE_KEYS = {
    "codice_fiscale",
    "partita_iva",
    "email",
    "telefono",
    "cellulare",
    "nome",
    "cognome",
    "ragione_sociale",
    "denominazione",
    "indirizzo",
}

_CODE_BLOCK_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


class ManualBridgeValidationError(ValueError):
    """Risposta esterna non conforme al contratto LogiDesk."""


@dataclass(frozen=True)
class ValidatedBridgeResponse:
    document_type: str
    proposed_trip_count: int
    mappings: tuple[dict[str, Any], ...]
    ambiguities: tuple[dict[str, Any], ...]
    new_fields: tuple[dict[str, Any], ...]
    warnings: tuple[str, ...]


def _stable_placeholder(kind: str, value: Any) -> str:
    digest = hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:10]
    return f"<{kind.upper()}_{digest}>"


def anonymize_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    keep_keys: Iterable[str] = (),
    max_rows: int = 12,
) -> list[dict[str, Any]]:
    """Anonimizza un campione senza alterare forma, null e valori numerici.

    ``keep_keys`` deve essere scelto esplicitamente dal chiamante. Non rende
    automaticamente esportabili codici o dati commerciali.
    """

    keep = {str(key).strip().lower() for key in keep_keys}
    result: list[dict[str, Any]] = []
    for row_index, row in enumerate(rows):
        if row_index >= max_rows:
            break
        safe_row: dict[str, Any] = {}
        for raw_key, value in row.items():
            key = str(raw_key)
            normalized_key = key.strip().lower()
            if value is None or isinstance(value, (int, float, bool)):
                safe_row[key] = value
            elif normalized_key in keep:
                safe_row[key] = str(value)
            elif normalized_key in _SENSITIVE_KEYS:
                safe_row[key] = _stable_placeholder(normalized_key, value)
            else:
                safe_row[key] = _stable_placeholder("valore", value)
        result.append(safe_row)
    return result


def build_manual_prompt(
    *,
    file_name: str,
    source_kind: str,
    sheets_or_sections: Iterable[Mapping[str, Any]],
    sample_rows: Iterable[Mapping[str, Any]],
    company_id: str,
    tenant_id: str | None,
    work_date: str | None,
    operator_note: str = "",
    keep_sample_keys: Iterable[str] = (),
) -> str:
    """Genera il testo che l'operatore può copiare in ChatGPT gratuito."""

    if not company_id.strip():
        raise ValueError("company_id obbligatorio")

    payload = {
        "schema_version": BRIDGE_SCHEMA_VERSION,
        "source": {
            "file_name": file_name,
            "source_kind": source_kind,
            "sections": list(sheets_or_sections),
        },
        "context": {
            "company_id": company_id,
            "tenant_id": tenant_id,
            "work_date": work_date,
            "operator_note": operator_note.strip(),
        },
        "canonical_fields": sorted(CANONICAL_FIELDS),
        "sample_rows_anonymized": anonymize_rows(
            sample_rows, keep_keys=keep_sample_keys
        ),
    }

    response_shape = {
        "schema_version": BRIDGE_SCHEMA_VERSION,
        "tipo_documento": "string",
        "numero_giri_proposto": 0,
        "mapping": [
            {
                "campo_sorgente": "string",
                "campo_logidesk": "uno dei canonical_fields",
                "confidenza": 0.0,
                "motivazione": "string",
            }
        ],
        "ambiguita": [{"campo_sorgente": "string", "domanda": "string"}],
        "campi_nuovi": [
            {"campo_sorgente": "string", "utilita_proposta": "string"}
        ],
        "avvisi": ["string"],
    }

    return (
        "Sei un consulente di mappatura dati per LogiDesk. Analizza soltanto "
        "la rappresentazione anonimizzata seguente. Non inventare valori "
        "mancanti e non considerare le tue proposte già approvate. Evidenzia "
        "ogni ambiguità, specialmente date, numero di giri, codici composti, "
        "quantità e unità. Restituisci esclusivamente JSON valido nella forma "
        "richiesta.\n\nDATI LOGIDESK:\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + "\n\nFORMA RISPOSTA:\n"
        + json.dumps(response_shape, ensure_ascii=False, indent=2)
    )


def validate_manual_response(raw_response: str) -> ValidatedBridgeResponse:
    """Valida una risposta incollata; non applica né persiste il mapping."""

    cleaned = _CODE_BLOCK_RE.sub("", raw_response.strip()).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ManualBridgeValidationError("La risposta non è JSON valido") from exc

    if not isinstance(data, dict):
        raise ManualBridgeValidationError("La risposta deve essere un oggetto JSON")
    if data.get("schema_version") != BRIDGE_SCHEMA_VERSION:
        raise ManualBridgeValidationError("Versione del contratto non riconosciuta")

    document_type = data.get("tipo_documento")
    if not isinstance(document_type, str) or not document_type.strip():
        raise ManualBridgeValidationError("tipo_documento obbligatorio")

    trip_count = data.get("numero_giri_proposto")
    if not isinstance(trip_count, int) or isinstance(trip_count, bool) or trip_count < 0:
        raise ManualBridgeValidationError("numero_giri_proposto deve essere un intero >= 0")

    mappings = _require_object_list(data, "mapping")
    for index, mapping in enumerate(mappings):
        source = mapping.get("campo_sorgente")
        target = mapping.get("campo_logidesk")
        confidence = mapping.get("confidenza")
        if not isinstance(source, str) or not source.strip():
            raise ManualBridgeValidationError(f"mapping[{index}].campo_sorgente non valido")
        if target not in CANONICAL_FIELDS:
            raise ManualBridgeValidationError(f"mapping[{index}].campo_logidesk sconosciuto")
        if (
            not isinstance(confidence, (int, float))
            or isinstance(confidence, bool)
            or not 0 <= confidence <= 1
        ):
            raise ManualBridgeValidationError(f"mapping[{index}].confidenza non valida")

    return ValidatedBridgeResponse(
        document_type=document_type.strip(),
        proposed_trip_count=trip_count,
        mappings=tuple(mappings),
        ambiguities=tuple(_require_object_list(data, "ambiguita")),
        new_fields=tuple(_require_object_list(data, "campi_nuovi")),
        warnings=tuple(_require_string_list(data, "avvisi")),
    )


def _require_object_list(data: Mapping[str, Any], key: str) -> list[dict[str, Any]]:
    value = data.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ManualBridgeValidationError(f"{key} deve essere una lista di oggetti")
    return value


def _require_string_list(data: Mapping[str, Any], key: str) -> list[str]:
    value = data.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ManualBridgeValidationError(f"{key} deve essere una lista di stringhe")
    return value
