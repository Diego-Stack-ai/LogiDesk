import firebase_admin
from firebase_admin import credentials, firestore
import json
import sys

print('Autenticazione con cantiere_key.json...')
try:
    cred = credentials.Certificate(r'H:\Il mio Drive\App\AppLogSolutionsWeb\cantiere_key.json')
    firebase_admin.initialize_app(cred, {
        'projectId': 'log-solutions-cantiere'
    })
    print('Connessione al db riuscita.')
except Exception as e:
    print(f'Errore di inizializzazione: {e}')
    sys.exit(1)

db = firestore.client()

print('Ricerca scheda tonello in punti_consegna...')
docs_ref = db.collection('aziende/NzXaCgyXxZWWehw1tSlo/tenants/AgvcnbuUMu7YhzSuUKTY/punti_consegna').stream()

tonello_docs = []
for doc in docs_ref:
    d = doc.to_dict()
    d['document_id'] = doc.id
    nome = d.get('nome', '').lower()
    if 'tonello' in nome:
        tonello_docs.append(d)

print(f'Trovate {len(tonello_docs)} schede tonello.')
print(json.dumps(tonello_docs, indent=2, ensure_ascii=False))
