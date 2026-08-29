"""
utils.py
SN COACHING MANAGEMENT SYSTEM
Shared helpers: validation, formatting, ID generation, small UI widgets.
"""

import random
import re
import string
from datetime import datetime, date

import pandas as pd
import streamlit as st


# ---------------------------------------------------------------------
def generate_student_id(institute_id: str, seq: int) -> str:
    year = datetime.now().strftime("%y")
    return f"STU{year}{seq:04d}"


def generate_receipt_number(seq: int) -> str:
    year = datetime.now().strftime("%y")
    return f"RCPT{year}{seq:05d}"


def is_valid_mobile(number: str) -> bool:
    if not number:
        return False
    digits = re.sub(r"\D", "", number)
    return 7 <= len(digits) <= 13


def is_valid_email(email: str) -> bool:
    if not email:
        return True  # optional field
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))


def fmt_currency(amount, symbol="₹") -> str:
    try:
        amount = float(amount or 0)
    except (ValueError, TypeError):
        amount = 0
    return f"{symbol}{amount:,.2f}"


def fmt_date(d, fmt="%d-%m-%Y"):
    if not d:
        return "-"
    if isinstance(d, str):
        try:
            d = datetime.strptime(d[:10], "%Y-%m-%d").date()
        except ValueError:
            return d
    return d.strftime(fmt)


def today_iso() -> str:
    return date.today().isoformat()


def calc_age(dob_str) -> str:
    if not dob_str:
        return "-"
    try:
        dob = datetime.strptime(dob_str[:10], "%Y-%m-%d").date()
    except ValueError:
        return "-"
    today = date.today()
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    return str(age)


def to_excel_bytes(df: pd.DataFrame, sheet_name="Sheet1") -> bytes:
    import io
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return buffer.getvalue()


def calc_grade(percentage) -> str:
    try:
        pct = float(percentage)
    except (ValueError, TypeError):
        return "-"
    if pct >= 90: return "A+"
    if pct >= 75: return "A"
    if pct >= 60: return "B"
    if pct >= 45: return "C"
    if pct >= 33: return "D"
    return "F"


def toast_success(msg):
    st.success(f"✅ {msg}")


def toast_error(msg):
    st.error(f"⚠️ {msg}")


def toast_info(msg):
    st.info(f"ℹ️ {msg}")


def confirm_action(key: str, label: str = "I understand, proceed") -> bool:
    """Simple two-step confirm using a checkbox, for destructive actions."""
    return st.checkbox(label, key=key)


def kpi_card_css_class(kind: str) -> str:
    mapping = {
        "student": "kpi-blue",
        "finance": "kpi-green",
        "academic": "kpi-purple",
        "alert": "kpi-orange",
    }
    return mapping.get(kind, "kpi-blue")
