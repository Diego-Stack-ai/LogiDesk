import unittest
from unittest.mock import MagicMock, patch
import os
import tempfile
import shutil
import json

from scripts.migrations.core_v1.m4_warehouses_live_audit import M4WarehousesLiveAudit, REQUIRED_PROJECT, REQUIRED_COMPANY

class TestM4WarehousesLiveAudit(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.args = MagicMock()
        self.args.project = REQUIRED_PROJECT
        self.args.company_id = REQUIRED_COMPANY
        self.temp_dir = tempfile.mkdtemp()
        self.args.output_dir = self.temp_dir
        
        # Mocks
        self.reg_doc = MagicMock()
        self.reg_doc.exists = True
        self.reg_doc.to_dict.return_value = {
            "status": "COMPLETE",
            "tenants": {
                "t1": {"legacy_name": "DNR", "canonical_id": "c_dnr"}
            }
        }
        
        self.db.document.return_value.get.return_value = self.reg_doc
        
        doc1 = MagicMock()
        doc1.id = "w1"
        doc1.to_dict.return_value = {"nome": "Magazzino 1", "indirizzo": "Via Roma 1"}
        doc1.reference.path = "magazzini_sedi/w1"
        
        self.db.collection.return_value.stream.return_value = [doc1]
        self.db.collection.return_value.limit.return_value.stream.return_value = [doc1]
        
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
        
    def test_run_success(self):
        audit = M4WarehousesLiveAudit(self.db, self.args)
        audit.run()
        
        self.assertEqual(audit.manifest["OVERALL_STATUS"], "PASS")
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, "M4_WAREHOUSES_VALIDATION_MANIFEST.json")))
        
    def test_invalid_project(self):
        self.args.project = "wrong-project"
        audit = M4WarehousesLiveAudit(self.db, self.args)
        with self.assertRaises(SystemExit):
            audit.run()
            
        self.assertEqual(audit.manifest["OVERALL_STATUS"], "FAIL")
        
    def test_missing_db(self):
        audit = M4WarehousesLiveAudit(None, self.args)
        with self.assertRaises(SystemExit):
            audit.run()

if __name__ == '__main__':
    unittest.main()
