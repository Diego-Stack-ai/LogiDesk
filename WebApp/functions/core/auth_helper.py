# core/auth_helper.py
from firebase_admin import firestore
from firebase_functions import https_fn
from infrastructure.company_context import get_current_company_id

def get_canonical_user(db, uid, company_id=None):
    """
    Recupera il documento utente canonico dalla subcollection aziendale.
    Restituisce None se non trovato o inattivo.
    """
    if not company_id:
        company_id = get_current_company_id()
    
    doc = db.collection('aziende').document(company_id).collection('utenti').document(uid).get()
    
    if not doc.exists:
        return None
    
    data = doc.to_dict()
    if data.get('attivo', False) is not True:
        return None
        
    return data

def get_canonical_user_role(db, uid, company_id=None):
    """
    Recupera il ruolo dell'utente canonico.
    """
    user_data = get_canonical_user(db, uid, company_id)
    if not user_data:
        return None
    return user_data.get('ruolo')

def require_role(db, req: https_fn.CallableRequest, allowed_roles: list, company_id=None):
    """
    Verifica che l'utente chiamante abbia uno dei ruoli consentiti.
    Solleva HttpsError se non autorizzato.
    """
    if not req.auth or not req.auth.uid:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.UNAUTHENTICATED,
            message="Utente non autenticato."
        )
        
    role = get_canonical_user_role(db, req.auth.uid, company_id)
    if not role or role not in allowed_roles:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.PERMISSION_DENIED,
            message="Privilegi insufficienti per questa operazione."
        )
    return role

def is_admin(db, req: https_fn.CallableRequest, company_id=None):
    """
    Helper comodo per verificare se l'utente e' amministratore.
    """
    return require_role(db, req, ['amministratore'], company_id)

