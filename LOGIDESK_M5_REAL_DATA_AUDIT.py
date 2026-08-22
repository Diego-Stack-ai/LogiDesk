import firebase_admin
from firebase_admin import credentials, firestore
import json
from collections import defaultdict
import sys

def run_audit():
    print("Inizializzazione Firebase Admin con Application Default Credentials...")
    try:
        cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred, {
            'projectId': 'log-solutions-cantiere'
        })
    except Exception as e:
        print(f"Errore di inizializzazione: {e}")
        sys.exit(1)

    db = firestore.client()
    collection_path = 'aziende/NzXaCgyXxZWWehw1tSlo/tenants/AgvcnbuUMu7YhzSuUKTY/punti_consegna'
    
    print(f"Lettura documenti da: {collection_path}")
    docs_ref = db.collection(collection_path).stream()
    
    all_docs = []
    for doc in docs_ref:
        d = doc.to_dict()
        d['document_id'] = doc.id
        all_docs.append(d)
        
    total_docs = len(all_docs)
    print(f"TOTAL_DOCUMENTS = {total_docs}")

    # Distributions
    dist = {
        'tipo': defaultdict(int),
        'competenza': defaultdict(int),
        'source': defaultdict(int),
        'source_type': defaultdict(int),
        'legacy_provenance': defaultdict(int)
    }
    
    presence = {
        'codice_punto': 0,
        'codice_esterno': 0,
        'sottocodice': 0,
        'association_group_id': 0,
        'finestre_consegna': 0,
        'geolocalizzazione': 0
    }

    groups = defaultdict(list)
    frutta_windows = []
    latte_windows = []

    for d in all_docs:
        # Counters
        for f in dist.keys():
            val = str(d.get(f, 'N/A'))
            dist[f][val] += 1
            
        for f in presence.keys():
            if d.get(f) not in [None, '', []]:
                presence[f] += 1
                
        # Group by association
        gid = d.get('association_group_id')
        if gid:
            groups[gid].append(d)

    # 3 - Type Classification
    # Tenta varie euristiche per raggiungere 392 FRUTTA e 217 LATTE
    certified = False
    certified_field = "N/D"
    certified_rule = "N/D"
    frutta_count = 0
    latte_count = 0
    unknown_count = total_docs
    
    # Heuristic 1: By source_type
    if dist['source_type'].get('FRUTTA', 0) == 392 and dist['source_type'].get('LATTE', 0) == 217:
        certified = True
        certified_field = "source_type"
        certified_rule = "source_type === 'FRUTTA' -> FRUTTA, source_type === 'LATTE' -> LATTE"
        frutta_count, latte_count = 392, 217
        unknown_count = total_docs - (392 + 217)
        
        for d in all_docs:
            if d.get('source_type') == 'FRUTTA' and len(frutta_windows) < 3 and d.get('finestre_consegna'):
                frutta_windows.append(d['finestre_consegna'])
            if d.get('source_type') == 'LATTE' and len(latte_windows) < 3 and d.get('finestre_consegna'):
                latte_windows.append(d['finestre_consegna'])
                
    # Heuristic 2: By source
    elif dist['source'].get('FRUTTA', 0) == 392 and dist['source'].get('LATTE', 0) == 217:
        certified = True
        certified_field = "source"
        certified_rule = "source === 'FRUTTA' -> FRUTTA, source === 'LATTE' -> LATTE"
        frutta_count, latte_count = 392, 217
        unknown_count = total_docs - (392 + 217)
        
        for d in all_docs:
            if d.get('source') == 'FRUTTA' and len(frutta_windows) < 3 and d.get('finestre_consegna'):
                frutta_windows.append(d['finestre_consegna'])
            if d.get('source') == 'LATTE' and len(latte_windows) < 3 and d.get('finestre_consegna'):
                latte_windows.append(d['finestre_consegna'])
                
    # Heuristic 3: By competenza
    elif dist['competenza'].get('FRUTTA', 0) == 392 and dist['competenza'].get('LATTE', 0) == 217:
        certified = True
        certified_field = "competenza"
        certified_rule = "competenza === 'FRUTTA' -> FRUTTA, competenza === 'LATTE' -> LATTE"
        frutta_count, latte_count = 392, 217
        unknown_count = total_docs - (392 + 217)
        
        for d in all_docs:
            if d.get('competenza') == 'FRUTTA' and len(frutta_windows) < 3 and d.get('finestre_consegna'):
                frutta_windows.append(d['finestre_consegna'])
            if d.get('competenza') == 'LATTE' and len(latte_windows) < 3 and d.get('finestre_consegna'):
                latte_windows.append(d['finestre_consegna'])
    else:
        # Try to infer windows anyway
        for d in all_docs:
            typ = str(d.get('source_type', d.get('source', d.get('tipo', '')))).upper()
            if 'FRUTTA' in typ and len(frutta_windows) < 3 and d.get('finestre_consegna'):
                frutta_windows.append(d['finestre_consegna'])
            if 'LATTE' in typ and len(latte_windows) < 3 and d.get('finestre_consegna'):
                latte_windows.append(d['finestre_consegna'])

    # Extract pairs
    pairs_list = [g for g in groups.values() if len(g) == 2]
    sample_pairs = []
    
    for i in range(min(5, len(pairs_list))):
        pair = pairs_list[i]
        sanitized_pair = {}
        for idx, r in enumerate(pair):
            sanitized = {
                'document_id': r.get('document_id'),
                'tipo': r.get('tipo'),
                'competenza': r.get('competenza'),
                'source': r.get('source'),
                'source_type': r.get('source_type'),
                'codice_punto': r.get('codice_punto'),
                'codice_esterno': r.get('codice_esterno'),
                'sottocodice': r.get('sottocodice'),
                'association_group_id': r.get('association_group_id'),
                'finestre_consegna': r.get('finestre_consegna'),
                'geolocalizzazione': r.get('geolocalizzazione')
            }
            sanitized_pair[f"record_{'A' if idx == 0 else 'B'}"] = sanitized
        sample_pairs.append(sanitized_pair)

    output = {
        "TOTAL_DOCUMENTS": total_docs,
        "DISTRIBUTIONS": {k: dict(v) for k, v in dist.items()},
        "PRESENCE": presence,
        "TYPE_CLASSIFICATION_CERTIFIED": certified,
        "CERTIFIED_TYPE_FIELD": certified_field,
        "CERTIFIED_TYPE_RULE": certified_rule,
        "FRUTTA_COUNT": frutta_count,
        "LATTE_COUNT": latte_count,
        "UNKNOWN_COUNT": unknown_count,
        "FRUTTA_OWN_CODE_FIELD": "Da dedurre in base all'output JSON",
        "LATTE_OWN_CODE_FIELD": "Da dedurre in base all'output JSON",
        "ASSOCIATED_CODE_LOOKUP_MODEL": "Da dedurre in base all'output JSON",
        "TIME_WINDOW_SCHEMA": {
            "FRUTTA_SAMPLES": frutta_windows,
            "LATTE_SAMPLES": latte_windows
        },
        "TIME_WINDOW_DISPLAY_RULE": "Da implementare in JS in base allo schema rilevato",
        "SAMPLE_ASSOCIATED_PAIRS": sample_pairs
    }

    with open('M5_REAL_DATA_AUDIT.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
        
    print("Salvataggio completato in M5_REAL_DATA_AUDIT.json")

if __name__ == '__main__':
    run_audit()
