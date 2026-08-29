"""modules/faculty.py - Faculty Management"""

from datetime import date

import streamlit as st
import pandas as pd

import database as db
import utils
from auth import current_user


def render():
    user = current_user()
    inst = user["institute_id"]
    st.markdown("## 👨‍🏫 Faculty Management")

    tabs = st.tabs(["📋 All Faculty", "➕ Add Faculty"])

    with tabs[0]:
        df = pd.DataFrame(db.query_all(
            "SELECT faculty_id, faculty_name, mobile, subject, joining_date, status FROM faculty WHERE institute_id=? ORDER BY faculty_id DESC",
            (inst,)))
        if df.empty:
            st.info("No faculty added yet.")
        else:
            q = st.text_input("Search faculty")
            view = df[df["faculty_name"].str.contains(q, case=False, na=False)] if q else df
            st.dataframe(view, use_container_width=True, hide_index=True)
            st.download_button("⬇️ Export Excel", utils.to_excel_bytes(df, "Faculty"),
                               file_name="faculty_export.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            st.markdown("#### Edit / Delete")
            sel = st.selectbox("Select faculty", df["faculty_name"].tolist())
            row = df[df["faculty_name"] == sel].iloc[0]
            with st.form("edit_faculty"):
                status = st.selectbox("Status", ["ACTIVE", "INACTIVE"], index=0 if row["status"] == "ACTIVE" else 1)
                mobile = st.text_input("Mobile", value=row["mobile"] or "")
                colA, colB = st.columns(2)
                update = colA.form_submit_button("💾 Update", use_container_width=True)
                delete = colB.form_submit_button("🗑️ Delete", use_container_width=True)
            if update:
                db.execute("UPDATE faculty SET status=?, mobile=? WHERE faculty_id=? AND institute_id=?",
                           (status, mobile, int(row["faculty_id"]), inst))
                utils.toast_success("Faculty updated.")
                st.rerun()
            if delete:
                db.execute("DELETE FROM faculty WHERE faculty_id=? AND institute_id=?", (int(row["faculty_id"]), inst))
                utils.toast_success("Faculty deleted.")
                st.rerun()

    with tabs[1]:
        with st.form("add_faculty", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                name = st.text_input("Faculty Name *")
                mobile = st.text_input("Mobile")
                whatsapp_num = st.text_input("WhatsApp Number")
                email = st.text_input("Email")
            with c2:
                subject = st.text_input("Subject")
                joining_date = st.date_input("Joining Date", value=date.today())
                salary = st.number_input("Salary", min_value=0.0, step=1000.0)
                address = st.text_area("Address")
            submit = st.form_submit_button("💾 Save Faculty", use_container_width=True)
        if submit:
            if not name:
                utils.toast_error("Faculty Name is required.")
            else:
                db.execute(
                    """INSERT INTO faculty (institute_id, faculty_name, mobile, whatsapp_number, email,
                       subject, joining_date, salary, address) VALUES (?,?,?,?,?,?,?,?,?)""",
                    (inst, name, mobile, whatsapp_num or mobile, email, subject,
                     joining_date.isoformat(), salary, address))
                utils.toast_success("Faculty added.")
                st.rerun()
