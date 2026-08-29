"""modules/attendance.py - Attendance Management"""

from datetime import date, timedelta

import streamlit as st
import pandas as pd

import database as db
import utils
from auth import current_user


def render():
    user = current_user()
    inst = user["institute_id"]
    st.markdown("## 📅 Attendance Management")

    tabs = st.tabs(["✅ Mark Attendance", "📊 Reports"])

    with tabs[0]:
        c1, c2, c3 = st.columns(3)
        with c1:
            att_date = st.date_input("Date", value=date.today())
        courses = db.query_all("SELECT course_id, course_name FROM courses WHERE institute_id=?", (inst,))
        course_map = {c["course_name"]: c["course_id"] for c in courses}
        with c2:
            course_name = st.selectbox("Course", ["All"] + list(course_map.keys()))
        batches = db.query_all(
            "SELECT batch_id, batch_name FROM batches WHERE institute_id=?" +
            (" AND course_id=?" if course_name != "All" else ""),
            (inst, course_map[course_name]) if course_name != "All" else (inst,))
        batch_map = {b["batch_name"]: b["batch_id"] for b in batches}
        with c3:
            batch_name = st.selectbox("Batch", ["All"] + list(batch_map.keys()))

        sql = "SELECT student_id, student_name, course_id, batch_id FROM students WHERE institute_id=? AND status='ACTIVE'"
        params = [inst]
        if course_name != "All":
            sql += " AND course_id=?"
            params.append(course_map[course_name])
        if batch_name != "All":
            sql += " AND batch_id=?"
            params.append(batch_map[batch_name])
        students = db.query_all(sql, tuple(params))

        if not students:
            st.info("No matching students found.")
        else:
            existing = {r["student_id"]: r["status"] for r in db.query_all(
                "SELECT student_id, status FROM attendance WHERE att_date=? AND institute_id=?",
                (att_date.isoformat(), inst))}

            st.markdown(f"**{len(students)} student(s)** — mark attendance below:")
            marks = {}
            for s in students:
                default = existing.get(s["student_id"], "PRESENT")
                marks[s["student_id"]] = st.radio(
                    s["student_name"], ["PRESENT", "ABSENT", "LATE"],
                    index=["PRESENT", "ABSENT", "LATE"].index(default),
                    key=f"att_{s['student_id']}_{att_date}", horizontal=True)

            if st.button("💾 Save Attendance", use_container_width=True):
                for s in students:
                    db.execute(
                        """INSERT INTO attendance (institute_id, student_id, batch_id, course_id, att_date, status)
                           VALUES (?,?,?,?,?,?)
                           ON CONFLICT(student_id, att_date)
                           DO UPDATE SET status=excluded.status""",
                        (inst, s["student_id"], s["batch_id"], s["course_id"], att_date.isoformat(), marks[s["student_id"]]))
                utils.toast_success("Attendance saved.")
                st.rerun()

    with tabs[1]:
        c1, c2 = st.columns(2)
        with c1:
            start = st.date_input("From", value=date.today() - timedelta(days=30), key="att_rep_start")
        with c2:
            end = st.date_input("To", value=date.today(), key="att_rep_end")

        rows = db.query_all(
            """SELECT a.att_date, s.student_name, c.course_name, b.batch_name, a.status
               FROM attendance a
               JOIN students s ON s.student_id=a.student_id
               LEFT JOIN courses c ON c.course_id=a.course_id
               LEFT JOIN batches b ON b.batch_id=a.batch_id
               WHERE a.institute_id=? AND a.att_date BETWEEN ? AND ?
               ORDER BY a.att_date DESC""",
            (inst, start.isoformat(), end.isoformat()))
        df = pd.DataFrame(rows)
        if df.empty:
            st.info("No attendance records in this range.")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.download_button("⬇️ Export Excel", utils.to_excel_bytes(df, "Attendance"),
                               file_name="attendance_report.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            summary = df.groupby("student_name")["status"].apply(
                lambda x: round((x.isin(["PRESENT", "LATE"]).sum() / len(x)) * 100, 1)
            ).reset_index(name="attendance_pct").sort_values("attendance_pct")
            st.markdown("#### Attendance % Summary")
            st.dataframe(summary, use_container_width=True, hide_index=True)
