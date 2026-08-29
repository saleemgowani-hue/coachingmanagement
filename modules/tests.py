"""modules/tests.py - Test / Exam Management

Create tests, record marks per student, and view batch-wise / subject-wise
performance reports with charts and Excel export.
"""

from datetime import date

import streamlit as st
import pandas as pd
import plotly.express as px

import database as db
import utils
import reports
import whatsapp as wa
from auth import current_user

TEST_TYPES = ["Unit Test", "Monthly Test", "Mock Test", "Term Exam", "Final Exam"]


def _course_map(inst):
    rows = db.query_all("SELECT course_id, course_name FROM courses WHERE institute_id=?", (inst,))
    return {r["course_name"]: r["course_id"] for r in rows}


def _batch_map(inst, course_id=None):
    if course_id:
        rows = db.query_all("SELECT batch_id, batch_name FROM batches WHERE institute_id=? AND course_id=?", (inst, course_id))
    else:
        rows = db.query_all("SELECT batch_id, batch_name FROM batches WHERE institute_id=?", (inst,))
    return {r["batch_name"]: r["batch_id"] for r in rows}


def render():
    user = current_user()
    inst = user["institute_id"]
    st.markdown("## 📋 Test Management")

    tabs = st.tabs(["📝 All Tests", "➕ Create Test", "✍️ Enter Marks", "📊 Performance Reports"])

    # ---------------- All Tests ----------------
    with tabs[0]:
        df = reports.report_tests(inst)
        if df.empty:
            st.info("No tests created yet. Use the 'Create Test' tab to add one.")
        else:
            view = df.rename(columns={
                "test_name": "Test", "subject": "Subject", "course_name": "Course",
                "batch_name": "Batch", "test_date": "Date", "max_marks": "Max Marks",
                "test_type": "Type", "results_entered": "Marks Entered", "avg_pct": "Avg %",
            })[["Test", "Subject", "Course", "Batch", "Date", "Max Marks", "Type", "Marks Entered", "Avg %"]]
            st.dataframe(view, use_container_width=True, hide_index=True)
            st.download_button("⬇️ Export Excel", utils.to_excel_bytes(view, "Tests"),
                               file_name="tests_list.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            st.markdown("#### Edit / Delete a Test")
            sel = st.selectbox("Select test", df["test_name"].tolist(), key="all_tests_sel")
            row = df[df["test_name"] == sel].iloc[0]
            with st.form("edit_test"):
                max_marks = st.number_input("Max Marks", min_value=1.0, value=float(row["max_marks"]))
                colA, colB = st.columns(2)
                update = colA.form_submit_button("💾 Update", use_container_width=True)
                delete = colB.form_submit_button("🗑️ Delete Test", use_container_width=True)
            if update:
                db.execute("UPDATE tests SET max_marks=? WHERE test_id=? AND institute_id=?",
                          (max_marks, int(row["test_id"]), inst))
                utils.toast_success("Test updated.")
                st.rerun()
            if delete:
                db.execute("DELETE FROM test_results WHERE test_id=? AND institute_id=?", (int(row["test_id"]), inst))
                db.execute("DELETE FROM tests WHERE test_id=? AND institute_id=?", (int(row["test_id"]), inst))
                utils.toast_success("Test and its results deleted.")
                st.rerun()

    # ---------------- Create Test ----------------
    with tabs[1]:
        courses = _course_map(inst)
        if not courses:
            st.warning("Please add at least one Course before creating a test.")
        else:
            with st.form("create_test", clear_on_submit=True):
                c1, c2 = st.columns(2)
                with c1:
                    test_name = st.text_input("Test Name *", placeholder="e.g. Unit Test 1 - Algebra")
                    subject = st.text_input("Subject *", placeholder="e.g. Mathematics")
                    test_type = st.selectbox("Test Type", TEST_TYPES)
                with c2:
                    course_name = st.selectbox("Course *", list(courses.keys()))
                    batches = _batch_map(inst, courses.get(course_name))
                    batch_name = st.selectbox("Batch *", list(batches.keys()) if batches else ["(add a batch first)"])
                    test_date = st.date_input("Test Date", value=date.today())
                    max_marks = st.number_input("Max Marks", min_value=1.0, value=100.0, step=5.0)
                notes = st.text_area("Notes")
                submit = st.form_submit_button("💾 Create Test", use_container_width=True)

            if submit:
                if not test_name or not subject:
                    utils.toast_error("Test Name and Subject are required.")
                elif not batches:
                    utils.toast_error("Please add a batch for this course first.")
                else:
                    db.execute(
                        """INSERT INTO tests (institute_id, test_name, subject, course_id, batch_id,
                           test_date, max_marks, test_type, notes)
                           VALUES (?,?,?,?,?,?,?,?,?)""",
                        (inst, test_name, subject, courses.get(course_name), batches.get(batch_name),
                         test_date.isoformat(), max_marks, test_type, notes))
                    utils.toast_success("Test created. Go to 'Enter Marks' to record student scores.")
                    st.rerun()

    # ---------------- Enter Marks ----------------
    with tabs[2]:
        all_tests = db.query_all(
            """SELECT t.test_id, t.test_name, t.subject, t.max_marks, t.batch_id, b.batch_name
               FROM tests t LEFT JOIN batches b ON b.batch_id=t.batch_id
               WHERE t.institute_id=? ORDER BY t.test_date DESC""",
            (inst,))
        if not all_tests:
            st.info("No tests available yet. Create one in the 'Create Test' tab first.")
        else:
            test_options = {f"{t['test_name']} — {t['subject']} ({t['batch_name'] or 'No batch'})": t for t in all_tests}
            sel_label = st.selectbox("Select Test", list(test_options.keys()))
            test = test_options[sel_label]

            students = db.query_all(
                "SELECT student_id, student_name, whatsapp_number FROM students WHERE institute_id=? AND batch_id=? AND status='ACTIVE' ORDER BY student_name",
                (inst, test["batch_id"]))

            if not students:
                st.warning("No active students found in this test's batch.")
            else:
                existing = {r["student_id"]: r["marks_obtained"] for r in db.query_all(
                    "SELECT student_id, marks_obtained FROM test_results WHERE test_id=?", (test["test_id"],))}

                st.markdown(f"**{len(students)} student(s)** in this batch — max marks: **{test['max_marks']}**")
                marks_input = {}
                with st.form("enter_marks_form"):
                    for s in students:
                        default_val = existing.get(s["student_id"])
                        marks_input[s["student_id"]] = st.number_input(
                            s["student_name"], min_value=0.0, max_value=float(test["max_marks"]),
                            value=float(default_val) if default_val is not None else 0.0,
                            step=1.0, key=f"marks_{test['test_id']}_{s['student_id']}")
                    save = st.form_submit_button("💾 Save All Marks", use_container_width=True)

                if save:
                    for sid, marks in marks_input.items():
                        db.execute(
                            """INSERT INTO test_results (institute_id, test_id, student_id, marks_obtained)
                               VALUES (?,?,?,?)
                               ON CONFLICT(test_id, student_id) DO UPDATE SET marks_obtained=excluded.marks_obtained""",
                            (inst, test["test_id"], sid, marks))
                    utils.toast_success("Marks saved.")
                    st.rerun()

                if existing:
                    st.markdown("---")
                    st.markdown("#### 📱 Send Results to Parents")
                    institute_row = db.query_one("SELECT institute_name FROM institutes WHERE institute_id=?", (inst,))
                    inst_name = institute_row["institute_name"] if institute_row else ""
                    templates = {t["template_name"]: t["template_text"] for t in wa.get_templates(inst)}
                    result_text = templates.get("Test Result", wa.DEFAULT_TEMPLATES["Test Result"])

                    for s in students:
                        marks = existing.get(s["student_id"])
                        if marks is None:
                            continue
                        pct = round(marks * 100.0 / test["max_marks"], 1)
                        msg = wa.fill_template(result_text, {
                            "STUDENT_NAME": s["student_name"], "TEST_NAME": test["test_name"],
                            "SUBJECT": test["subject"], "MARKS_OBTAINED": marks,
                            "MAX_MARKS": test["max_marks"], "PERCENTAGE": pct,
                            "INSTITUTE_NAME": inst_name,
                        })
                        link = wa.build_link(s["whatsapp_number"], msg)
                        c1, c2, c3 = st.columns([3, 1, 1])
                        c1.markdown(f"**{s['student_name']}** — {marks}/{test['max_marks']} ({pct}%, {utils.calc_grade(pct)})")
                        with c3:
                            if link:
                                st.link_button("📱 Send", link, use_container_width=True)
                            else:
                                st.caption("No WhatsApp #")

    # ---------------- Performance Reports ----------------
    with tabs[3]:
        kpis = reports.test_kpis(inst)
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Tests", kpis["total_tests"])
        c2.metric("Upcoming Tests", kpis["upcoming_tests"])
        c3.metric("Overall Average %", f"{kpis['overall_avg_pct']}%" if kpis["overall_avg_pct"] is not None else "—")

        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Batch-wise Performance")
            batch_df = reports.batch_wise_test_performance(inst)
            batch_df_valid = batch_df[batch_df["avg_pct"].notna()] if not batch_df.empty else batch_df
            if batch_df_valid.empty:
                st.info("No test results yet.")
            else:
                fig = px.bar(batch_df_valid, x="batch_name", y="avg_pct", title="Average % by Batch",
                             color_discrete_sequence=["#1565C0"])
                fig.update_layout(margin=dict(t=40, b=10, l=10, r=10), height=320, yaxis_range=[0, 100])
                st.plotly_chart(fig, use_container_width=True)
                st.dataframe(batch_df, use_container_width=True, hide_index=True)

        with col2:
            st.markdown("#### Subject-wise Performance")
            subj_df = reports.subject_wise_test_performance(inst)
            subj_df_valid = subj_df[subj_df["avg_pct"].notna()] if not subj_df.empty else subj_df
            if subj_df_valid.empty:
                st.info("No test results yet.")
            else:
                fig = px.bar(subj_df_valid, x="subject", y="avg_pct", title="Average % by Subject",
                             color_discrete_sequence=["#6A1B9A"])
                fig.update_layout(margin=dict(t=40, b=10, l=10, r=10), height=320, yaxis_range=[0, 100])
                st.plotly_chart(fig, use_container_width=True)
                st.dataframe(subj_df, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.markdown("#### 🏆 Top & Bottom Performers (overall average, across all tests)")
        top_df, bottom_df = reports.top_bottom_performers(inst)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Top 5**")
            if top_df.empty:
                st.caption("No data yet.")
            else:
                st.dataframe(top_df, use_container_width=True, hide_index=True)
        with c2:
            st.markdown("**Needs Attention (Bottom 5)**")
            if bottom_df.empty:
                st.caption("No data yet.")
            else:
                st.dataframe(bottom_df, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.markdown("#### 📄 Detailed Results (all tests)")
        results_df = reports.report_test_results(inst)
        if results_df.empty:
            st.info("No marks entered yet.")
        else:
            results_df = results_df.copy()
            results_df["grade"] = results_df["percentage"].apply(utils.calc_grade)
            st.dataframe(results_df, use_container_width=True, hide_index=True)
            st.download_button("⬇️ Export All Results", utils.to_excel_bytes(results_df, "Test Results"),
                               file_name="test_results.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
