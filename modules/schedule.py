"""modules/schedule.py - Class Schedule Management"""

from datetime import date, time, timedelta

import streamlit as st
import pandas as pd

import database as db
import utils
import whatsapp as wa
from auth import current_user


def render():
    user = current_user()
    inst = user["institute_id"]
    st.markdown("## 📆 Class Schedule")

    courses = db.query_all("SELECT course_id, course_name FROM courses WHERE institute_id=?", (inst,))
    batches = db.query_all("SELECT batch_id, batch_name FROM batches WHERE institute_id=?", (inst,))
    faculty = db.query_all("SELECT faculty_id, faculty_name FROM faculty WHERE institute_id=?", (inst,))
    course_map = {c["course_name"]: c["course_id"] for c in courses}
    batch_map = {b["batch_name"]: b["batch_id"] for b in batches}
    faculty_map = {f["faculty_name"]: f["faculty_id"] for f in faculty}

    tabs = st.tabs(["🗓️ Upcoming Classes", "➕ Schedule a Class"])

    with tabs[0]:
        rows = db.query_all(
            """SELECT cs.schedule_id, cs.class_date, cs.start_time, cs.end_time, cs.room, cs.topic,
                      c.course_name, b.batch_name, f.faculty_name
               FROM class_schedule cs
               LEFT JOIN courses c ON c.course_id=cs.course_id
               LEFT JOIN batches b ON b.batch_id=cs.batch_id
               LEFT JOIN faculty f ON f.faculty_id=cs.faculty_id
               WHERE cs.institute_id=? AND cs.class_date >= ?
               ORDER BY cs.class_date, cs.start_time""",
            (inst, date.today().isoformat()))
        if not rows:
            st.info("No upcoming classes scheduled.")
        else:
            institute = db.query_one("SELECT institute_name FROM institutes WHERE institute_id=?", (inst,))
            inst_name = institute["institute_name"] if institute else ""
            templates = {t["template_name"]: t["template_text"] for t in wa.get_templates(inst)}
            reminder = templates.get("Class Reminder", wa.DEFAULT_TEMPLATES["Class Reminder"])

            for r in rows:
                c1, c2, c3 = st.columns([3, 2, 1])
                with c1:
                    st.markdown(f"**{r['course_name'] or '—'}** — {r['batch_name'] or '—'}")
                    st.caption(f"{utils.fmt_date(r['class_date'])} | {r['start_time']}–{r['end_time']} | Room: {r['room'] or '—'}")
                with c2:
                    st.markdown(f"Faculty: {r['faculty_name'] or '—'}")
                    if r["topic"]:
                        st.caption(f"Topic: {r['topic']}")
                with c3:
                    students = db.query_all(
                        "SELECT whatsapp_number FROM students WHERE batch_id=(SELECT batch_id FROM class_schedule WHERE schedule_id=?) AND status='ACTIVE' LIMIT 1",
                        (r["schedule_id"],))
                    st.caption("Use WhatsApp Centre to notify the full batch")
                st.divider()
            df = pd.DataFrame(rows)
            st.download_button("⬇️ Export Schedule", utils.to_excel_bytes(df, "Schedule"),
                               file_name="class_schedule.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    with tabs[1]:
        with st.form("add_schedule", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                course_name = st.selectbox("Course", list(course_map.keys()) if course_map else ["(none)"])
                batch_name = st.selectbox("Batch", list(batch_map.keys()) if batch_map else ["(none)"])
                faculty_name = st.selectbox("Faculty", list(faculty_map.keys()) if faculty_map else ["(none)"])
            with c2:
                class_date = st.date_input("Date", value=date.today() + timedelta(days=1))
                start_time = st.time_input("Start Time", value=time(17, 0))
                end_time = st.time_input("End Time", value=time(18, 0))
                room = st.text_input("Room")
            topic = st.text_input("Topic")
            notes = st.text_area("Notes")
            submit = st.form_submit_button("💾 Schedule Class", use_container_width=True)
        if submit:
            db.execute(
                """INSERT INTO class_schedule (institute_id, course_id, batch_id, faculty_id, class_date,
                   start_time, end_time, room, topic, notes) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (inst, course_map.get(course_name), batch_map.get(batch_name), faculty_map.get(faculty_name),
                 class_date.isoformat(), start_time.strftime("%H:%M"), end_time.strftime("%H:%M"), room, topic, notes))
            utils.toast_success("Class scheduled.")
            st.rerun()
