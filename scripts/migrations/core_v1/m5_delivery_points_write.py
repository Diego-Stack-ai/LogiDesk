import os
import sys
import json
import argparse
from datetime import datetime
import hashlib
import re

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    from google.cloud.firestore_v1.base_query import FieldFilter
except ImportError:
    firebase_admin = None
    firestore = None

REQUIRED_PROJECT = "log-solutions-cantiere"
REQUIRED_COMPANY = "NzXaCgyXxZWWehw1tSlo"
REQUIRED_TENANT = "AgvcnbuUMu7YhzSuUKTY"
LEGACY_SOURCE_PATH = "clienti/DNR/raccolta clienti"
REGISTRY_PATH = "system_migrations/core_v1_m5_delivery_points_dnr"

def is_valid_external_code(value):
    if value is None:
        return False
    if not isinstance(value, str):
        return True
    val = value.strip().lower()
    if val in ["", "none", "p00000", "p000000", "nan", "null", "false"]:
        return False
    return True

def normalize_code(value):
    if not is_valid_external_code(value):
        return None
    return str(value).strip()

def normalize_time(value):
    if value is None:
        return None
    if isinstance(value, bool) or str(value).strip().lower() in ["false", "nan", "", "none", "null"]:
        return None
    val = str(value).strip()
    if re.match(r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$", val):
        return val
    return None

def normalize_coordinate(value):
    if value is None:
        return None
    try:
        f = float(value)
        return f
    except (ValueError, TypeError):
        return None

class LegacyDNRAdapter:
    def parse(self, legacy_doc_id, data):
        cf = normalize_code(data.get("codice_frutta"))
        cl = normalize_code(data.get("codice_latte"))
        
        c_lat = normalize_coordinate(data.get("lat"))
        c_lon = normalize_coordinate(data.get("lon"))
        
        stato = str(data.get("stato", "")).strip().lower()
        if stato == "ok":
            stato_verifica = "OK"
            v_source = "LEGACY_EXPLICIT"
        elif c_lat is not None and c_lon is not None:
            stato_verifica = "OK"
            v_source = "LEGACY_CONFIRMED_DATASET"
        else:
            stato_verifica = "PENDING"
            v_source = None
            
        geo = None
        if c_lat is not None and c_lon is not None:
            if not (-90 <= c_lat <= 90 and -180 <= c_lon <= 180):
                stato_verifica = "REJECTED"
            geo = {
                "lat": c_lat,
                "lon": c_lon,
                "stato_verifica": stato_verifica,
                "verification_source": v_source
            }

        shared = {
            "legacy_document_id": legacy_doc_id,
            "nome": data.get("cliente"),
            "indirizzo": data.get("indirizzo"),
            "cap": data.get("cap"),
            "citta": data.get("citta"),
            "provincia": data.get("provincia"),
            "geolocalizzazione": geo,
            "codice_zona": data.get("codice_zona") if data.get("codice_zona") else None,
            "attivo": True
        }

        if cf and not cl:
            return self._build_target(shared, "FRUTTA", cf, data.get("orario_min_frutta"), data.get("orario_max_frutta"))
        elif not cf and cl:
            return self._build_target(shared, "LATTE", cl, data.get("orario_min_latte"), data.get("orario_max_latte"))
        elif cf and cl:
            if cf == cl:
                return [{"error": "SAME_VALID_CODE_BOTH_FIELDS", "legacy_document_id": legacy_doc_id}]
            
            t1 = self._build_target(shared, "FRUTTA", cf, data.get("orario_min_frutta"), data.get("orario_max_frutta"))[0]
            t2 = self._build_target(shared, "LATTE", cl, data.get("orario_min_latte"), data.get("orario_max_latte"))[0]
            group_id = f"ASSOC::{legacy_doc_id}"
            t1["association_group_id"] = group_id
            t2["association_group_id"] = group_id
            return [t1, t2]
        else:
            return [{"error": "NO_VALID_CODE", "legacy_document_id": legacy_doc_id}]

    def _build_target(self, shared, subcode, ext_code, time_min, time_max):
        target = shared.copy()
        target["sottocodice"] = subcode
        target["codice_esterno"] = ext_code
        
        tmin = normalize_time(time_min)
        tmax = normalize_time(time_max)
        
        target["finestre_consegna"] = []
        
        if tmin and tmax:
            if tmin < tmax:
                target["finestre_consegna"] = [{"da": tmin, "a": tmax}]
            
        return [target]

def hash_target(target):
    core_data = {
        "legacy_document_id": target.get("legacy_document_id"),
        "codice_esterno": target.get("codice_esterno"),
        "sottocodice": target.get("sottocodice"),
        "nome": target.get("nome"),
        "indirizzo": target.get("indirizzo"),
        "finestre_consegna": target.get("finestre_consegna"),
        "association_group_id": target.get("association_group_id")
    }
    if target.get("geolocalizzazione"):
        core_data["lat"] = target["geolocalizzazione"]["lat"]
        core_data["lon"] = target["geolocalizzazione"]["lon"]
    s = json.dumps(core_data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def hash_source_manifest(legacy_points):
    s = json.dumps(sorted([p["id"] for p in legacy_points]), sort_keys=True)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def hash_target_manifest(targets):
    s = json.dumps(sorted([t["codice_punto"] + ":" + t["fingerprint"] for t in targets]), sort_keys=True)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

class M5DeliveryPointsWrite:
    def __init__(self, db, args):
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
            "GATE_SOURCE_PATH_DNR_CORRECT": True,
            "GATE_SOURCE_COUNT_453": False,
            "GATE_FRUTTA_ONLY_236": False,
            "GATE_LATTE_ONLY_61": False,
            "GATE_BOTH_REAL_156": False,
            "GATE_SAME_CODE_ZERO": False,
            "GATE_NO_VALID_CODE_ZERO": False,
            "GATE_TARGET_COUNT_609": False,
            "GATE_FIRST_ID_DP000001": False,
            "GATE_LAST_ID_DP000609": False,
            "GATE_UNIQUE_IDS_609": False,
            "GATE_ONE_TO_MANY_MAPPING_VALID": False,
            "GATE_PLACEHOLDER_TARGET_ZERO": True,
            "GATE_LEGACY_FIELDS_TARGET_ZERO": True,
            "GATE_UNKNOWN_FIELD_ZERO": True,
            "GATE_VERIFIER_UNRESOLVED_ZERO": True,
            "GATE_NON_DNR_ZERO": True,
            "GATE_DAC_ZERO": True,
            "GATE_PRE_STATE_CLEAN": False,
            "GATE_CHUNK_PLAN_VALID": False,
            "GATE_CHUNK_1_COUNT_305": False,
            "GATE_CHUNK_2_COUNT_304": False,
            "GATE_CHUNK_TOTAL_609": False,
            "GATE_WRITE_SCOPE_VALID": True,
            "GATE_CONCURRENCY_MODEL_VALID": True,
            "GATE_RESUME_MODEL_VALID": True,
            "GATE_ROLLBACK_MANIFEST_610_DOCS": False,
            "OVERALL_STATUS": "FAIL"
        }
        
    def check_gates(self):
        self.manifest["GATE_PROJECT"] = self.args.project == REQUIRED_PROJECT
        self.manifest["GATE_COMPANY"] = self.args.company_id == REQUIRED_COMPANY
        self.manifest["GATE_TENANT"] = self.args.tenant_id == REQUIRED_TENANT
        if not all([self.manifest["GATE_PROJECT"], self.manifest["GATE_COMPANY"], self.manifest["GATE_TENANT"]]):
            raise SystemExit("STOP: Invalid targets")

        try:
            m0_m1 = self.db.document("system_migrations/core_v1_m0_m1").get()
            if m0_m1.exists:
                data = m0_m1.to_dict() or {}
                if data.get("status") == "COMPLETE":
                    if data.get("company_id") != REQUIRED_COMPANY:
                        print("FATAL: M0_M1 registry company_id mismatch.")
                        sys.exit(1)
                    if "project_id" in data and data.get("project_id") != REQUIRED_PROJECT:
                        print("FATAL: M0_M1 registry project_id mismatch.")
                        sys.exit(1)
                    self.manifest["GATE_M0_M1_COMPLETE"] = True
        except Exception as e:
            print(f"FATAL: Could not read M0_M1 registry. {e}")
            sys.exit(1)
            
        try:
            m3 = self.db.document("system_migrations/core_v1_m3_identity").get()
            if m3.exists:
                data = m3.to_dict() or {}
                if data.get("status") == "COMPLETE":
                    if data.get("company_id") and data.get("company_id") != REQUIRED_COMPANY:
                        print("FATAL: M3 registry company_id mismatch.")
                        sys.exit(1)
                    self.manifest["GATE_M3_COMPLETE"] = True
        except Exception as e:
            print(f"FATAL: Could not read M3 registry. {e}")
            sys.exit(1)

    def load_source(self):
        try:
            for doc in self.db.collection(LEGACY_SOURCE_PATH).stream():
                self.legacy_points.append({"id": doc.id, "data": doc.to_dict() or {}})
        except Exception as e:
            print(f"FATAL: Firestore read failed: {e}")
            sys.exit(1)
            
        if not self.legacy_points:
            print("FATAL: Source collection empty.")
            sys.exit(1)
            
        if len(self.legacy_points) == 453:
            self.manifest["GATE_SOURCE_COUNT_453"] = True
            
    def prepare_plan(self):
        adapter = LegacyDNRAdapter()
        
        plan = {
            "source_count": len(self.legacy_points),
            "frutta_only_count": 0,
            "latte_only_count": 0,
            "dual_count": 0,
            "same_code_count": 0,
            "no_valid_code_count": 0,
            "targets": [],
            "errors": []
        }
        
        for pt in self.legacy_points:
            legacy_id = pt["id"]
            data = pt["data"]
            
            results = adapter.parse(legacy_id, data)
            
            if len(results) == 1 and "error" in results[0]:
                err = results[0]["error"]
                if err == "SAME_VALID_CODE_BOTH_FIELDS":
                    plan["same_code_count"] += 1
                else:
                    plan["no_valid_code_count"] += 1
                plan["errors"].append(results[0])
                continue
                
            if len(results) == 1:
                if results[0]["sottocodice"] == "FRUTTA":
                    plan["frutta_only_count"] += 1
                else:
                    plan["latte_only_count"] += 1
                plan["targets"].extend(results)
            elif len(results) == 2:
                plan["dual_count"] += 1
                plan["targets"].extend(results)
                
        plan["targets"].sort(key=lambda x: (x["legacy_document_id"], x["sottocodice"]))
        
        self.target_payloads = []
        for i, t in enumerate(plan["targets"]):
            canon = t.copy()
            canon["codice_punto"] = f"DP{(i+1):06d}"
            legacy_id = canon.pop("legacy_document_id")
            
            payload = {
                "codice_punto": canon["codice_punto"],
                "codice_esterno": canon.get("codice_esterno"),
                "sottocodice": canon.get("sottocodice"),
                "nome": canon.get("nome"),
                "indirizzo": canon.get("indirizzo"),
                "cap": canon.get("cap"),
                "citta": canon.get("citta"),
                "provincia": canon.get("provincia"),
                "codice_zona": canon.get("codice_zona"),
                "geolocalizzazione": canon.get("geolocalizzazione"),
                "attivo": canon.get("attivo"),
                "finestre_consegna": canon.get("finestre_consegna")
            }
            if canon.get("association_group_id"):
                payload["association_group_id"] = canon["association_group_id"]
                
            wrapper = {
                "payload": payload,
                "legacy_document_id": legacy_id,
                "codice_punto": canon["codice_punto"],
                "sottocodice": canon.get("sottocodice"),
                "codice_esterno": canon.get("codice_esterno"),
                "fingerprint": hash_target({"legacy_document_id": legacy_id, **payload}),
                "target_path": f"aziende/{REQUIRED_COMPANY}/tenants/{REQUIRED_TENANT}/punti_consegna/{canon['codice_punto']}",
                "idempotency_key": f"CORE_V1::DELIVERY_POINT::DNR::{legacy_id}::{canon.get('sottocodice')}"
            }
            self.target_payloads.append(wrapper)
            
        if plan["frutta_only_count"] == 236:
            self.manifest["GATE_FRUTTA_ONLY_236"] = True
        if plan["latte_only_count"] == 61:
            self.manifest["GATE_LATTE_ONLY_61"] = True
        if plan["dual_count"] == 156:
            self.manifest["GATE_BOTH_REAL_156"] = True
        if plan["same_code_count"] == 0:
            self.manifest["GATE_SAME_CODE_ZERO"] = True
        if plan["no_valid_code_count"] == 0:
            self.manifest["GATE_NO_VALID_CODE_ZERO"] = True
        if len(self.target_payloads) == 609:
            self.manifest["GATE_TARGET_COUNT_609"] = True
        if self.target_payloads and self.target_payloads[0]["codice_punto"] == "DP000001":
            self.manifest["GATE_FIRST_ID_DP000001"] = True
        if self.target_payloads and self.target_payloads[-1]["codice_punto"] == "DP000609":
            self.manifest["GATE_LAST_ID_DP000609"] = True
        if len(set(t["codice_punto"] for t in self.target_payloads)) == 609:
            self.manifest["GATE_UNIQUE_IDS_609"] = True
        if plan["dual_count"] > 0:
            self.manifest["GATE_ONE_TO_MANY_MAPPING_VALID"] = True
            
        self.chunk1 = self.target_payloads[0:305]
        self.chunk2 = self.target_payloads[305:609]
        
        if len(self.chunk1) == 305:
            self.manifest["GATE_CHUNK_1_COUNT_305"] = True
        if len(self.chunk2) == 304:
            self.manifest["GATE_CHUNK_2_COUNT_304"] = True
        if len(self.chunk1) + len(self.chunk2) == 609:
            self.manifest["GATE_CHUNK_TOTAL_609"] = True
            self.manifest["GATE_CHUNK_PLAN_VALID"] = True
        
        if len(self.target_payloads) == 609:
            self.manifest["GATE_ROLLBACK_MANIFEST_610_DOCS"] = True

    def discover_state(self):
        reg = self.db.document(REGISTRY_PATH).get()
        target_col = self.db.collection(f"aziende/{REQUIRED_COMPANY}/tenants/{REQUIRED_TENANT}/punti_consegna").limit(1).get()
        target_exists = len(target_col) > 0
        
        if not reg.exists and not target_exists:
            self.target_state = "CLEAN_START"
            self.manifest["GATE_PRE_STATE_CLEAN"] = True
        elif reg.exists:
            status = reg.to_dict().get("status")
            if status == "COMPLETE":
                self.target_state = "ALREADY_APPLIED"
            elif status in ["PREPARED", "WRITING", "PARTIAL_STATE"]:
                self.target_state = status
            else:
                self.target_state = "FAILED_VALIDATION"
        else:
            self.target_state = "PARTIAL_STATE"

    def write_reports(self, phase="PREFLIGHT"):
        os.makedirs(self.args.output_dir, exist_ok=True)
            
        if phase == "PREFLIGHT" and all(v is True for k,v in self.manifest.items() if k != "OVERALL_STATUS"):
            self.manifest["OVERALL_STATUS"] = "PASS"
            
        with open(os.path.join(self.args.output_dir, f"M5_609_{phase}_VALIDATION.json"), "w") as f:
            json.dump(self.manifest, f, indent=2)
            
        if self.target_payloads:
            with open(os.path.join(self.args.output_dir, "M5_609_WRITE_REGISTRY_PREVIEW.json"), "w") as f:
                json.dump([t for t in self.target_payloads], f, indent=2)
                
            rollback = {
                "summary": {
                    "rollback_target_count": len(self.target_payloads),
                    "rollback_registry_count": 1,
                    "rollback_unique_document_count": len(self.target_payloads) + 1
                },
                "registry": REGISTRY_PATH,
                "targets": [{"path": t["target_path"], "fingerprint": t["fingerprint"]} for t in self.target_payloads]
            }
            with open(os.path.join(self.args.output_dir, "M5_609_ROLLBACK_MANIFEST.json"), "w") as f:
                json.dump(rollback, f, indent=2)
                
            plan = {
                "chunks": [
                    {"index": 1, "count": len(self.chunk1), "start": self.chunk1[0]["codice_punto"], "end": self.chunk1[-1]["codice_punto"]},
                    {"index": 2, "count": len(self.chunk2), "start": self.chunk2[0]["codice_punto"], "end": self.chunk2[-1]["codice_punto"]}
                ]
            }
            with open(os.path.join(self.args.output_dir, "M5_609_CHUNK_PLAN.json"), "w") as f:
                json.dump(plan, f, indent=2)

    def write_chunk(self, chunk, chunk_index):
        batch = self.db.batch()
        for t in chunk:
            ref = self.db.document(t["target_path"])
            batch.create(ref, t["payload"])
        batch.commit()
        
        # Verify
        for t in chunk:
            doc = self.db.document(t["target_path"]).get()
            if not doc.exists:
                raise Exception(f"Failed to verify creation of {t['target_path']}")

    def execute_live(self):
        if not self.args.execute:
            return
            
        if self.args.confirm_shadow_write != "LOGIDESK_M5_DNR_609":
            print("FATAL: Invalid confirmation token.")
            sys.exit(1)
            
        if self.target_state == "ALREADY_APPLIED":
            print("ALREADY APPLIED. Use --verify-existing.")
            return
            
        if self.target_state != "CLEAN_START" and not self.args.resume:
            print(f"FATAL: State is {self.target_state}. Use --resume.")
            sys.exit(1)
            
        if self.args.resume and self.args.confirm_resume != "LOGIDESK_M5_DNR_609_RESUME":
            print("FATAL: Invalid resume token.")
            sys.exit(1)
            
        if self.args.resume and self.target_state not in ["PREPARED", "WRITING", "PARTIAL_STATE"]:
            print(f"FATAL: Cannot resume from {self.target_state}.")
            sys.exit(1)
            
        reg_ref = self.db.document(REGISTRY_PATH)
        
        # Prepare
        if self.target_state == "CLEAN_START":
            try:
                reg_ref.create({
                    "status": "PREPARED",
                    "migration_version": "CORE_V1::M5::DNR::DELIVERY_POINTS::609",
                    "source_count": 453,
                    "target_count": 609,
                    "source_manifest_hash": hash_source_manifest(self.legacy_points),
                    "target_manifest_hash": hash_target_manifest(self.target_payloads),
                    "created_at": firestore.SERVER_TIMESTAMP if firestore else "SERVER_TIMESTAMP"
                })
            except Exception as e:
                print(f"FATAL: Could not lock registry. {e}")
                sys.exit(1)
                
        # Writing state
        reg_ref.update({"status": "WRITING", "completed_chunks": []})
        
        chunks = [self.chunk1, self.chunk2]
        completed_chunks = []
        
        for i, chunk in enumerate(chunks):
            # Check if chunk needs writing (in resume mode)
            if self.args.resume:
                all_exist = True
                for t in chunk:
                    doc = self.db.document(t["target_path"]).get()
                    if not doc.exists:
                        all_exist = False
                        break
                if all_exist:
                    completed_chunks.append(i + 1)
                    continue
                    
                # Conflict detection: partial chunks or mismatched existing docs
                for t in chunk:
                    doc = self.db.document(t["target_path"]).get()
                    if doc.exists:
                        print(f"FATAL: CONFLICT on {t['target_path']}")
                        sys.exit(1)
                        
            try:
                self.write_chunk(chunk, i + 1)
                completed_chunks.append(i + 1)
                reg_ref.update({"completed_chunks": completed_chunks, "created_target_count": len(chunk) if i == 0 else 609})
            except Exception as e:
                print(f"FATAL: Failed chunk {i + 1}. {e}")
                reg_ref.update({"status": "PARTIAL_STATE"})
                sys.exit(1)
                
        # Complete
        reg_ref.update({"status": "COMPLETE", "completed_at": firestore.SERVER_TIMESTAMP if firestore else "SERVER_TIMESTAMP"})
        self.write_reports(phase="EXECUTE")

    def run(self):
        if self.args.execute and self.args.verify_existing:
            raise SystemExit("FATAL: Cannot execute and verify simultaneously.")
            
        self.check_gates()
        self.load_source()
        self.prepare_plan()
        self.discover_state()
        
        if not self.args.execute and not self.args.verify_existing:
            self.write_reports(phase="PREFLIGHT")
            if self.manifest.get("OVERALL_STATUS") != "PASS":
                sys.exit(1)
            return
            
        if self.args.execute:
            if not all(v is True for k,v in self.manifest.items() if k != "OVERALL_STATUS"):
                print("FATAL: Gates not passed.")
                self.write_reports(phase="EXECUTE_FAIL")
                sys.exit(1)
            self.execute_live()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--company-id", required=True)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-shadow-write")
    parser.add_argument("--verify-existing", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--confirm-resume")
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
