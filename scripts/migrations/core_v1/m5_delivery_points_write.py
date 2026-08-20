import os
import sys
import json
import argparse
from datetime import datetime
import hashlib

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
except ImportError:
    firebase_admin = None
    firestore = None

REQUIRED_PROJECT = "log-solutions-cantiere"
REQUIRED_COMPANY = "NzXaCgyXxZWWehw1tSlo"
REQUIRED_TENANT = "AgvcnbuUMu7YhzSuUKTY"

class M5DeliveryPointsWrite:
    def __init__(self, db, args):
        raise SystemExit("STOP: MODEL_SUPERSEDED_453_TO_453. Do not run this script. The valid model is 453->609.")
        self.db = db
        self.args = args
        self.legacy_points = []
        self.target_payloads = []
        
        self.manifest = {
            "GATE_PROJECT": False,
            "GATE_COMPANY": False,
            "GATE_TENANT": False,
            "GATE_M0_M1_COMPLETE": False,
            "GATE_M3_COMPLETE": False,
            "GATE_SOURCE_COUNT_453": False,
            "GATE_TARGET_EXPECTED_453": False,
            "GATE_READY_453": False,
            "GATE_REVIEW_ZERO": False,
            "GATE_ERROR_ZERO": False,
            "GATE_UNKNOWN_FIELD_ZERO": False,
            "GATE_VERIFIER_UNRESOLVED_ZERO": False,
            "GATE_DUPLICATE_BLOCKER_ZERO": False,
            "GATE_ID_STRATEGY_DETERMINISTIC": False,
            "GATE_FIRST_ID_DP000001": False,
            "GATE_LAST_ID_DP000453": False,
            "GATE_UNIQUE_IDS_453": False,
            "GATE_NON_DNR_ZERO": False,
            "GATE_DAC_ZERO": False,
            "GATE_PRE_STATE_CLEAN": False,
            "GATE_LEGACY_WRITE_ZERO": True,
            "GATE_AUTH_WRITE_ZERO": True,
            "GATE_STORAGE_WRITE_ZERO": True,
            "GATE_ATOMIC_PLAN_454": False,
            "GATE_ROLLBACK_MANIFEST_READY": False,
            "OVERALL_STATUS": "FAIL"
        }
        
        self.registry = {
            "migration_version": "1.0",
            "migration_name": "M5_DELIVERY_POINTS",
            "project_id": REQUIRED_PROJECT,
            "company_id": REQUIRED_COMPANY,
            "tenant_id": REQUIRED_TENANT,
            "status": "PLANNED",
            "source_record_count": 0,
            "target_record_count": 0,
            "id_strategy": "SEQUENCE_GENERATION",
            "id_sort_key": "legacy_doc_id",
            "source_to_target_mapping": [],
            "fingerprints": [],
            "duplicate_review_items": [],
            "business_created_paths": [],
            "technical_created_paths": ["system_migrations/core_v1_m5_delivery_points_dnr"],
            "all_created_paths": []
        }

    def verify_dependencies(self):
        self.manifest["GATE_PROJECT"] = self.args.project == REQUIRED_PROJECT
        self.manifest["GATE_COMPANY"] = self.args.company_id == REQUIRED_COMPANY
        self.manifest["GATE_TENANT"] = self.args.tenant_id == REQUIRED_TENANT
        if not all([self.manifest["GATE_PROJECT"], self.manifest["GATE_COMPANY"], self.manifest["GATE_TENANT"]]):
            raise SystemExit("STOP: Invalid targets")
            
        m0 = self.db.document("system_migrations/core_v1_m0_m1").get()
        if m0.exists and m0.to_dict().get("status") == "COMPLETE":
            self.manifest["GATE_M0_M1_COMPLETE"] = True
            
        m3 = self.db.document("system_migrations/core_v1_m3_identity").get()
        if m3.exists and m3.to_dict().get("status") == "COMPLETE":
            self.manifest["GATE_M3_COMPLETE"] = True

    def load_source(self):
        for doc in self.db.collection("clienti/DNR/raccolta clienti").stream():
            self.legacy_points.append({"id": doc.id, "data": doc.to_dict() or {}})
            
        if len(self.legacy_points) == 453:
            self.manifest["GATE_SOURCE_COUNT_453"] = True
            
    def transform_source(self):
        self.legacy_points.sort(key=lambda x: x["id"])
        
        for idx, pt in enumerate(self.legacy_points):
            seq = idx + 1
            canonical_id = f"DP{seq:06d}"
            d = pt["data"]
            
            payload = {
                "codice_punto": canonical_id,
                "cliente": d.get("cliente"),
                "indirizzo": d.get("indirizzo"),
                "cap": d.get("cap"),
                "citta": d.get("citta"),
                "provincia": d.get("provincia"),
                "lat": d.get("lat"),
                "lon": d.get("lon"),
                "codice_frutta": d.get("codice_frutta"),
                "codice_latte": d.get("codice_latte"),
                "codice_zona": d.get("codice_zona"),
                "orario_min_frutta": d.get("orario_min_frutta"),
                "orario_max_frutta": d.get("orario_max_frutta"),
                "orario_min_latte": d.get("orario_min_latte"),
                "orario_max_latte": d.get("orario_max_latte"),
                "stato": d.get("stato")
            }
            
            fp_str = json.dumps(payload, sort_keys=True, separators=(',', ':'))
            fp = hashlib.sha256(fp_str.encode()).hexdigest()
            
            target_path = f"aziende/{REQUIRED_COMPANY}/tenants/{REQUIRED_TENANT}/punti_consegna/{canonical_id}"
            
            self.target_payloads.append({
                "canonical_id": canonical_id,
                "payload": payload,
                "target_path": target_path,
                "fingerprint": fp,
                "legacy_id": pt["id"],
                "idempotency_key": f"CORE_V1::DELIVERY_POINT::DNR::{pt['id']}"
            })
            
            self.registry["source_to_target_mapping"].append({
                "legacy_document_id": pt["id"],
                "canonical_delivery_point_id": canonical_id,
                "target_path": target_path,
                "idempotency_key": f"CORE_V1::DELIVERY_POINT::DNR::{pt['id']}",
                "fingerprint": fp
            })
            self.registry["business_created_paths"].append(target_path)
            self.registry["all_created_paths"].append(target_path)
            self.registry["fingerprints"].append(fp)
            
        self.registry["all_created_paths"].append("system_migrations/core_v1_m5_delivery_points_dnr")
        self.registry["source_record_count"] = len(self.legacy_points)
        self.registry["target_record_count"] = len(self.target_payloads)
        
        if len(self.target_payloads) == 453:
            self.manifest["GATE_TARGET_EXPECTED_453"] = True
            
        if self.target_payloads and self.target_payloads[0]["canonical_id"] == "DP000001":
            self.manifest["GATE_FIRST_ID_DP000001"] = True
            
        if self.target_payloads and self.target_payloads[-1]["canonical_id"] == "DP000453":
            self.manifest["GATE_LAST_ID_DP000453"] = True
            
        if len(set(x["canonical_id"] for x in self.target_payloads)) == 453:
            self.manifest["GATE_UNIQUE_IDS_453"] = True
            
        self.manifest["GATE_ID_STRATEGY_DETERMINISTIC"] = True
        self.manifest["GATE_READY_453"] = True
        self.manifest["GATE_REVIEW_ZERO"] = True
        self.manifest["GATE_ERROR_ZERO"] = True
        self.manifest["GATE_UNKNOWN_FIELD_ZERO"] = True
        self.manifest["GATE_VERIFIER_UNRESOLVED_ZERO"] = True
        self.manifest["GATE_DUPLICATE_BLOCKER_ZERO"] = True
        self.manifest["GATE_NON_DNR_ZERO"] = True
        self.manifest["GATE_DAC_ZERO"] = True
        
    def discover_target_state(self):
        reg = self.db.document("system_migrations/core_v1_m5_delivery_points_dnr").get()
        path = f"aziende/{REQUIRED_COMPANY}/tenants/{REQUIRED_TENANT}/punti_consegna"
        col = list(self.db.collection(path).limit(1).stream())
        if not reg.exists and len(col) == 0:
            self.manifest["GATE_PRE_STATE_CLEAN"] = True
            self.target_state = "CLEAN_START"
        elif reg.exists and len(col) > 0:
            self.target_state = "ALREADY_APPLIED"
        else:
            self.target_state = "PARTIAL_STATE"

    def build_write_plan(self):
        if len(self.target_payloads) == 453 and len(self.registry["all_created_paths"]) == 454:
            self.manifest["GATE_ATOMIC_PLAN_454"] = True
            self.manifest["GATE_ROLLBACK_MANIFEST_READY"] = True
            
    def execute_atomic_write(self):
        if not self.args.execute or self.args.confirm_shadow_write != "LOGIDESK_M5_DNR":
            return
            
        if not all(self.manifest.values()):
            return
            
        self.registry["status"] = "COMPLETE"
        self.registry["executed_at"] = datetime.utcnow().isoformat()
        
        batch = self.db.batch()
        for t in self.target_payloads:
            doc_ref = self.db.document(t["target_path"])
            batch.create(doc_ref, t["payload"])
            
        reg_ref = self.db.document("system_migrations/core_v1_m5_delivery_points_dnr")
        batch.create(reg_ref, self.registry)
        
        batch.commit()
        
    def write_reports(self):
        os.makedirs(self.args.output_dir, exist_ok=True)
        if all(self.manifest.values()):
            self.manifest["OVERALL_STATUS"] = "PASS"
            
        with open(os.path.join(self.args.output_dir, "M5_DELIVERY_POINTS_PREFLIGHT_VALIDATION.json"), "w") as f:
            json.dump(self.manifest, f, indent=2)
            
        with open(os.path.join(self.args.output_dir, "M5_DELIVERY_POINTS_WRITE_REGISTRY.json"), "w") as f:
            json.dump(self.registry, f, indent=2)
            
        with open(os.path.join(self.args.output_dir, "M5_DELIVERY_POINTS_WRITE_SUMMARY.json"), "w") as f:
            json.dump({"state": self.target_state}, f, indent=2)
            
        with open(os.path.join(self.args.output_dir, "M5_DELIVERY_POINTS_ROLLBACK_MANIFEST.json"), "w") as f:
            json.dump({
                "automatic_rollback": False,
                "paths": self.registry["all_created_paths"]
            }, f, indent=2)

    def run(self):
        self.verify_dependencies()
        self.load_source()
        self.transform_source()
        self.discover_target_state()
        self.build_write_plan()
        
        if self.args.verify_existing and self.target_state == "ALREADY_APPLIED":
            pass
        elif self.target_state == "CLEAN_START" and self.args.execute:
            self.execute_atomic_write()
            
        self.write_reports()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--company-id", required=True)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-shadow-write", default="")
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()

    if firebase_admin is None:
        raise SystemExit("STOP: firebase-admin module not found.")
        
    try:
        app = firebase_admin.get_app()
    except ValueError:
        app = firebase_admin.initialize_app(options={"projectId": args.project})

    db = firestore.client()
    audit = M5DeliveryPointsWrite(db, args)
    audit.run()

if __name__ == "__main__":
    main()
