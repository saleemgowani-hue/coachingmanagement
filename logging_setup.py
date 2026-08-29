"""
logging_setup.py
SN COACHING MANAGEMENT SYSTEM

Minimal, dependency-free logging for key application events (logins,
signups, licence activations, admin actions, errors). Deliberately never
logs passwords, password hashes, database URLs, or secret keys - only
identifiers (username, institute_id, plan) needed to trace what happened.
"""

import logging
import os

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

_logger = logging.getLogger("sn_coaching")
if not _logger.handlers:
    _logger.setLevel(logging.INFO)
    handler = logging.FileHandler(os.path.join(LOG_DIR, "app.log"), encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    _logger.addHandler(handler)
    # Also echo to stdout - useful on cloud hosts that capture process logs
    stream = logging.StreamHandler()
    stream.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    _logger.addHandler(stream)


def log_event(event: str, **fields):
    """Logs one structured line, e.g.
    log_event('login_success', username='admin1', institute_id='SNC-123')
    Never pass password, password_hash, or any secret/token as a field."""
    forbidden = {"password", "password_hash", "database_url", "secret", "licence_key_plain"}
    safe_fields = {k: v for k, v in fields.items() if k.lower() not in forbidden}
    parts = " ".join(f"{k}={v}" for k, v in safe_fields.items())
    _logger.info(f"{event} {parts}".strip())


def log_error(event: str, error: Exception, **fields):
    forbidden = {"password", "password_hash", "database_url", "secret"}
    safe_fields = {k: v for k, v in fields.items() if k.lower() not in forbidden}
    parts = " ".join(f"{k}={v}" for k, v in safe_fields.items())
    _logger.error(f"{event} {parts} error={type(error).__name__}: {error}".strip())
