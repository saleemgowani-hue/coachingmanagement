"""modules/notifications.py - Simple in-app notification center"""

import streamlit as st

import database as db
import reports
from auth import current_user


def render():
    user = current_user()
    inst = user["institute_id"]
    st.markdown("## 🔔 Notifications")

    alerts = []
    pending = reports.pending_fee_students(inst)
    if pending:
        alerts.append(("💰", f"{len(pending)} student(s) have pending fees."))
    low_att = reports.low_attendance_students(inst)
    if low_att:
        alerts.append(("⚠️", f"{len(low_att)} student(s) have attendance below 75%."))
    bday_today = reports.birthdays_today(inst)
    if bday_today:
        alerts.append(("🎂", f"{len(bday_today)} student(s) have a birthday today!"))
    bday_soon = reports.birthdays_upcoming(inst)
    if bday_soon:
        alerts.append(("🎉", f"{len(bday_soon)} student(s) have birthdays in the next 7 days."))

    if not alerts:
        st.success("You're all caught up — no alerts right now.")
    for icon, text in alerts:
        st.markdown(f"{icon} {text}")

    custom = db.query_all(
        "SELECT title, message, created_at FROM notifications WHERE institute_id=? ORDER BY created_at DESC LIMIT 50",
        (inst,))
    if custom:
        st.markdown("---")
        st.markdown("#### System Notifications")
        for n in custom:
            st.markdown(f"**{n['title']}** — {n['message']}")
            st.caption(n["created_at"])
