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

class M2VehiclesDryRun:
    def __init__(self, db, args):
        self.db = db
        self.args = args
        self.legacy_data = []
        self.field_audit = {}
        self.target_preview = []
        self.registry_preview = []
        self.review_required = []

        self.stats = {
            "legacy_collection_document_count": 0,
            "configuration_document_count": 0,
            "real_vehicle_source_count": 0,
            "simulated_target_count": 0,
            "ready_count": 0,
            "review_required_count": 0,
            "error_count": 0,
            "empty_targa_real_vehicle_count": 0,
            "duplicate_targa_exact_count": 0,
            "duplicate_targa_normalized_count": 0,
        }

    def run(self):
        self.check_dependencies()
        self.read_source()
        self.audit_fields()
        self.process_vehicles()
        self.write_outputs()

    def check_dependencies(self):
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

    def read_source(self):
        if not self.db:
            return

        mezzi_ref = self.db.collection("mezzi")
        for doc in mezzi_ref.stream():
            self.legacy_data.append({
                "legacy_document_id": doc.id,
                "legacy_data": doc.to_dict()
            })
            self.stats["legacy_collection_document_count"] += 1

    def audit_fields(self):
        for item in self.legacy_data:
            data = item["legacy_data"]
            for key, value in data.items():
                if key not in self.field_audit:
                    self.field_audit[key] = {
                        "PRESENT": 0,
                        "MISSING": 0,
                        "TYPES": set(),
                        "VALUES": {}
                    }
                self.field_audit[key]["PRESENT"] += 1
                val_type = type(value).__name__
                self.field_audit[key]["TYPES"].add(val_type)

                val_str = str(value)
                if val_str not in self.field_audit[key]["VALUES"]:
                    self.field_audit[key]["VALUES"][val_str] = 0
                self.field_audit[key]["VALUES"][val_str] += 1

        total = len(self.legacy_data)
        for key, stats in self.field_audit.items():
            stats["MISSING"] = total - stats["PRESENT"]
            stats["TYPES"] = list(stats["TYPES"])
            # Get top values
            sorted_vals = sorted(stats["VALUES"].items(), key=lambda x: x[1], reverse=True)
            stats["TOP_VALUES"] = {k: v for k, v in sorted_vals[:5]}
            stats["UNIQUE"] = len(stats["VALUES"])
            del stats["VALUES"]

    def process_vehicles(self):
        # First pass to find duplicates only on real vehicles
        exact_targas = {}
        norm_targas = {}
        for item in self.legacy_data:
            doc_id = item["legacy_document_id"]
            if doc_id in CONFIGURATION_DOCUMENT_IDS:
                continue

            data = item["legacy_data"]
            targa = data.get("targa")
            norm_targa = normalize_targa(targa)

            if targa is not None:
                exact_targas[targa] = exact_targas.get(targa, 0) + 1
            if norm_targa:
                norm_targas[norm_targa] = norm_targas.get(norm_targa, 0) + 1

        for item in self.legacy_data:
            doc_id = item["legacy_document_id"]
            data = item["legacy_data"]

            if doc_id in CONFIGURATION_DOCUMENT_IDS:
                self.stats["configuration_document_count"] += 1
                continue

            self.stats["real_vehicle_source_count"] += 1

            status = "READY"
            warnings = []

            targa_raw = data.get("targa")
            targa_norm = normalize_targa(targa_raw)

            if not targa_norm:
                status = "REVIEW_REQUIRED"
                warnings.append("MISSING_TARGA")
                self.stats["empty_targa_real_vehicle_count"] += 1
            else:
                if exact_targas.get(targa_raw, 0) > 1:
                    self.stats["duplicate_targa_exact_count"] += 1
                if norm_targas.get(targa_norm, 0) > 1:
                    status = "REVIEW_REQUIRED"
                    warnings.append("DUPLICATE_NORMALIZED_TARGA")
                    self.stats["duplicate_targa_normalized_count"] += 1

            attivo = data.get("attivo")
            if attivo is None:
                status = "REVIEW_REQUIRED"
                warnings.append("ACTIVE_STATUS_UNCERTAIN")
                attivo_val = False
            else:
                attivo_val = bool(attivo)

            canonical_payload = {
                "targa": targa_norm,
                "attivo": attivo_val,
                "schema_version": 1
            }

            # Field rename mapping
            if "tipologia" in data:
                canonical_payload["tipo"] = data["tipologia"]
            if "patente" in data:
                canonical_payload["patente_richiesta"] = data["patente"]

            canonical_fields = ["modello", "immatricolazione", "note", "scadenza_revisione", "scadenza_atp", "scadenza_assicurazione", "scadenza_tachigrafo", "tessera_carburante", "storico_manutenzioni", "proprietario", "assicurazione", "inUso", "stato", "fotoUrls", "documentiUrls", "copertinaUrl"]

            for f in canonical_fields:
                if f in data:
                    canonical_payload[f] = data[f]

            simulated_id = f"SIM::VEHICLE::{doc_id}"
            idempotency_key = f"CORE_V1::VEHICLE::{doc_id}"
            target_path = f"aziende/{REQUIRED_COMPANY_ID}/mezzi/{simulated_id}"

            fingerprint = generate_fingerprint({
                "entity_type": "vehicle",
                "legacy_document_id": doc_id,
                "preview_model": canonical_payload,
                "idempotency_key": idempotency_key
            })

            self.target_preview.append({
                "path": target_path,
                "payload": canonical_payload
            })
            self.stats["simulated_target_count"] += 1

            self.registry_preview.append({
                "legacy_document_id": doc_id,
                "legacy_targa_raw": targa_raw,
                "normalized_targa": targa_norm,
                "simulated_target_vehicle_id": simulated_id,
                "target_path_preview": target_path,
                "idempotency_key": idempotency_key,
                "migration_status": status,
                "migration_warnings": warnings,
                "fingerprint": fingerprint
            })

            if status == "REVIEW_REQUIRED":
                self.review_required.append({
                    "legacy_document_id": doc_id,
                    "legacy_payload": data,
                    "warnings": warnings,
                    "simulated_target": canonical_payload,
                    "normalized_targa": targa_norm
                })
                self.stats["review_required_count"] += 1
            elif status == "READY":
                self.stats["ready_count"] += 1
            else:
                self.stats["error_count"] += 1

    def write_outputs(self):
        os.makedirs(self.args.output_dir, exist_ok=True)

        overall_status = "PASS"
        if self.stats["error_count"] > 0:
            overall_status = "FAIL"
        elif self.stats["review_required_count"] > 0:
            overall_status = "PASS_WITH_REVIEW"

        summary = {
            "project": self.args.project,
            "company_id": self.args.company_id,
            "mode": "DRY_RUN",
            "source_path": "mezzi",
            "target_path": f"aziende/{REQUIRED_COMPANY_ID}/mezzi",
            "legacy_collection_document_count": self.stats["legacy_collection_document_count"],
            "configuration_document_count": self.stats["configuration_document_count"],
            "configuration_document_ids": CONFIGURATION_DOCUMENT_IDS,
            "real_vehicle_source_count": self.stats["real_vehicle_source_count"],
            "simulated_target_count": self.stats["simulated_target_count"],
            "ready_count": self.stats["ready_count"],
            "review_required_count": self.stats["review_required_count"],
            "error_count": self.stats["error_count"],
            "empty_targa_real_vehicle_count": self.stats["empty_targa_real_vehicle_count"],
            "duplicate_targa_exact_count": self.stats["duplicate_targa_exact_count"],
            "duplicate_targa_normalized_count": self.stats["duplicate_targa_normalized_count"],
            "firestore_write_operations": False,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }

        with open(os.path.join(self.args.output_dir, "M2_VEHICLES_DRYRUN_SUMMARY.json"), "w") as f:
            json.dump(summary, f, indent=2)

        with open(os.path.join(self.args.output_dir, "M2_VEHICLES_FIELD_AUDIT.json"), "w") as f:
            json.dump(self.field_audit, f, indent=2)

        with open(os.path.join(self.args.output_dir, "M2_VEHICLES_TARGET_PREVIEW.json"), "w") as f:
            json.dump(self.target_preview, f, indent=2)

        with open(os.path.join(self.args.output_dir, "M2_VEHICLES_MAPPING_REGISTRY_PREVIEW.json"), "w") as f:
            json.dump(self.registry_preview, f, indent=2)

        with open(os.path.join(self.args.output_dir, "M2_VEHICLES_REVIEW_REQUIRED.json"), "w") as f:
            json.dump(self.review_required, f, indent=2)

        manifest = {
            "source_count": self.stats["real_vehicle_source_count"],
            "target_preview_count": self.stats["simulated_target_count"],
            "unique_simulated_ids": len(set([x["simulated_target_vehicle_id"] for x in self.registry_preview])) == len(self.registry_preview),
            "unique_idempotency_keys": len(set([x["idempotency_key"] for x in self.registry_preview])) == len(self.registry_preview),
            "fingerprints_present": all(["fingerprint" in x for x in self.registry_preview]),
            "zero_write": True,
            "overall_status": overall_status
        }

        with open(os.path.join(self.args.output_dir, "M2_VEHICLES_VALIDATION_MANIFEST.json"), "w") as f:
            json.dump(manifest, f, indent=2)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--company-id", required=True)
    parser.add_argument("--dry-run", action="store_true", required=True)
    parser.add_argument("--output-dir", required=True)

    args = parser.parse_args()

    if args.project != "log-solutions-cantiere":
        print("ERROR: Unauthorized project.")
        sys.exit(1)

    if args.company_id != REQUIRED_COMPANY_ID:
        print("ERROR: Unauthorized company.")
        sys.exit(1)

    db = firestore.Client(project=args.project) if firestore else None

    mig = M2VehiclesDryRun(db, args)
    mig.run()

if __name__ == "__main__":
    main()
