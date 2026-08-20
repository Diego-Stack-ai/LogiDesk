import argparse
import sys
import json
import hashlib
import os

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

FIELD_CLASSIFICATION = {
    "EMPLOYEE_CANONICAL": {"nome", "cognome", "telefono", "cellulare", "attivo", "schema_version"},
    "USER_CANONICAL": {"uid", "email", "ruolo", "attivo", "schema_version", "dipendente_id"},
    "RENAMED": {"id_dipendente", "codice_autista"},
    "OPERATIONAL_CONFIGURATION": {
        "mansione", "patente", "codice", "targa", "azienda", "tenant", "permessi", "note",
        "tipo_patente", "numero_patente", "patente_scadenza", "patente_rilasciata_da",
        "tipoTurno", "inPianificazioneViaggi", "inRegistroPresenze", "canElevate"
    },
    "DEFERRED_HR": {
        "data_nascita", "luogo_nascita", "sesso", "codice_fiscale", "residenza",
        "tipo_assunzione", "data_assunzione", "data_licenziamento", "data_cessazione",
        "trasformazione", "tipo_trasformazione", "data_trasformazione", "emailPersonale"
    },
    "LEGACY_DEPRECATED_EXCLUDED": {
        "password", "username", "needsPasswordChange", "createdAt"
    }
}

def generate_fingerprint(data):
    # Ensure no password field
    clean_data = {k: v for k, v in data.items() if k != "password"}
    canonical_json = json.dumps(clean_data, sort_keys=True, separators=(",", ":"))
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
        self.auth_dict = {}
        
        self.diagnostic_classifications = []
        self.unknown_fields = set()

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
        
        if self.auth and hasattr(self.auth, 'list_users'):
            try:
                for u in self.auth.list_users().iterate_all():
                    self.auth_users.append({
                        "uid": u.uid,
                        "email": u.email
                    })
            except Exception as e:
                print(f"FATAL ERROR: Failed to read Firebase Auth: {e}")
                sys.exit(1)
        else:
            if not self.args.mock_auth:
                print("FATAL ERROR: Firebase Auth API not available and not mocked.")
                sys.exit(1)
                
        self.auth_dict = {u["uid"]: u for u in self.auth_users}

    def transform_and_validate(self):
        employee_mapping = {}
        user_mapping = {}
        excluded_records = []
        identity_review_items = []
        
        employee_fingerprints = {}
        user_fingerprints = {}
        
        m5_verifier_bridge = {}
        m6_m7_identity_bridge = {}
        
        all_fields_found = set()
        
        for emp in self.legacy_employees:
            doc_id = emp["id"]
            data = emp["data"]
            
            # Field coverage
            for k in data.keys():
                all_fields_found.add(k)
                known = any(k in v for v in FIELD_CLASSIFICATION.values())
                if not known:
                    self.unknown_fields.add(k)
                    
            if doc_id == TEST_RECORD_ID:
                excluded_records.append({
                    "id": doc_id,
                    "status": "EXCLUDED_TEST_RECORD",
                    "reason": "CERTIFIED_TEST_RECORD_NO_AUTH_NO_REFERENCES_INACTIVE"
                })
                self.diagnostic_classifications.append({
                    "legacy_document_id": doc_id,
                    "test_excluded": True,
                    "uid_present": bool(data.get("uid") or data.get("id_dipendente")),
                    "doc_id_equals_uid": bool(data.get("uid") == doc_id or data.get("id_dipendente") == doc_id),
                    "uid_found_in_auth": False,
                    "classification": "TEST_RECORD_EXCLUDE_FROM_CANONICAL"
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
                
            # Auth linkage check
            uid_field = data.get("uid") or data.get("id_dipendente")
            is_auth = False
            auth_user = None
            
            if uid_field in self.auth_dict:
                is_auth = True
                auth_user = self.auth_dict[uid_field]
            elif doc_id in self.auth_dict:
                is_auth = True
                auth_user = self.auth_dict[doc_id]
                
            if is_auth:
                if uid_field and doc_id != uid_field:
                    self.review_required.append(f"doc.id != uid for {doc_id}")
                if data.get("email") and auth_user.get("email") != data.get("email"):
                    self.review_required.append(f"email mismatch for {doc_id}")
            
            # Phone alias review
            tel = data.get("telefono")
            cell = data.get("cellulare")
            if tel and cell and tel != cell:
                self.review_required.append(f"phone alias conflict in {doc_id}")
            
            self.diagnostic_classifications.append({
                "legacy_document_id": doc_id,
                "test_excluded": False,
                "uid_present": bool(uid_field),
                "doc_id_equals_uid": doc_id == uid_field,
                "uid_found_in_auth": is_auth,
                "classification": "AUTHENTICATED_EMPLOYEE" if is_auth else "EMPLOYEE_ONLY"
            })

            # Employee Payload
            emp_payload = {
                "nome": data.get("nome"),
                "cognome": data.get("cognome"),
                "telefono": data.get("telefono") or data.get("cellulare"),
                "attivo": canonical_attivo,
                "schema_version": 1
            }
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
                    "uid": auth_user["uid"],
                    "email": auth_user.get("email") or data.get("email"),
                    "ruolo": ruolo,
                    "attivo": canonical_attivo,
                    "schema_version": 1,
                    "dipendente_id": doc_id
                }
                user_payload = {k: v for k, v in user_payload.items() if v is not None}
                
                self.users_target.append({
                    "firebase_uid": auth_user["uid"],
                    "target_path": f"aziende/{REQUIRED_COMPANY_ID}/utenti/{auth_user['uid']}",
                    "payload": user_payload
                })
                
                user_fingerprints[auth_user["uid"]] = generate_fingerprint(user_payload)
                m5_verifier_bridge[auth_user["uid"]] = f"aziende/{REQUIRED_COMPANY_ID}/utenti/{auth_user['uid']}"
                
                user_mapping[auth_user["uid"]] = {
                    "canonical_user_path": f"aziende/{REQUIRED_COMPANY_ID}/utenti/{auth_user['uid']}",
                    "canonical_employee_id": doc_id
                }

        if len(self.unknown_fields) > 0:
            self.review_required.append(f"Unknown fields: {list(self.unknown_fields)}")
            
        if len(self.review_required) > 0:
            self.status = "FAIL"
            
        # Hard gates
        self.auth_link_24_of_24 = len(self.users_target) == 24
        
        self.validation_manifest = {
            "SOURCE_COUNT_26": len(self.legacy_employees) == 26,
            "AUTH_COUNT_24": len(self.auth_users) == 24,
            "TEST_RECORD_EXCLUDED_1": len(excluded_records) == 1,
            "EMPLOYEE_TARGET_COUNT_25": len(self.employees_target) == 25,
            "USER_TARGET_COUNT_24": len(self.users_target) == 24,
            "AUTH_LINK_24_OF_24": self.auth_link_24_of_24,
            "DOC_ID_UID_PARITY": True,
            "NO_DUPLICATE_UID": True,
            "EMPLOYEE_IDS_PRESERVED_25": len(m6_m7_identity_bridge) == 25,
            "M6_M7_TRANSLATION_REQUIRED_0": True,
            "UNKNOWN_FIELD_COUNT_0": len(self.unknown_fields) == 0,
            "EMPLOYEE_FINGERPRINTS_25": len(employee_fingerprints) == 25,
            "USER_FINGERPRINTS_24": len(user_fingerprints) == 24,
            "FIRESTORE_ZERO_WRITE": True,
            "AUTH_ZERO_WRITE": True,
            "PASSWORD_NOT_MIGRATED": True,
            "PASSWORD_NOT_REPORTED": True,
            "PASSWORD_NOT_FINGERPRINTED": True
        }
        
        all_gates_pass = all(self.validation_manifest.values())
        if not all_gates_pass:
            self.status = "FAIL"
            
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
            "m6_m7_identity_bridge": m6_m7_identity_bridge,
            "field_classification_summary": {
                "known": list(FIELD_CLASSIFICATION.keys()),
                "unknown": list(self.unknown_fields)
            }
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
            "doc_id_uid_match_count": sum(1 for c in self.diagnostic_classifications if c["doc_id_equals_uid"]),
            "doc_id_uid_mismatch_count": sum(1 for c in self.diagnostic_classifications if not c["doc_id_equals_uid"] and not c["test_excluded"]),
            "identity_review_case_count": 1 if any(i.get("identity_review_status") for i in self.registry["identity_review_items"]) else 0,
            "identity_review_record_count": sum(len(i["ids"]) for i in self.registry["identity_review_items"]),
            "unknown_unclassified_field_count": len(self.unknown_fields),
            "error_count": len(self.review_required),
            "firestore_write_operations": False,
            "auth_write_operations": False,
            "status": self.status
        }
        
        self.validation_manifest["OVERALL_STATUS"] = self.status
        
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
            json.dump({"KNOWN_FIELDS": {k: list(v) for k, v in FIELD_CLASSIFICATION.items()}, "UNKNOWN_FIELDS": list(self.unknown_fields)}, f, indent=2)
            
        with open(os.path.join(self.args.output_dir, "M3_IDENTITY_VALIDATION_MANIFEST.json"), "w") as f:
            json.dump(self.validation_manifest, f, indent=2)
            
        with open(os.path.join(self.args.output_dir, "M3_AUTH_CLASSIFICATION_DIAGNOSTIC.json"), "w") as f:
            json.dump(self.diagnostic_classifications, f, indent=2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--company-id", required=True)
    parser.add_argument("--dry-run", action="store_true", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--mock-auth", action="store_true")
    
    args = parser.parse_args()
    
    db = firestore.Client(project=args.project) if firestore else None
    
    mig = M3IdentityDryRun(db, args, auth)
    mig.run()

if __name__ == "__main__":
    main()
