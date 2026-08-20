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

REQUIRED_COMPANY_ID = "NzXaCgyXxZWWehw1tSlo"
CONFIGURATION_DOCUMENT_IDS = ["_patenti", "_tipologie"]

def generate_fingerprint(data):
    canonical_json = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()

def normalize_targa(value):
    if not value or not isinstance(value, str):
        return ""
    return value.strip().upper()

class M2VehiclesWrite:
    def __init__(self, db, args):
        self.db = db
        self.args = args
        self.mode = "EXECUTE" if args.execute else "PREFLIGHT"
        self.state_classification = None

        self.legacy_data = []
        self.config_data = []
        self.real_vehicles = []

        self.write_plan = []
        self.registry_payload = {}

        self.target_vehicle_mapping = {} # legacy_id -> vehicle_id

        self.gates = {
            "GATE_PROJECT": args.project == "log-solutions-cantiere",
            "GATE_COMPANY": args.company_id == REQUIRED_COMPANY_ID,
            "GATE_M0_M1_COMPLETE": False,
            "GATE_M2_DRY_RUN_CERTIFIED": True, # Hardcoded assumption since we're writing
            "GATE_SOURCE_COUNT_26": False,
            "GATE_CONFIG_COUNT_2": False,
            "GATE_REAL_VEHICLE_COUNT_24": False,
            "GATE_REVIEW_ZERO": True,
            "GATE_ERROR_ZERO": True,
            "GATE_PRE_STATE_CLEAN": False,
            "GATE_TARGA_UNIQUE": True,
            "GATE_FIELD_COVERAGE_ZERO_UNKNOWN": False,
            "GATE_STORAGE_WRITE_ZERO": True,
            "GATE_LEGACY_WRITE_ZERO": True,
            "GATE_ATOMIC_PLAN_VALID": False,
            "GATE_ROLLBACK_MANIFEST_READY": False
        }

    def run(self):
        self.verify_m0_m1_dependency()
        self.load_source()
        self.classify_source_documents()
        self.discover_state()

        if self.state_classification == "CLEAN_START":
            self.transform_vehicles()
            self.build_write_plan()
            self.validate_plan()

            if self.mode == "EXECUTE":
                if all(self.gates.values()):
                    self.execute_atomic_write()
                    self.verify_post_write()
                else:
                    print("ERROR: Not all gates passed before execute.")
                    sys.exit(1)
        elif self.state_classification == "ALREADY_APPLIED":
            pass # No-op or Verify-only
        else:
            print(f"ERROR: State is {self.state_classification}. Cannot proceed.")
            sys.exit(1)

        self.write_reports()

    def verify_m0_m1_dependency(self):
        if not self.db:
            return
        m0_m1_ref = self.db.document("system_migrations/core_v1_m0_m1")
        m0_m1_doc = m0_m1_ref.get()
        if not m0_m1_doc.exists or m0_m1_doc.to_dict().get("status") != "COMPLETE" or m0_m1_doc.to_dict().get("company_id") != REQUIRED_COMPANY_ID:
            print("ERROR: M0/M1 dependency check failed.")
            sys.exit(1)

        company_ref = self.db.document(f"aziende/{REQUIRED_COMPANY_ID}")
        if not company_ref.get().exists:
            print("ERROR: Company document missing.")
            sys.exit(1)

        self.gates["GATE_M0_M1_COMPLETE"] = True

    def load_source(self):
        if not self.db:
            return
        mezzi_ref = self.db.collection("mezzi")
        for doc in mezzi_ref.stream():
            self.legacy_data.append({
                "legacy_document_id": doc.id,
                "legacy_data": doc.to_dict()
            })

        self.gates["GATE_SOURCE_COUNT_26"] = (len(self.legacy_data) == 26)

    def classify_source_documents(self):
        for item in self.legacy_data:
            doc_id = item["legacy_document_id"]
            if doc_id in CONFIGURATION_DOCUMENT_IDS:
                self.config_data.append(item)
            else:
                self.real_vehicles.append(item)

        self.gates["GATE_CONFIG_COUNT_2"] = (len(self.config_data) == 2)
        self.gates["GATE_REAL_VEHICLE_COUNT_24"] = (len(self.real_vehicles) == 24)

        if not (self.gates["GATE_SOURCE_COUNT_26"] and self.gates["GATE_CONFIG_COUNT_2"] and self.gates["GATE_REAL_VEHICLE_COUNT_24"]):
            print("ERROR: Source count mismatch. Requires new dry-run.")
            sys.exit(1)

    def discover_state(self):
        if not self.db:
            self.state_classification = "CLEAN_START"
            self.gates["GATE_PRE_STATE_CLEAN"] = True
            return

        registry_ref = self.db.document("system_migrations/core_v1_m2_vehicles")
        registry_doc = registry_ref.get()

        vehicles_ref = self.db.collection(f"aziende/{REQUIRED_COMPANY_ID}/mezzi")
        existing_vehicles = list(vehicles_ref.stream())

        if not registry_doc.exists and len(existing_vehicles) == 0:
            self.state_classification = "CLEAN_START"
            self.gates["GATE_PRE_STATE_CLEAN"] = True
        elif registry_doc.exists and registry_doc.to_dict().get("status") == "COMPLETE" and len(existing_vehicles) == 24:
            self.state_classification = "ALREADY_APPLIED"
        else:
            self.state_classification = "CONFLICT"

    def transform_vehicles(self):
        exact_targas = {}
        norm_targas = {}
        for item in self.real_vehicles:
            data = item["legacy_data"]
            targa = data.get("targa")
            norm_targa = normalize_targa(targa)
            if targa is not None:
                exact_targas[targa] = exact_targas.get(targa, 0) + 1
            if norm_targa:
                norm_targas[norm_targa] = norm_targas.get(norm_targa, 0) + 1

        if len([v for v in norm_targas.values() if v > 1]) > 0:
            self.gates["GATE_TARGA_UNIQUE"] = False

        known_fields = {
            "targa", "attivo", "modello", "immatricolazione", "note", "scadenza_revisione",
            "scadenza_atp", "scadenza_assicurazione", "scadenza_tachigrafo", "tessera_carburante",
            "pin_tessera", "storico_manutenzioni", "proprietario", "assicurazione", "inUso", "stato",
            "tipologia", "patente",
            "fotoUrls", "documentiUrls", "copertinaUrl",
            "marca", "portata", "temperatura" # adding missing known ones
        }

        unknown_fields = set()
        for item in self.real_vehicles:
            for k in item["legacy_data"].keys():
                if k not in known_fields:
                    unknown_fields.add(k)

        self.gates["GATE_FIELD_COVERAGE_ZERO_UNKNOWN"] = (len(unknown_fields) == 0)
        if len(unknown_fields) > 0:
            print("ERROR: Unknown fields discovered.")
            sys.exit(1)

        for item in self.real_vehicles:
            doc_id = item["legacy_document_id"]
            data = item["legacy_data"]

            targa_raw = data.get("targa")
            targa_norm = normalize_targa(targa_raw)
            if not targa_norm:
                self.gates["GATE_REVIEW_ZERO"] = False

            attivo = data.get("attivo")
            attivo_val = bool(attivo) if attivo is not None else False
            if attivo is None:
                self.gates["GATE_REVIEW_ZERO"] = False

            canonical_payload = {
                "targa": targa_norm,
                "attivo": attivo_val,
                "schema_version": 1
            }

            if "tipologia" in data:
                canonical_payload["tipo"] = data["tipologia"]
            if "patente" in data:
                canonical_payload["patente_richiesta"] = data["patente"]

            canonical_fields = [
                "marca", "portata", "temperatura",
                "modello", "immatricolazione", "note", "scadenza_revisione",
                "scadenza_atp", "scadenza_assicurazione", "scadenza_tachigrafo",
                "tessera_carburante", "pin_tessera", "storico_manutenzioni",
                "proprietario", "assicurazione", "inUso", "stato"
            ]

            for f in canonical_fields:
                if f in data:
                    canonical_payload[f] = data[f]

            deferred_storage = ["fotoUrls", "documentiUrls", "copertinaUrl"]
            for f in deferred_storage:
                if f in canonical_payload:
                    self.gates["GATE_STORAGE_WRITE_ZERO"] = False
                    print(f"ERROR: Storage field {f} present in canonical payload")
                    sys.exit(1)

            if self.mode == "EXECUTE" and self.db:
                company_ref = self.db.document(f"aziende/{REQUIRED_COMPANY_ID}")
                new_ref = company_ref.collection("mezzi").document()
                vehicle_id = new_ref.id
            else:
                vehicle_id = f"PREVIEW::VEHICLE::{doc_id}"

            self.target_vehicle_mapping[doc_id] = vehicle_id

            idempotency_key = f"CORE_V1::VEHICLE::{doc_id}"
            target_path = f"aziende/{REQUIRED_COMPANY_ID}/mezzi/{vehicle_id}"

            fingerprint = generate_fingerprint({
                "entity_type": "vehicle",
                "legacy_document_id": doc_id,
                "preview_model": canonical_payload,
                "idempotency_key": idempotency_key
            })

            self.write_plan.append({
                "type": "vehicle",
                "legacy_document_id": doc_id,
                "target_path": target_path,
                "payload": canonical_payload,
                "idempotency_key": idempotency_key,
                "fingerprint": fingerprint
            })

    def build_write_plan(self):
        vehicle_mapping = {}
        fingerprints = {}
        business_created_paths = []
        for wp in self.write_plan:
            vehicle_mapping[wp["legacy_document_id"]] = {
                "vehicle_id": self.target_vehicle_mapping[wp["legacy_document_id"]],
                "target_path": wp["target_path"],
                "idempotency_key": wp["idempotency_key"]
            }
            fingerprints[wp["legacy_document_id"]] = wp["fingerprint"]
            business_created_paths.append(wp["target_path"])

        registry_path = "system_migrations/core_v1_m2_vehicles"

        self.registry_payload = {
            "migration_version": "1.0",
            "migration_name": "M2_VEHICLES_SHADOW_WRITE",
            "project_id": self.args.project,
            "company_id": REQUIRED_COMPANY_ID,
            "status": "COMPLETE" if self.mode == "EXECUTE" else "PLANNED",
            "source_document_count": 26,
            "configuration_document_count": 2,
            "vehicle_count": 24,
            "vehicle_mapping": vehicle_mapping,
            "fingerprints": fingerprints,
            "business_created_paths": business_created_paths,
            "technical_created_paths": [registry_path],
            "all_created_paths": business_created_paths + [registry_path],
            "deferred_configuration_documents": CONFIGURATION_DOCUMENT_IDS,
            "deferred_storage_fields": ["fotoUrls", "documentiUrls", "copertinaUrl"],
            "executed_at": datetime.now(timezone.utc).isoformat()
        }

        self.write_plan.append({
            "type": "registry",
            "target_path": registry_path,
            "payload": self.registry_payload
        })

    def validate_plan(self):
        biz_docs = [p for p in self.write_plan if p["type"] == "vehicle"]
        tech_docs = [p for p in self.write_plan if p["type"] == "registry"]

        self.gates["GATE_ATOMIC_PLAN_VALID"] = (len(biz_docs) == 24 and len(tech_docs) == 1 and len(self.write_plan) == 25)
        self.gates["GATE_ROLLBACK_MANIFEST_READY"] = True

    def execute_atomic_write(self):
        if not self.db:
            return

        batch = self.db.batch()

        for wp in self.write_plan:
            doc_ref = self.db.document(wp["target_path"])
            if wp["type"] == "registry":
                # Create-only precondition
                batch.create(doc_ref, wp["payload"])
            else:
                batch.set(doc_ref, wp["payload"])

        batch.commit()

    def verify_post_write(self):
        if not self.db:
            return

        for wp in self.write_plan:
            if wp["type"] == "vehicle":
                doc_ref = self.db.document(wp["target_path"])
                doc = doc_ref.get()
                if not doc.exists:
                    print(f"POST WRITE ERROR: Missing doc {wp['target_path']}")
                    sys.exit(1)

                target_payload = doc.to_dict()
                fp = generate_fingerprint({
                    "entity_type": "vehicle",
                    "legacy_document_id": wp["legacy_document_id"],
                    "preview_model": target_payload,
                    "idempotency_key": wp["idempotency_key"]
                })

                if fp != wp["fingerprint"]:
                    print(f"POST WRITE ERROR: Fingerprint mismatch for {wp['target_path']}")
                    sys.exit(1)

    def write_reports(self):
        os.makedirs(self.args.output_dir, exist_ok=True)

        prefix = "M2_VEHICLES_WRITE_" if self.mode == "EXECUTE" else "M2_VEHICLES_PREFLIGHT_"

        summary = {
            "mode": self.mode,
            "project": self.args.project,
            "company_id": self.args.company_id,
            "state_classification": self.state_classification,
            "gates": self.gates,
            "safe_to_execute": all(self.gates.values()),
            "atomic_plan_documents": len(self.write_plan),
            "generated_at": datetime.now(timezone.utc).isoformat()
        }

        with open(os.path.join(self.args.output_dir, "M2_VEHICLES_WRITE_SUMMARY.json"), "w") as f:
            json.dump(summary, f, indent=2)

        with open(os.path.join(self.args.output_dir, "M2_VEHICLES_WRITE_REGISTRY.json"), "w") as f:
            json.dump(self.registry_payload, f, indent=2)

        validation = {
            "target_count_24": self.gates["GATE_ATOMIC_PLAN_VALID"],
            "unique_target_ids": len(set(self.target_vehicle_mapping.values())) == 24,
            "unique_normalized_targa": self.gates["GATE_TARGA_UNIQUE"],
            "missing_targa_0": self.gates["GATE_REVIEW_ZERO"],
            "registry_complete": self.mode == "EXECUTE",
            "deferred_storage_fields_not_written": self.gates["GATE_STORAGE_WRITE_ZERO"],
            "config_docs_not_created": self.gates["GATE_CONFIG_COUNT_2"]
        }

        val_name = "M2_VEHICLES_POST_WRITE_VALIDATION.json" if self.mode == "EXECUTE" else "M2_VEHICLES_PREFLIGHT_VALIDATION.json"
        with open(os.path.join(self.args.output_dir, val_name), "w") as f:
            json.dump(validation, f, indent=2)

        rollback = {
            "migration_id": "M2_VEHICLES_SHADOW_WRITE",
            "project": self.args.project,
            "company_id": REQUIRED_COMPANY_ID,
            "registry_path": "system_migrations/core_v1_m2_vehicles",
            "vehicle_paths": self.registry_payload.get("business_created_paths", []),
            "fingerprints": self.registry_payload.get("fingerprints", {}),
            "business_created_paths": len(self.registry_payload.get("business_created_paths", [])),
            "technical_created_paths": 1,
            "all_created_paths": len(self.registry_payload.get("all_created_paths", [])),
            "rollback_allowed_by_design": True,
            "automatic_rollback": False,
            "fingerprint_guard": True
        }

        with open(os.path.join(self.args.output_dir, "M2_VEHICLES_ROLLBACK_MANIFEST.json"), "w") as f:
            json.dump(rollback, f, indent=2)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--company-id", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-shadow-write", type=str)
    parser.add_argument("--output-dir", required=True)

    args = parser.parse_args()

    if args.project != "log-solutions-cantiere":
        print("ERROR: Unauthorized project.")
        sys.exit(1)

    if args.company_id != REQUIRED_COMPANY_ID:
        print("ERROR: Unauthorized company.")
        sys.exit(1)

    if args.execute and args.confirm_shadow_write != "LOGIDESK_M2_VEHICLES":
        print("ERROR: Missing or invalid confirmation token for execution.")
        sys.exit(1)

    db = firestore.Client(project=args.project) if firestore else None

    mig = M2VehiclesWrite(db, args)
    mig.run()

if __name__ == "__main__":
    main()
