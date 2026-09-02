"""Migrate July 2026 planning sheets from Production into company scope."""

from __future__ import annotations

import argparse
import copy
import json

import firebase_admin
from firebase_admin import firestore


SOURCE_PROJECT = "log-solution-60007"
TARGET_PROJECT = "log-solutions-cantiere"
COMPANY_ID = "NzXaCgyXxZWWehw1tSlo"
TARGET_MONTH = "2026-07"


def normalize(value: object) -> str:
    return " ".join(str(value or "").strip().upper().split())


def read_collection(ref) -> dict[str, dict]:
    return {doc.id: doc.to_dict() or {} for doc in ref.stream()}


def run(execute: bool) -> int:
    source_app = firebase_admin.initialize_app(
        options={"projectId": SOURCE_PROJECT}, name="planning-source"
    )
    target_app = firebase_admin.initialize_app(
        options={"projectId": TARGET_PROJECT}, name="planning-target"
    )
    source_db = firestore.client(app=source_app)
    target_db = firestore.client(app=target_app)

    source_ref = (
        source_db.collection("clienti")
        .document("DNR")
        .collection("pianificazione_viaggi")
    )
    target_ref = (
        target_db.collection("aziende")
        .document(COMPANY_ID)
        .collection("pianificazioni_viaggi")
    )
    tenant_docs = read_collection(
        target_db.collection("aziende").document(COMPANY_ID).collection("tenants")
    )
    tenant_ids = {
        normalize(data.get("nome") or data.get("name")): tenant_id
        for tenant_id, data in tenant_docs.items()
    }

    source = {
        doc_id: data
        for doc_id, data in read_collection(source_ref).items()
        if doc_id.startswith(TARGET_MONTH + "-")
    }
    transformed: dict[str, dict] = {}
    mapped = 0
    business_assignments = 0
    unresolved: set[str] = set()
    for doc_id, data in source.items():
        payload = copy.deepcopy(data)
        assignments = []
        for assignment in payload.get("assegnazioni", []):
            item = copy.deepcopy(assignment)
            customer = normalize(item.get("cliente"))
            if customer and customer not in {"MAGAZZINO"}:
                business_assignments += 1
                tenant_id = tenant_ids.get(customer)
                if tenant_id:
                    item["tenant_id"] = tenant_id
                    mapped += 1
                else:
                    unresolved.add(customer)
            else:
                item.pop("tenant_id", None)
            assignments.append(item)
        payload["assegnazioni"] = assignments
        payload["dataPianificazione"] = doc_id
        transformed[doc_id] = payload

    existing = read_collection(target_ref)
    conflicts = [doc_id for doc_id, data in existing.items() if doc_id in transformed and data != transformed[doc_id]]
    unexpected = [doc_id for doc_id in existing if doc_id.startswith(TARGET_MONTH + "-") and doc_id not in transformed]
    report = {
        "mode": "EXECUTE" if execute else "PREFLIGHT",
        "month": TARGET_MONTH,
        "source_documents": len(source),
        "target_existing": sum(1 for doc_id in existing if doc_id.startswith(TARGET_MONTH + "-")),
        "business_assignments": business_assignments,
        "tenant_assignments_mapped": mapped,
        "unresolved_customer_names": sorted(unresolved),
        "conflicts": conflicts,
        "unexpected_target_documents": unexpected,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    if len(source) != 25:
        raise RuntimeError(f"GATE_SOURCE_COUNT: attesi 25 documenti, trovati {len(source)}")
    if unresolved or conflicts or unexpected:
        raise RuntimeError("GATE_PREFLIGHT_FAILED")
    if not execute:
        return 0

    batch = target_db.batch()
    for doc_id, payload in transformed.items():
        batch.set(target_ref.document(doc_id), payload)
    batch.commit()
    verified = read_collection(target_ref)
    failures = [doc_id for doc_id, payload in transformed.items() if verified.get(doc_id) != payload]
    if failures:
        raise RuntimeError("GATE_POST_WRITE_VERIFY: " + ", ".join(failures))
    print(json.dumps({"written": len(transformed), "verified": len(transformed)}, indent=2))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    raise SystemExit(run(parser.parse_args().execute))
