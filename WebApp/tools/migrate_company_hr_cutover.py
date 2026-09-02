"""Copia controllata di giustificativi e presenze luglio nel perimetro aziendale."""

from __future__ import annotations

import argparse
import json

import firebase_admin
from firebase_admin import firestore


EXPECTED_PROJECT = "log-solutions-cantiere"
COMPANY_ID = "NzXaCgyXxZWWehw1tSlo"
TARGET_MONTH = "2026-07"


def init_db(project_id: str):
    if project_id != EXPECTED_PROJECT:
        raise RuntimeError(f"GATE_PROJECT: atteso {EXPECTED_PROJECT}, ricevuto {project_id}")
    if not firebase_admin._apps:
        firebase_admin.initialize_app(options={"projectId": project_id})
    return firestore.client()


def is_target_month(data: dict) -> bool:
    month = str(data.get("mese") or "")
    day = str(data.get("data") or "")
    return month == TARGET_MONTH or day.startswith(f"{TARGET_MONTH}-")


def comparable(data: dict) -> dict:
    return {key: value for key, value in data.items() if key != "migrated_at"}


def employee_display_name(data: dict) -> str:
    return " ".join(
        part for part in (str(data.get("nome") or "").strip(), str(data.get("cognome") or "").strip())
        if part
    )


def collect(db, source_name: str, target_name: str, predicate):
    rows = []
    conflicts = []
    already_applied = []
    target = db.collection("aziende").document(COMPANY_ID).collection(target_name)

    for source_doc in db.collection(source_name).stream():
        source_data = source_doc.to_dict() or {}
        if not predicate(source_data):
            continue
        target_doc = target.document(source_doc.id).get()
        if target_doc.exists:
            if comparable(target_doc.to_dict() or {}) == comparable(source_data):
                already_applied.append(source_doc.id)
            else:
                conflicts.append(source_doc.id)
        rows.append((source_doc.id, source_data))
    return rows, already_applied, conflicts


def run(project_id: str, execute: bool) -> int:
    db = init_db(project_id)
    reasons, reasons_existing, reasons_conflicts = collect(
        db, "giustificativi", "giustificativi", lambda _: True
    )
    attendance, attendance_existing, attendance_conflicts = collect(
        db, "presenze", "presenze", is_target_month
    )
    conflicts = reasons_conflicts + attendance_conflicts
    employees = list(
        db.collection("aziende").document(COMPANY_ID).collection("dipendenti").stream()
    )
    employee_label_updates = [
        (employee.reference, expected)
        for employee in employees
        if (expected := employee_display_name(employee.to_dict() or {}))
        and (employee.to_dict() or {}).get("nome_completo") != expected
    ]

    report = {
        "project": project_id,
        "company_id": COMPANY_ID,
        "month": TARGET_MONTH,
        "mode": "EXECUTE" if execute else "PREFLIGHT",
        "giustificativi_source": len(reasons),
        "giustificativi_already_applied": len(reasons_existing),
        "presenze_source": len(attendance),
        "presenze_already_applied": len(attendance_existing),
        "employee_labels_pending": len(employee_label_updates),
        "conflicts": conflicts,
        "root_deletions": 0,
    }
    print(json.dumps(report, indent=2, sort_keys=True, default=str))
    if conflicts:
        raise RuntimeError("GATE_TARGET_CONFLICT: " + ", ".join(conflicts))
    if not execute:
        return 0

    writes = 0
    pending = []
    for target_name, rows, existing in (
        ("giustificativi", reasons, set(reasons_existing)),
        ("presenze", attendance, set(attendance_existing)),
    ):
        target = db.collection("aziende").document(COMPANY_ID).collection(target_name)
        for doc_id, data in rows:
            if doc_id in existing:
                continue
            pending.append(
                (
                    target.document(doc_id),
                    {**data, "migrated_at": firestore.SERVER_TIMESTAMP},
                )
            )
            writes += 1

    for offset in range(0, len(pending), 400):
        batch = db.batch()
        for reference, data in pending[offset : offset + 400]:
            batch.create(reference, data)
        batch.commit()

    for offset in range(0, len(employee_label_updates), 400):
        batch = db.batch()
        for reference, name in employee_label_updates[offset : offset + 400]:
            batch.set(reference, {"nome_completo": name}, merge=True)
            writes += 1
        batch.commit()

    _, reasons_verified, reasons_verify_conflicts = collect(
        db, "giustificativi", "giustificativi", lambda _: True
    )
    attendance_rows, attendance_verified, attendance_verify_conflicts = collect(
        db, "presenze", "presenze", is_target_month
    )
    verification_conflicts = reasons_verify_conflicts + attendance_verify_conflicts
    if verification_conflicts or len(attendance_verified) != len(attendance_rows):
        raise RuntimeError(
            "GATE_POST_VERIFY: copia non verificata; conflitti="
            + ", ".join(verification_conflicts)
        )

    employee_labels_verified = 0
    for employee in db.collection("aziende").document(COMPANY_ID).collection("dipendenti").stream():
        data = employee.to_dict() or {}
        expected = employee_display_name(data)
        if expected and data.get("nome_completo") == expected:
            employee_labels_verified += 1

    print(
        json.dumps(
            {
                "status": "COPY_COMPLETE_VERIFIED",
                "writes": writes,
                "giustificativi_verified": len(reasons_verified),
                "presenze_verified": len(attendance_verified),
                "employee_labels_verified": employee_labels_verified,
                "root_deletions": 0,
            }
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    try:
        return run(args.project, args.execute)
    except Exception as exc:
        print(f"HR_CUTOVER_ABORTED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
