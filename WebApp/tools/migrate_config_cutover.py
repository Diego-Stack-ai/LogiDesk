"""Preflight ed esecuzione controllata del cutover della raccolta root config."""

from __future__ import annotations

import argparse
import json
import sys

import firebase_admin
from firebase_admin import firestore


EXPECTED_PROJECT = "log-solutions-cantiere"
COMPANY_ID = "NzXaCgyXxZWWehw1tSlo"
CATTEL_TENANT_ID = "bSomOWB7pieGNej2KdJA"
COMPANY_SETTINGS = {
    "email_settings": "email",
    "permessi_dashboard": "permissions",
    "system_status": "system",
}


def _init_db(project_id: str):
    if project_id != EXPECTED_PROJECT:
        raise RuntimeError(
            f"GATE_PROJECT fallito: atteso {EXPECTED_PROJECT}, ricevuto {project_id}."
        )
    if not firebase_admin._apps:
        firebase_admin.initialize_app(options={"projectId": project_id})
    return firestore.client()


def _build_cattel_payload(source_data: dict) -> dict:
    username = str(source_data.get("username") or "").strip()
    portal_url = str(source_data.get("url") or "").strip()
    if not username or not portal_url:
        raise RuntimeError("GATE_CATTEL_FIELDS fallito: username o URL mancanti.")

    return {
        "provider": "CATTEL",
        "username": username,
        "url": portal_url,
        "password_secret": "CATTEL_PORTAL_PASSWORD",
        "schema_version": 1,
        "source_legacy_path": "config/cattel",
        "migrated_at": firestore.SERVER_TIMESTAMP,
    }


def run(project_id: str, execute: bool) -> int:
    db = _init_db(project_id)

    missing_company_targets: list[str] = []
    for legacy_id, target_id in COMPANY_SETTINGS.items():
        legacy = db.collection("config").document(legacy_id).get()
        target = (
            db.collection("aziende")
            .document(COMPANY_ID)
            .collection("settings")
            .document(target_id)
            .get()
        )
        if not legacy.exists or not target.exists:
            missing_company_targets.append(f"{legacy_id}->{target_id}")

    if missing_company_targets:
        raise RuntimeError(
            "GATE_COMPANY_SETTINGS fallito: " + ", ".join(missing_company_targets)
        )

    cattel_source = db.collection("config").document("cattel").get()
    if not cattel_source.exists:
        raise RuntimeError("GATE_CATTEL_SOURCE fallito: config/cattel non esiste.")

    source_data = cattel_source.to_dict()
    cattel_payload = _build_cattel_payload(source_data)
    if "password" in cattel_payload:
        raise RuntimeError("GATE_SECRET_WRITE_ZERO fallito.")

    target_ref = (
        db.collection("aziende")
        .document(COMPANY_ID)
        .collection("tenants")
        .document(CATTEL_TENANT_ID)
        .collection("configurazioni")
        .document("integrazione")
    )
    target_snapshot = target_ref.get()
    state = "CLEAN_START"
    if target_snapshot.exists:
        existing = target_snapshot.to_dict()
        comparable_fields = ("provider", "username", "url", "password_secret", "schema_version")
        if all(existing.get(key) == cattel_payload.get(key) for key in comparable_fields):
            state = "ALREADY_APPLIED"
        else:
            state = "CONFLICT"

    report = {
        "project": project_id,
        "company_id": COMPANY_ID,
        "company_settings_verified": sorted(COMPANY_SETTINGS.values()),
        "cattel_source_exists": True,
        "cattel_target_state": state,
        "secret_fields_written": 0,
        "mode": "EXECUTE" if execute else "PREFLIGHT",
    }
    print(json.dumps(report, indent=2, sort_keys=True))

    if state == "CONFLICT":
        raise RuntimeError("GATE_TARGET_STATE fallito: target CATTEL in conflitto.")
    if not execute or state == "ALREADY_APPLIED":
        return 0

    registry_ref = db.collection("system_migrations").document("config_root_cutover")
    batch = db.batch()
    batch.create(target_ref, cattel_payload)
    batch.set(
        registry_ref,
        {
            "company_id": COMPANY_ID,
            "migration_name": "config_root_cutover",
            "project_id": project_id,
            "status": "COMPLETE",
            "cattel_target": target_ref.path,
            "secret_fields_written": 0,
            "executed_at": firestore.SERVER_TIMESTAMP,
        },
        merge=True,
    )
    batch.commit()
    print("CUTOVER_CATTEL_TARGET_COMPLETE")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    try:
        return run(args.project, args.execute)
    except Exception as exc:
        print(f"CUTOVER_ABORTED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
