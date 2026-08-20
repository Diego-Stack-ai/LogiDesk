import unittest
from unittest.mock import MagicMock, patch
import os
import tempfile
import shutil

from scripts.migrations.core_v1.m5_delivery_points_write import M5DeliveryPointsWrite, REQUIRED_PROJECT, REQUIRED_COMPANY, REQUIRED_TENANT

class TestM5DeliveryPointsWrite(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.args = MagicMock()
        self.args.project = REQUIRED_PROJECT
        self.args.company_id = REQUIRED_COMPANY
        self.args.tenant_id = REQUIRED_TENANT
        self.args.execute = False
        self.args.confirm_shadow_write = ""
        self.args.verify_existing = False
        self.temp_dir = tempfile.mkdtemp()
        self.args.output_dir = self.temp_dir
        
        def mock_doc(path):
            doc = MagicMock()
            if "m5" in path:
                doc.get.return_value.exists = False
            else:
                doc.get.return_value.exists = True
                doc.get.return_value.to_dict.return_value = {"status": "COMPLETE"}
            return doc
            
        self.db.document.side_effect = mock_doc
        
        # Target state clean (registry absent)
        self.db.collection.return_value.limit.return_value.stream.return_value = []
        
        # 453 Legacy Points
        mock_docs = []
        for i in range(453):
            d = MagicMock()
            d.id = f"L{i:03d}"
            d.to_dict.return_value = {"cliente": f"Test {i}"}
            mock_docs.append(d)
        
        self.db.collection.return_value.stream.return_value = mock_docs
        
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
        
    def test_preflight(self):
        audit = M5DeliveryPointsWrite(self.db, self.args)
        audit.run()
        
        self.assertEqual(len(audit.target_payloads), 453)
        self.assertEqual(audit.target_payloads[0]["canonical_id"], "DP000001")
        self.assertEqual(audit.target_payloads[-1]["canonical_id"], "DP000453")
        self.assertTrue(audit.manifest["GATE_SOURCE_COUNT_453"])
        self.assertTrue(audit.manifest["GATE_TARGET_EXPECTED_453"])
        self.assertTrue(audit.manifest["GATE_ATOMIC_PLAN_454"])
        self.assertEqual(audit.target_state, "CLEAN_START")
        
    def test_execute(self):
        self.args.execute = True
        self.args.confirm_shadow_write = "LOGIDESK_M5_DNR"
        
        audit = M5DeliveryPointsWrite(self.db, self.args)
        audit.run()
        
        # Batch should be called
        self.db.batch.assert_called_once()
        batch_mock = self.db.batch.return_value
        self.assertEqual(batch_mock.create.call_count, 454)
        batch_mock.commit.assert_called_once()
        
if __name__ == '__main__':
    unittest.main()
