import unittest
from unittest.mock import MagicMock
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts.migrations.core_v1.m6a_settings_dry_run import M6ASettingsDryRun

class ArgsMock:
    def __init__(self):
        self.project = "log-solutions-cantiere"
        self.company_id = "NzXaCgyXxZWWehw1tSlo"
        self.output_dir = "tests/test_output_m6a"

class TestM6ADryRun(unittest.TestCase):
    def setUp(self):
        self.db_mock = MagicMock()
        self.args = ArgsMock()
        self.dry_run = M6ASettingsDryRun(self.db_mock, self.args)

    def test_m6a_dry_run_logic(self):
        self.dry_run.sources["company"] = [
            {"id": "permessi_dashboard", "path": "config/permessi_dashboard", "data": {"admin": True}},
            {"id": "system_status", "path": "config/system_status", "data": {"admins": ["uid1"]}},
            {"id": "email_settings", "path": "config/email_settings", "data": {"email_user": "test", "email_password": "secret_pass"}}
        ]
        self.dry_run.manifest["GATE_COMPANY_SOURCE_3"] = True
        
        self.dry_run.sources["tenant_listino"] = [
            {"legacy_tenant": "DNR", "core_tenant": "AgvcnbuUMu7YhzSuUKTY", "id": "listino", "path": "clienti/DNR/impostazioni/listino", "data": {"tariffa": 10}},
            {"legacy_tenant": "GRAN CHEF", "core_tenant": "UZC65YbnIbXsei88xNBX", "id": "listino", "path": "clienti/GRAN CHEF/impostazioni/listino", "data": {"tariffa": 20}},
            {"legacy_tenant": "CATTEL", "core_tenant": "bSomOWB7pieGNej2KdJA", "id": "listino", "path": "clienti/CATTEL/impostazioni/listino", "data": {"tariffa": 30}}
        ]
        self.dry_run.manifest["GATE_TENANT_LISTINO_SOURCE_3"] = True
        
        for i in range(41):
            self.dry_run.sources["import_mapping"].append({
                "legacy_tenant": "DNR", "core_tenant": "AgvcnbuUMu7YhzSuUKTY", "id": f"10-AT-{i}", "path": f"clienti/DNR/codici articoli/10-AT-{i}", "data": {"ratio": 1}
            })
        self.dry_run.manifest["GATE_IMPORT_MAPPING_SOURCE_41"] = True
        self.dry_run.manifest["GATE_SOURCE_COUNT_47"] = True
        self.dry_run.manifest["GATE_CLIENTI_FATTURAZIONE_ZERO"] = True
        
        self.dry_run.process_targets()
        self.dry_run.validate_targets()
        
        self.assertTrue(self.dry_run.manifest["GATE_COMPANY_TARGET_3"])
        self.assertTrue(self.dry_run.manifest["GATE_TENANT_SETTINGS_TARGET_3"])
        self.assertTrue(self.dry_run.manifest["GATE_IMPORT_MAPPING_TARGET_41"])
        self.assertTrue(self.dry_run.manifest["GATE_TOTAL_TARGET_47"])
        self.assertTrue(self.dry_run.manifest["GATE_EMAIL_SECRET_EXCLUDED"])
        
        email_payload = next(t["payload"] for t in self.dry_run.targets if t["source_id"] == "email_settings")
        self.assertNotIn("email_password", email_payload)
        
        self.assertTrue(self.dry_run.manifest["GATE_CLIENTI_FATTURAZIONE_ZERO"])
        self.assertTrue(self.dry_run.manifest["GATE_UNKNOWN_FIELD_ZERO"])
        self.assertTrue(self.dry_run.manifest["GATE_UNRESOLVED_OWNER_ZERO"])
        self.assertTrue(self.dry_run.manifest["GATE_TARGET_COLLISION_ZERO"])
        
        self.assertEqual(len(self.dry_run.targets), 47)
        self.assertEqual(len(self.dry_run.secret_audit["secret_fields_excluded"]), 1)

if __name__ == '__main__':
    unittest.main()
