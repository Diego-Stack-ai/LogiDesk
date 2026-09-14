import json
import unittest

from services.local_ai_agent import propose_mapping
from services.manual_ai_bridge import BRIDGE_SCHEMA_VERSION


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


class LocalAiAgentTests(unittest.TestCase):
    def test_validates_local_model_response(self):
        proposal = {
            "schema_version": BRIDGE_SCHEMA_VERSION,
            "tipo_documento": "lista_consegne",
            "numero_giri_proposto": 1,
            "mapping": [{
                "campo_sorgente": "Codice cliente",
                "campo_logidesk": "codice_punto_committente",
                "confidenza": 0.95,
            }],
            "ambiguita": [], "campi_nuovi": [], "avvisi": [],
        }
        opener = lambda *_args, **_kwargs: _Response({"model": "qwen3.5:9b", "response": json.dumps(proposal)})
        result = propose_mapping("prompt", opener=opener)
        self.assertEqual(result.proposal.proposed_trip_count, 1)

    def test_rejects_non_local_endpoint(self):
        with self.assertRaisesRegex(ValueError, "loopback"):
            propose_mapping("prompt", endpoint="https://example.test/api")

    def test_repairs_one_invalid_response(self):
        invalid = {"schema_version": BRIDGE_SCHEMA_VERSION, "tipo_documento": "lista", "numero_giri_proposto": 1,
                   "mapping": [{"campo_sorgente": "Pr.", "campo_logidesk": "provincia", "confienza": 0.8}],
                   "ambiguita": [], "campi_nuovi": [], "avvisi": []}
        valid = {**invalid, "mapping": [{"campo_sorgente": "Pr.", "campo_logidesk": "provincia", "confidenza": 0.8}]}
        responses = iter([_Response({"response": json.dumps(invalid)}), _Response({"response": json.dumps(valid)})])
        result = propose_mapping("prompt", opener=lambda *_args, **_kwargs: next(responses))
        self.assertEqual(result.proposal.mappings[0]["campo_logidesk"], "provincia")


if __name__ == "__main__":
    unittest.main()
