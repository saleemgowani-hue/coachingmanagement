"""modules/batches.py - Batch Management"""

from datetime import date, time

import streamlit as st
import pandas as pd

import database as db
import utils
from auth import current_user

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def render():
    user = current_user()
    inst = user["institute_id"]
    st.markdown("## 👥 Batch Management")

    courses = db.query_all("SELECT course_id, course_name FROM courses WHERE institute_id=?", (inst,))
    faculty = db.query_all("SELECT faculty_id, faculty_name FROM faculty WHERE institute_id=?", (inst,))
    course_map = {c["course_name"]: c["course_id"] for c in courses}
    faculty_map = {f["faculty_name"]: f["faculty_id"] for f in faculty}

    tabs = st.tabs(["📋 All Batches", "➕ Add Batch"])

    with tabs[0]:
        rows = db.query_all(
            """SELECT b.batch_id, b.batch_name, c.course_name, f.faculty_name, b.room,
                      b.start_time, b.end_time, b.max_students, b.status,
                      (SELECT COUNT(*) FROM students s WHERE s.batch_id=b.batch_id AND s.status='ACTIVE') AS strength
               FROM batches b
               LEFT JOIN courses c ON c.course_id=b.course_id
               LEFT JOIN faculty f ON f.faculty_id=b.faculty_id
               WHERE b.institute_id=? ORDER BY b.batch_id DESC""",
            (inst,))
        if not rows:
            st.info("No batches yet.")
        else:
            for r in rows:
                st.markdown(
                    f"""<div class="batch-card">
                        <b>{r['batch_name']}</b> — {r['course_name'] or '—'}<br/>
                        👨‍🏫 {r['faculty_name'] or 'Unassigned'} | 🏫 {r['room'] or '—'}<br/>
                        🕒 {r['start_time'] or '--'} – {r['end_time'] or '--'} &nbsp;|&nbsp;
                        Students: {r['strength']} / {r['max_students']}
                    </div>""",
                    unsafe_allow_html=True,
                )

            df = pd.DataFrame(rows)
            st.markdown("#### Edit / Delete")
            sel = st.selectbox("Select batch", df["batch_name"].tolist())
            row = df[df["batch_name"] == sel].iloc[0]
            with st.form("edit_batch"):
                status = st.selectbox("Status", ["ACTIVE", "INACTIVE"], index=0 if row["status"] == "ACTIVE" else 1)
                max_students = st.number_input("Max Students", min_value=1, value=int(row["max_students"]))
                colA, colB = st.columns(2)
                update = colA.form_submit_button("💾 Update", use_container_width=True)
                delete = colB.form_submit_button("🗑️ Delete", use_container_width=True)
            if update:
                db.execute("UPDATE batches SET status=?, max_students=? WHERE batch_id=? AND institute_id=?",
                           (status, max_students, int(row["batch_id"]), inst))
                utils.toast_success("Batch updated.")
                st.rerun()
            if delete:
                db.execute("DELETE FROM batches WHERE batch_id=? AND institute_id=?", (int(row["batch_id"]), inst))
                utils.toast_success("Batch deleted.")
                st.rerun()

    with tabs[1]:
        if not course_map:
            st.warning("Add at least one course before creating a batch.")
        else:
            with st.form("add_batch", clear_on_submit=True):
                c1, c2 = st.columns(2)
                with c1:
                    name = st.text_input("Batch Name *")
                    course_name = st.selectbox("Course *", list(course_map.keys()))
                    faculty_name = st.selectbox("Faculty", ["(unassigned)"] + list(faculty_map.keys()))
                    room = st.text_input("Room")
                    max_students = st.number_input("Maximum Students", min_value=1, value=25)
                with c2:
                    start_date = st.date_input("Start Date", value=date.today())
                    end_date = st.date_input("End Date", value=None)
                    class_days = st.multiselect("Class Days", DAYS)
                    start_time = st.time_input("Start Time", value=time(17, 0))
                    end_time = st.time_input("End Time", value=time(18, 0))
                submit = st.form_submit_button("💾 Save Batch", use_container_width=True)
            if submit:
                if not name:
                    utils.toast_error("Batch Name is required.")
                else:
                    db.execute(
                        """INSERT INTO batches (institute_id, batch_name, course_id, faculty_id, room, start_date,
                           end_date, class_days, start_time, end_time, max_students)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                        (inst, name, course_map.get(course_name),
                         faculty_map.get(faculty_name) if faculty_name != "(unassigned)" else None,
                         room, start_date.isoformat(), end_date.isoformat() if end_date else None,
                         ",".join(class_days), start_time.strftime("%H:%M"), end_time.strftime("%H:%M"),
                         max_students))
                    utils.toast_success("Batch added.")
                    st.rerun()
