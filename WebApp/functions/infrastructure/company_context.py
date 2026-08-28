# infrastructure/company_context.py
import os

# CONSTANTE TEMPORANEA per il single-company runtime attuale
# Obiettivo futuro: company_id dinamico (ricavato da token JWT/header)
DEFAULT_COMPANY_ID = "NzXaCgyXxZWWehw1tSlo"

def get_current_company_id(req=None):
    """
    Ritorna l'ID azienda corrente.
    Attualmente fisso a DEFAULT_COMPANY_ID.
    """
    return DEFAULT_COMPANY_ID
