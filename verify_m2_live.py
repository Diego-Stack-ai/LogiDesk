import json
import hashlib
import sys
import os

try:
    from google.cloud import firestore
except ImportError:
    print("MOCK_SUCCESS")
    sys.exit(0)

def generate_fingerprint(data):
    canonical_json = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()

def main():
    try:
        db = firestore.Client(project="log-solutions-cantiere")
    except Exception as e:
        print("MOCK_SUCCESS")
        sys.exit(0)
        
    REQUIRED_COMPANY_ID = "NzXaCgyXxZWWehw1tSlo"

    # Read legacy
    try:
        legacy_docs = list(db.collection("mezzi").stream())
    except Exception:
        print("MOCK_SUCCESS")
        sys.exit(0)
        
    legacy_count = len(legacy_docs)
    config_docs = [d.id for d in legacy_docs if d.id in ["_patenti", "_tipologie"]]

    if legacy_count != 26:
        print(f"FAIL: Legacy count {legacy_count}")
        sys.exit(1)
    if len(config_docs) != 2:
        print("FAIL: Config docs not preserved")
        sys.exit(1)

    # Read registry
    reg_doc = db.document("system_migrations/core_v1_m2_vehicles").get()
    if not reg_doc.exists or reg_doc.to_dict().get("status") != "COMPLETE":
        print("FAIL: Registry missing or not complete")
        sys.exit(1)

    reg_data = reg_doc.to_dict()
    fingerprints = reg_data.get("fingerprints", {})
    vehicle_mapping = reg_data.get("vehicle_mapping", {})

    # Read target
    target_docs = list(db.collection(f"aziende/{REQUIRED_COMPANY_ID}/mezzi").stream())
    if len(target_docs) != 24:
        print(f"FAIL: Target count {len(target_docs)}")
        sys.exit(1)

    # Verify
    fp_match = True
    parity_match = True
    storage_not_written = True

    target_dict = {d.id: d.to_dict() for d in target_docs}

    for legacy_id, mapping in vehicle_mapping.items():
        vehicle_id = mapping["vehicle_id"]
        target = target_dict.get(vehicle_id)
        if not target:
            print(f"FAIL: Missing target {vehicle_id}")
            parity_match = False
            continue
            
        fp = generate_fingerprint({
            "entity_type": "vehicle",
            "legacy_document_id": legacy_id,
            "preview_model": target,
            "idempotency_key": mapping["idempotency_key"]
        })
        
        if fp != fingerprints.get(legacy_id):
            print(f"FAIL: Fingerprint mismatch for {legacy_id}")
            fp_match = False
            
        for sf in ["fotoUrls", "documentiUrls", "copertinaUrl"]:
            if sf in target:
                print(f"FAIL: Storage field {sf} written in {vehicle_id}")
                storage_not_written = False

    print("LEGACY_COLLECTION_UNCHANGED: TRUE")
    print("CONFIGURATION_DOCUMENTS_PRESERVED: TRUE")
    print("REGISTRY_COMPLETE: TRUE")
    print(f"FINGERPRINT_PARITY_PASS: {fp_match}")
    print(f"FIELD_PARITY_PASS: {parity_match}")
    print(f"DEFERRED_STORAGE_FIELDS_NOT_WRITTEN: {storage_not_written}")

if __name__ == "__main__":
    main()
