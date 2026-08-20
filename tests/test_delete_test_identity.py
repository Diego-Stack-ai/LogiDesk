import unittest
from unittest.mock import MagicMock, patch
import argparse
import os

from scripts.cleanup.delete_test_identity import TestIdentityCleanup, REQUIRED_PROJECT, REQUIRED_COMPANY, REQUIRED_UID, CONFIRM_TOKEN, UserNotFoundError

class TestDeleteTestIdentity(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.auth = MagicMock()

        self.args = argparse.Namespace(
            project=REQUIRED_PROJECT,
            uid=REQUIRED_UID,
            execute=False,
            confirm_delete="",
            output_dir="./migration_output/cleanup"
        )

        # Mock M3 registry complete
        self.reg_doc = MagicMock()
        self.reg_doc.exists = True
        self.reg_doc.to_dict.return_value = {"status": "COMPLETE"}

        # Mock Canonical Counts
        self.emp_stream = [MagicMock(id=f"emp{i}") for i in range(25)]
        self.usr_stream = [MagicMock(id=f"usr{i}") for i in range(23)]

        # Mock Legacy Document
        self.legacy_doc = MagicMock()
        self.legacy_doc.exists = True

        def document_side_effect(path):
            doc_ref = MagicMock()
            if path == "system_migrations/core_v1_m3_identity":
                doc_ref.get.return_value = self.reg_doc
            elif path == f"dipendenti/{REQUIRED_UID}":
                doc_ref.get.return_value = self.legacy_doc
            else:
                doc_ref.get.return_value = MagicMock()
            return doc_ref

        self.db.document.side_effect = document_side_effect

        def collection_side_effect(path):
            coll = MagicMock()
            if path == f"aziende/{REQUIRED_COMPANY}/dipendenti":
                coll.stream.return_value = self.emp_stream
            elif path == f"aziende/{REQUIRED_COMPANY}/utenti":
                coll.stream.return_value = self.usr_stream
            else:
                coll.stream.return_value = []
            return coll

        self.db.collection.side_effect = collection_side_effect

    def test_wrong_project(self):
        self.args.project = "wrong-project"
        mig = TestIdentityCleanup(self.db, self.args, self.auth)
        with self.assertRaises(SystemExit) as cm:
            mig.run()
        self.assertIn("Invalid project", str(cm.exception))

    def test_wrong_uid(self):
        self.args.uid = "wrong-uid"
        mig = TestIdentityCleanup(self.db, self.args, self.auth)
        with self.assertRaises(SystemExit) as cm:
            mig.run()
        self.assertIn("Invalid UID", str(cm.exception))

    def test_no_execute_zero_delete(self):
        mig = TestIdentityCleanup(self.db, self.args, self.auth)
        mig.run()
        self.auth.delete_user.assert_not_called()
        self.assertFalse(mig.firestore_deleted)
        self.assertEqual(mig.status, "PLANNED")

    def test_wrong_token_zero_delete(self):
        self.args.execute = True
        self.args.confirm_delete = "WRONG_TOKEN"
        mig = TestIdentityCleanup(self.db, self.args, self.auth)
        with self.assertRaises(SystemExit) as cm:
            mig.run()
        self.assertIn("Invalid confirmation token", str(cm.exception))
        self.auth.delete_user.assert_not_called()
        self.assertFalse(mig.firestore_deleted)

    def test_reference_count_greater_than_zero(self):
        def collection_side_effect(path):
            coll = MagicMock()
            if path == f"aziende/{REQUIRED_COMPANY}/dipendenti":
                coll.stream.return_value = self.emp_stream
            elif path == f"aziende/{REQUIRED_COMPANY}/utenti":
                coll.stream.return_value = self.usr_stream
            elif path == "presenze":
                doc = MagicMock()
                doc.to_dict.return_value = {"dipendente_id": REQUIRED_UID}
                coll.stream.return_value = [doc]
            else:
                coll.stream.return_value = []
            return coll
        self.db.collection.side_effect = collection_side_effect

        mig = TestIdentityCleanup(self.db, self.args, self.auth)
        with self.assertRaises(SystemExit) as cm:
            mig.run()
        self.assertIn("Preflight validation failed", str(cm.exception))
        self.assertFalse(mig.gates["GATE_REFS_0"])

    def test_auth_missing_unexpectedly(self):
        self.auth.get_user.side_effect = UserNotFoundError("User not found")
        mig = TestIdentityCleanup(self.db, self.args, self.auth)
        with self.assertRaises(SystemExit) as cm:
            mig.run()
        self.assertFalse(mig.gates["GATE_AUTH_EXISTS"])

    def test_canonical_test_exists(self):
        self.emp_stream.append(MagicMock(id=REQUIRED_UID))
        mig = TestIdentityCleanup(self.db, self.args, self.auth)
        with self.assertRaises(SystemExit) as cm:
            mig.run()
        self.assertFalse(mig.gates["GATE_EMP_ABSENT"])

    def test_m3_incomplete(self):
        self.reg_doc.to_dict.return_value = {"status": "IN_PROGRESS"}
        mig = TestIdentityCleanup(self.db, self.args, self.auth)
        with self.assertRaises(SystemExit) as cm:
            mig.run()
        self.assertFalse(mig.gates["GATE_M3_COMPLETE"])

    def test_execute_correct(self):
        self.args.execute = True
        self.args.confirm_delete = CONFIRM_TOKEN

        # For post-delete validation
        def auth_get_user_side_effect(uid):
            if mig.status == "EXECUTED":
                raise UserNotFoundError("Deleted")
            return MagicMock()
        self.auth.get_user.side_effect = auth_get_user_side_effect

        def doc_side_effect(path):
            doc_ref = MagicMock()
            if path == "system_migrations/core_v1_m3_identity":
                doc_ref.get.return_value = self.reg_doc
            elif path == f"dipendenti/{REQUIRED_UID}":
                doc = MagicMock()
                doc.exists = mig.status != "EXECUTED"
                doc_ref.get.return_value = doc
            else:
                doc_ref.get.return_value = MagicMock()
            return doc_ref
        self.db.document.side_effect = doc_side_effect

        mig = TestIdentityCleanup(self.db, self.args, self.auth)
        mig.run()

        self.auth.delete_user.assert_called_once_with(REQUIRED_UID)
        self.assertTrue(mig.firestore_deleted)
        self.assertEqual(mig.post_validation["overall_status"], "CLEANUP_SUCCESS")

    def test_auth_delete_failure(self):
        self.args.execute = True
        self.args.confirm_delete = CONFIRM_TOKEN

        self.auth.delete_user.side_effect = Exception("Firebase error")

        mig = TestIdentityCleanup(self.db, self.args, self.auth)
        with self.assertRaises(SystemExit) as cm:
            mig.run()

        self.assertIn("Auth delete failed", str(cm.exception))
        self.assertFalse(mig.firestore_deleted)

    @patch('scripts.cleanup.delete_test_identity.initialize_app', create=True)
    def test_existing_app_correct_project(self, mock_init_app):
        with patch('scripts.cleanup.delete_test_identity.get_app') as mock_get_app, patch('scripts.cleanup.delete_test_identity.firestore') as mock_fs, patch('scripts.cleanup.delete_test_identity.auth') as mock_auth:
            mock_app = MagicMock()
            mock_app.project_id = REQUIRED_PROJECT
            mock_get_app.return_value = mock_app

            mig = TestIdentityCleanup(None, self.args, self.auth)
            mock_fs.client.return_value = self.db
            mock_auth.get_user = self.auth.get_user
            mig.run()
            self.assertTrue(mig.preflight_passed)

    @patch('scripts.cleanup.delete_test_identity.initialize_app', create=True)
    def test_existing_app_wrong_project(self, mock_init_app):
        with patch('scripts.cleanup.delete_test_identity.get_app') as mock_get_app:
            mock_app = MagicMock()
            mock_app.project_id = "wrong-project-id"
            mock_get_app.return_value = mock_app

            mig = TestIdentityCleanup(None, self.args, self.auth)
            with self.assertRaises(SystemExit) as cm:
                mig.run()
            self.assertIn("Existing Firebase app points to wrong-project-id", str(cm.exception))

    def test_preflight_failure_writes_reports(self):
        self.reg_doc.to_dict.return_value = {"status": "IN_PROGRESS"} # Causes failure
        mig = TestIdentityCleanup(self.db, self.args, self.auth)

        with patch('scripts.cleanup.delete_test_identity.open') as mock_open:
            with self.assertRaises(SystemExit):
                mig.run()
            mock_open.assert_any_call(os.path.join(self.args.output_dir, "TEST_IDENTITY_DELETE_SUMMARY.json"), 'w')
            mock_open.assert_any_call(os.path.join(self.args.output_dir, "TEST_IDENTITY_PREDELETE_VALIDATION.json"), 'w')

if __name__ == '__main__':
    unittest.main()
