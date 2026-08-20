import unittest
import argparse
from unittest.mock import MagicMock, patch
from scripts.migrations.core_v1.m3_identity_dry_run import M3IdentityDryRun, REQUIRED_COMPANY_ID, TEST_RECORD_ID, DUPLICATES, FIELD_CLASSIFICATION
import sys

class TestM3IdentityDryRun(unittest.TestCase):
    def setUp(self):
        self.args = argparse.Namespace(
            project="log-solutions-cantiere",
            company_id=REQUIRED_COMPANY_ID,
            dry_run=True,
            output_dir="./migration_output/m3",
            mock_auth=True
        )
        self.db = MagicMock()
        
        # Mock dependencies
        m0_doc = MagicMock(); m0_doc.exists = True; m0_doc.to_dict.return_value = {"status": "COMPLETE"}
        m2_doc = MagicMock(); m2_doc.exists = True; m2_doc.to_dict.return_value = {"status": "COMPLETE"}
        comp_doc = MagicMock(); comp_doc.exists = True
        
        def doc_side_effect(path):
            if path == "system_migrations/core_v1_m0_m1": return m0_doc
            if path == "system_migrations/core_v1_m2_vehicles": return m2_doc
            if path == f"aziende/{REQUIRED_COMPANY_ID}": return comp_doc
            return MagicMock(exists=False)
            
        self.db.document.side_effect = doc_side_effect
        self.auth = MagicMock()

    def create_mock_employees(self, num_auth_canonical=23, num_emp_only=2, include_test_auth=True, extra_fields=None, auth_fail=False):
        employees = []
        auth_users = []
        
        for i in range(num_auth_canonical):
            uid = f"auth_uid_{i}"
            if i == 0: uid = DUPLICATES[0]
            if i == 1: uid = DUPLICATES[1]
            data = {"nome": f"Nome {i}", "attivo": True, "uid": uid, "email": f"test{i}@test.com", "ruolo": "autista", "password": "secret"}
            if extra_fields:
                data.update(extra_fields)
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
            
        def stream_mock():
            for e in employees:
                d = MagicMock()
                d.id = e["id"]
                d.to_dict.return_value = e["data"]
                yield d
        self.db.collection().stream = stream_mock
        
        if auth_fail:
            self.auth.list_users.side_effect = Exception("Firebase Error")
        else:
            list_users_mock = MagicMock()
            list_users_mock.iterate_all.return_value = auth_users
            self.auth.list_users.return_value = list_users_mock

    def test_successful_run(self):
        self.create_mock_employees()
        mig = M3IdentityDryRun(self.db, self.args, self.auth)
        mig.load_data()
        mig.transform_and_validate()
        
        self.assertEqual(len(mig.employees_target), 25)
        self.assertEqual(len(mig.users_target), 23)
        self.assertEqual(mig.status, "PASS_WITH_IDENTITY_REVIEW")
        
    def test_auth_exception_fails(self):
        self.create_mock_employees(auth_fail=True)
        mig = M3IdentityDryRun(self.db, self.args, self.auth)
        with self.assertRaises(SystemExit):
            mig.load_data()
            
    def test_unexpected_active_value(self):
        self.create_mock_employees(extra_fields={"attivo": "false"})
        mig = M3IdentityDryRun(self.db, self.args, self.auth)
        mig.load_data()
        mig.transform_and_validate()
        
        self.assertEqual(mig.status, "FAIL")
        self.assertTrue(any("Unexpected active value" in r for r in mig.review_required))
        
    def test_auth_count_zero(self):
        self.create_mock_employees(num_auth_canonical=0, num_emp_only=25, include_test_auth=False)
        mig = M3IdentityDryRun(self.db, self.args, self.auth)
        mig.load_data()
        mig.transform_and_validate()
        self.assertEqual(mig.status, "FAIL")
        self.assertFalse(mig.validation_manifest["AUTH_TOTAL_COUNT_24"])
        
    def test_unknown_fields(self):
        self.create_mock_employees(extra_fields={"some_new_field": 123})
        mig = M3IdentityDryRun(self.db, self.args, self.auth)
        mig.load_data()
        mig.transform_and_validate()
        self.assertEqual(mig.status, "FAIL")
        self.assertFalse(mig.validation_manifest["UNKNOWN_FIELD_COUNT_0"])
        
    def test_password_exclusion(self):
        self.create_mock_employees()
        mig = M3IdentityDryRun(self.db, self.args, self.auth)
        mig.load_data()
        mig.transform_and_validate()
        
        # Check fingerprints don't fail, payload doesn't contain password
        for target in mig.employees_target:
            self.assertNotIn("password", target["payload"])
        for target in mig.users_target:
            self.assertNotIn("password", target["payload"])
        
        self.assertTrue(mig.validation_manifest["PASSWORD_NOT_MIGRATED"])

if __name__ == '__main__':
    unittest.main()
