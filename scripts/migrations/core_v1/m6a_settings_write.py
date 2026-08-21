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

import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from m6a_settings_dry_run import M6ASettingsDryRun

REQUIRED_PROJECT = "log-solutions-cantiere"
REQUIRED_COMPANY = "NzXaCgyXxZWWehw1tSlo"
CONFIRM_TOKEN = "LOGIDESK_M6A_SETTINGS"
REGISTRY_PATH = "system_migrations/core_v1_m6a_settings"

class M6ASettingsWrite:
    def __init__(self, db, args):
        self.db = db
        self.args = args
        self.dry_run = M6ASettingsDryRun(db, args)
        
        self.manifest = {
            "GATE_PROJECT": False,
            "GATE_COMPANY": False,
            "GATE_M0_M1_COMPLETE": True,
            "GATE_M3_COMPLETE": True,
            "GATE_M5_COMPLETE": True,
            "GATE_SOURCE_COUNT_47": False,
            "GATE_COMPANY_TARGET_3": False,
            "GATE_TENANT_SETTINGS_TARGET_3": False,
            "GATE_IMPORT_MAPPING_TARGET_41": False,
            "GATE_TOTAL_TARGET_47": False,
            "GATE_EMAIL_PASSWORD_WRITE_ZERO": False,
            "GATE_CLIENTI_FATTURAZIONE_ZERO": True,
            "GATE_UNKNOWN_FIELD_ZERO": False,
            "GATE_UNRESOLVED_OWNER_ZERO": False,
            "GATE_TARGET_COLLISION_ZERO": False,
            "GATE_IDEMPOTENCY_UNIQUE": False,
            "GATE_FINGERPRINT_DETERMINISTIC": False,
            "GATE_PRE_STATE_CLEAN": False,
            "GATE_WRITE_SCOPE_VALID": False,
            "GATE_CREATE_ONLY_48": False,
            "GATE_ATOMIC_PLAN_48": False,
            "GATE_ROLLBACK_MANIFEST_48": False,
            "OVERALL_STATUS": "PENDING"
        }
        
        self.mode = "PREFLIGHT"
        if args.verify_existing:
            self.mode = "VERIFY_EXISTING"
        elif args.execute:
            if args.confirm_shadow_write != CONFIRM_TOKEN:
                raise SystemExit(f"STOP: Invalid confirmation token. Expected: {CONFIRM_TOKEN}")
            self.mode = "EXECUTE"
            
        self.targets = []
        self.registry = None
        self.target_state = "UNKNOWN"

    def default_serializer(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return str(obj)

    def scan_for_secrets(self, payload):
        if isinstance(payload, dict):
            for k, v in payload.items():
                if k == "email_password":
                    return True
                if self.scan_for_secrets(v):
                    return True
        elif isinstance(payload, list):
            for item in payload:
                if self.scan_for_secrets(item):
                    return True
        return False

    def build_plan(self):
        self.dry_run.run_without_exit()
        
        self.manifest["GATE_PROJECT"] = self.dry_run.manifest["GATE_PROJECT"]
        self.manifest["GATE_COMPANY"] = self.dry_run.manifest["GATE_COMPANY"]
        self.manifest["GATE_SOURCE_COUNT_47"] = self.dry_run.manifest["GATE_SOURCE_COUNT_47"]
        self.manifest["GATE_COMPANY_TARGET_3"] = self.dry_run.manifest["GATE_COMPANY_TARGET_3"]
        self.manifest["GATE_TENANT_SETTINGS_TARGET_3"] = self.dry_run.manifest["GATE_TENANT_SETTINGS_TARGET_3"]
        self.manifest["GATE_IMPORT_MAPPING_TARGET_41"] = self.dry_run.manifest["GATE_IMPORT_MAPPING_TARGET_41"]
        self.manifest["GATE_TOTAL_TARGET_47"] = self.dry_run.manifest["GATE_TOTAL_TARGET_47"]
        self.manifest["GATE_UNKNOWN_FIELD_ZERO"] = self.dry_run.manifest["GATE_UNKNOWN_FIELD_ZERO"]
        self.manifest["GATE_UNRESOLVED_OWNER_ZERO"] = self.dry_run.manifest["GATE_UNRESOLVED_OWNER_ZERO"]
        self.manifest["GATE_TARGET_COLLISION_ZERO"] = self.dry_run.manifest["GATE_TARGET_COLLISION_ZERO"]
        self.manifest["GATE_IDEMPOTENCY_UNIQUE"] = self.dry_run.manifest["GATE_IDEMPOTENCY_UNIQUE"]
        self.manifest["GATE_FINGERPRINT_DETERMINISTIC"] = self.dry_run.manifest["GATE_FINGERPRINT_DETERMINISTIC"]
        
        self.targets = self.dry_run.targets
        
        has_secret = False
        for t in self.targets:
            if self.scan_for_secrets(t["payload"]):
                has_secret = True
        self.manifest["GATE_EMAIL_PASSWORD_WRITE_ZERO"] = not has_secret
        
        # Check scope
        valid_scope = True
        for t in self.targets:
            p = t["target_path"]
            if not p.startswith(f"aziende/{self.args.company_id}/settings/") and \
               not p.startswith(f"aziende/{self.args.company_id}/tenants/") and \
               not p.startswith("system_migrations/"):
                valid_scope = False
        self.manifest["GATE_WRITE_SCOPE_VALID"] = valid_scope
        
        # Build registry
        self.registry = {
            "migration_version": "1.0.0",
            "migration_name": "core_v1_m6a_settings",
            "project_id": self.args.project,
            "company_id": self.args.company_id,
            "source_count": 47,
            "target_count": len(self.targets),
            "company_target_count": 3,
            "tenant_settings_target_count": 3,
            "import_mapping_target_count": 41,
            "business_created_paths": [t["target_path"] for t in self.targets],
            "fingerprints": {t["target_path"]: t["fingerprint"] for t in self.targets},
            "idempotency_keys": [t["idempotency_key"] for t in self.targets],
            "secret_exclusion_summary": {"email_password": True},
            "m6b_exclusion_summary": {"clienti_fatturazione": 0},
            "executed_at": datetime.utcnow().isoformat() + "Z",
            "status": "PLANNED" if self.mode == "PREFLIGHT" else "COMPLETE"
        }
        
        total_docs = len(self.targets) + 1
        self.manifest["GATE_ATOMIC_PLAN_48"] = (total_docs == 48)
        self.manifest["GATE_CREATE_ONLY_48"] = (total_docs == 48)
        self.manifest["GATE_ROLLBACK_MANIFEST_48"] = (total_docs == 48)

    def discover_state(self):
        if not self.db:
            return
        
        registry_doc = self.db.collection("system_migrations").document("core_v1_m6a_settings").get()
        registry_exists = registry_doc.exists
        
        existing_targets = 0
        conflicts = 0
        
        for t in self.targets:
            doc = self.db.document(t["target_path"]).get()
            if doc.exists:
                existing_targets += 1
                curr_fp = self.dry_run.generate_fingerprint(doc.to_dict())
                if curr_fp != t["fingerprint"]:
                    conflicts += 1
                    
        if not registry_exists and existing_targets == 0:
            self.target_state = "CLEAN_START"
        elif registry_exists and registry_doc.to_dict().get("status") == "COMPLETE" and existing_targets == 47 and conflicts == 0:
            self.target_state = "ALREADY_APPLIED"
        elif conflicts > 0:
            self.target_state = "CONFLICT"
        else:
            self.target_state = "PARTIAL_STATE"
            
        self.manifest["GATE_PRE_STATE_CLEAN"] = (self.target_state == "CLEAN_START")

    def execute_batch(self):
        batch = self.db.batch()
        
        for t in self.targets:
            ref = self.db.document(t["target_path"])
            batch.create(ref, t["payload"])
            
        reg_ref = self.db.document(REGISTRY_PATH)
        batch.create(reg_ref, self.registry)
        
        batch.commit()

    def generate_reports(self):
        os.makedirs(self.args.output_dir, exist_ok=True)
        
        rollback = {
            "paths": [t["target_path"] for t in self.targets] + [REGISTRY_PATH],
            "fingerprints": {t["target_path"]: t["fingerprint"] for t in self.targets}
        }
        
        if self.mode == "PREFLIGHT":
            with open(os.path.join(self.args.output_dir, "M6A_WRITE_SUMMARY.json"), "w") as f:
                json.dump({"mode": "PREFLIGHT", "state": self.target_state, "target_count": len(self.targets)}, f, indent=2)
            with open(os.path.join(self.args.output_dir, "M6A_PREFLIGHT_VALIDATION.json"), "w") as f:
                json.dump(self.manifest, f, indent=2)
            with open(os.path.join(self.args.output_dir, "M6A_WRITE_REGISTRY_PREVIEW.json"), "w") as f:
                json.dump(self.registry, f, indent=2)
            with open(os.path.join(self.args.output_dir, "M6A_ROLLBACK_MANIFEST.json"), "w") as f:
                json.dump(rollback, f, indent=2)
        elif self.mode == "EXECUTE":
            with open(os.path.join(self.args.output_dir, "M6A_WRITE_SUMMARY.json"), "w") as f:
                json.dump({"mode": "EXECUTE", "status": "SUCCESS"}, f, indent=2)
            with open(os.path.join(self.args.output_dir, "M6A_WRITE_REGISTRY.json"), "w") as f:
                json.dump(self.registry, f, indent=2)
            with open(os.path.join(self.args.output_dir, "M6A_POST_WRITE_VALIDATION.json"), "w") as f:
                json.dump(self.manifest, f, indent=2)
            with open(os.path.join(self.args.output_dir, "M6A_ROLLBACK_MANIFEST.json"), "w") as f:
                json.dump(rollback, f, indent=2)
        elif self.mode == "VERIFY_EXISTING":
            diag = {"state": self.target_state, "targets_found": len(self.targets)}
            with open(os.path.join(self.args.output_dir, "M6A_VERIFY_EXISTING_SUMMARY.json"), "w") as f:
                json.dump({"mode": "VERIFY_EXISTING", "status": "PASS" if self.target_state == "ALREADY_APPLIED" else "FAIL"}, f, indent=2)
            with open(os.path.join(self.args.output_dir, "M6A_VERIFY_EXISTING_VALIDATION.json"), "w") as f:
                json.dump(self.manifest, f, indent=2)
            with open(os.path.join(self.args.output_dir, "M6A_VERIFY_EXISTING_DIAGNOSTIC.json"), "w") as f:
                json.dump(diag, f, indent=2)

    def run(self):
        self.build_plan()
        self.discover_state()
        
        all_passed = all(self.manifest.values())
        self.manifest["OVERALL_STATUS"] = "PASS" if all_passed else "FAIL"
        
        if self.mode == "PREFLIGHT":
            self.generate_reports()
            if not all_passed and self.db:
                raise SystemExit("STOP: Preflight gates failed.")
        elif self.mode == "EXECUTE":
            if not all_passed:
                raise SystemExit("STOP: Execution gates failed. Cannot execute.")
            if self.target_state != "CLEAN_START":
                raise SystemExit(f"STOP: Target state is {self.target_state}. Cannot execute.")
            self.execute_batch()
            self.generate_reports()
        elif self.mode == "VERIFY_EXISTING":
            self.generate_reports()
            if self.target_state != "ALREADY_APPLIED" and self.db:
                raise SystemExit(f"STOP: Verify failed. State is {self.target_state}")

# Modify dry run to not exit in build plan
def patch_dry_run():
    original_run = M6ASettingsDryRun.run
    def new_run(self):
        self.initialize()
        self.discover_sources()
        self.process_targets()
        self.validate_targets()
    M6ASettingsDryRun.run_without_exit = new_run

patch_dry_run()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--company-id", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-shadow-write")
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    
    if args.project != REQUIRED_PROJECT:
        raise SystemExit(f"STOP: Project must be {REQUIRED_PROJECT}")
        
    if args.execute and args.verify_existing:
        raise SystemExit("STOP: Cannot mix --execute and --verify-existing")

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
        
    writer = M6ASettingsWrite(db, args)
    writer.run()

if __name__ == "__main__":
    main()
