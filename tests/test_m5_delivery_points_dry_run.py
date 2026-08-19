import unittest
import sys
import os

# Aggiungi scripts path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
from scripts.migrations.core_v1.m5_delivery_points_dry_run import (
    is_legacy_null_code, 
    normalize_time, 
    normalize_coordinate,
    LegacyDNRAdapter,
    hash_target
)

class TestM5DryRun(unittest.TestCase):
    def test_null_codes(self):
        self.assertTrue(is_legacy_null_code("p00000"))
        self.assertTrue(is_legacy_null_code("P000000"))
        self.assertTrue(is_legacy_null_code("None"))
        self.assertTrue(is_legacy_null_code(""))
        self.assertFalse(is_legacy_null_code("P123"))

    def test_normalize_time(self):
        self.assertEqual(normalize_time("07:30"), "07:30")
        self.assertEqual(normalize_time("15:00"), "15:00")
        self.assertIsNone(normalize_time("false"))
        self.assertIsNone(normalize_time("False"))
        self.assertIsNone(normalize_time("NaN"))
        self.assertIsNone(normalize_time(""))
        self.assertIsNone(normalize_time("24:00")) # regex fail
        self.assertIsNone(normalize_time("09:99")) # regex fail

    def test_normalize_coordinate(self):
        self.assertEqual(normalize_coordinate("12.34"), 12.34)
        self.assertIsNone(normalize_coordinate("abc"))

    def test_adapter_frutta_only(self):
        adapter = LegacyDNRAdapter()
        data = {
            "codice_frutta": "P123",
            "codice_latte": "p00000",
            "lat": "45.0",
            "lon": "9.0",
            "orario_min_frutta": "08:00",
            "orario_max_frutta": "10:00"
        }
        res = adapter.parse("doc1", "path/doc1", data)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["sottocodice"], "FRUTTA")
        self.assertEqual(res[0]["finestre_consegna"][0]["da"], "08:00")
        
    def test_adapter_dual_code(self):
        adapter = LegacyDNRAdapter()
        data = {
            "codice_frutta": "P123",
            "codice_latte": "P456",
            "lat": "45.0",
            "lon": "9.0"
        }
        res = adapter.parse("doc2", "path/doc2", data)
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0]["sottocodice"], "FRUTTA")
        self.assertEqual(res[1]["sottocodice"], "LATTE")
        self.assertEqual(res[0]["association_group_id"], "ASSOC::doc2")
        self.assertEqual(res[1]["association_group_id"], "ASSOC::doc2")

    def test_adapter_same_code(self):
        adapter = LegacyDNRAdapter()
        data = {
            "codice_frutta": "P123",
            "codice_latte": "P123",
            "lat": "45.0",
            "lon": "9.0"
        }
        res = adapter.parse("doc3", "path/doc3", data)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["error"], "SAME_VALID_CODE_BOTH_FIELDS")
        
    def test_static_write_safety(self):
        with open("scripts/migrations/core_v1/m5_delivery_points_dry_run.py", "r") as f:
            code = f.read()
        self.assertNotIn(".set(", code)
        self.assertNotIn(".update(", code)
        self.assertNotIn(".create(", code)
        self.assertNotIn(".delete(", code)
        self.assertNotIn("batch.commit", code)

if __name__ == "__main__":
    unittest.main()
