import unittest
from unittest.mock import MagicMock, patch
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'migrations', 'core_v1')))
import m6a_settings_write as write_script
import m6a_settings_dry_run as dry_run_script

class ArgsMock:
    def __init__(self):
        self.project = "log-solutions-cantiere"
        self.company_id = "NzXaCgyXxZWWehw1tSlo"
        self.output_dir = "tests/test_output_m6a_write"
        self.execute = False
        self.verify_existing = False
        self.confirm_shadow_write = None

class TestM6AWrite(unittest.TestCase):
    def setUp(self):
        self.db_mock = MagicMock()
        self.args = ArgsMock()
        
        write_script.firebase_admin = None
        dry_run_script.firebase_admin = None
        
        self.writer = write_script.M6ASettingsWrite(self.db_mock, self.args)

    def test_m6a_write_logic(self):
        self.writer.dry_run.sources["company"] = [
            {"id": "permessi_dashboard", "path": "config/permessi_dashboard", "data": {"admin": True}},
            {"id": "system_status", "path": "config/system_status", "data": {"admins": ["uid1"]}},
            {"id": "email_settings", "path": "config/email_settings", "data": {"email_user": "test", "email_password": "secret_pass"}}
        ]
        self.writer.dry_run.sources["tenant_listino"] = [
            {"legacy_tenant": "DNR", "core_tenant": "AgvcnbuUMu7YhzSuUKTY", "id": "listino", "path": "clienti/DNR/impostazioni/listino", "data": {"tariffa": 10}},
            {"legacy_tenant": "GRAN CHEF", "core_tenant": "UZC65YbnIbXsei88xNBX", "id": "listino", "path": "clienti/GRAN CHEF/impostazioni/listino", "data": {"tariffa": 20}},
            {"legacy_tenant": "CATTEL", "core_tenant": "bSomOWB7pieGNej2KdJA", "id": "listino", "path": "clienti/CATTEL/impostazioni/listino", "data": {"tariffa": 30}}
        ]
        
        for i in range(41):
            self.writer.dry_run.sources["import_mapping"].append({
                "legacy_tenant": "DNR", "core_tenant": "AgvcnbuUMu7YhzSuUKTY", "id": f"10-AT-{i}", "path": f"clienti/DNR/codici articoli/10-AT-{i}", "data": {"ratio": 1}
            })
            
        self.writer.dry_run.manifest["GATE_PROJECT"] = True
        self.writer.dry_run.manifest["GATE_COMPANY"] = True
        self.writer.dry_run.manifest["GATE_COMPANY_SOURCE_3"] = True
        self.writer.dry_run.manifest["GATE_TENANT_LISTINO_SOURCE_3"] = True
        self.writer.dry_run.manifest["GATE_IMPORT_MAPPING_SOURCE_41"] = True
        self.writer.dry_run.manifest["GATE_SOURCE_COUNT_47"] = True
        self.writer.dry_run.manifest["GATE_CLIENTI_FATTURAZIONE_ZERO"] = True
        self.writer.dry_run.manifest["GATE_UNKNOWN_FIELD_ZERO"] = True
        self.writer.dry_run.manifest["GATE_UNRESOLVED_OWNER_ZERO"] = True
        self.writer.dry_run.manifest["GATE_IDEMPOTENCY_UNIQUE"] = True
        self.writer.dry_run.manifest["GATE_FINGERPRINT_DETERMINISTIC"] = True
        self.writer.dry_run.manifest["GATE_TARGET_COLLISION_ZERO"] = True
        
        doc_mock = MagicMock()
        doc_mock.exists = False
        self.db_mock.collection().document().get.return_value = doc_mock
        self.db_mock.document().get.return_value = doc_mock
        
        self.writer.run()
        
        self.assertTrue(self.writer.manifest["GATE_COMPANY_TARGET_3"])
        self.assertTrue(self.writer.manifest["GATE_TENANT_SETTINGS_TARGET_3"])
        self.assertTrue(self.writer.manifest["GATE_IMPORT_MAPPING_TARGET_41"])
        self.assertTrue(self.writer.manifest["GATE_TOTAL_TARGET_47"])
        self.assertTrue(self.writer.manifest["GATE_EMAIL_PASSWORD_WRITE_ZERO"])
        
        self.assertTrue(self.writer.manifest["GATE_CLIENTI_FATTURAZIONE_ZERO"])
        self.assertTrue(self.writer.manifest["GATE_UNKNOWN_FIELD_ZERO"])
        self.assertTrue(self.writer.manifest["GATE_UNRESOLVED_OWNER_ZERO"])
        self.assertTrue(self.writer.manifest["GATE_TARGET_COLLISION_ZERO"])
        
        self.assertEqual(len(self.writer.targets), 47)
        self.assertEqual(self.writer.registry["target_count"], 47)
        self.assertEqual(self.writer.registry["status"], "PLANNED")

    def test_firebase_init_safety(self):
        with open('scripts/migrations/core_v1/m6a_settings_write.py', 'r') as f:
            content = f.read()
        self.assertNotIn('credentials.Certificate', content)
        self.assertNotIn('AppLogSolutionsWeb', content)
        self.assertNotIn('cantiere_key.json', content)
        self.assertIn('firebase_admin.initialize_app(options={"projectId": args.project})', content)
        self.assertIn('app.project_id != args.project', content)

if __name__ == '__main__':
    unittest.main()
