import unittest

from services.route_sheet_ingestion import extract_route_sheet


class RouteSheetIngestionTests(unittest.TestCase):
    def test_extracts_route_and_distinguishes_customer_destination_codes(self):
        text = """| Autista F1-MIRA-VEN |\nData partenza   04/09/2026\nOra  part.  6:09\n    221273  | |Assemblatore\n------------------------------\n 30  |        |87118  SERVIZI RIUNITI MIRA SRL |\n    SF 390713 188163 SERVIZI RIUNITI MIRA S.R.L. |   95,972| | S F G |\n     |               VIA MARE MEDITERRANEO 28/2, |\n     |               MIRA                 VE |\n     |               Telefono : 0415600811 |\n     |               Apertura dalle 05:30 alle 07:00 |\n------------------------------"""
        result = extract_route_sheet([(1, text)])
        self.assertEqual(result["route_code"], "221273")
        self.assertEqual(result["departure_date"], "04/09/2026")
        self.assertEqual(len(result["stops"]), 1)
        stop = result["stops"][0]
        self.assertEqual(stop["customer_code"], "87118")
        self.assertEqual(stop["document_or_service_code"], "390713")
        self.assertEqual(stop["delivery_point_code"], "188163")
        self.assertEqual(stop["phone"], "0415600811")
        self.assertEqual(stop["service_flags"], ["S", "F", "G"])
