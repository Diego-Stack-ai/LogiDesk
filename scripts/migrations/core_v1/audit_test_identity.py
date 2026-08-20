import os
import json
import sys
from google.cloud import firestore
import firebase_admin
from firebase_admin import auth, storage, credentials

PROJECT_ID = "log-solutions-cantiere"
COMPANY_ID = "NzXaCgyXxZWWehw1tSlo"
TEST_UID = "qtQWKWaJRMZNv0UzhOETC0t2hdU2"

# 1. Init Firebase
try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app(options={"projectId": PROJECT_ID})

db = firestore.Client(project=PROJECT_ID)

output = {
    "PROJECT": PROJECT_ID,
    "M3_REGISTRY_COMPLETE": False,
    "M3_CANONICAL_EMPLOYEE_COUNT": 0,
    "M3_CANONICAL_USER_COUNT": 0,
    "CANONICAL_TEST_EMPLOYEE_EXISTS": False,
    "CANONICAL_TEST_USER_EXISTS": False,
    "LEGACY_TEST_DOCUMENT_EXISTS": False,
    "TEST_AUTH_EXISTS": False,
    "TEST_AUTH_DISABLED": None,
    "TEST_AUTH_PROVIDER_IDS": [],
    "TEST_AUTH_EMAIL_PRESENT": False,
    "TEST_AUTH_CUSTOM_CLAIMS": None,
    "FIRESTORE_REFERENCE_TOTAL": 0,
    "FIRESTORE_REFERENCED_LOCATIONS": [],
    "AUTH_DEPENDENCY_COUNT": 0,
    "STORAGE_REFERENCE_COUNT": 0,
    "LEGACY_TEST_DOC_DATA": {}
}

# 2. Verify M3 Complete
reg = db.document("system_migrations/core_v1_m3_identity").get()
if reg.exists and reg.to_dict().get("status") == "COMPLETE":
    output["M3_REGISTRY_COMPLETE"] = True

emp_count = sum(1 for _ in db.collection(f"aziende/{COMPANY_ID}/dipendenti").stream())
usr_count = sum(1 for _ in db.collection(f"aziende/{COMPANY_ID}/utenti").stream())

output["M3_CANONICAL_EMPLOYEE_COUNT"] = emp_count
output["M3_CANONICAL_USER_COUNT"] = usr_count

if db.document(f"aziende/{COMPANY_ID}/dipendenti/{TEST_UID}").get().exists:
    output["CANONICAL_TEST_EMPLOYEE_EXISTS"] = True
if db.document(f"aziende/{COMPANY_ID}/utenti/{TEST_UID}").get().exists:
    output["CANONICAL_TEST_USER_EXISTS"] = True

# 3. Legacy Test Document
legacy_doc = db.document(f"dipendenti/{TEST_UID}").get()
if legacy_doc.exists:
    output["LEGACY_TEST_DOCUMENT_EXISTS"] = True
    d = legacy_doc.to_dict()
    output["LEGACY_TEST_DOC_DATA"] = {
        "attivo": d.get("attivo"),
        "ruolo": d.get("ruolo"),
        "uid_present": bool(d.get("uid")),
        "email_present": bool(d.get("email"))
    }

# 4. Auth Test Account
try:
    user = auth.get_user(TEST_UID)
    output["TEST_AUTH_EXISTS"] = True
    output["TEST_AUTH_DISABLED"] = user.disabled
    output["TEST_AUTH_PROVIDER_IDS"] = [p.provider_id for p in user.provider_data]
    output["TEST_AUTH_EMAIL_PRESENT"] = bool(user.email)
    output["TEST_AUTH_CUSTOM_CLAIMS"] = user.custom_claims
    if user.custom_claims:
        output["AUTH_DEPENDENCY_COUNT"] = len(user.custom_claims)
except auth.UserNotFoundError:
    output["TEST_AUTH_EXISTS"] = False

# 5. Firestore Reference Audit
collections_to_audit = ["presenze", "viaggi", "pianificazione", "costi_personale", "turni", "report", "fatturazione", "assenze", "ferie", "assegnazioni"]
for coll_name in collections_to_audit:
    docs = db.collection(coll_name).stream()
    coll_count = 0
    ref_fields = set()
    for doc in docs:
        d = doc.to_dict() or {}
        for k, v in d.items():
            if v == TEST_UID:
                coll_count += 1
                ref_fields.add(k)
            # Check inner dicts/lists naive
            elif isinstance(v, list) and TEST_UID in v:
                coll_count += 1
                ref_fields.add(k)
            elif isinstance(v, dict) and TEST_UID in v.values():
                coll_count += 1
                ref_fields.add(k)
    
    if coll_count > 0:
        output["FIRESTORE_REFERENCED_LOCATIONS"].append({
            "collection": coll_name,
            "count": coll_count,
            "reference_fields": list(ref_fields)
        })
        output["FIRESTORE_REFERENCE_TOTAL"] += coll_count

print(json.dumps(output, indent=2))
