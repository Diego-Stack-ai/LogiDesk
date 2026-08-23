import firebase_admin
from firebase_admin import credentials, firestore, auth
import json
import sys

def main():
    try:
        app = firebase_admin.initialize_app()
        db = firestore.client()
    except Exception as e:
        print(f"ERROR INIT: {e}")
        sys.exit(1)

    # FIREBASE AUTH
    try:
        auth_users = auth.list_users().iterate_all()
        auth_users_data = []
        for u in auth_users:
            auth_users_data.append({
                "uid": u.uid,
                "email": u.email,
                "display_name": u.display_name,
                "disabled": u.disabled,
                "provider_ids": [p.provider_id for p in u.provider_data]
            })
    except Exception as e:
        print(f"ERROR AUTH: {e}")
        auth_users_data = []

    # FIRESTORE DIPENDENTI
    legacy_dipendenti = []
    try:
        docs = db.collection("dipendenti").stream()
        for d in docs:
            legacy_dipendenti.append({
                "id": d.id,
                "data": d.to_dict()
            })
    except Exception as e:
        print(f"ERROR FIRESTORE: {e}")
        
    audit = {
        "legacy_dipendenti_count": len(legacy_dipendenti),
        "auth_user_count": len(auth_users_data),
        "auth_users": auth_users_data,
        "legacy_dipendenti": legacy_dipendenti
    }
    
    with open("M3_AUDIT_DUMP.json", "w") as f:
        json.dump(audit, f, indent=2)
        
    print("M3_AUDIT_SUCCESS")

if __name__ == "__main__":
    main()
