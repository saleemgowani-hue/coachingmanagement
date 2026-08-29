"""
auth.py
SN COACHING MANAGEMENT SYSTEM
Handles account creation, login, password hashing and session state.
"""

import hashlib
import hmac
import os
import secrets
import string
from datetime import datetime

import streamlit as st

import database as db


# ---------------------------------------------------------------------
# Password hashing (PBKDF2-HMAC-SHA256, salted). No plaintext ever kept.
# ---------------------------------------------------------------------
def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 200_000)
    return f"{salt}${dk.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, hashed = stored_hash.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 200_000)
        return hmac.compare_digest(dk.hex(), hashed)
    except Exception:
        return False


def generate_institute_id() -> str:
    year = datetime.now().strftime("%y")
    rand = "".join(secrets.choice(string.digits) for _ in range(5))
    return f"SNC-{year}{rand}"


# ---------------------------------------------------------------------
# Sign up
# ---------------------------------------------------------------------
def create_account(institute_name, owner_name, mobile, whatsapp_number, email,
                    username, password) -> tuple[bool, str]:
    if not all([institute_name, owner_name, mobile, username, password]):
        return False, "Please fill in all required fields."

    existing = db.query_one("SELECT user_id FROM users WHERE username = ?", (username,))
    if existing:
        return False, "This username is already taken. Please choose another."

    institute_id = generate_institute_id()
    while db.query_one("SELECT institute_id FROM institutes WHERE institute_id = ?", (institute_id,)):
        institute_id = generate_institute_id()

    db.execute(
        """INSERT INTO institutes
           (institute_id, institute_name, owner_name, mobile, whatsapp_number, email)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (institute_id, institute_name.strip(), owner_name.strip(), mobile.strip(),
         (whatsapp_number or mobile).strip(), (email or "").strip()),
    )

    pw_hash = hash_password(password)
    db.execute(
        """INSERT INTO users (institute_id, username, email, password_hash, full_name, role)
           VALUES (?, ?, ?, ?, ?, 'ADMIN')""",
        (institute_id, username.strip(), (email or "").strip(), pw_hash, owner_name.strip()),
    )

    seed_default_templates(institute_id)

    from logging_setup import log_event
    log_event("account_created", institute_id=institute_id, username=username.strip())

    return True, institute_id


def seed_default_templates(institute_id):
    from whatsapp import DEFAULT_TEMPLATES
    for name, text in DEFAULT_TEMPLATES.items():
        db.execute(
            """INSERT INTO whatsapp_templates (institute_id, template_name, template_text, is_default)
               VALUES (?, ?, ?, 1)""",
            (institute_id, name, text),
        )


# ---------------------------------------------------------------------
# Login / session
# ---------------------------------------------------------------------
def login(username_or_email: str, password: str) -> tuple[bool, str]:
    from logging_setup import log_event

    user = db.query_one(
        "SELECT * FROM users WHERE username = ? OR email = ?",
        (username_or_email, username_or_email),
    )
    if not user:
        log_event("login_failed", reason="no_such_user", attempted=username_or_email)
        return False, "No account found with that username or email."
    if user["status"] != "ACTIVE":
        log_event("login_failed", reason="account_disabled", username=user["username"])
        return False, "This account has been disabled. Contact your administrator."
    if not verify_password(password, user["password_hash"]):
        log_event("login_failed", reason="bad_password", username=user["username"])
        return False, "Incorrect password."

    institute = db.query_one(
        "SELECT * FROM institutes WHERE institute_id = ?", (user["institute_id"],)
    )

    st.session_state["auth"] = {
        "user_id": user["user_id"],
        "username": user["username"],
        "full_name": user["full_name"],
        "role": user["role"],
        "institute_id": user["institute_id"],
        "institute_name": institute["institute_name"] if institute else "",
        "is_demo": bool(user.get("is_demo")),
    }
    log_event("login_success", username=user["username"], institute_id=user["institute_id"])
    return True, "success"


def is_demo() -> bool:
    user = current_user()
    return bool(user and user.get("is_demo"))


def change_password(user_id: int, current_password: str, new_password: str) -> tuple[bool, str]:
    user = db.query_one("SELECT * FROM users WHERE user_id=?", (user_id,))
    if not user:
        return False, "User not found."
    if user.get("is_demo"):
        return False, "Password changes are disabled for the demo account."
    if not verify_password(current_password, user["password_hash"]):
        return False, "Current password is incorrect."
    if len(new_password) < 6:
        return False, "New password must be at least 6 characters."
    db.execute("UPDATE users SET password_hash=? WHERE user_id=?",
              (hash_password(new_password), user_id))
    return True, "Password updated successfully."


def ensure_demo_account():
    """Idempotently creates the fixed demo institute + demo admin login,
    pre-populated with sample data, so prospective customers can explore
    the full software without needing their own account. Safe to call on
    every app startup - does nothing once the demo account already exists."""
    import config
    existing = db.query_one("SELECT user_id FROM users WHERE username = ?", (config.DEMO_USERNAME,))
    if existing:
        return

    institute_id = generate_institute_id()
    while db.query_one("SELECT institute_id FROM institutes WHERE institute_id = ?", (institute_id,)):
        institute_id = generate_institute_id()

    db.execute(
        """INSERT INTO institutes (institute_id, institute_name, owner_name, mobile, whatsapp_number, email, is_demo)
           VALUES (?, ?, ?, ?, ?, ?, 1)""",
        (institute_id, config.DEMO_INSTITUTE_NAME, "Demo Owner", "9999999999", "9999999999", "demo@example.com"),
    )
    db.execute(
        """INSERT INTO users (institute_id, username, email, password_hash, full_name, role, is_demo)
           VALUES (?, ?, ?, ?, ?, 'ADMIN', 1)""",
        (institute_id, config.DEMO_USERNAME, "demo@example.com", hash_password(config.DEMO_PASSWORD), "Demo Admin"),
    )
    seed_default_templates(institute_id)

    from modules import sample_data
    sample_data.generate(institute_id)


def logout():
    for key in ("auth", "page"):
        if key in st.session_state:
            del st.session_state[key]


def is_logged_in() -> bool:
    return "auth" in st.session_state


def current_user():
    return st.session_state.get("auth")


def require_role(*roles):
    user = current_user()
    if not user:
        return False
    return user["role"] in roles


ROLE_PERMISSIONS = {
    "ADMIN": "ALL",
    "MANAGER": {"dashboard", "students", "courses", "batches", "admissions",
                "attendance", "tests", "fees", "reports", "whatsapp", "birthdays",
                "schedule", "faculty", "notifications"},
    "STAFF": {"dashboard", "students", "attendance", "tests", "schedule", "whatsapp",
              "birthdays", "notifications"},
}


def can_access(page_key: str) -> bool:
    user = current_user()
    if not user:
        return False
    perms = ROLE_PERMISSIONS.get(user["role"], set())
    if perms == "ALL":
        return True
    return page_key in perms
