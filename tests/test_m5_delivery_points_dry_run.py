import unittest
import sys
import os
import json
import tempfile
import shutil

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
from scripts.migrations.core_v1.m5_delivery_points_dry_run import (
    is_legacy_null_code, 
    normalize_time, 
    normalize_coordinate,
    LegacyDNRAdapter,
    build_plan,
    write_output_files
)

class TestM5DryRun(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
        
    def test_build_and_write(self):
        documents = [
            ("doc1", "path/doc1", {
                "codice_frutta": "P123", "codice_latte": "p00000",
                "lat": "45.0", "lon": "9.0", "cliente": "Test 1"
            }),
            ("doc2", "path/doc2", {
                "codice_frutta": "P124", "codice_latte": "P456",
                "lat": "45.1", "lon": "9.1", "cliente": "Test 2"
            })
        ]
        plan = build_plan("test-project", "DNR", documents)
        self.assertEqual(plan["source_document_count"], 2)
        self.assertEqual(len(plan["targets"]), 3)
        self.assertEqual(plan["frutta_only_count"], 1)
        self.assertEqual(plan["dual_count"], 1)
        
        write_output_files(self.temp_dir, "test-project", "DNR", plan)
        
        files = os.listdir(self.temp_dir)
        self.assertIn("M5_DNR_DRYRUN_SUMMARY.json", files)
        self.assertIn("M5_DNR_TARGET_PREVIEW.json", files)
        self.assertIn("M5_DNR_MIGRATION_REGISTRY_PREVIEW.json", files)
        self.assertIn("M5_DNR_REVIEW_REQUIRED.json", files)
        self.assertIn("M5_DNR_VALIDATION_MANIFEST.json", files)
        
        with open(os.path.join(self.temp_dir, "M5_DNR_DRYRUN_SUMMARY.json")) as f:
            summary = json.load(f)
            self.assertEqual(summary["source_document_count"], 2)
            self.assertEqual(summary["simulated_target_count"], 3)

    def test_static_write_safety(self):
        with open("scripts/migrations/core_v1/m5_delivery_points_dry_run.py", "r") as f:
            code = f.read()
        self.assertNotIn(".set(", code)
        self.assertNotIn(".update(", code)
        self.assertNotIn(".create(", code)
        self.assertNotIn(".delete(", code)
        self.assertNotIn("batch.commit", code)
        self.assertNotIn("transaction.set", code)
        self.assertNotIn("transaction.update", code)
        self.assertNotIn("transaction.delete", code)

if __name__ == "__main__":
    unittest.main()
