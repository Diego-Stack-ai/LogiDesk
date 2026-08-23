import firebase_admin
from firebase_admin import credentials, firestore
import json
import os
import argparse
from collections import Counter

def get_app():
    try:
        app = firebase_admin.get_app()
    except ValueError:
        app = firebase_admin.initialize_app(options={"projectId": "log-solutions-cantiere"})
    return app

def main():
    app = get_app()
    db = firestore.client()
    
    # 1. Fetch Tenant mappings from M0/M1 registry
    reg = db.document("system_migrations/core_v1_m0_m1").get()
    tenants = reg.to_dict().get("tenants", {})
    legacy_to_canonical = {t.get("legacy_name"): t.get("canonical_id") for t in tenants.values()}
    
    # Discovery
    root_warehouses = []
    for doc in db.collection("magazzini_sedi").stream():
        root_warehouses.append({"id": doc.id, "data": doc.to_dict(), "path": doc.reference.path, "tenant": None})
        
    tenant_warehouses = []
    tenant_counts = {}
    for tenant_name in legacy_to_canonical.keys():
        count = 0
        for doc in db.collection(f"clienti/{tenant_name}/magazzini_sedi").stream():
            tenant_warehouses.append({"id": doc.id, "data": doc.to_dict(), "path": doc.reference.path, "tenant": tenant_name})
            count += 1
        if count > 0:
            tenant_counts[tenant_name] = count
            
    all_warehouses = root_warehouses + tenant_warehouses
    
    # Fields & Stats
    fields_counter = Counter()
    for w in all_warehouses:
        if w["data"]:
            for k in w["data"].keys():
                fields_counter[k] += 1
                
    # Duplicates (naive check on name/address)
    name_address_counter = Counter()
    for w in all_warehouses:
        d = w["data"] or {}
        name = str(d.get("nome", "")).strip().lower()
        address = str(d.get("indirizzo", "")).strip().lower()
        if name or address:
            name_address_counter[(name, address)] += 1
            
    duplicates = {str(k): v for k, v in name_address_counter.items() if v > 1}
    
    # IDs
    id_types = Counter()
    for w in all_warehouses:
        if len(w["id"]) == 20: # Typical firestore auto-id
            id_types["AUTO_ID"] += 1
        else:
            id_types["CUSTOM_ID"] += 1
            
    summary = {
        "root_count": len(root_warehouses),
        "tenant_counts": tenant_counts,
        "total": len(all_warehouses),
        "fields": dict(fields_counter),
        "duplicates": duplicates,
        "id_types": dict(id_types),
        "tenants_map": legacy_to_canonical
    }
    
    os.makedirs("migration_output/m4", exist_ok=True)
    with open("migration_output/m4/audit_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
        
    print("M4 AUDIT COMPLETE.")

if __name__ == "__main__":
    main()
