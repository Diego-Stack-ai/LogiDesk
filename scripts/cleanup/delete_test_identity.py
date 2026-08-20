import argparse
import os
import json
from datetime import datetime

try:
    from firebase_admin import firestore, auth, initialize_app, get_app
    from firebase_admin._auth_utils import UserNotFoundError
except ImportError:
    firestore = None
    auth = None
    initialize_app = None
    get_app = None
    
    class UserNotFoundError(Exception):
        pass

REQUIRED_PROJECT = "log-solutions-cantiere"
REQUIRED_COMPANY = "NzXaCgyXxZWWehw1tSlo"
REQUIRED_UID = "qtQWKWaJRMZNv0UzhOETC0t2hdU2"
CONFIRM_TOKEN = "LOGIDESK_DELETE_TEST_IDENTITY"

class TestIdentityCleanup:
    def __init__(self, db, args, auth_client=None):
        self.db = db
        self.args = args
        self.auth = auth_client
        self.status = "PLANNED"
        self.gates = {}
        self.post_validation = {}
        self.auth_deleted = False
        self.firestore_deleted = False
        
    def initialize(self):
        if self.db is None and initialize_app:
            try:
                get_app()
            except ValueError:
                initialize_app()
            self.db = firestore.client()
            self.auth = auth
            
    def check_gates(self):
        self.gates["GATE_PROJECT"] = self.args.project == REQUIRED_PROJECT
        self.gates["GATE_UID"] = self.args.uid == REQUIRED_UID
        
        if not self.gates["GATE_PROJECT"]:
            raise SystemExit("STOP: Invalid project")
        if not self.gates["GATE_UID"]:
            raise SystemExit("STOP: Invalid UID")
            
    def preflight_revalidation(self):
        # M3 Status
        reg = self.db.document("system_migrations/core_v1_m3_identity").get()
        self.gates["GATE_M3_COMPLETE"] = reg.exists and reg.to_dict().get("status") == "COMPLETE"
        
        # Canonical counts
        emp_targets = list(self.db.collection(f"aziende/{REQUIRED_COMPANY}/dipendenti").stream())
        usr_targets = list(self.db.collection(f"aziende/{REQUIRED_COMPANY}/utenti").stream())
        
        self.gates["GATE_EMP_COUNT_25"] = len(emp_targets) == 25
        self.gates["GATE_USR_COUNT_23"] = len(usr_targets) == 23
        
        # Test presence in Canonical
        self.gates["GATE_EMP_ABSENT"] = all(e.id != REQUIRED_UID for e in emp_targets)
        self.gates["GATE_USR_ABSENT"] = all(u.id != REQUIRED_UID for u in usr_targets)
        
        # Legacy existence
        legacy_doc = self.db.document(f"dipendenti/{REQUIRED_UID}").get()
        self.gates["GATE_LEGACY_EXISTS"] = legacy_doc.exists
        
        # Auth existence
        try:
            self.auth.get_user(REQUIRED_UID)
            self.gates["GATE_AUTH_EXISTS"] = True
        except Exception as e:
            if type(e).__name__ == "UserNotFoundError" or (isinstance(e, Exception) and "UserNotFoundError" in str(type(e))):
                self.gates["GATE_AUTH_EXISTS"] = False
            else:
                self.gates["GATE_AUTH_EXISTS"] = False
            
        # Ref counts
        collections_to_audit = ["presenze", "viaggi", "pianificazione", "costi_personale", "turni", "report", "fatturazione", "assenze", "ferie", "assegnazioni"]
        ref_count = 0
        for coll_name in collections_to_audit:
            for doc in self.db.collection(coll_name).stream():
                d = doc.to_dict() or {}
                for k, v in d.items():
                    if v == REQUIRED_UID or (isinstance(v, list) and REQUIRED_UID in v) or (isinstance(v, dict) and REQUIRED_UID in v.values()):
                        ref_count += 1
                        
        self.gates["GATE_REFS_0"] = ref_count == 0
        
        if not all(self.gates.values()):
            raise SystemExit(f"STOP: Preflight validation failed: {self.gates}")
            
    def execute_delete(self):
        if not self.args.execute:
            return
            
        if self.args.confirm_delete != CONFIRM_TOKEN:
            raise SystemExit("STOP: Invalid confirmation token")
            
        # 1. Firebase Auth Delete
        try:
            self.auth.delete_user(REQUIRED_UID)
            self.auth_deleted = True
        except Exception as e:
            raise SystemExit(f"STOP: Auth delete failed: {str(e)}")
            
        # 2. Firestore Legacy Delete
        try:
            self.db.document(f"dipendenti/{REQUIRED_UID}").delete()
            self.firestore_deleted = True
        except Exception as e:
            self.status = "PARTIAL_CLEANUP"
            raise SystemExit(f"STOP: Firestore delete failed: {str(e)}")
            
        self.status = "EXECUTED"
        
    def post_delete_validation(self):
        if self.status != "EXECUTED":
            return
            
        try:
            self.auth.get_user(REQUIRED_UID)
            auth_absent = False
        except Exception as e:
            if type(e).__name__ == "UserNotFoundError" or (isinstance(e, Exception) and "UserNotFoundError" in str(type(e))):
                auth_absent = True
            else:
                auth_absent = True
            
        legacy_doc = self.db.document(f"dipendenti/{REQUIRED_UID}").get()
        legacy_absent = not legacy_doc.exists
        
        emp_targets = list(self.db.collection(f"aziende/{REQUIRED_COMPANY}/dipendenti").stream())
        usr_targets = list(self.db.collection(f"aziende/{REQUIRED_COMPANY}/utenti").stream())
        
        reg = self.db.document("system_migrations/core_v1_m3_identity").get()
        m3_complete = reg.exists and reg.to_dict().get("status") == "COMPLETE"
        
        self.post_validation = {
            "auth_absent": auth_absent,
            "legacy_doc_absent": legacy_absent,
            "canonical_employee_count_25": len(emp_targets) == 25,
            "canonical_user_count_23": len(usr_targets) == 23,
            "m3_registry_complete": m3_complete,
            "overall_status": "CLEANUP_SUCCESS" if (auth_absent and legacy_absent) else "CLEANUP_FAILED"
        }
        
    def write_reports(self):
        os.makedirs(self.args.output_dir, exist_ok=True)
        
        summary = {
            "project": self.args.project,
            "uid": self.args.uid,
            "mode": "EXECUTE" if self.args.execute else "PREFLIGHT",
            "auth_delete_executed": self.auth_deleted,
            "firestore_delete_executed": self.firestore_deleted,
            "partial_cleanup": self.status == "PARTIAL_CLEANUP",
            "executed_at": datetime.now().isoformat(),
            "gates": self.gates
        }
        
        with open(os.path.join(self.args.output_dir, "TEST_IDENTITY_DELETE_SUMMARY.json"), "w") as f:
            json.dump(summary, f, indent=2)
            
        if self.args.execute:
            with open(os.path.join(self.args.output_dir, "TEST_IDENTITY_POST_DELETE_VALIDATION.json"), "w") as f:
                json.dump(self.post_validation, f, indent=2)

    def run(self):
        self.initialize()
        self.check_gates()
        self.preflight_revalidation()
        try:
            self.execute_delete()
            self.post_delete_validation()
        finally:
            self.write_reports()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--uid", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-delete", default="")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    
    db = firestore.Client(project=args.project) if firestore else None
    
    mig = TestIdentityCleanup(db, args, auth)
    mig.run()

if __name__ == "__main__":
    main()
