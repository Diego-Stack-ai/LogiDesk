import unittest
from unittest.mock import MagicMock
import os
import tempfile
import shutil
import json

from scripts.migrations.core_v1.m5_delivery_points_write import M5DeliveryPointsWrite, REQUIRED_PROJECT, REQUIRED_COMPANY, REQUIRED_TENANT

class TestM5WriteReporting(unittest.TestCase):
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

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_overall_status_execute_pass(self):
        audit = M5DeliveryPointsWrite(self.db, self.args)
        audit.manifest = {"GATE_1": True, "GATE_2": True}
        audit.write_reports(phase="EXECUTE")
        
        with open(os.path.join(self.temp_dir, "M5_609_EXECUTE_VALIDATION.json")) as f:
            data = json.load(f)
        self.assertEqual(data.get("OVERALL_STATUS"), "PASS")

    def test_overall_status_execute_fail(self):
        audit = M5DeliveryPointsWrite(self.db, self.args)
        audit.manifest = {"GATE_1": True, "GATE_2": False, "OVERALL_STATUS": "FAIL"}
        audit.write_reports(phase="EXECUTE")
        
        with open(os.path.join(self.temp_dir, "M5_609_EXECUTE_VALIDATION.json")) as f:
            data = json.load(f)
        self.assertEqual(data.get("OVERALL_STATUS"), "FAIL")

if __name__ == '__main__':
    unittest.main()
