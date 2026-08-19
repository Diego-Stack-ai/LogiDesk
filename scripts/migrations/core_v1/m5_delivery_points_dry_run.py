import argparse
import sys
import json
import hashlib
import datetime
import re
import os

SUPPORTED_TENANTS = ["DNR"]

def is_legacy_null_code(value):
    if value is None:
        return True
    if not isinstance(value, str):
        return False
    val = value.strip().lower()
    return val in ["", "none", "p00000", "p000000", "nan", "null"]

def normalize_code(value):
    if is_legacy_null_code(value):
        return None
    return str(value).strip()

def normalize_time(value):
    if value is None:
        return None
    if isinstance(value, bool) or str(value).strip().lower() in ["false", "nan", "", "none"]:
        return None
    val = str(value).strip()
    if re.match(r"^([01][0-9]|2[0-3]):[0-5][0-9]$", val):
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
    def parse(self, legacy_doc_id, legacy_path, data):
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
            "source": {"legacy_path": legacy_path, "legacy_document_id": legacy_doc_id},
            "nome": data.get("cliente"),
            "indirizzo": data.get("indirizzo"),
            "cap": data.get("cap"),
            "citta": data.get("citta"),
            "provincia": data.get("provincia"),
            "geolocalizzazione": geo,
            "codice_zona": data.get("codice_zona") if data.get("codice_zona") else None,
            "attivo": True
        }

        # Classify
        if cf and not cl:
            return self._build_target(shared, "FRUTTA", cf, data.get("orario_min_frutta"), data.get("orario_max_frutta"))
        elif not cf and cl:
            return self._build_target(shared, "LATTE", cl, data.get("orario_min_latte"), data.get("orario_max_latte"))
        elif cf and cl:
            if cf == cl:
                return [{"error": "SAME_VALID_CODE_BOTH_FIELDS", "legacy_doc_id": legacy_doc_id, "data": data}]
            
            t1 = self._build_target(shared, "FRUTTA", cf, data.get("orario_min_frutta"), data.get("orario_max_frutta"))[0]
            t2 = self._build_target(shared, "LATTE", cl, data.get("orario_min_latte"), data.get("orario_max_latte"))[0]
            group_id = f"ASSOC::{legacy_doc_id}"
            t1["association_group_id"] = group_id
            t2["association_group_id"] = group_id
            return [t1, t2]
        else:
            return [{"error": "NO_VALID_CODE", "legacy_doc_id": legacy_doc_id, "data": data}]

    def _build_target(self, shared, subcode, ext_code, time_min, time_max):
        target = shared.copy()
        target["sottocodice"] = subcode
        target["codice_esterno"] = ext_code
        target["simulated_punto_id"] = f"SIM::{shared['source']['legacy_document_id']}::{subcode}"
        
        tmin = normalize_time(time_min)
        tmax = normalize_time(time_max)
        
        target["migration_status"] = "READY"
        target["migration_warnings"] = []
        target["finestre_consegna"] = []
        
        if tmin and tmax:
            if tmin < tmax:
                target["finestre_consegna"] = [{"da": tmin, "a": tmax}]
            else:
                target["migration_status"] = "REVIEW_REQUIRED"
                target["migration_warnings"].append("INVALID_TIME_RANGE")
        elif tmin or tmax:
            target["migration_status"] = "REVIEW_REQUIRED"
            target["migration_warnings"].append("PARTIAL_TIME_WINDOW")
            
        if not target["geolocalizzazione"]:
            target["migration_status"] = "REVIEW_REQUIRED"
            target["migration_warnings"].append("GEO_INVALID")
            
        return [target]

def hash_target(target):
    core_data = {
        "legacy_doc_id": target["source"]["legacy_document_id"],
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

def build_plan(project, tenant, documents):
    adapter = LegacyDNRAdapter()
    
    plan = {
        "source_document_count": 0,
        "frutta_only_count": 0,
        "latte_only_count": 0,
        "dual_count": 0,
        "same_code_count": 0,
        "no_valid_code_count": 0,
        "anomalous_count": 0,
        
        "targets": [],
        "errors": []
    }
    
    for legacy_id, legacy_path, data in documents:
        plan["source_document_count"] += 1
        results = adapter.parse(legacy_id, legacy_path, data)
        
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
            
    # Assegnazione sequence e ordinamento
    plan["targets"].sort(key=lambda x: (x["source"]["legacy_document_id"], x["sottocodice"]))
    
    for i, t in enumerate(plan["targets"]):
        t["codice_punto"] = f"DP{(i+1):06d}"
        t["fingerprint"] = hash_target(t)
        
    return plan

def write_output_files(outdir, project, tenant, plan):
    os.makedirs(outdir, exist_ok=True)
    
    targets = plan["targets"]
    
    # Calculate summary metrics
    frutta_target = sum(1 for t in targets if t["sottocodice"] == "FRUTTA")
    latte_target = sum(1 for t in targets if t["sottocodice"] == "LATTE")
    ready = sum(1 for t in targets if t["migration_status"] == "READY")
    review = sum(1 for t in targets if t["migration_status"] == "REVIEW_REQUIRED")
    
    assoc_groups = set(t["association_group_id"] for t in targets if t.get("association_group_id"))
    
    ext_codes = [t.get("codice_esterno") for t in targets if t.get("codice_esterno")]
    dup_ext = len(ext_codes) - len(set(ext_codes))
    
    sim_ids = [t.get("simulated_punto_id") for t in targets]
    dup_sim = len(sim_ids) - len(set(sim_ids))
    
    dp_codes = [t.get("codice_punto") for t in targets]
    dup_dp = len(dp_codes) - len(set(dp_codes))
    
    geo_ok_explicit = sum(1 for t in targets if t.get("geolocalizzazione", {}).get("verification_source") == "LEGACY_EXPLICIT")
    geo_ok_dataset = sum(1 for t in targets if t.get("geolocalizzazione", {}).get("verification_source") == "LEGACY_CONFIRMED_DATASET")

    summary = {
        "project": project,
        "tenant": tenant,
        "mode": "DRY_RUN",
        "source_path": f"clienti/{tenant}/raccolta clienti",
        "source_document_count": plan["source_document_count"],
        "frutta_only_count": plan["frutta_only_count"],
        "latte_only_count": plan["latte_only_count"],
        "dual_count": plan["dual_count"],
        "same_code_count": plan["same_code_count"],
        "no_valid_code_count": plan["no_valid_code_count"],
        "anomalous_count": plan["anomalous_count"],
        "simulated_target_count": len(targets),
        "frutta_target_count": frutta_target,
        "latte_target_count": latte_target,
        "ready_count": ready,
        "review_required_count": review,
        "error_count": len(plan["errors"]),
        "association_group_count": len(assoc_groups),
        "duplicate_external_code_count": dup_ext,
        "duplicate_codice_punto_count": dup_dp,
        "duplicate_simulated_id_count": dup_sim,
        "explicit_geo_ok_count": geo_ok_explicit,
        "confirmed_dataset_geo_count": geo_ok_dataset,
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z"
    }

    manifest = {
        "source_count_expected": 453,
        "source_count_actual": plan["source_document_count"],
        "target_count_expected": 609,
        "target_count_actual": len(targets),
        "count_validation_pass": plan["source_document_count"] == 453 and len(targets) == 609,
        "frutta_only_expected": 236,
        "frutta_only_actual": plan["frutta_only_count"],
        "latte_only_expected": 61,
        "latte_only_actual": plan["latte_only_count"],
        "dual_expected": 156,
        "dual_actual": plan["dual_count"],
        "classification_validation_pass": plan["frutta_only_count"] == 236 and plan["latte_only_count"] == 61 and plan["dual_count"] == 156,
        "frutta_target_expected": 392,
        "frutta_target_actual": frutta_target,
        "latte_target_expected": 217,
        "latte_target_actual": latte_target,
        "association_group_expected": 156,
        "association_group_actual": len(assoc_groups),
        "association_validation_pass": len(assoc_groups) == 156,
        "duplicate_validation_pass": dup_ext == 0 and dup_dp == 0 and dup_sim == 0,
        "canonical_validation_pass": all(t.get("nome") and t.get("codice_esterno") and t.get("geolocalizzazione") for t in targets),
        "write_operations_detected": False,
        "review_required_count": review,
        "error_count": len(plan["errors"])
    }
    manifest["overall_validation_pass"] = (
        manifest["count_validation_pass"] and 
        manifest["classification_validation_pass"] and 
        manifest["association_validation_pass"] and 
        manifest["duplicate_validation_pass"] and 
        manifest["canonical_validation_pass"] and 
        manifest["error_count"] == 0
    )

    registry = []
    for t in targets:
        registry.append({
            "legacy_path": t["source"]["legacy_path"],
            "legacy_document_id": t["source"]["legacy_document_id"],
            "target_simulated_id": t["simulated_punto_id"],
            "codice_punto": t["codice_punto"],
            "codice_esterno": t["codice_esterno"],
            "sottocodice": t["sottocodice"],
            "association_group_id": t.get("association_group_id"),
            "migration_status": t["migration_status"],
            "fingerprint": t["fingerprint"]
        })
        
    reviews = [t for t in targets if t["migration_status"] == "REVIEW_REQUIRED"] + plan["errors"]

    with open(os.path.join(outdir, "M5_DNR_DRYRUN_SUMMARY.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    with open(os.path.join(outdir, "M5_DNR_TARGET_PREVIEW.json"), "w", encoding="utf-8") as f:
        json.dump(targets, f, ensure_ascii=False, indent=2)
    with open(os.path.join(outdir, "M5_DNR_MIGRATION_REGISTRY_PREVIEW.json"), "w", encoding="utf-8") as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)
    with open(os.path.join(outdir, "M5_DNR_REVIEW_REQUIRED.json"), "w", encoding="utf-8") as f:
        json.dump(reviews, f, ensure_ascii=False, indent=2)
    with open(os.path.join(outdir, "M5_DNR_VALIDATION_MANIFEST.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

def execute_dry_run(project, tenant, outdir):
    print("READ-ONLY MIGRATION PREVIEW")
    if tenant not in SUPPORTED_TENANTS:
        print("TENANT NOT SUPPORTED")
        sys.exit(1)
        
    try:
        from google.cloud import firestore
        db = firestore.Client(project=project)
        path = f"clienti/{tenant}/raccolta clienti"
        print(f"Reading from {path} in project {project}...")
        docs = db.collection(path).stream()
        documents = [(d.id, path, d.to_dict()) for d in docs]
    except Exception as e:
        print(f"Could not connect to Firestore: {e}")
        print("MOCKING DATA NOT ALLOWED. ABORTING.")
        sys.exit(1)
        
    plan = build_plan(project, tenant, documents)
    write_output_files(outdir, project, tenant, plan)
    print("Dry-run completed successfully.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--dry-run", action="store_true", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    
    if not args.dry_run:
        print("ERROR: --dry-run flag is required.")
        sys.exit(1)
    
    execute_dry_run(args.project, args.tenant, args.output_dir)
