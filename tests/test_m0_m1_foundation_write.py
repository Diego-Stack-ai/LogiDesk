import os
import sys
import unittest
import json
import tempfile
import subprocess
from unittest.mock import MagicMock, patch

# Append path to import the script directly for some tests if needed
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'migrations', 'core_v1'))
from m0_m1_foundation_write import M0M1Migration

class TestM0M1FoundationWrite(unittest.TestCase):
    def setUp(self):
        self.script_path = os.path.join(
            os.path.dirname(__file__), '..', 'scripts', 'migrations', 'core_v1', 'm0_m1_foundation_write.py'
        )
        self.output_dir = tempfile.mkdtemp()

    def test_unauthorized_project(self):
        cmd = [
            "python", self.script_path,
            "--project", "wrong-project",
            "--output-dir", self.output_dir
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Unauthorized project", result.stdout)

    def test_execute_without_confirmation(self):
        cmd = [
            "python", self.script_path,
            "--project", "log-solutions-cantiere",
            "--execute",
            "--output-dir", self.output_dir
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("confirmation string", result.stdout)

    def test_preflight_clean_start(self):
        cmd = [
            "python", self.script_path,
            "--project", "log-solutions-cantiere",
            "--output-dir", self.output_dir
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        
        summary_path = os.path.join(self.output_dir, "M0_M1_WRITE_SUMMARY.json")
        with open(summary_path) as f:
            summary = json.load(f)
            
        self.assertEqual(summary["mode"], "PREFLIGHT")
        self.assertEqual(summary["state_classification"], "CLEAN_START")
        self.assertEqual(summary["document_count"], 6)
        self.assertEqual(summary["legacy_write_count"], 0)
        self.assertEqual(summary["punti_consegna_write_count"], 0)
        
        # Check that all gates passed
        self.assertTrue(all(summary["gates"].values()))
        
        rollback_path = os.path.join(self.output_dir, "M0_M1_ROLLBACK_MANIFEST.json")
        self.assertTrue(os.path.exists(rollback_path))

    @patch('m0_m1_foundation_write.firestore')
    def test_execute_already_applied(self, mock_firestore):
        # Mocking db interactions for ALREADY_APPLIED
        db_mock = MagicMock()
        mock_registry_doc = MagicMock()
        mock_registry_doc.exists = True
        mock_registry_doc.to_dict.return_value = {"status": "COMPLETE"}
        db_mock.document.return_value.get.return_value = mock_registry_doc
        
        args = MagicMock()
        args.project = "log-solutions-cantiere"
        args.execute = True
        args.output_dir = self.output_dir
        
        mig = M0M1Migration(db_mock, args)
        mig.run()
        
        self.assertEqual(mig.state_classification, "ALREADY_APPLIED")
        # Ensure batch operations were not called
        db_mock.batch.assert_not_called()

    @patch('m0_m1_foundation_write.firestore')
    def test_execute_partial_state(self, mock_firestore):
        db_mock = MagicMock()
        mock_registry_doc = MagicMock()
        mock_registry_doc.exists = True
        mock_registry_doc.to_dict.return_value = {"status": "PENDING"}
        db_mock.document.return_value.get.return_value = mock_registry_doc
        
        args = MagicMock()
        args.project = "log-solutions-cantiere"
        args.execute = True
        args.output_dir = self.output_dir
        
        mig = M0M1Migration(db_mock, args)
        mig.run()
        
        self.assertEqual(mig.state_classification, "PARTIAL_STATE")
        db_mock.batch.assert_not_called()

    def test_static_write_safety(self):
        # Read the script to ensure it doesn't contain forbidden paths
        with open(self.script_path, 'r') as f:
            content = f.read()
            self.assertNotIn('collection("clienti")', content)
            self.assertNotIn('collection("dipendenti")', content)
            self.assertNotIn('collection("mezzi")', content)
            self.assertNotIn('collection("presenze")', content)
            self.assertNotIn('collection("clienti_fatturazione")', content)
            self.assertNotIn('collection("punti_consegna")', content)
            # Only allowed paths: aziende, tenants, system_migrations
            # Check create-only lock pattern
            self.assertIn('.create(', content)

if __name__ == "__main__":
    unittest.main()
