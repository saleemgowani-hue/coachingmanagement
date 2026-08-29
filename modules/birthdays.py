"""modules/birthdays.py - Birthday Management"""

import streamlit as st
import pandas as pd

import database as db
import utils
import reports
import whatsapp as wa
from auth import current_user


def render():
    user = current_user()
    inst = user["institute_id"]
    st.markdown("## 🎂 Birthday Management")

    templates = {t["template_name"]: t["template_text"] for t in wa.get_templates(inst)}
    wish_text = templates.get("Birthday Wish", wa.DEFAULT_TEMPLATES["Birthday Wish"])
    institute = db.query_one("SELECT institute_name FROM institutes WHERE institute_id=?", (inst,))
    inst_name = institute["institute_name"] if institute else ""

    def _render_list(students, empty_msg):
        if not students:
            st.info(empty_msg)
            return
        for s in students:
            c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
            with c1:
                st.markdown(f"**{s['student_name']}**")
            with c2:
                st.markdown(f"Age: {utils.calc_age(s['dob'])}")
            with c3:
                if "days_away" in s:
                    st.markdown(f"In {s['days_away']} day(s)")
            with c4:
                msg = wa.fill_template(wish_text, {"STUDENT_NAME": s["student_name"], "INSTITUTE_NAME": inst_name})
                link = wa.build_link(s.get("whatsapp_number"), msg)
                if link:
                    st.link_button("🎂 Send Wish", link, use_container_width=True)
                else:
                    st.caption("No WhatsApp #")
            st.divider()

    tabs = st.tabs(["🎉 Today's Birthdays", "📅 Upcoming (7 days)"])
    with tabs[0]:
        _render_list(reports.birthdays_today(inst), "No birthdays today.")
    with tabs[1]:
        _render_list(reports.birthdays_upcoming(inst), "No birthdays in the next 7 days.")
