"""
config.py
SN COACHING MANAGEMENT SYSTEM

Centralized configuration so pricing, branding, demo credentials and the
database backend can be changed WITHOUT touching code - via environment
variables (offline / any host) or Streamlit secrets (Streamlit Cloud).

Nothing sensitive (passwords, DB URLs, secret keys) is hard-coded here -
every value has a safe default that should be overridden in production
via a `.env` file (offline) or `.streamlit/secrets.toml` (online), neither
of which should ever be committed to version control (see .gitignore).
"""

import os

try:
    import streamlit as st
    _SECRETS = st.secrets if hasattr(st, "secrets") else {}
except Exception:
    _SECRETS = {}


def _get(key: str, default: str = "") -> str:
    """Checks Streamlit secrets first (online/cloud), then environment
    variables (offline/any host), then falls back to a default."""
    try:
        if key in _SECRETS:
            return str(_SECRETS[key])
    except Exception:
        pass
    return os.environ.get(key, default)


# ---------------------------------------------------------------------
# Branding / business configuration
# ---------------------------------------------------------------------
COMPANY_NAME = _get("COMPANY_NAME", "SN Softech Solutions")
PRODUCT_NAME = _get("PRODUCT_NAME", "SN Coaching Management System")
SUPPORT_EMAIL = _get("SUPPORT_EMAIL", "support@snsoftech.example")
SUPPORT_WHATSAPP = _get("SUPPORT_WHATSAPP", "9993199719")

MONTHLY_PRICE = float(_get("MONTHLY_PRICE", "999"))
YEARLY_PRICE = float(_get("YEARLY_PRICE", "9999"))
CURRENCY_SYMBOL = _get("CURRENCY_SYMBOL", "₹")

# ---------------------------------------------------------------------
# Demo account (fixed credentials, shown to prospective customers)
# ---------------------------------------------------------------------
DEMO_USERNAME = _get("DEMO_USERNAME", "demo")
DEMO_PASSWORD = _get("DEMO_PASSWORD", "demo@1234")
DEMO_INSTITUTE_NAME = _get("DEMO_INSTITUTE_NAME", "Demo Coaching Centre")

# ---------------------------------------------------------------------
# Super Admin (cross-tenant management panel - separate from any
# customer login; never stored in the multi-tenant users table)
# ---------------------------------------------------------------------
SUPER_ADMIN_USERNAME = _get("SUPER_ADMIN_USERNAME", "superadmin")
SUPER_ADMIN_PASSWORD = _get("SUPER_ADMIN_PASSWORD", "")  # must be set in production - see README

# ---------------------------------------------------------------------
# Database backend: "sqlite" (offline / default) or "postgres" (online SaaS)
# DATABASE_URL example: postgresql://user:password@host:5432/dbname
# ---------------------------------------------------------------------
DB_BACKEND = _get("DB_BACKEND", "sqlite").lower()
DATABASE_URL = _get("DATABASE_URL", "")

# ---------------------------------------------------------------------
# Expiry warning thresholds (days remaining) for the subscription banner
# ---------------------------------------------------------------------
EXPIRY_WARNING_DAYS = [30, 15, 7, 3, 1]
