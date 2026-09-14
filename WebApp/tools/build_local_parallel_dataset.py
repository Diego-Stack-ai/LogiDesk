"""Genera archivi locali paralleli, senza accesso a Firebase o Storage."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader

FUNCTIONS_DIR = Path(__file__).resolve().parents[1] / "functions"
sys.path.insert(0, str(FUNCTIONS_DIR))
from services.document_ingestion import extract_ddt  # noqa: E402


def dump(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()

    points: dict[tuple[str, str], dict] = {}
    articles: dict[tuple[str, str, str], dict] = {}
    travel_notes: list[dict] = []
    processed = []

    for path in sorted(args.source.glob("DDT *.pdf")):
        # Associazione esplicita derivata dal nome/famiglia campione concordata;
        # non è un fallback applicativo.
        tenant_id = "DNR"
        reader = PdfReader(str(path))
        processed.append({"file": path.name, "tenant_id": tenant_id, "pages": len(reader.pages)})
        for page_number, page in enumerate(reader.pages, 1):
            data = extract_ddt(page.extract_text() or "")
            source = {"file": path.name, "page": page_number, "numero_ddt": data["numero_ddt"]}
            code = data["codice_punto_committente"]
            if code:
                key = (tenant_id, code.upper())
                candidate = points.setdefault(key, {
                    "tenant_id": tenant_id, "codice_punto_committente": code,
                    "denominazione_punto": data["denominazione_punto"], "indirizzo": data["indirizzo"],
                    "cap": data["cap"], "localita": data["localita"], "provincia": data["provincia"],
                    "telefono": data["telefono"], "referente": data["referente"],
                    "status": "LOCAL_CANDIDATE_NOT_PERSISTED", "sources": [],
                })
                candidate["sources"].append(source)
            if data["orario_operativo_raw"]:
                travel_notes.append({
                    "tenant_id": tenant_id, "codice_punto_committente": code,
                    "data_ddt": data["data_ddt"], "numero_ddt": data["numero_ddt"],
                    "tipo": "ORARIO_OPERATIVO_DA_CODICE_ZONA",
                    "valore_originale": data["orario_operativo_raw"],
                    "valore_proposto": data["orario_operativo_proposto"],
                    "master_update_allowed": False, "status": "OPERATOR_REVIEW_REQUIRED",
                    "source": source,
                })
            for article in data["articoli"]:
                base = article["codice_articolo_committente"]
                operational = article["codice_articolo_operativo"] or ""
                key = (tenant_id, base, operational)
                candidate = articles.setdefault(key, {
                    "tenant_id": tenant_id, **article,
                    "status": "LOCAL_CANDIDATE_NOT_PERSISTED", "occurrences": 0, "sources": [],
                })
                candidate["occurrences"] += 1
                candidate["sources"].append(source)

    generated_at = datetime.now(timezone.utc).isoformat()
    point_rows = sorted(points.values(), key=lambda item: (item["tenant_id"], item["codice_punto_committente"]))
    article_rows = sorted(articles.values(), key=lambda item: (item["tenant_id"], item["codice_articolo_committente"], item["codice_articolo_operativo"] or ""))
    dump(args.destination / "punti_consegna" / "proposte.json", point_rows)
    dump(args.destination / "note_viaggio" / "proposte.json", travel_notes)
    dump(args.destination / "articoli" / "proposte.json", article_rows)
    manifest = {
        "mode": "LOCAL_PARALLEL_DATASET_NO_PERSISTENCE", "generated_at": generated_at,
        "source_files": processed, "counts": {"punti_consegna": len(point_rows), "note_viaggio": len(travel_notes), "articoli": len(article_rows)},
        "firebase_reads": 0, "firebase_writes": 0, "storage_writes": 0,
    }
    dump(args.destination / "manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
