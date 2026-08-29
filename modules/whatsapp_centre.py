"""modules/whatsapp_centre.py - WhatsApp Centre: templates + click-to-chat messaging"""

from datetime import date

import streamlit as st
import pandas as pd

import database as db
import utils
import whatsapp as wa
from auth import current_user


def render():
    user = current_user()
    inst = user["institute_id"]
    st.markdown("## 📱 WhatsApp Centre")
    st.caption("Uses WhatsApp Web click-to-chat. Messages are pre-filled for your review — "
               "you always press Send yourself inside WhatsApp.")

    tabs = st.tabs(["✉️ Send Message", "📇 Templates", "🗂️ Message Log"])

    institute = db.query_one("SELECT institute_name FROM institutes WHERE institute_id=?", (inst,))
    inst_name = institute["institute_name"] if institute else ""

    with tabs[0]:
        scope = st.radio("Send to", ["Individual Student", "Entire Batch", "Entire Course"], horizontal=True)
        templates = wa.get_templates(inst)
        template_names = [t["template_name"] for t in templates]
        template_choice = st.selectbox("Message Template", template_names)
        template_row = next(t for t in templates if t["template_name"] == template_choice)

        recipients = []
        if scope == "Individual Student":
            students = db.query_all("SELECT student_id, student_name, whatsapp_number FROM students WHERE institute_id=? AND status='ACTIVE'", (inst,))
            opts = {f"{s['student_name']} ({s['student_id']})": s for s in students}
            sel = st.multiselect("Select Student(s)", list(opts.keys()))
            recipients = [opts[s] for s in sel]
        elif scope == "Entire Batch":
            batches = db.query_all("SELECT batch_id, batch_name FROM batches WHERE institute_id=?", (inst,))
            bmap = {b["batch_name"]: b["batch_id"] for b in batches}
            bsel = st.selectbox("Select Batch", list(bmap.keys()) if bmap else ["(none)"])
            if bmap:
                recipients = db.query_all(
                    "SELECT student_id, student_name, whatsapp_number FROM students WHERE institute_id=? AND batch_id=? AND status='ACTIVE'",
                    (inst, bmap[bsel]))
        else:
            courses = db.query_all("SELECT course_id, course_name FROM courses WHERE institute_id=?", (inst,))
            cmap = {c["course_name"]: c["course_id"] for c in courses}
            csel = st.selectbox("Select Course", list(cmap.keys()) if cmap else ["(none)"])
            if cmap:
                recipients = db.query_all(
                    "SELECT student_id, student_name, whatsapp_number FROM students WHERE institute_id=? AND course_id=? AND status='ACTIVE'",
                    (inst, cmap[csel]))

        extra_vars = {}
        with st.expander("Fill in message variables"):
            extra_vars["DATE"] = st.text_input("DATE", value=date.today().strftime("%d-%m-%Y"))
            extra_vars["TIME"] = st.text_input("TIME", value="")
            extra_vars["AMOUNT"] = st.text_input("AMOUNT", value="")
            extra_vars["EXAM_NAME"] = st.text_input("EXAM_NAME", value="")
            extra_vars["REASON"] = st.text_input("REASON", value="")
            extra_vars["CUSTOM_MESSAGE"] = st.text_area("CUSTOM_MESSAGE", value="")

        if recipients:
            st.markdown(f"**{len(recipients)} recipient(s)** — review and send individually:")
            for r in recipients:
                course_row = db.query_one(
                    "SELECT c.course_name, b.batch_name FROM students s "
                    "LEFT JOIN courses c ON c.course_id=s.course_id "
                    "LEFT JOIN batches b ON b.batch_id=s.batch_id WHERE s.student_id=?",
                    (r["student_id"],))
                values = {
                    "STUDENT_NAME": r["student_name"],
                    "PARENT_NAME": "Parent",
                    "COURSE_NAME": course_row["course_name"] if course_row else "",
                    "BATCH_NAME": course_row["batch_name"] if course_row else "",
                    "INSTITUTE_NAME": inst_name,
                    "PENDING_AMOUNT": "", "DUE_DATE": "", "FACULTY_NAME": "",
                    **extra_vars,
                }
                msg = wa.fill_template(template_row["template_text"], values)
                link = wa.build_link(r["whatsapp_number"], msg)
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.text_area(f"Preview — {r['student_name']}", msg, height=80, key=f"prev_{r['student_id']}")
                with c2:
                    if link:
                        if st.link_button("📱 Open WhatsApp", link, use_container_width=True):
                            pass
                        wa.log_message(inst, r["student_id"], template_choice, msg, user["username"])
                    else:
                        st.caption("No WhatsApp number on file")
                st.divider()

    with tabs[1]:
        st.markdown("#### Manage Templates")
        templates = wa.get_templates(inst)
        for t in templates:
            with st.expander(t["template_name"]):
                new_text = st.text_area("Message", value=t["template_text"], key=f"tpl_{t['template_id']}")
                if st.button("💾 Save", key=f"save_tpl_{t['template_id']}"):
                    wa.save_template(inst, t["template_name"], new_text)
                    utils.toast_success("Template updated.")
                    st.rerun()
        st.markdown("Available variables: " + ", ".join(f"`[{v}]`" for v in wa.VARIABLES))

        with st.form("new_template", clear_on_submit=True):
            st.markdown("##### Add Custom Template")
            name = st.text_input("Template Name")
            text = st.text_area("Message Text")
            submit = st.form_submit_button("➕ Add Template")
        if submit and name and text:
            wa.save_template(inst, name, text)
            utils.toast_success("Custom template added.")
            st.rerun()

    with tabs[2]:
        logs = pd.DataFrame(db.query_all(
            """SELECT wl.created_at, s.student_name, wl.template_used, wl.sent_by
               FROM whatsapp_logs wl LEFT JOIN students s ON s.student_id = wl.student_id
               WHERE wl.institute_id=? ORDER BY wl.created_at DESC LIMIT 200""",
            (inst,)))
        if logs.empty:
            st.info("No messages prepared yet.")
        else:
            st.dataframe(logs, use_container_width=True, hide_index=True)
