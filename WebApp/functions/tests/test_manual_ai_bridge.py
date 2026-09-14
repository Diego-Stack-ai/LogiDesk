import json
import unittest

from services.manual_ai_bridge import (
    BRIDGE_SCHEMA_VERSION,
    ManualBridgeValidationError,
    anonymize_rows,
    build_manual_prompt,
    validate_manual_response,
)


class ManualAiBridgeTests(unittest.TestCase):
    def test_anonymizes_sensitive_and_unknown_strings_stably(self):
        rows = [
            {
                "Ragione_Sociale": "Cliente Prova",
                "Indirizzo": "Via Roma 12",
                "Peso": 25.5,
                "Giro": "4512",
            }
        ]
        first = anonymize_rows(rows)
        second = anonymize_rows(rows)

        self.assertEqual(first, second)
        self.assertTrue(first[0]["Ragione_Sociale"].startswith("<RAGIONE_SOCIALE_"))
        self.assertTrue(first[0]["Indirizzo"].startswith("<INDIRIZZO_"))
        self.assertTrue(first[0]["Giro"].startswith("<VALORE_"))
        self.assertEqual(first[0]["Peso"], 25.5)

    def test_prompt_contains_contract_and_no_raw_sensitive_value(self):
        prompt = build_manual_prompt(
            file_name="giri.xlsx",
            source_kind="xlsx",
            sheets_or_sections=[{"name": "Riepilogo", "columns": ["Cliente"]}],
            sample_rows=[{"Cliente": "Nome riservato"}],
            company_id="azienda-test",
            tenant_id=None,
            work_date="2026-09-04",
        )

        self.assertIn(BRIDGE_SCHEMA_VERSION, prompt)
        self.assertNotIn("Nome riservato", prompt)
        self.assertIn("tenant_id", prompt)

    def test_validates_supported_mapping(self):
        response = json.dumps(
            {
                "schema_version": BRIDGE_SCHEMA_VERSION,
                "tipo_documento": "pianificazione_viaggi",
                "numero_giri_proposto": 3,
                "mapping": [
                    {
                        "campo_sorgente": "Codice Dest.",
                        "campo_logidesk": "codice_punto_committente",
                        "confidenza": 0.96,
                        "motivazione": "Codice univoco",
                    }
                ],
                "ambiguita": [],
                "campi_nuovi": [],
                "avvisi": ["Confermare il tenant"],
            }
        )

        validated = validate_manual_response(response)
        self.assertEqual(validated.proposed_trip_count, 3)
        self.assertEqual(validated.mappings[0]["campo_logidesk"], "codice_punto_committente")

    def test_rejects_unknown_canonical_field(self):
        response = json.dumps(
            {
                "schema_version": BRIDGE_SCHEMA_VERSION,
                "tipo_documento": "ddt",
                "numero_giri_proposto": 1,
                "mapping": [
                    {
                        "campo_sorgente": "Campo",
                        "campo_logidesk": "campo_inventato",
                        "confidenza": 0.5,
                    }
                ],
            }
        )

        with self.assertRaises(ManualBridgeValidationError):
            validate_manual_response(response)


if __name__ == "__main__":
    unittest.main()
