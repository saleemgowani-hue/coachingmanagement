"""
license.py
SN COACHING MANAGEMENT SYSTEM

Licence state machine: NOT_ACTIVATED -> ACTIVE_MONTHLY / ACTIVE_YEARLY -> EXPIRED
There is no free trial - a valid Monthly or Yearly licence key must be
entered before the software can be used. Architecture supports future
plans (QUARTERLY, HALF_YEARLY, LIFETIME) by just adding an entry to
PLAN_DURATIONS - no other code changes required.

NOTE ON SECURITY: the current implementation validates dates using the
local machine clock, same as any offline desktop application. The schema
(licence_id, licence_key, institute_id, plan, activation/expiry dates,
status) is already shaped so a future version can swap `_today()` for a
call to a server-side time/licence verification endpoint without changing
any of the calling code.
"""

import secrets
import string
from datetime import datetime, timedelta

import database as db

PLAN_DURATIONS = {
    "MONTHLY": 30,
    "YEARLY": 365,
    # future: "QUARTERLY": 90, "HALF_YEARLY": 182, "LIFETIME": None,
}

DATE_FMT = "%Y-%m-%d"


def _today():
    return datetime.now().date()


def _fmt(d):
    return d.strftime(DATE_FMT)


def _parse(s):
    return datetime.strptime(s, DATE_FMT).date()


# ---------------------------------------------------------------------
def generate_licence_key(plan: str) -> str:
    prefix = "SNM" if plan == "MONTHLY" else "SNY"
    body = "-".join(
        "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4))
        for _ in range(3)
    )
    key = f"{prefix}-{body}"
    db.execute(
        "INSERT INTO licence_keys (licence_key, plan, is_used) VALUES (?, ?, 0)",
        (key, plan),
    )
    return key


def get_latest_licence(institute_id: str):
    return db.query_one(
        """SELECT * FROM licences WHERE institute_id = ?
           ORDER BY licence_id DESC LIMIT 1""",
        (institute_id,),
    )


def get_status(institute_id: str) -> dict:
    """
    Returns a dict describing current licence state, recomputing EXPIRED
    on the fly if the stored status is stale relative to today's date.
    An institute with no licence row yet is NOT_ACTIVATED - there is no
    trial period, so the software stays locked until a key is entered.

    The fixed demo tenant (institutes.is_demo = 1) always reports a
    permanently active licence, regardless of the licences table, so
    prospective customers can explore the full software without needing
    a real key. A Super-Admin-suspended tenant always reports SUSPENDED,
    overriding whatever the licence row says.
    """
    inst_row = db.query_one("SELECT is_demo, is_suspended, suspension_reason FROM institutes WHERE institute_id=?", (institute_id,))
    if inst_row and inst_row.get("is_suspended"):
        return {"status": "SUSPENDED", "plan": None, "remaining_days": 0,
                "expiry_date": None, "activation_date": None, "licence_key": None,
                "suspension_reason": inst_row.get("suspension_reason")}

    if inst_row and inst_row.get("is_demo"):
        return {"status": "ACTIVE_YEARLY", "plan": "YEARLY", "remaining_days": 36500,
                "expiry_date": "Never (Demo Account)", "activation_date": "-", "licence_key": "DEMO"}

    row = get_latest_licence(institute_id)
    if not row:
        return {"status": "NOT_ACTIVATED", "plan": None, "remaining_days": 0,
                "expiry_date": None, "activation_date": None, "licence_key": None}

    expiry = _parse(row["expiry_date"]) if row["expiry_date"] else None
    remaining = (expiry - _today()).days if expiry else 0

    status = row["status"]
    if expiry and _today() > expiry and status not in ("EXPIRED",):
        status = "EXPIRED"
        db.execute("UPDATE licences SET status = ? WHERE licence_id = ?", (status, row["licence_id"]))

    return {
        "status": status,
        "plan": row["plan"],
        "remaining_days": max(remaining, 0),
        "expiry_date": row["expiry_date"],
        "activation_date": row["activation_date"],
        "licence_key": row["licence_key"],
    }


def count_available_keys() -> dict:
    """Returns how many unused licence keys currently exist in THIS database,
    per plan. Useful for confirming a key batch was actually imported before
    trying to activate one - a key only in an Excel sheet or JSON file that
    was never imported here will always show as 'Invalid'."""
    rows = db.query_all(
        "SELECT plan, COUNT(*) c FROM licence_keys WHERE is_used = 0 GROUP BY plan")
    counts = {"MONTHLY": 0, "YEARLY": 0}
    for r in rows:
        counts[r["plan"]] = r["c"]
    return counts


def admin_activate(institute_id: str, plan: str) -> tuple[bool, str]:
    """Direct admin-issued activation/renewal for the Super Admin panel -
    bypasses the customer-facing licence_keys requirement entirely, since
    an internal admin action doesn't need to consume a pre-generated key."""
    plan = plan.upper()
    if plan not in PLAN_DURATIONS:
        return False, "Unsupported plan type."
    start = _today()
    expiry = start + timedelta(days=PLAN_DURATIONS[plan])
    status = "ACTIVE_MONTHLY" if plan == "MONTHLY" else "ACTIVE_YEARLY"
    db.execute(
        """INSERT INTO licences (institute_id, licence_key, plan, status, activation_date, expiry_date)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (institute_id, "ADMIN-ISSUED", plan, status, _fmt(start), _fmt(expiry)),
    )
    return True, status


def set_suspended(institute_id: str, suspended: bool, reason: str = None):
    """Super Admin suspend/cancel (both map to this - the wording shown to
    the customer differs, the effect is identical: access is blocked while
    data is fully preserved) and unsuspend/reactivate."""
    db.execute(
        "UPDATE institutes SET is_suspended=?, suspension_reason=? WHERE institute_id=?",
        (1 if suspended else 0, reason if suspended else None, institute_id),
    )


def all_tenants_overview() -> list:
    """Cross-tenant summary for the Super Admin panel: one row per
    institute with its latest licence status, used only by the admin
    panel - never exposed to a customer session."""
    institutes = db.query_all("SELECT * FROM institutes ORDER BY created_at DESC")
    overview = []
    for inst in institutes:
        status = get_status(inst["institute_id"])
        student_count = db.query_one(
            "SELECT COUNT(*) c FROM students WHERE institute_id=?", (inst["institute_id"],))["c"]
        overview.append({
            "institute_id": inst["institute_id"],
            "institute_name": inst["institute_name"],
            "owner_name": inst["owner_name"],
            "mobile": inst["mobile"],
            "is_demo": bool(inst.get("is_demo")),
            "is_suspended": bool(inst.get("is_suspended")),
            "status": status["status"],
            "plan": status["plan"],
            "expiry_date": status["expiry_date"],
            "remaining_days": status["remaining_days"],
            "student_count": student_count,
            "created_at": inst["created_at"],
        })
    return overview


def activate_licence(institute_id: str, licence_key: str, plan: str) -> tuple[bool, str]:
    plan = plan.upper()
    if plan not in PLAN_DURATIONS:
        return False, "Unsupported plan type."

    key_row = db.query_one("SELECT * FROM licence_keys WHERE licence_key = ?", (licence_key.strip(),))
    if not key_row:
        return False, "Invalid licence key. Please check and try again."
    if key_row["is_used"]:
        return False, "This licence key has already been used."
    if key_row["plan"] != plan:
        return False, f"This licence key is not valid for the {plan.title()} plan."

    start = _today()
    duration = PLAN_DURATIONS[plan]
    expiry = start + timedelta(days=duration)
    status = "ACTIVE_MONTHLY" if plan == "MONTHLY" else "ACTIVE_YEARLY"

    db.execute(
        """INSERT INTO licences (institute_id, licence_key, plan, status, activation_date, expiry_date)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (institute_id, licence_key.strip(), plan, status, _fmt(start), _fmt(expiry)),
    )
    db.execute(
        "UPDATE licence_keys SET is_used = 1, used_by_institute = ? WHERE licence_key = ?",
        (institute_id, licence_key.strip()),
    )
    return True, status


def is_locked(institute_id: str) -> bool:
    """True if the software should show the locked / activate-licence screen."""
    status = get_status(institute_id)["status"]
    return status in ("EXPIRED", "NOT_ACTIVATED", "INVALID", "SUSPENDED")
