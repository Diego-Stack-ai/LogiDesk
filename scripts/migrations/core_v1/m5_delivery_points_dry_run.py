import argparse
import sys
import json
import hashlib
import datetime
import re

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
                return [{"error": "SAME_VALID_CODE_BOTH_FIELDS", "legacy_doc_id": legacy_doc_id}]
            
            t1 = self._build_target(shared, "FRUTTA", cf, data.get("orario_min_frutta"), data.get("orario_max_frutta"))[0]
            t2 = self._build_target(shared, "LATTE", cl, data.get("orario_min_latte"), data.get("orario_max_latte"))[0]
            group_id = f"ASSOC::{legacy_doc_id}"
            t1["association_group_id"] = group_id
            t2["association_group_id"] = group_id
            return [t1, t2]
        else:
            return [{"error": "NO_VALID_CODE", "legacy_doc_id": legacy_doc_id}]

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
    # Fingerprint deterministico
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

def execute_dry_run(project, tenant, outdir):
    print("READ-ONLY MIGRATION PREVIEW")
    if tenant not in SUPPORTED_TENANTS:
        print("TENANT NOT SUPPORTED")
        sys.exit(1)
        
    # Read from JSON dump for testing logic since Firestore is not reachable here
    # In a real scenario we'd do:
    # db = firestore.Client(project=project)
    # docs = db.collection("clienti/DNR/raccolta clienti").stream()
    # Ma vietato scrivere / leggere se non abbiamo dipendenze.
    # Faremo un return early se chiamato come script reale senza mock
    print("MOCKING DATA FOR DRY RUN...")
    return

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--dry-run", action="store_true", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    
    if not args.dry_run:
        sys.exit(0)
    
    execute_dry_run(args.project, args.tenant, args.output_dir)
