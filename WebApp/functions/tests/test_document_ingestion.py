import unittest

from services.document_ingestion import extract_ddt


SAMPLE = """
DDT n° FNS17765 del 28/05/2026
Luogo di destinazione: p1847
Ponso - Carlo Collodi
Via Rosselle 16a
35040 Ponso (PD)
CAUSALE DEL TRASPORTO: Consegna
D4110 H10 730
Cod. Articolo Descrizione
YO-CN-MN-04-
LB
Codice: 8008
Yogurt naturale bianco
FO-DI-AS-04-LV
Codice: 8009
SPECIALE 3 Asiago DOP
"""


class DocumentIngestionTests(unittest.TestCase):
    def test_preserves_full_zone_and_separates_agent(self):
        result = extract_ddt(SAMPLE)
        self.assertEqual(result["codice_zona_originale"], "D4110")
        self.assertEqual(result["codice_agente"], "D")
        self.assertEqual(result["codice_zona_logistica"], "4110")
        self.assertEqual(result["orario_operativo_raw"], "730")
        self.assertEqual(result["orario_operativo_proposto"], "07:30")

    def test_extracts_delivery_point_identity(self):
        result = extract_ddt(SAMPLE)
        self.assertEqual(result["numero_ddt"], "FNS17765")
        self.assertEqual(result["codice_punto_committente"], "p1847")
        self.assertEqual(result["cap"], "35040")
        self.assertEqual(result["provincia"], "PD")

    def test_joins_wrapped_article_code_and_keeps_operational_code(self):
        articles = extract_ddt(SAMPLE)["articoli"]
        self.assertEqual(articles[0]["codice_articolo_committente"], "YO-CN-MN-04-LB")
        self.assertEqual(articles[0]["codice_articolo_operativo"], "8008")
        self.assertEqual(articles[1]["codice_articolo_committente"], "FO-DI-AS-04-LV")
        self.assertEqual(articles[1]["codice_articolo_operativo"], "8009")

    def test_joins_wrapped_operational_code(self):
        sample = SAMPLE.replace("Codice: 8008", "Codice: 7-3-\n250526")
        self.assertEqual(extract_ddt(sample)["articoli"][0]["codice_articolo_operativo"], "7-3-250526")


if __name__ == "__main__":
    unittest.main()
