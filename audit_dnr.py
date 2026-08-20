import os
import sys
import firebase_admin
from firebase_admin import credentials, firestore

# Provo ad usare le credenziali di default o il config locale
try:
    cred = credentials.Certificate('backend_secrets/firebase_service_account.json') # o simile se esiste
    firebase_admin.initialize_app(cred)
except:
    try:
        firebase_admin.initialize_app()
    except Exception as e:
        print('Errore init firebase:', e)

db = firestore.client()
docs = db.collection('clienti').document('DNR').collection('raccolta clienti').stream()

null_values = set()
frutta_only = 0
latte_only = 0
both = 0
same = 0
no_code = 0
anomalo = 0
total = 0

codes = {}
dups = []

def is_null(val):
    if val is None: return True
    if not isinstance(val, str): return False
    s = val.strip().lower()
    if s in ['', 'none', 'p00000', 'p000000', 'null']:
        null_values.add(val)
        return True
    return False

for d in docs:
    total += 1
    data = d.to_dict()
    cf = data.get('codice_frutta')
    cl = data.get('codice_latte')
    
    nf = is_null(cf)
    nl = is_null(cl)
    
    # Store for dup checking if not null
    if not nf:
        cf_clean = str(cf).strip()
        if cf_clean not in codes: codes[cf_clean] = []
        codes[cf_clean].append((d.id, 'frutta'))
    if not nl:
        cl_clean = str(cl).strip()
        if cl_clean not in codes: codes[cl_clean] = []
        codes[cl_clean].append((d.id, 'latte'))

    if nf and nl:
        no_code += 1
    elif not nf and nl:
        frutta_only += 1
    elif nf and not nl:
        latte_only += 1
    elif not nf and not nl:
        if str(cf).strip() == str(cl).strip():
            same += 1
        else:
            both += 1

print('TOTAL:', total)
print('NULLS:', list(null_values))
print('FRUTTA_ONLY:', frutta_only)
print('LATTE_ONLY:', latte_only)
print('BOTH:', both)
print('SAME:', same)
print('NO_CODE:', no_code)

dup_count = 0
for k, v in codes.items():
    if len(v) > 1:
        dup_count += 1
print('DUPLICATES:', dup_count)

