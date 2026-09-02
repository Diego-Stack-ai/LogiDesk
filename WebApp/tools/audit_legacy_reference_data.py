"""Audit read-only dei dati legacy di riferimento tra Produzione e Cantiere."""

from __future__ import annotations

import json

import firebase_admin
from firebase_admin import credentials, firestore


PRODUCTION_PROJECT = "log-solution-60007"
STAGING_PROJECT = "log-solutions-cantiere"
COMPANY_ID = "NzXaCgyXxZWWehw1tSlo"
DNR_TENANT_ID = "AgvcnbuUMu7YhzSuUKTY"
SOURCE_COLLECTIONS = (
    "codici articoli",
    "fatturazione_magazzini_sedi",
    "fatturazione_navette_carichi",
    "fatturazione_navette_clienti",
    "fatturazione_navette_destinazioni",
    "fatturazione_navette_partenze",
    "magazzini_sedi",
    "navetta_carico",
    "navetta_clienti",
    "navetta_destinazioni_merce",
    "navetta_partenze",
    "navette_anagrafica_carichi",
    "navette_anagrafica_clienti",
    "navette_anagrafica_destinazioni",
    "navette_anagrafica_partenze",
    "resi_e_ritiri",
    "viaggi ddt",
)


def make_client(project_id: str, name: str):
    app = firebase_admin.initialize_app(
        credentials.ApplicationDefault(), {"projectId": project_id}, name=name
    )
    return firestore.client(app=app)


def describe(collection_ref) -> dict:
    docs = list(collection_ref.stream())
    fields = sorted({key for doc in docs[:25] for key in (doc.to_dict() or {})})
    return {
        "count": len(docs),
        "sample_ids": [doc.id for doc in docs[:5]],
        "sample_fields": fields,
    }


def main() -> int:
    production = make_client(PRODUCTION_PROJECT, "production-audit")
    staging = make_client(STAGING_PROJECT, "staging-audit")
    report = {"mode": "READ_ONLY", "production": {}, "staging": {}}

    source = production.collection("clienti").document("DNR")
    for name in SOURCE_COLLECTIONS:
        report["production"][name] = describe(source.collection(name))

    tenant = (
        staging.collection("aziende")
        .document(COMPANY_ID)
        .collection("tenants")
        .document(DNR_TENANT_ID)
    )
    company = staging.collection("aziende").document(COMPANY_ID)
    for name in (
        "import_mappings",
        "magazzini",
        "navette",
        "rientri_ddt",
        "viaggi_ddt",
    ):
        report["staging"][f"tenant/{name}"] = describe(tenant.collection(name))
    report["staging"]["company/magazzini"] = describe(company.collection("magazzini"))

    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
