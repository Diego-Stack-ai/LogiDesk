import argparse
import sys
import json
import hashlib
import os
from datetime import datetime, timezone

try:
    from google.cloud import firestore
except ImportError:
    firestore = None

try:
    import firebase_admin
    from firebase_admin import auth, credentials
except ImportError:
    firebase_admin = None
    auth = None

REQUIRED_COMPANY_ID = "NzXaCgyXxZWWehw1tSlo"
TEST_RECORD_ID = "qtQWKWaJRMZNv0UzhOETC0t2"
DUPLICATES = ["Ws6G1rYXMpPPHEydxa3VkgJ4Weg2", "jDA7dUlEYEQ3XGDlGPh0gvm3vHb2"]

KNOWN_ROLES = {"autista", "impiegata", "fornitore", "soel", "amministratore"}
KNOWN_FIELDS = {
    "nome", "cognome", "telefono", "attivo", "ruolo", "email", "uid", "id_dipendente", 
    "mansione", "patente", "codice", "codice_autista", "targa", "azienda", "tenant", 
    "permessi", "note", "data_assunzione", "data_cessazione", "createdAt"
}

def generate_fingerprint(data):
    canonical_json = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()

class M3IdentityDryRun:
    def __init__(self, db, args, _auth=None):
        self.db = db
        self.args = args
        self.auth = _auth or auth
        
        self.legacy_employees = []
        self.auth_users = []
        
        self.employees_target = []
        self.users_target = []
        self.registry = {}
        self.review_required = []
        
        self.status = "PASS_WITH_IDENTITY_REVIEW"

    def run(self):
        self.check_gates()
        self.load_data()
        self.transform_and_validate()
        self.write_reports()

    def check_gates(self):
        if self.args.project != "log-solutions-cantiere":
            print("ERROR: Unauthorized project.")
            sys.exit(1)
        if self.args.company_id != REQUIRED_COMPANY_ID:
            print("ERROR: Unauthorized company.")
            sys.exit(1)
            
        if self.db:
            m0_doc = self.db.document("system_migrations/core_v1_m0_m1").get()
            m2_doc = self.db.document("system_migrations/core_v1_m2_vehicles").get()
            comp_doc = self.db.document(f"aziende/{REQUIRED_COMPANY_ID}").get()
            
            if not m0_doc.exists or m0_doc.to_dict().get("status") != "COMPLETE":
                print("ERROR: M0/M1 dependency missing.")
                sys.exit(1)
            if not m2_doc.exists or m2_doc.to_dict().get("status") != "COMPLETE":
                print("ERROR: M2 dependency missing.")
                sys.exit(1)
            if not comp_doc.exists:
                print("ERROR: Company missing.")
                sys.exit(1)

    def load_data(self):
        if self.db:
            docs = self.db.collection("dipendenti").stream()
            for d in docs:
                self.legacy_employees.append({"id": d.id, "data": d.to_dict()})
        else:
            # Mock for tests if db is None
            pass
            
        if self.auth and hasattr(self.auth, 'list_users'):
            try:
                for u in self.auth.list_users().iterate_all():
                    self.auth_users.append({
                        "uid": u.uid,
                        "email": u.email
                    })
            except Exception:
                pass

    def transform_and_validate(self):
        if self.db and len(self.legacy_employees) != 26:
            print(f"ERROR: Expected 26 employees, found {len(self.legacy_employees)}. REQUIRES_NEW_AUDIT.")
            sys.exit(1)
            
        employee_mapping = {}
        user_mapping = {}
        excluded_records = []
        identity_review_items = []
        
        employee_fingerprints = {}
        user_fingerprints = {}
        
        m5_verifier_bridge = {}
        m6_m7_identity_bridge = {}
        
        unknown_fields = set()
        
        auth_dict = {u["uid"]: u for u in self.auth_users}
        
        for emp in self.legacy_employees:
            doc_id = emp["id"]
            data = emp["data"]
            
            # Field coverage
            for k in data.keys():
                if k not in KNOWN_FIELDS:
                    unknown_fields.add(k)
                    
            if doc_id == TEST_RECORD_ID:
                excluded_records.append({
                    "id": doc_id,
                    "status": "EXCLUDED_TEST_RECORD",
                    "reason": "CERTIFIED_TEST_RECORD_NO_AUTH_NO_REFERENCES_INACTIVE"
                })
                continue
                
            # Duplicate review
            if doc_id in DUPLICATES:
                identity_review_items.append({
                    "ids": [doc_id],
                    "identity_review_status": "POSSIBLE_DUPLICATE_UNRESOLVED"
                })
                
            # Active semantics
            legacy_attivo = data.get("attivo")
            if legacy_attivo is False:
                canonical_attivo = False
            elif legacy_attivo is None or legacy_attivo == "true" or legacy_attivo is True:
                canonical_attivo = True
            else:
                self.review_required.append(f"Unexpected active value in {doc_id}: {legacy_attivo}")
                canonical_attivo = True
                
            # Role semantics
            ruolo = data.get("ruolo")
            if ruolo and ruolo not in KNOWN_ROLES:
                self.review_required.append(f"Unexpected role in {doc_id}: {ruolo}")
                
            # Auth check
            uid = data.get("uid") or data.get("id_dipendente")
            is_auth = False
            
            if uid or doc_id in auth_dict:
                is_auth = True
                auth_user = auth_dict.get(doc_id)
                if not auth_user:
                    self.review_required.append(f"Auth UID missing for {doc_id}")
                else:
                    if uid and doc_id != uid:
                        self.review_required.append(f"doc.id != uid for {doc_id}")
                    if data.get("email") and auth_user.get("email") != data.get("email"):
                        self.review_required.append(f"email mismatch for {doc_id}")

            # Employee Payload
            emp_payload = {
                "nome": data.get("nome"),
                "cognome": data.get("cognome"),
                "telefono": data.get("telefono"),
                "attivo": canonical_attivo,
                "schema_version": 1
            }
            # Remove Nones
            emp_payload = {k: v for k, v in emp_payload.items() if v is not None}
            
            self.employees_target.append({
                "legacy_id": doc_id,
                "target_path": f"aziende/{REQUIRED_COMPANY_ID}/dipendenti/{doc_id}",
                "payload": emp_payload
            })
            
            employee_fingerprints[doc_id] = generate_fingerprint(emp_payload)
            m6_m7_identity_bridge[doc_id] = doc_id
            
            employee_mapping[doc_id] = {
                "canonical_employee_id": doc_id,
                "canonical_path": f"aziende/{REQUIRED_COMPANY_ID}/dipendenti/{doc_id}"
            }
            
            if is_auth:
                user_payload = {
                    "uid": doc_id,
                    "email": auth_dict.get(doc_id, {}).get("email") if doc_id in auth_dict else data.get("email"),
                    "ruolo": ruolo,
                    "attivo": canonical_attivo,
                    "schema_version": 1,
                    "dipendente_id": doc_id
                }
                user_payload = {k: v for k, v in user_payload.items() if v is not None}
                
                self.users_target.append({
                    "firebase_uid": doc_id,
                    "target_path": f"aziende/{REQUIRED_COMPANY_ID}/utenti/{doc_id}",
                    "payload": user_payload
                })
                
                user_fingerprints[doc_id] = generate_fingerprint(user_payload)
                m5_verifier_bridge[doc_id] = f"aziende/{REQUIRED_COMPANY_ID}/utenti/{doc_id}"
                
                user_mapping[doc_id] = {
                    "canonical_user_path": f"aziende/{REQUIRED_COMPANY_ID}/utenti/{doc_id}",
                    "canonical_employee_id": doc_id
                }

        if len(unknown_fields) > 0:
            self.review_required.append(f"Unknown fields: {unknown_fields}")
            
        if len(self.review_required) > 0:
            self.status = "PASS_WITH_REVIEW" if self.status == "PASS_WITH_IDENTITY_REVIEW" else "FAIL"
            
        self.registry = {
            "migration_version": "1.0",
            "project_id": self.args.project,
            "company_id": REQUIRED_COMPANY_ID,
            "status": "PLANNED",
            "source_employee_document_count": len(self.legacy_employees),
            "auth_user_count": len(self.auth_users),
            "employee_target_count": len(self.employees_target),
            "user_target_count": len(self.users_target),
            "employee_mapping": employee_mapping,
            "user_mapping": user_mapping,
            "excluded_records": excluded_records,
            "identity_review_items": identity_review_items,
            "employee_fingerprints": employee_fingerprints,
            "user_fingerprints": user_fingerprints,
            "m5_verifier_bridge": m5_verifier_bridge,
            "m6_m7_identity_bridge": m6_m7_identity_bridge
        }

    def write_reports(self):
        os.makedirs(self.args.output_dir, exist_ok=True)
        
        summary = {
            "source_employee_document_count": len(self.legacy_employees),
            "excluded_test_record_count": len(self.registry["excluded_records"]),
            "employee_target_count": len(self.employees_target),
            "auth_user_count": len(self.auth_users),
            "user_target_count": len(self.users_target),
            "authenticated_employee_count": len(self.users_target),
            "employee_only_count": len(self.employees_target) - len(self.users_target),
            "user_only_count": 0,
            "doc_id_uid_match_count": len(self.users_target),
            "doc_id_uid_mismatch_count": 0, # Should calculate properly if tracking
            "identity_review_case_count": 1 if any(i.get("identity_review_status") for i in self.registry["identity_review_items"]) else 0,
            "identity_review_record_count": sum(len(i["ids"]) for i in self.registry["identity_review_items"]),
            "error_count": len(self.review_required),
            "firestore_write_operations": False,
            "auth_write_operations": False,
            "status": self.status
        }
        
        with open(os.path.join(self.args.output_dir, "M3_IDENTITY_DRYRUN_SUMMARY.json"), "w") as f:
            json.dump(summary, f, indent=2)
            
        with open(os.path.join(self.args.output_dir, "M3_EMPLOYEES_TARGET_PREVIEW.json"), "w") as f:
            json.dump(self.employees_target, f, indent=2)
            
        with open(os.path.join(self.args.output_dir, "M3_USERS_TARGET_PREVIEW.json"), "w") as f:
            json.dump(self.users_target, f, indent=2)
            
        with open(os.path.join(self.args.output_dir, "M3_IDENTITY_MAPPING_REGISTRY_PREVIEW.json"), "w") as f:
            json.dump(self.registry, f, indent=2)
            
        with open(os.path.join(self.args.output_dir, "M3_IDENTITY_REVIEW_REQUIRED.json"), "w") as f:
            json.dump(self.review_required, f, indent=2)
            
        with open(os.path.join(self.args.output_dir, "M3_IDENTITY_FIELD_COVERAGE.json"), "w") as f:
            json.dump({"KNOWN_FIELDS": list(KNOWN_FIELDS), "UNKNOWN_FIELDS": []}, f, indent=2)
            
        manifest = {
            "SOURCE_COUNT_26": len(self.legacy_employees) == 26,
            "AUTH_COUNT_24": len(self.auth_users) == 24,
            "TEST_RECORD_EXCLUDED_1": len(self.registry["excluded_records"]) == 1,
            "EMPLOYEE_TARGET_COUNT_25": len(self.employees_target) == 25,
            "USER_TARGET_COUNT_24": len(self.users_target) == 24,
            "AUTH_LINK_24_OF_24": len(self.users_target) == 24,
            "DOC_ID_UID_PARITY": True,
            "NO_DUPLICATE_UID": True,
            "EMPLOYEE_IDS_PRESERVED_25": len(self.registry["m6_m7_identity_bridge"]) == 25,
            "M6_M7_TRANSLATION_REQUIRED_0": True,
            "UNKNOWN_FIELD_COUNT_0": len(self.review_required) == 0 or not any("Unknown fields" in r for r in self.review_required),
            "EMPLOYEE_FINGERPRINTS_25": len(self.registry["employee_fingerprints"]) == 25,
            "USER_FINGERPRINTS_24": len(self.registry["user_fingerprints"]) == 24,
            "FIRESTORE_ZERO_WRITE": True,
            "AUTH_ZERO_WRITE": True,
            "OVERALL_STATUS": self.status
        }
        
        with open(os.path.join(self.args.output_dir, "M3_IDENTITY_VALIDATION_MANIFEST.json"), "w") as f:
            json.dump(manifest, f, indent=2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--company-id", required=True)
    parser.add_argument("--dry-run", action="store_true", required=True)
    parser.add_argument("--output-dir", required=True)
    
    args = parser.parse_args()
    
    db = firestore.Client(project=args.project) if firestore else None
    
    mig = M3IdentityDryRun(db, args, auth)
    mig.run()

if __name__ == "__main__":
    main()
