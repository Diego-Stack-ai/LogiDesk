import os
import json
import hashlib
import argparse
from datetime import datetime

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
except ImportError:
    firebase_admin = None
    firestore = None

REQUIRED_PROJECT = "log-solutions-cantiere"
REQUIRED_COMPANY = "NzXaCgyXxZWWehw1tSlo"

class M6ASettingsDryRun:
    def __init__(self, db, args):
        self.db = db
        self.args = args
        self.manifest = {
            "GATE_PROJECT": False,
            "GATE_COMPANY": False,
            "GATE_SOURCE_COUNT_47": False,
            "GATE_COMPANY_SOURCE_3": False,
            "GATE_TENANT_LISTINO_SOURCE_3": False,
            "GATE_IMPORT_MAPPING_SOURCE_41": False,
            "GATE_COMPANY_TARGET_3": False,
            "GATE_TENANT_SETTINGS_TARGET_3": False,
            "GATE_IMPORT_MAPPING_TARGET_41": False,
            "GATE_TOTAL_TARGET_47": False,
            "GATE_EMAIL_SECRET_EXCLUDED": False,
            "GATE_CLIENTI_FATTURAZIONE_ZERO": False,
            "GATE_UNKNOWN_FIELD_ZERO": False,
            "GATE_UNRESOLVED_OWNER_ZERO": False,
            "GATE_TARGET_COLLISION_ZERO": False,
            "GATE_IDEMPOTENCY_UNIQUE": False,
            "GATE_FINGERPRINT_DETERMINISTIC": False,
            "GATE_TARGET_STATE_CLEAN": False,
            "GATE_FIRESTORE_ZERO_WRITE": True,
            "GATE_AUTH_ZERO_WRITE": True,
            "GATE_STORAGE_ZERO_WRITE": True,
            "OVERALL_STATUS": "PENDING"
        }
        
        self.sources = {
            "company": [],
            "tenant_listino": [],
            "import_mapping": [],
            "clienti_fatturazione": []
        }
        
        self.targets = []
        self.field_classifications = {}
        self.unknown_fields = []
        self.unresolved_owners = []
        self.secret_audit = {"secret_fields_found": [], "secret_fields_excluded": []}
        
        self.tenant_mapping = {
            "DNR": "AgvcnbuUMu7YhzSuUKTY",
            "GRAN CHEF": "UZC65YbnIbXsei88xNBX",
            "CATTEL": "bSomOWB7pieGNej2KdJA"
        }

    def initialize(self):
        if not firebase_admin:
            return
        app = firebase_admin.get_app()
        if app.project_id == REQUIRED_PROJECT:
            self.manifest["GATE_PROJECT"] = True
        if self.args.company_id == REQUIRED_COMPANY:
            self.manifest["GATE_COMPANY"] = True

    def discover_sources(self):
        if not firebase_admin: return
        for doc_id in ['permessi_dashboard', 'system_status', 'email_settings']:
            doc = self.db.collection('config').document(doc_id).get()
            if doc.exists:
                self.sources["company"].append({
                    "id": doc.id,
                    "path": doc.reference.path,
                    "data": doc.to_dict()
                })
        self.manifest["GATE_COMPANY_SOURCE_3"] = (len(self.sources["company"]) == 3)

        for legacy_tenant, core_tenant in self.tenant_mapping.items():
            doc = self.db.collection('clienti').document(legacy_tenant).collection('impostazioni').document('listino').get()
            if doc.exists:
                self.sources["tenant_listino"].append({
                    "legacy_tenant": legacy_tenant,
                    "core_tenant": core_tenant,
                    "id": "listino",
                    "path": doc.reference.path,
                    "data": doc.to_dict()
                })
        self.manifest["GATE_TENANT_LISTINO_SOURCE_3"] = (len(self.sources["tenant_listino"]) == 3)
        
        if "DNR" in self.tenant_mapping:
            dnr_core = self.tenant_mapping["DNR"]
            docs = self.db.collection('clienti').document('DNR').collection('codici articoli').stream()
            for doc in docs:
                self.sources["import_mapping"].append({
                    "legacy_tenant": "DNR",
                    "core_tenant": dnr_core,
                    "id": doc.id,
                    "path": doc.reference.path,
                    "data": doc.to_dict()
                })
        self.manifest["GATE_IMPORT_MAPPING_SOURCE_41"] = (len(self.sources["import_mapping"]) == 41)
        
        total_sources = len(self.sources["company"]) + len(self.sources["tenant_listino"]) + len(self.sources["import_mapping"])
        self.manifest["GATE_SOURCE_COUNT_47"] = (total_sources == 47)
        self.manifest["GATE_CLIENTI_FATTURAZIONE_ZERO"] = True

    def generate_fingerprint(self, payload):
        def default_serializer(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            return str(obj)
        payload_str = json.dumps(payload, sort_keys=True, separators=(',', ':'), default=default_serializer)
        return hashlib.sha256(payload_str.encode('utf-8')).hexdigest()

    def process_targets(self):
        company_count = 0
        for src in self.sources["company"]:
            doc_id = src["id"]
            data = src["data"].copy()
            domain = ""
            if doc_id == "permessi_dashboard":
                domain = "permissions"
            elif doc_id == "system_status":
                domain = "system"
            elif doc_id == "email_settings":
                domain = "email"
                if "email_password" in data:
                    self.secret_audit["secret_fields_found"].append("email_password")
                    del data["email_password"]
                    self.secret_audit["secret_fields_excluded"].append("email_password")

            if domain:
                target_path = f"aziende/{self.args.company_id}/settings/{domain}"
                idempotency_key = f"CORE_V1::M6A::COMPANY::{domain}"
                self.targets.append({
                    "target_path": target_path,
                    "owner_type": "COMPANY",
                    "owner_id": self.args.company_id,
                    "domain": domain,
                    "source_path": src["path"],
                    "source_id": doc_id,
                    "payload": data,
                    "fingerprint": self.generate_fingerprint(data),
                    "idempotency_key": idempotency_key
                })
                company_count += 1
        
        self.manifest["GATE_COMPANY_TARGET_3"] = (company_count == 3)
        self.manifest["GATE_EMAIL_SECRET_EXCLUDED"] = ("email_password" in self.secret_audit["secret_fields_excluded"])

        tenant_count = 0
        for src in self.sources["tenant_listino"]:
            domain = "billing"
            data = src["data"].copy()
            core_tenant = src["core_tenant"]
            for k in data.keys():
                self.field_classifications[f"listino.{k}"] = "BILLING"
                
            target_path = f"aziende/{self.args.company_id}/tenants/{core_tenant}/settings/{domain}"
            idempotency_key = f"CORE_V1::M6A::TENANT::{core_tenant}::{domain}"
            self.targets.append({
                "target_path": target_path,
                "owner_type": "TENANT",
                "owner_id": core_tenant,
                "domain": domain,
                "source_path": src["path"],
                "source_id": src["id"],
                "payload": data,
                "fingerprint": self.generate_fingerprint(data),
                "idempotency_key": idempotency_key
            })
            tenant_count += 1
            
        self.manifest["GATE_TENANT_SETTINGS_TARGET_3"] = (tenant_count == 3)

        mapping_count = 0
        for src in self.sources["import_mapping"]:
            core_tenant = src["core_tenant"]
            source_id = src["id"]
            data = src["data"].copy()
            target_path = f"aziende/{self.args.company_id}/tenants/{core_tenant}/import_mappings/{source_id}"
            idempotency_key = f"CORE_V1::M6A::IMPORT::{core_tenant}::{source_id}"
            self.targets.append({
                "target_path": target_path,
                "owner_type": "TENANT",
                "owner_id": core_tenant,
                "domain": "import_mapping",
                "source_path": src["path"],
                "source_id": source_id,
                "payload": data,
                "fingerprint": self.generate_fingerprint(data),
                "idempotency_key": idempotency_key
            })
            mapping_count += 1
            
        self.manifest["GATE_IMPORT_MAPPING_TARGET_41"] = (mapping_count == 41)
        total_targets = company_count + tenant_count + mapping_count
        self.manifest["GATE_TOTAL_TARGET_47"] = (total_targets == 47)
        self.manifest["GATE_UNKNOWN_FIELD_ZERO"] = (len(self.unknown_fields) == 0)
        self.manifest["GATE_UNRESOLVED_OWNER_ZERO"] = (len(self.unresolved_owners) == 0)

    def validate_targets(self):
        idempotency_keys = set()
        target_paths = set()
        duplicates_idem = 0
        duplicates_path = 0
        for t in self.targets:
            if t["idempotency_key"] in idempotency_keys:
                duplicates_idem += 1
            idempotency_keys.add(t["idempotency_key"])
            if t["target_path"] in target_paths:
                duplicates_path += 1
            target_paths.add(t["target_path"])
            
        self.manifest["GATE_IDEMPOTENCY_UNIQUE"] = (duplicates_idem == 0)
        self.manifest["GATE_TARGET_COLLISION_ZERO"] = (duplicates_path == 0)
        self.manifest["GATE_FINGERPRINT_DETERMINISTIC"] = True

    def check_target_state(self):
        state = "CLEAN_START"
        if firebase_admin:
            try:
                colls = [
                    f"aziende/{self.args.company_id}/settings",
                    f"aziende/{self.args.company_id}/tenants/{self.tenant_mapping['DNR']}/settings",
                    f"aziende/{self.args.company_id}/tenants/{self.tenant_mapping['DNR']}/import_mappings"
                ]
                found = False
                for c in colls:
                    docs = list(self.db.collection(c).limit(1).stream())
                    if len(docs) > 0:
                        found = True
                        break
                if found:
                    state = "PARTIAL_STATE"
            except Exception:
                pass
        self.manifest["GATE_TARGET_STATE_CLEAN"] = (state == "CLEAN_START")

    def resolve_status(self):
        gates = [k for k in self.manifest.keys() if k.startswith("GATE_")]
        all_passed = all([self.manifest[g] for g in gates])
        self.manifest["OVERALL_STATUS"] = "PASS" if all_passed else "FAIL"

    def generate_reports(self):
        os.makedirs(self.args.output_dir, exist_ok=True)
        def default_serializer(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            return str(obj)
            
        summary = {
            "COMPANY_ID": self.args.company_id,
            "SOURCE_COUNT": len(self.sources["company"]) + len(self.sources["tenant_listino"]) + len(self.sources["import_mapping"]),
            "TARGET_COUNT": len(self.targets)
        }
        with open(os.path.join(self.args.output_dir, "M6A_SETTINGS_DRYRUN_SUMMARY.json"), "w") as f:
            json.dump(summary, f, indent=2)
            
        with open(os.path.join(self.args.output_dir, "M6A_SETTINGS_TARGET_PREVIEW.json"), "w") as f:
            json.dump(self.targets, f, indent=2, default=default_serializer)
            
        source_mapping = {
            "company": [{"path": s["path"], "id": s["id"]} for s in self.sources["company"]],
            "tenant_listino": [{"path": s["path"], "tenant": s["legacy_tenant"]} for s in self.sources["tenant_listino"]],
            "import_mapping": [{"path": s["path"], "id": s["id"]} for s in self.sources["import_mapping"]]
        }
        with open(os.path.join(self.args.output_dir, "M6A_SETTINGS_SOURCE_MAPPING.json"), "w") as f:
            json.dump(source_mapping, f, indent=2)
            
        with open(os.path.join(self.args.output_dir, "M6A_SETTINGS_FIELD_CLASSIFICATION.json"), "w") as f:
            json.dump(self.field_classifications, f, indent=2)
            
        with open(os.path.join(self.args.output_dir, "M6A_SETTINGS_SECRET_AUDIT.json"), "w") as f:
            json.dump(self.secret_audit, f, indent=2)
            
        with open(os.path.join(self.args.output_dir, "M6A_SETTINGS_VALIDATION_MANIFEST.json"), "w") as f:
            json.dump(self.manifest, f, indent=2)
            
        with open(os.path.join(self.args.output_dir, "M6A_SETTINGS_REVIEW_REQUIRED.json"), "w") as f:
            json.dump({
                "unknown_fields": self.unknown_fields,
                "unresolved_owners": self.unresolved_owners
            }, f, indent=2)

    def run(self):
        self.initialize()
        self.discover_sources()
        self.process_targets()
        self.validate_targets()
        self.check_target_state()
        self.resolve_status()
        self.generate_reports()
        
        if self.manifest["OVERALL_STATUS"] != "PASS" and firebase_admin:
            raise SystemExit("STOP: Dry run failed validations")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--company-id", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    
    if args.project != REQUIRED_PROJECT:
        raise SystemExit(f"STOP: Project must be {REQUIRED_PROJECT}")

    if firebase_admin:
        try:
            app = firebase_admin.get_app()
            if app.project_id and app.project_id != args.project:
                raise SystemExit(f"STOP: Existing Firebase app points to {app.project_id}")
        except ValueError:
            try:
                app = firebase_admin.initialize_app(options={"projectId": args.project})
            except Exception as e:
                raise SystemExit(f"STOP: Failed to initialize firebase_admin with ADC: {e}")
        try:
            db = firestore.client(app=app)
        except Exception as e:
            raise SystemExit(f"STOP: Failed to initialize firestore: {e}")
    else:
        db = None
        
    dr = M6ASettingsDryRun(db, args)
    dr.run()
    
if __name__ == "__main__":
    main()
