import unittest
from unittest.mock import MagicMock
import os
import tempfile
import shutil

from scripts.migrations.core_v1.m5_delivery_points_write import M5DeliveryPointsWrite, REQUIRED_PROJECT, REQUIRED_COMPANY, REQUIRED_TENANT

class TestM5Write609(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.args = MagicMock()
        self.args.project = REQUIRED_PROJECT
        self.args.company_id = REQUIRED_COMPANY
        self.args.tenant_id = REQUIRED_TENANT
        self.args.execute = False
        self.args.verify_existing = False
        self.args.resume = False
        self.temp_dir = tempfile.mkdtemp()
        self.args.output_dir = self.temp_dir
        
        def mock_doc(path):
            doc = MagicMock()
            if "m5" in path:
                doc.get.return_value.exists = False
            else:
                doc.get.return_value.exists = True
                doc.get.return_value.to_dict.return_value = {
                    "status": "COMPLETE",
                    "company_id": REQUIRED_COMPANY,
                    "project_id": REQUIRED_PROJECT
                }
            return doc
            
        self.db.document.side_effect = mock_doc
        
        self.db.collection.return_value.limit.return_value.get.return_value = []
        
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
        
    def test_preflight(self):
        audit = M5DeliveryPointsWrite(self.db, self.args)
        audit.run()
        
        self.assertEqual(len(audit.target_payloads), 609)
        self.assertEqual(audit.target_payloads[0]["codice_punto"], "DP000001")
        self.assertEqual(audit.target_payloads[-1]["codice_punto"], "DP000609")
        
        self.assertTrue(audit.manifest["GATE_SOURCE_COUNT_453"])
        self.assertTrue(audit.manifest["GATE_TARGET_COUNT_609"])
        self.assertTrue(audit.manifest["GATE_CHUNK_PLAN_VALID"])
        self.assertEqual(audit.target_state, "CLEAN_START")
        
        self.assertEqual(len(audit.chunk1), 305)
        self.assertEqual(len(audit.chunk2), 304)

    def test_execute_clean_start(self):
        self.args.execute = True
        self.args.confirm_shadow_write = "LOGIDESK_M5_DNR_609"
        
        audit = M5DeliveryPointsWrite(self.db, self.args)
        try:
            audit.run()
        except SystemExit as e:
            print("SystemExit:", e)
            print("Manifest non-True gates:", [k for k, v in audit.manifest.items() if v is not True])
            raise
        self.assertEqual(self.db.batch.call_count, 2)
        
    def test_static_write_safety(self):
        with open("scripts/migrations/core_v1/m5_delivery_points_write.py", "r") as f:
            code = f.read()
        self.assertNotIn(".set(", code)
        self.assertNotIn(".delete(", code)
        
if __name__ == '__main__':
    unittest.main()
