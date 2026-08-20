import unittest
from unittest.mock import MagicMock
import os
import tempfile
import shutil

from scripts.migrations.core_v1.m5_delivery_points_live_audit import M5DeliveryPointsLiveAudit, REQUIRED_PROJECT, REQUIRED_COMPANY, REQUIRED_TENANT

class TestM5LiveAudit(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.args = MagicMock()
        self.args.project = REQUIRED_PROJECT
        self.args.company_id = REQUIRED_COMPANY
        self.args.tenant_id = REQUIRED_TENANT
        self.temp_dir = tempfile.mkdtemp()
        self.args.output_dir = self.temp_dir
        
        # M3 Registry mock
        reg = MagicMock()
        reg.exists = True
        reg.to_dict.return_value = {
            "status": "COMPLETE",
            "users": {"user1": {"canonical_path": "path/user1"}}
        }
        self.db.document.return_value.get.return_value = reg
        
        # Legacy source mock
        doc1 = MagicMock()
        doc1.id = "p1"
        doc1.to_dict.return_value = {"cliente": "Mario", "verificato_da": "user1"}
        
        doc2 = MagicMock()
        doc2.id = "p2"
        doc2.to_dict.return_value = {"cliente": "Luigi", "consegna_frutta": "true", "consegna_latte": "true", "verificato_da": "qtQWKWaJRMZNv0UzhOETC0t2hdU2"}
        
        self.db.collection.return_value.stream.return_value = [doc1, doc2]
        
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
        
    def test_audit_run(self):
        audit = M5DeliveryPointsLiveAudit(self.db, self.args)
        audit.run()
        
        self.assertEqual(audit.stats["source_count"], 2)
        # 1:1 mapping now. Total = 2.
        self.assertEqual(audit.stats["target_expected_count"], 2)
        self.assertTrue(audit.manifest["GATE_SOURCE_DISCOVERED"])
        self.assertTrue(audit.manifest["GATE_VERIFIER_MAPPING_COMPLETE"])

if __name__ == '__main__':
    unittest.main()
