"""modules/courses.py - Course Management"""

import streamlit as st
import pandas as pd

import database as db
import utils
from auth import current_user


def render():
    user = current_user()
    inst = user["institute_id"]
    st.markdown("## 📚 Course Management")

    tabs = st.tabs(["📋 All Courses", "➕ Add Course"])

    with tabs[0]:
        df = pd.DataFrame(db.query_all(
            "SELECT course_id, course_name, course_code, duration, course_fees, status FROM courses WHERE institute_id=? ORDER BY course_id DESC",
            (inst,)))
        if df.empty:
            st.info("No courses yet. Add your first course (e.g. Abacus, Spoken English, Computer, Coding).")
        else:
            q = st.text_input("Search course")
            view = df[df["course_name"].str.contains(q, case=False, na=False)] if q else df
            st.dataframe(view, use_container_width=True, hide_index=True)

            st.markdown("#### Edit / Delete")
            sel = st.selectbox("Select course", df["course_name"].tolist())
            row = df[df["course_name"] == sel].iloc[0]
            with st.form("edit_course"):
                c1, c2 = st.columns(2)
                with c1:
                    name = st.text_input("Course Name", value=row["course_name"])
                    code = st.text_input("Course Code", value=row["course_code"] or "")
                    duration = st.text_input("Duration", value=row["duration"] or "")
                with c2:
                    fees = st.number_input("Course Fees", value=float(row["course_fees"] or 0), min_value=0.0, step=500.0)
                    status = st.selectbox("Status", ["ACTIVE", "INACTIVE"], index=0 if row["status"] == "ACTIVE" else 1)
                colA, colB = st.columns(2)
                update = colA.form_submit_button("💾 Update", use_container_width=True)
                delete = colB.form_submit_button("🗑️ Delete", use_container_width=True)
            if update:
                db.execute(
                    "UPDATE courses SET course_name=?, course_code=?, duration=?, course_fees=?, status=? WHERE course_id=? AND institute_id=?",
                    (name, code, duration, fees, status, int(row["course_id"]), inst))
                utils.toast_success("Course updated.")
                st.rerun()
            if delete:
                db.execute("DELETE FROM courses WHERE course_id=? AND institute_id=?", (int(row["course_id"]), inst))
                utils.toast_success("Course deleted.")
                st.rerun()

    with tabs[1]:
        with st.form("add_course", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                name = st.text_input("Course Name *")
                code = st.text_input("Course Code")
                duration = st.text_input("Duration (e.g. 6 months)")
            with c2:
                fees = st.number_input("Course Fees", min_value=0.0, step=500.0)
                description = st.text_area("Description")
            submit = st.form_submit_button("💾 Save Course", use_container_width=True)
        if submit:
            if not name:
                utils.toast_error("Course Name is required.")
            else:
                db.execute(
                    "INSERT INTO courses (institute_id, course_name, course_code, duration, course_fees, description) VALUES (?,?,?,?,?,?)",
                    (inst, name, code, duration, fees, description))
                utils.toast_success("Course added.")
                st.rerun()
