import unittest
from unittest.mock import MagicMock, patch
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'migrations', 'core_v1')))
import m6a_settings_write as write_script
import m6a_settings_dry_run as dry_run_script

class ArgsMock:
    def __init__(self, mode="PREFLIGHT"):
        self.project = "log-solutions-cantiere"
        self.company_id = "NzXaCgyXxZWWehw1tSlo"
        self.output_dir = "tests/test_output_m6a_write"
        self.execute = (mode == "EXECUTE")
        self.verify_existing = (mode == "VERIFY_EXISTING")
        self.confirm_shadow_write = "LOGIDESK_M6A_SETTINGS" if self.execute else None

class TestM6AWrite(unittest.TestCase):
    def setUp(self):
        self.db_mock = MagicMock()
        write_script.firebase_admin = None
        dry_run_script.firebase_admin = None

    def setup_writer(self, mode):
        self.args = ArgsMock(mode)
        self.writer = write_script.M6ASettingsWrite(self.db_mock, self.args)
        
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
        
        return self.writer

    def test_preflight_clean_start(self):
        writer = self.setup_writer("PREFLIGHT")
        
        doc_mock = MagicMock()
        doc_mock.exists = False
        self.db_mock.collection().document().get.return_value = doc_mock
        self.db_mock.document().get.return_value = doc_mock
        
        writer.run()
        self.assertTrue(writer.manifest["GATE_PRE_STATE_CLEAN"])
        self.assertEqual(writer.manifest["OVERALL_STATUS"], "PASS")

    def test_verify_existing_already_applied(self):
        writer = self.setup_writer("VERIFY_EXISTING")
        
        # Monkey patch discover_state
        def mock_discover_state():
            writer.target_state = "ALREADY_APPLIED"
            writer.manifest["GATE_PRE_STATE_CLEAN"] = False
            writer.manifest["GATE_STATE_ALREADY_APPLIED"] = True
        writer.discover_state = mock_discover_state
        
        writer.run()
        self.assertEqual(writer.manifest["OVERALL_STATUS"], "PASS")

    def test_verify_existing_clean_start(self):
        writer = self.setup_writer("VERIFY_EXISTING")
        
        # Monkey patch discover_state
        def mock_discover_state():
            writer.target_state = "CLEAN_START"
            writer.manifest["GATE_PRE_STATE_CLEAN"] = True
            writer.manifest["GATE_STATE_ALREADY_APPLIED"] = False
        writer.discover_state = mock_discover_state
        
        try:
            writer.run()
        except SystemExit:
            pass
            
        self.assertEqual(writer.manifest["OVERALL_STATUS"], "FAIL")

if __name__ == '__main__':
    unittest.main()
