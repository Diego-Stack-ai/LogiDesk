"""Smoke test anonimo dell'agente locale. Non legge né scrive Firebase."""

from __future__ import annotations

import json
import sys
from pathlib import Path

FUNCTIONS_DIR = Path(__file__).resolve().parents[1] / "functions"
sys.path.insert(0, str(FUNCTIONS_DIR))

from services.local_ai_agent import LocalAiProposalRejected, propose_mapping  # noqa: E402
from services.manual_ai_bridge import BRIDGE_SCHEMA_VERSION  # noqa: E402


def main() -> int:
    headers = ["Codice cliente", "Ragione Sociale", "Indirizzo", "Localita", "Pr.", "Colli", "Peso", "Note", "Fascia oraria"]
    prompt = f"""Restituisci SOLO JSON valido. Analizza intestazioni Excel anonimizzate: {headers}.
Schema obbligatorio: {{"schema_version":"{BRIDGE_SCHEMA_VERSION}","tipo_documento":"string","numero_giri_proposto":1,"mapping":[{{"campo_sorgente":"string","campo_logidesk":"string","confidenza":0.8,"motivazione":"string"}}],"ambiguita":[],"campi_nuovi":[],"avvisi":[]}}.
Campi ammessi: codice_punto_committente, denominazione_punto, indirizzo, localita, provincia, colli, peso, note_consegna, orario_da, orario_a. Ogni confidenza deve essere un numero JSON fra 0 e 1, mai testo o null. Non inventare valori e non scrivere dati."""
    try:
        result = propose_mapping(prompt)
    except LocalAiProposalRejected as exc:
        print(json.dumps({"status": "REJECTED_BY_CONTRACT", "reason": str(exc), "raw": json.loads(exc.raw_json), "writes_performed": 0}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps({
        "mode": "LOCAL_AI_DRY_RUN_NO_PERSISTENCE",
        "model": result.model,
        "document_type": result.proposal.document_type,
        "proposed_trip_count": result.proposal.proposed_trip_count,
        "mapped_fields": [item["campo_logidesk"] for item in result.proposal.mappings],
        "ambiguities": len(result.proposal.ambiguities),
        "writes_performed": 0,
        "elapsed_seconds": round((result.elapsed_ns or 0) / 1_000_000_000, 2),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
