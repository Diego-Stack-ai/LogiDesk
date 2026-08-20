import os
import sys
import unittest
import json
import tempfile
import subprocess
from unittest.mock import MagicMock, patch

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'migrations', 'core_v1'))
from m2_vehicles_dry_run import M2VehiclesDryRun, normalize_targa

class TestM2VehiclesDryRun(unittest.TestCase):
    def setUp(self):
        self.script_path = os.path.join(
            os.path.dirname(__file__), '..', 'scripts', 'migrations', 'core_v1', 'm2_vehicles_dry_run.py'
        )
        self.output_dir = tempfile.mkdtemp()

    def test_normalize_targa(self):
        self.assertEqual(normalize_targa(" ab 123 cd "), "AB 123 CD")
        self.assertEqual(normalize_targa(None), "")
        self.assertEqual(normalize_targa(""), "")

    def test_unauthorized_project(self):
        cmd = [
            "python", self.script_path,
            "--project", "wrong-project",
            "--company-id", "NzXaCgyXxZWWehw1tSlo",
            "--dry-run",
            "--output-dir", self.output_dir
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)

    def test_process_vehicles(self):
        db_mock = MagicMock()
        args = MagicMock()
        args.project = "log-solutions-cantiere"
        args.company_id = "NzXaCgyXxZWWehw1tSlo"
        args.output_dir = self.output_dir
        args.dry_run = True
        
        mig = M2VehiclesDryRun(db_mock, args)
        mig.legacy_data = [
            {"legacy_document_id": "v1", "legacy_data": {"targa": "AB123CD", "attivo": True, "tipo": "Furgone"}},
            {"legacy_document_id": "v2", "legacy_data": {"attivo": True}}, # Missing targa
            {"legacy_document_id": "v3", "legacy_data": {"targa": "ab123cd", "attivo": True}}, # Duplicate norm
            {"legacy_document_id": "v4", "legacy_data": {"targa": "XYZ999", "note": "..."}} # Missing attivo
        ]
        
        mig.audit_fields()
        mig.process_vehicles()
        mig.write_outputs()
        
        self.assertEqual(mig.stats["empty_targa_count"], 1)
        self.assertEqual(mig.stats["duplicate_targa_normalized_count"], 2)
        
        with open(os.path.join(self.output_dir, "M2_VEHICLES_VALIDATION_MANIFEST.json")) as f:
            manifest = json.load(f)
            
        self.assertEqual(manifest["overall_status"], "PASS_WITH_REVIEW")
        self.assertTrue(manifest["zero_write"])
        
    def test_static_write_safety(self):
        with open(self.script_path, 'r') as f:
            content = f.read()
            self.assertNotIn('.set(', content)
            self.assertNotIn('.update(', content)
            self.assertNotIn('.create(', content)
            self.assertNotIn('.delete(', content)
            self.assertNotIn('batch.commit', content)

if __name__ == "__main__":
    unittest.main()
