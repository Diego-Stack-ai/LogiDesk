import unittest
import argparse
from unittest.mock import MagicMock, patch
from scripts.migrations.core_v1.m3_identity_write import M3IdentityWrite
from scripts.migrations.core_v1.m3_identity_dry_run import REQUIRED_COMPANY_ID, TEST_RECORD_ID, DUPLICATES

class TestM3IdentityWrite(unittest.TestCase):
    def setUp(self):
        self.args = argparse.Namespace(
            project="log-solutions-cantiere",
            company_id=REQUIRED_COMPANY_ID,
            execute=False,
            confirm_shadow_write="",
            output_dir="./migration_output/m3_write",
            mock_auth=True
        )
        self.db = MagicMock()
        
        m0_doc = MagicMock(); m0_doc.exists = True; m0_doc.to_dict.return_value = {"status": "COMPLETE"}
        m2_doc = MagicMock(); m2_doc.exists = True; m2_doc.to_dict.return_value = {"status": "COMPLETE"}
        comp_doc = MagicMock(); comp_doc.exists = True
        
        m0_ref = MagicMock(); m0_ref.get.return_value = m0_doc
        m2_ref = MagicMock(); m2_ref.get.return_value = m2_doc
        comp_ref = MagicMock(); comp_ref.get.return_value = comp_doc
        
        self.reg_doc = MagicMock(exists=False)
        reg_ref = MagicMock(); reg_ref.get.return_value = self.reg_doc
        
        def doc_side_effect(path):
            if path == "system_migrations/core_v1_m0_m1": return m0_ref
            if path == "system_migrations/core_v1_m2_vehicles": return m2_ref
            if path == f"aziende/{REQUIRED_COMPANY_ID}": return comp_ref
            if path == "system_migrations/core_v1_m3_identity": return reg_ref
            
            ref = MagicMock()
            ref.get.return_value = MagicMock(exists=False)
            return ref
            
        self.db.document.side_effect = doc_side_effect
        self.auth = MagicMock()
        
        # Mocks for streams
        def stream_mock():
            return []
            
        collection_mock = MagicMock()
        collection_mock.stream = stream_mock
        
        def collection_side_effect(path):
            if path == f"aziende/{REQUIRED_COMPANY_ID}/dipendenti":
                return collection_mock
            if path == f"aziende/{REQUIRED_COMPANY_ID}/utenti":
                return collection_mock
            # Default to dry-run employee mocks
            return self.create_legacy_stream()
            
        self.db.collection.side_effect = collection_side_effect

    def create_legacy_stream(self, num_auth_canonical=23, num_emp_only=2, include_test_auth=True):
        employees = []
        auth_users = []
        
        for i in range(num_auth_canonical):
            uid = f"auth_uid_{i}"
            if i == 0: uid = DUPLICATES[0]
            if i == 1: uid = DUPLICATES[1]
            data = {"nome": f"Nome {i}", "attivo": True, "uid": uid, "email": f"test{i}@test.com", "ruolo": "autista", "password": "secret"}
            employees.append({"id": uid, "data": data})
            
            user_mock = MagicMock()
            user_mock.uid = uid
            user_mock.email = f"test{i}@test.com"
            auth_users.append(user_mock)
            
        for i in range(num_emp_only):
            employees.append({"id": f"emp_{i}", "data": {"nome": f"Emp Only {i}", "attivo": False, "ruolo": "impiegata"}})
            
        employees.append({"id": TEST_RECORD_ID, "data": {"nome": "Diego Test", "attivo": False}})
        if include_test_auth:
            user_mock = MagicMock()
            user_mock.uid = TEST_RECORD_ID
            user_mock.email = "test@test.com"
            auth_users.append(user_mock)
            
        collection_mock = MagicMock()
        def stream_mock():
            for e in employees:
                d = MagicMock()
                d.id = e["id"]
                d.to_dict.return_value = e["data"]
                yield d
        collection_mock.stream = stream_mock
        
        list_users_mock = MagicMock()
        list_users_mock.iterate_all.return_value = auth_users
        self.auth.list_users.return_value = list_users_mock
        
        return collection_mock

    def test_preflight_clean_start(self):
        mig = M3IdentityWrite(self.db, self.args, self.auth)
        mig.run()
        self.assertEqual(mig.target_state, "CLEAN_START")
        self.assertEqual(len(mig.write_plan), 49)
        self.assertEqual(mig.status, "PLANNED")
        
    def test_wrong_project_fails(self):
        self.args.project = "wrong-project"
        mig = M3IdentityWrite(self.db, self.args, self.auth)
        with self.assertRaises(SystemExit):
            mig.run()
            
    def test_wrong_company_fails(self):
        self.args.company_id = "wrong-company"
        mig = M3IdentityWrite(self.db, self.args, self.auth)
        with self.assertRaises(SystemExit):
            mig.run()
            
    def test_execute_wrong_token(self):
        self.args.execute = True
        self.args.confirm_shadow_write = "WRONG_TOKEN"
        mig = M3IdentityWrite(self.db, self.args, self.auth)
        with self.assertRaises(SystemExit):
            mig.run()
            
    def test_execute_success(self):
        self.args.execute = True
        self.args.confirm_shadow_write = "LOGIDESK_M3_IDENTITY"
        
        batch_mock = MagicMock()
        self.db.batch.return_value = batch_mock
        
        mig = M3IdentityWrite(self.db, self.args, self.auth)
        mig.run()
        
        self.assertEqual(mig.status, "EXECUTED")
        self.assertEqual(batch_mock.create.call_count, 49)
        batch_mock.commit.assert_called_once()
        
    def test_password_not_in_payload(self):
        mig = M3IdentityWrite(self.db, self.args, self.auth)
        mig.run()
        
        for w in mig.write_plan:
            self.assertNotIn("password", w["payload"])

if __name__ == '__main__':
    unittest.main()
