import os
import json
import subprocess
import tempfile
import unittest

class TestM0M1FoundationDryRun(unittest.TestCase):
    def setUp(self):
        self.script_path = os.path.join(
            os.path.dirname(__file__), '..', 'scripts', 'migrations', 'core_v1', 'm0_m1_foundation_dry_run.py'
        )
        self.output_dir = tempfile.mkdtemp()
        
    def test_dry_run_execution(self):
        cmd = [
            "python", self.script_path,
            "--project", "log-solutions-cantiere",
            "--dry-run",
            "--output-dir", self.output_dir
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, f"Script failed: {result.stderr}")
        
        # Verify files created
        summary_path = os.path.join(self.output_dir, "M0_M1_DRYRUN_SUMMARY.json")
        self.assertTrue(os.path.exists(summary_path))
        
        with open(summary_path) as f:
            summary = json.load(f)
            
        self.assertEqual(summary["company_preview_count"], 1)
        self.assertEqual(summary["tenant_preview_count"], 4)
        self.assertEqual(summary["company_name_status"], "REVIEW_REQUIRED")
        self.assertFalse(summary["dac_created_preview"])
        
        # Verify Tenants Preview
        tenants_path = os.path.join(self.output_dir, "M1_TENANTS_PREVIEW.json")
        with open(tenants_path) as f:
            tenants = json.load(f)
            
        self.assertEqual(len(tenants), 4)
        tenant_names = [t["data"]["nome"] for t in tenants]
        self.assertCountEqual(tenant_names, ["DNR", "CATTEL", "GRAN CHEF", "BAUER"])
        
        # Check DNR config
        dnr = next(t for t in tenants if t["data"]["nome"] == "DNR")
        self.assertTrue(dnr["data"]["configurazione_codici"]["sottocodice_attivo"])
        self.assertEqual(dnr["data"]["configurazione_codici"]["valori_ammessi"], ["FRUTTA", "LATTE"])
        
        # Check other configs
        for name in ["CATTEL", "GRAN CHEF", "BAUER"]:
            t = next(t for t in tenants if t["data"]["nome"] == name)
            self.assertFalse(t["data"]["configurazione_codici"]["sottocodice_attivo"])
            self.assertEqual(t["data"]["configurazione_codici"]["valori_ammessi"], [])
            
        # Verify registry and fingerprint
        registry_path = os.path.join(self.output_dir, "M0_M1_MIGRATION_REGISTRY_PREVIEW.json")
        with open(registry_path) as f:
            registry = json.load(f)
            
        self.assertEqual(len(registry), 5) # 4 tenants + 1 DAC
        dac = next(r for r in registry if r["legacy_name"] == "DAC")
        self.assertEqual(dac["status"], "PENDING_RECONCILIATION")
        self.assertIsNone(dac["target_preview_id"])
        
        # Verify unique preview IDs
        preview_ids = [r["target_preview_id"] for r in registry if r["target_preview_id"] is not None]
        self.assertEqual(len(preview_ids), len(set(preview_ids)))
        
        # Verify fingerprints are populated
        for r in registry:
            self.assertIsNotNone(r["fingerprint"])
            
        # Verify manifest
        manifest_path = os.path.join(self.output_dir, "M0_M1_VALIDATION_MANIFEST.json")
        with open(manifest_path) as f:
            manifest = json.load(f)
            
        self.assertEqual(manifest["overall_status"], "PASS_WITH_REVIEW")

if __name__ == "__main__":
    unittest.main()
