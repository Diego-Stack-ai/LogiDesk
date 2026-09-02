"""Copy company-owned warehouses and shuttle lists from Production to Cantiere."""
import argparse, json
import firebase_admin
from firebase_admin import firestore

SOURCE_PROJECT = "log-solution-60007"
TARGET_PROJECT = "log-solutions-cantiere"
COMPANY_ID = "NzXaCgyXxZWWehw1tSlo"
MAPPING = {
    "fatturazione_magazzini_sedi": "magazzini",
    "fatturazione_navette_partenze": "navette_partenze",
    "fatturazione_navette_carichi": "navette_carichi",
    "fatturazione_navette_clienti": "navette_clienti",
    "fatturazione_navette_destinazioni": "navette_destinazioni",
}

def read(ref):
    return {d.id: d.to_dict() or {} for d in ref.stream()}

def run(execute=False):
    src = firestore.client(app=firebase_admin.initialize_app(options={"projectId": SOURCE_PROJECT}, name="lists-source"))
    dst = firestore.client(app=firebase_admin.initialize_app(options={"projectId": TARGET_PROJECT}, name="lists-target"))
    company = dst.collection("aziende").document(COMPANY_ID)
    report, payloads, conflicts = {}, {}, []
    for source_name, target_name in MAPPING.items():
        source = read(src.collection("clienti").document("DNR").collection(source_name))
        target = read(company.collection(target_name))
        payloads[target_name] = source
        current_conflicts = [i for i, data in source.items() if i in target and target[i] != data]
        conflicts.extend(f"{target_name}/{i}" for i in current_conflicts)
        report[target_name] = {"source": len(source), "target": len(target)}
    print(json.dumps({"mode": "EXECUTE" if execute else "PREFLIGHT", "collections": report, "conflicts": conflicts}, indent=2))
    if conflicts or not any(payloads.values()):
        raise RuntimeError("GATE_PREFLIGHT_FAILED")
    if not execute:
        return 0
    batch = dst.batch()
    written = 0
    for target_name, docs in payloads.items():
        for doc_id, data in docs.items():
            batch.set(company.collection(target_name).document(doc_id), data)
            written += 1
    batch.commit()
    failures = []
    for target_name, docs in payloads.items():
        verified = read(company.collection(target_name))
        failures.extend(f"{target_name}/{i}" for i, data in docs.items() if verified.get(i) != data)
    if failures:
        raise RuntimeError("VERIFY_FAILED: " + ", ".join(failures))
    print(json.dumps({"written": written, "verified": written}, indent=2))
    return 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    raise SystemExit(run(parser.parse_args().execute))
