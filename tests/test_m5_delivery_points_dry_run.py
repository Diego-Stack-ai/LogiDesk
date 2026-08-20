import unittest
from unittest.mock import MagicMock
import os
import tempfile
import shutil

from scripts.migrations.core_v1.m5_delivery_points_dry_run import M5DeliveryPointsDryRun, REQUIRED_PROJECT, REQUIRED_COMPANY, REQUIRED_TENANT, is_valid_external_code

class TestM5DryRun609(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.args = MagicMock()
        self.args.project = REQUIRED_PROJECT
        self.args.company_id = REQUIRED_COMPANY
        self.args.tenant_id = REQUIRED_TENANT
        self.args.dry_run = True
        self.temp_dir = tempfile.mkdtemp()
        self.args.output_dir = self.temp_dir
        
        mock_docs = []
        # Frutta only
        for i in range(236):
            d = MagicMock()
            d.id = f"F{i:03d}"
            d.to_dict.return_value = {"codice_frutta": f"F{i}", "codice_latte": "P00000", "cliente": f"Test {i}"}
            mock_docs.append(d)
            
        # Latte only
        for i in range(61):
            d = MagicMock()
            d.id = f"L{i:03d}"
            d.to_dict.return_value = {"codice_frutta": "", "codice_latte": f"L{i}", "cliente": f"Test {i}"}
            mock_docs.append(d)
            
        # Both
        for i in range(156):
            d = MagicMock()
            d.id = f"B{i:03d}"
            d.to_dict.return_value = {"codice_frutta": f"BF{i}", "codice_latte": f"BL{i}", "cliente": f"Test {i}"}
            mock_docs.append(d)
        
        self.db.collection.return_value.stream.return_value = mock_docs
        
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
        
    def test_placeholder_policy(self):
        self.assertFalse(is_valid_external_code(None))
        self.assertFalse(is_valid_external_code("p00000"))
        self.assertFalse(is_valid_external_code("P00000"))
        self.assertFalse(is_valid_external_code("False"))
        self.assertFalse(is_valid_external_code("NaN"))
        self.assertFalse(is_valid_external_code("null"))
        self.assertFalse(is_valid_external_code(""))
        self.assertTrue(is_valid_external_code("12345"))
        self.assertTrue(is_valid_external_code(12345))
        
    def test_preflight_609(self):
        audit = M5DeliveryPointsDryRun(self.db, self.args)
        audit.run()
        
        self.assertTrue(audit.manifest["GATE_SOURCE_COUNT_453"])
        self.assertTrue(audit.manifest["GATE_FRUTTA_ONLY_236"])
        self.assertTrue(audit.manifest["GATE_LATTE_ONLY_61"])
        self.assertTrue(audit.manifest["GATE_BOTH_REAL_156"])
        self.assertTrue(audit.manifest["GATE_TARGET_COUNT_609"])
        self.assertTrue(audit.manifest["GATE_FIRST_ID_DP000001"])
        self.assertTrue(audit.manifest["GATE_LAST_ID_DP000609"])
        self.assertTrue(audit.manifest["OVERALL_STATUS"] == "PASS")
        
        # Verify both from same legacy doc share assoc_group
        import json
        with open(os.path.join(self.temp_dir, "M5_DELIVERY_POINTS_609_TARGET_PREVIEW.json")) as f:
            targets = json.load(f)
            self.assertEqual(len(targets), 609)
            
            b000 = [t for t in targets if t["legacy_document_id"] == "B000"]
            self.assertEqual(len(b000), 2)
            self.assertEqual(b000[0]["association_group_id"], "ASSOC::B000")
            self.assertEqual(b000[1]["association_group_id"], "ASSOC::B000")
            self.assertNotEqual(b000[0]["sottocodice"], b000[1]["sottocodice"])

if __name__ == '__main__':
    unittest.main()
