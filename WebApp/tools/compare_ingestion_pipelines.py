"""Confronta parser app, parser candidato e AI locale senza accesso Firebase."""

from __future__ import annotations

import argparse
from collections import Counter
import importlib
import io
import json
import sys
import types
from pathlib import Path
from urllib.request import Request, urlopen

from pypdf import PdfReader, PdfWriter

FUNCTIONS_DIR = Path(__file__).resolve().parents[1] / "functions"
sys.path.insert(0, str(FUNCTIONS_DIR))
from services.document_ingestion import extract_ddt  # noqa: E402
from services.ingestion_candidate_contract import SCHEMA_VERSION, validate_candidate_bundle  # noqa: E402


def _load_legacy_parser():
    firebase_admin = types.ModuleType("firebase_admin")
    firebase_admin.firestore = types.SimpleNamespace()
    firebase_admin.storage = types.SimpleNamespace()
    sys.modules.setdefault("firebase_admin", firebase_admin)
    firebase_functions = types.ModuleType("firebase_functions")
    firebase_functions.https_fn = types.SimpleNamespace(CallableRequest=object)
    sys.modules.setdefault("firebase_functions", firebase_functions)
    firebase_setup = types.ModuleType("infrastructure.firebase_setup")
    firebase_setup.get_db = lambda: None
    firebase_setup.BUCKET_NAME = "unused-local-dry-run"
    sys.modules["infrastructure.firebase_setup"] = firebase_setup
    return importlib.import_module("services.pdf_service")._processa_pdf_core_logic


def _single_page(reader: PdfReader, page_index: int) -> bytes:
    writer = PdfWriter()
    writer.add_page(reader.pages[page_index])
    stream = io.BytesIO()
    writer.write(stream)
    return stream.getvalue()


def _legacy_bundle(raw: dict, tenant_id: str) -> dict:
    points = []
    for code, data in raw.get("nuovi_dati", {}).items():
        points.append({"tenant_id": tenant_id, "codice_punto_committente": code, "denominazione_punto": data.get("dest"),
                       "indirizzo": data.get("ind"), "cap": data.get("cap"), "localita": data.get("cit"),
                       "provincia": data.get("prov"), "orario_da": data.get("om"), "orario_a": data.get("oM")})
    notes = [{"codice_punto_committente": item.get("codice_consegna"), "codice_zona_logistica": item.get("zona")}
             for item in raw.get("deliveries", [])]
    articles = [{"codice_articolo_committente": code, **data} for code, data in raw.get("nuovi_articoli", {}).items()]
    return {"producer": "CURRENT_APP_PARSER", "delivery_points": points, "travel_notes": notes, "articles": articles}


def _candidate_bundle(data: dict, tenant_id: str) -> dict:
    point_fields = ("codice_punto_committente", "denominazione_punto", "indirizzo", "cap", "localita", "provincia", "telefono", "referente")
    point = {"tenant_id": tenant_id, **{key: data.get(key) for key in point_fields}}
    note = {key: data.get(key) for key in ("codice_punto_committente", "codice_zona_originale", "codice_agente", "codice_zona_logistica", "orario_operativo_raw", "orario_operativo_proposto")}
    return {"producer": "DETERMINISTIC_CANDIDATE", "delivery_points": [point], "travel_notes": [note], "articles": data["articoli"]}


def _ai_bundle(text: str, tenant_id: str, model: str) -> dict:
    schema = {"numero_ddt": None, "delivery_points": [{"codice_punto_committente": None, "denominazione_punto": None, "indirizzo": None,
              "cap": None, "localita": None, "provincia": None, "telefono": None, "referente": None}],
              "travel_notes": [{"codice_zona_originale": None, "codice_agente": None, "codice_zona_logistica": None,
              "orario_operativo_raw": None, "orario_operativo_proposto": None}],
              "articles": [{"codice_articolo_committente": None, "codice_articolo_operativo": None, "descrizione": None,
              "data_distribuzione": None, "scadenza_minima": None}], "ambiguities": []}
    prompt = (
        "Estrai fedelmente il DDT seguente. Restituisci esclusivamente JSON con questa struttura: "
        + json.dumps(schema, ensure_ascii=False)
        + ". Non inventare. Conserva D4110 intero, separa l'eventuale lettera agente dalla zona numerica, ricomponi codici spezzati su righe consecutive. "
        "L'orario vicino alla zona è solo candidato operativo del viaggio, non campo master.\n\nDDT:\n" + text
    )
    body = json.dumps({"model": model, "prompt": prompt, "stream": False, "think": False, "format": "json",
                       "keep_alive": "5m", "options": {"temperature": 0.0, "num_ctx": 8192, "num_predict": 1800}}).encode()
    request = Request("http://127.0.0.1:11434/api/generate", data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(request, timeout=420) as response:
        envelope = json.loads(response.read().decode())
    result = json.loads(envelope["response"])
    if not isinstance(result.get("delivery_points"), list) or not isinstance(result.get("articles"), list):
        raise ValueError("Risposta AI priva delle liste richieste")
    for point in result["delivery_points"]:
        point["tenant_id"] = tenant_id
    result["producer"] = "LOCAL_AI"
    result["model"] = envelope.get("model", model)
    result["elapsed_seconds"] = round(envelope.get("total_duration", 0) / 1_000_000_000, 2)
    return result


def _first(bundle: dict, group: str) -> dict:
    values = bundle.get(group, [])
    return values[0] if values else {}


def _compare(bundles: list[dict]) -> dict:
    fields = {"delivery_points": ["codice_punto_committente", "denominazione_punto", "indirizzo", "cap", "localita", "provincia", "telefono", "referente", "orario_da", "orario_a"],
              "travel_notes": ["codice_zona_originale", "codice_agente", "codice_zona_logistica", "orario_operativo_raw", "orario_operativo_proposto"]}
    rows = []
    for group, names in fields.items():
        for field in names:
            values = {bundle["producer"]: _first(bundle, group).get(field) for bundle in bundles}
            normalized = {str(value or "").strip().upper() for value in values.values()}
            rows.append({"group": group, "field": field, "values": values, "status": "EQUAL" if len(normalized) == 1 else "DIFFERENT"})
    rows.append({"group": "articles", "field": "record_count", "values": {bundle["producer"]: len(bundle.get("articles", [])) for bundle in bundles}, "status": "COUNT_COMPARISON"})
    candidate = next(bundle for bundle in bundles if bundle["producer"] == "DETERMINISTIC_CANDIDATE")
    ai = next(bundle for bundle in bundles if bundle["producer"] == "LOCAL_AI")
    pair = lambda item: (str(item.get("codice_articolo_committente") or "").upper(), str(item.get("codice_articolo_operativo") or "").upper())
    candidate_pairs = Counter(pair(item) for item in candidate["articles"])
    ai_pairs = Counter(pair(item) for item in ai["articles"])
    article_analysis = {
        "candidate_occurrences": sum(candidate_pairs.values()),
        "ai_occurrences": sum(ai_pairs.values()),
        "missing_from_ai": [{"codice_articolo_committente": key[0], "codice_articolo_operativo": key[1] or None, "occurrences": count}
                            for key, count in (candidate_pairs - ai_pairs).items()],
        "unexpected_from_ai": [{"codice_articolo_committente": key[0], "codice_articolo_operativo": key[1] or None, "occurrences": count}
                               for key, count in (ai_pairs - candidate_pairs).items()],
    }
    return {"mode": "THREE_WAY_LOCAL_DRY_RUN", "writes_performed": 0, "rows": rows, "article_analysis": article_analysis}


def _dump(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("ddt")
    parser.add_argument("output", type=Path)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--channel", choices=("FRUTTA", "LATTE"), required=True)
    parser.add_argument("--model", default="qwen3.5:9b")
    parser.add_argument("--reuse", action="store_true", help="Ricalcola il confronto dagli output locali esistenti")
    args = parser.parse_args()
    if args.reuse:
        bundles = [json.loads((args.output / name).read_text(encoding="utf-8")) for name in
                   ("current_app_parser.json", "deterministic_candidate.json", "local_ai.json")]
        context = {"tenant_id": args.tenant, "source_file": args.pdf.name, "source_page": 1, "numero_ddt": args.ddt}
        for bundle, name in zip(bundles, ("current_app_parser.json", "deterministic_candidate.json", "local_ai.json")):
            bundle.update({"schema_version": SCHEMA_VERSION, "context": context, "writes_performed": 0})
            validate_candidate_bundle(bundle)
            _dump(args.output / name, bundle)
        comparison = _compare(bundles)
        comparison.update({"source_file": args.pdf.name, "numero_ddt": args.ddt, "tenant_id": args.tenant})
        _dump(args.output / "comparison.json", comparison)
        print(json.dumps({"output": str(args.output), "reused": True,
                          "different_fields": sum(row["status"] == "DIFFERENT" for row in comparison["rows"]),
                          "article_analysis": comparison["article_analysis"], "writes_performed": 0}, ensure_ascii=False, indent=2))
        return 0
    reader = PdfReader(str(args.pdf))
    page_index = next((index for index, page in enumerate(reader.pages) if args.ddt.upper() in (page.extract_text() or "").upper()), None)
    if page_index is None:
        raise SystemExit(f"DDT {args.ddt} non trovato")
    text = reader.pages[page_index].extract_text() or ""
    legacy_raw = _load_legacy_parser()(_single_page(reader, page_index), args.channel, {}, {})
    bundles = [_legacy_bundle(legacy_raw, args.tenant), _candidate_bundle(extract_ddt(text), args.tenant), _ai_bundle(text, args.tenant, args.model)]
    context = {"tenant_id": args.tenant, "source_file": args.pdf.name, "source_page": page_index + 1, "numero_ddt": args.ddt}
    for bundle in bundles:
        bundle.update({"schema_version": SCHEMA_VERSION, "context": context, "writes_performed": 0})
        validate_candidate_bundle(bundle)
        _dump(args.output / f"{bundle['producer'].lower()}.json", bundle)
    comparison = _compare(bundles)
    comparison.update({"source_file": args.pdf.name, "source_page": page_index + 1, "numero_ddt": args.ddt, "tenant_id": args.tenant})
    _dump(args.output / "comparison.json", comparison)
    print(json.dumps({"output": str(args.output), "ddt": args.ddt, "page": page_index + 1,
                      "counts": {bundle["producer"]: {"points": len(bundle.get("delivery_points", [])), "notes": len(bundle.get("travel_notes", [])), "articles": len(bundle.get("articles", []))} for bundle in bundles},
                      "different_fields": sum(row["status"] == "DIFFERENT" for row in comparison["rows"]), "writes_performed": 0}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
