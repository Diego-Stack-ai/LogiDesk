import firebase_admin
from firebase_admin import credentials, firestore
import json
from collections import defaultdict

# Use Application Default Credentials
cred = credentials.ApplicationDefault()
try:
    firebase_admin.initialize_app(cred, {
        'projectId': 'log-solutions-cantiere'
    })
except ValueError:
    pass # App already initialized

db = firestore.client()

collection_path = 'aziende/NzXaCgyXxZWWehw1tSlo/tenants/AgvcnbuUMu7YhzSuUKTY/punti_consegna'
docs = db.collection(collection_path).stream()

all_docs = []
for d in docs:
    all_docs.append({**d.to_dict(), 'document_id': d.id})

print(f"Total documents fetched: {len(all_docs)}")

# Find pairs
groups = defaultdict(list)
for d in all_docs:
    gid = d.get('association_group_id')
    if gid:
        groups[gid].append(d)

pairs = [g for g in groups.values() if len(g) == 2]
print(f"Total pairs found: {len(pairs)}")

if len(pairs) >= 3:
    for i in range(3):
        pair = pairs[i]
        print(f"--- PAIR_{i+1} ---")
        for idx, r in enumerate(pair):
            sanitized = {
                'document_id': r.get('document_id'),
                'codice_punto': r.get('codice_punto'),
                'codice_esterno': r.get('codice_esterno'),
                'sottocodice': r.get('sottocodice'),
                'tipo': r.get('tipo'),
                'competenza': r.get('competenza'),
                'source': r.get('source'),
                'source_type': r.get('source_type'),
                'association_group_id': r.get('association_group_id'),
                'finestre_consegna': r.get('finestre_consegna'),
                'geolocalizzazione_keys': list(r.get('geolocalizzazione', {}).keys()) if r.get('geolocalizzazione') else None,
                'attivo': r.get('attivo')
            }
            print(f"record_{'A' if idx == 0 else 'B'}: {json.dumps(sanitized, indent=2)}")

# Distributions
dist_tipo = defaultdict(int)
dist_competenza = defaultdict(int)
dist_source = defaultdict(int)
dist_source_type = defaultdict(int)
dist_sottocodice = defaultdict(int)

for d in all_docs:
    dist_tipo[str(d.get('tipo'))] += 1
    dist_competenza[str(d.get('competenza'))] += 1
    dist_source[str(d.get('source'))] += 1
    dist_source_type[str(d.get('source_type'))] += 1
    dist_sottocodice['has_sottocodice' if d.get('sottocodice') else 'no_sottocodice'] += 1

print("--- DISTRIBUTIONS ---")
print("tipo:", dict(dist_tipo))
print("competenza:", dict(dist_competenza))
print("source:", dict(dist_source))
print("source_type:", dict(dist_source_type))
print("sottocodice:", dict(dist_sottocodice))

# Find the best field to separate 392 and 217
# Let's count by 'source' or 'competenza'
