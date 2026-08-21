import json
import hashlib

def compute_delivery_point_fingerprint(target):
    core_data = {
        "legacy_document_id": target.get("legacy_document_id"),
        "codice_esterno": target.get("codice_esterno"),
        "sottocodice": target.get("sottocodice"),
        "nome": target.get("nome"),
        "indirizzo": target.get("indirizzo"),
        "finestre_consegna": target.get("finestre_consegna"),
        "association_group_id": target.get("association_group_id")
    }
    geo = target.get("geolocalizzazione")
    if geo:
        if hasattr(geo, "latitude"):
            core_data["lat"] = geo.latitude
            core_data["lon"] = geo.longitude
        elif isinstance(geo, dict):
            core_data["lat"] = geo.get("lat") or geo.get("latitude")
            core_data["lon"] = geo.get("lon") or geo.get("longitude")
    s = json.dumps(core_data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(s.encode("utf-8")).hexdigest()
