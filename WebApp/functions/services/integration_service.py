import os

from firebase_functions import https_fn

from infrastructure.company_context import get_current_company_id
from infrastructure.firebase_setup import get_db


CATTEL_TENANT_ID = "bSomOWB7pieGNej2KdJA"
ALLOWED_CREDENTIAL_ROLES = {"amministratore", "impiegata"}


def handle_get_cattel_portal_credentials(req: https_fn.CallableRequest) -> dict:
    """Restituisce le credenziali CATTEL solo agli operatori autorizzati."""
    if not req.auth or not req.auth.uid:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.UNAUTHENTICATED,
            message="Non autorizzato.",
        )

    db = get_db()
    company_id = get_current_company_id(req)
    caller_doc = (
        db.collection("aziende")
        .document(company_id)
        .collection("utenti")
        .document(req.auth.uid)
        .get()
    )
    caller_role = caller_doc.to_dict().get("ruolo") if caller_doc.exists else None
    if caller_role not in ALLOWED_CREDENTIAL_ROLES:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.PERMISSION_DENIED,
            message="Permessi insufficienti.",
        )

    integration_doc = (
        db.collection("aziende")
        .document(company_id)
        .collection("tenants")
        .document(CATTEL_TENANT_ID)
        .collection("configurazioni")
        .document("integrazione")
        .get()
    )
    if not integration_doc.exists:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.FAILED_PRECONDITION,
            message="Configurazione portale CATTEL mancante.",
        )

    data = integration_doc.to_dict()
    password = os.environ.get("CATTEL_PORTAL_PASSWORD")
    if not password:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.FAILED_PRECONDITION,
            message="Segreto del portale CATTEL non configurato.",
        )

    username = str(data.get("username") or "").strip()
    portal_url = str(data.get("url") or "").strip()
    if not username or not portal_url:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.FAILED_PRECONDITION,
            message="Configurazione portale CATTEL incompleta.",
        )

    return {
        "username": username,
        "password": password,
        "url": portal_url,
    }
