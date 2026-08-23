import urllib.request
import ssl
import json
from google.oauth2 import service_account
from google.auth.transport.requests import Request
import requests

# Disabilita warning SSL per requests
requests.packages.urllib3.disable_warnings()

# 1. Carica le credenziali
cred = service_account.Credentials.from_service_account_file(
    r'H:\Il mio Drive\App\AppLogSolutionsWeb\cantiere_key.json',
    scopes=['https://www.googleapis.com/auth/datastore']
)

# 2. Ottieni token (senza SSL check se serve, custom session)
session = requests.Session()
session.verify = False

request = Request(session=session)
cred.refresh(request)
token = cred.token

print('Token ottenuto. Leggo Firestore...')

# 3. Chiamata REST
url = 'https://firestore.googleapis.com/v1/projects/log-solutions-cantiere/databases/(default)/documents/aziende/NzXaCgyXxZWWehw1tSlo/tenants/AgvcnbuUMu7YhzSuUKTY/punti_consegna?pageSize=1000'
headers = {
    'Authorization': f'Bearer {token}'
}
resp = session.get(url, headers=headers)
if resp.status_code == 200:
    data = resp.json()
    docs = data.get('documents', [])
    for d in docs:
        fields = d.get('fields', {})
        nome = fields.get('nome', {}).get('stringValue', '').lower()
        if 'tonello' in nome:
            print(json.dumps(fields, indent=2))
else:
    print('Errore', resp.status_code, resp.text)
