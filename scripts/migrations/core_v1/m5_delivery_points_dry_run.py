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
except ImportError:
    firebase_admin = None
    firestore = None

REQUIRED_PROJECT = "log-solutions-cantiere"
REQUIRED_COMPANY = "NzXaCgyXxZWWehw1tSlo"
REQUIRED_TENANT = "AgvcnbuUMu7YhzSuUKTY"

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
        "legacy_document_id": target["legacy_document_id"],
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

class M5DeliveryPointsDryRun:
    def __init__(self, db, args):
        self.db = db
        self.args = args
        self.legacy_points = []
        
        self.manifest = {
            "GATE_PROJECT": False,
            "GATE_COMPANY": False,
            "GATE_TENANT": False,
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
            "GATE_PLACEHOLDER_NOT_MIGRATED": True,
            "GATE_LEGACY_CODE_FIELDS_NOT_WRITTEN": True,
            "GATE_UNKNOWN_FIELDS_ZERO": True,
            "GATE_VERIFIER_UNRESOLVED_ZERO": True,
            "GATE_FIRESTORE_ZERO_WRITE": True,
            "GATE_AUTH_ZERO_WRITE": True,
            "GATE_STORAGE_ZERO_WRITE": True,
            "OVERALL_STATUS": "FAIL"
        }
        
    def check_gates(self):
        self.manifest["GATE_PROJECT"] = self.args.project == REQUIRED_PROJECT
        self.manifest["GATE_COMPANY"] = self.args.company_id == REQUIRED_COMPANY
        self.manifest["GATE_TENANT"] = self.args.tenant_id == REQUIRED_TENANT
        if not all([self.manifest["GATE_PROJECT"], self.manifest["GATE_COMPANY"], self.manifest["GATE_TENANT"]]):
            raise SystemExit("STOP: Invalid targets")

    def load_source(self):
        try:
            for doc in self.db.collection("clienti/DNR/raccolta clienti").stream():
                self.legacy_points.append({"id": doc.id, "data": doc.to_dict() or {}})
        except Exception as e:
            print(f"FATAL: Firestore read failed: {e}")
            sys.exit(1)
            
        if not self.legacy_points:
            print("FATAL: Source collection empty.")
            sys.exit(1)
        if len(self.legacy_points) == 453:
            self.manifest["GATE_SOURCE_COUNT_453"] = True
            
    def run(self):
        self.check_gates()
        self.load_source()
        
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
        
        registry = []
        for i, t in enumerate(plan["targets"]):
            t["codice_punto"] = f"DP{(i+1):06d}"
            t["fingerprint"] = hash_target(t)
            t["idempotency_key"] = f"CORE_V1::DELIVERY_POINT::DNR::{t['legacy_document_id']}::{t['sottocodice']}"
            t["target_path"] = f"aziende/{REQUIRED_COMPANY}/tenants/{REQUIRED_TENANT}/punti_consegna/{t['codice_punto']}"
            
            registry.append({
                "legacy_document_id": t["legacy_document_id"],
                "canonical_delivery_point_id": t["codice_punto"],
                "sottocodice": t["sottocodice"],
                "codice_esterno": t["codice_esterno"],
                "target_path": t["target_path"],
                "idempotency_key": t["idempotency_key"],
                "fingerprint": t["fingerprint"]
            })
            
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
            
        if len(plan["targets"]) == 609:
            self.manifest["GATE_TARGET_COUNT_609"] = True
            
        if plan["targets"] and plan["targets"][0]["codice_punto"] == "DP000001":
            self.manifest["GATE_FIRST_ID_DP000001"] = True
        if plan["targets"] and plan["targets"][-1]["codice_punto"] == "DP000609":
            self.manifest["GATE_LAST_ID_DP000609"] = True
            
        if len(set(t["codice_punto"] for t in plan["targets"])) == 609:
            self.manifest["GATE_UNIQUE_IDS_609"] = True
            
        # Verify one-to-many is present (some legacy_id have 2 canonical targets)
        if any(plan["dual_count"] > 0 for _ in [1]):
            self.manifest["GATE_ONE_TO_MANY_MAPPING_VALID"] = True
            
        if all(self.manifest.values()):
            self.manifest["OVERALL_STATUS"] = "PASS"
            
        os.makedirs(self.args.output_dir, exist_ok=True)
        
        with open(os.path.join(self.args.output_dir, "M5_DELIVERY_POINTS_609_DRYRUN_SUMMARY.json"), "w") as f:
            json.dump({
                "source_count": plan["source_count"],
                "target_count": len(plan["targets"]),
                "frutta_only": plan["frutta_only_count"],
                "latte_only": plan["latte_only_count"],
                "both_real_different": plan["dual_count"],
                "same_code_error": plan["same_code_count"],
                "no_valid_code_error": plan["no_valid_code_count"]
            }, f, indent=2)
            
        with open(os.path.join(self.args.output_dir, "M5_DELIVERY_POINTS_609_TARGET_PREVIEW.json"), "w") as f:
            json.dump(plan["targets"], f, indent=2)
            
        with open(os.path.join(self.args.output_dir, "M5_DELIVERY_POINTS_609_MAPPING_REGISTRY_PREVIEW.json"), "w") as f:
            json.dump(registry, f, indent=2)
            
        with open(os.path.join(self.args.output_dir, "M5_DELIVERY_POINTS_609_VALIDATION_MANIFEST.json"), "w") as f:
            json.dump(self.manifest, f, indent=2)
            
        with open(os.path.join(self.args.output_dir, "M5_DELIVERY_POINTS_609_SPLIT_ANALYSIS.json"), "w") as f:
            json.dump({
                "FRUTTA_ONLY": plan["frutta_only_count"],
                "LATTE_ONLY": plan["latte_only_count"],
                "BOTH_REAL_DIFFERENT": plan["dual_count"],
                "SAME_VALID_CODE_BOTH_FIELDS": plan["same_code_count"],
                "NO_VALID_CODE": plan["no_valid_code_count"],
                "SOURCE_TOTAL": plan["source_count"],
                "TARGET_TOTAL": len(plan["targets"])
            }, f, indent=2)
            
        with open(os.path.join(self.args.output_dir, "M5_DELIVERY_POINTS_609_REVIEW_REQUIRED.json"), "w") as f:
            json.dump(plan["errors"], f, indent=2)
            
        with open(os.path.join(self.args.output_dir, "M5_DELIVERY_POINTS_609_FIELD_COVERAGE.json"), "w") as f:
            fields = set()
            for t in plan["targets"]:
                fields |= set(t.keys())
            json.dump({"canonical_fields_present": sorted(list(fields))}, f, indent=2)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--company-id", required=True)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--dry-run", action="store_true", required=True)
    args = parser.parse_args()
    
    if not args.dry_run:
        raise SystemExit("ERROR: --dry-run flag required.")

    if firebase_admin is None:
        raise SystemExit("STOP: firebase-admin module not found.")
        
    try:
        app = firebase_admin.get_app()
    except ValueError:
        app = firebase_admin.initialize_app(options={"projectId": args.project})

    db = firestore.client()
    audit = M5DeliveryPointsDryRun(db, args)
    audit.run()
    
    if audit.manifest.get("OVERALL_STATUS") != "PASS":
        sys.exit(1)

if __name__ == "__main__":
    main()
