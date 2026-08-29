"""modules/students.py - Student Management (add/edit/delete/search/profile)"""

from datetime import date

import streamlit as st
import pandas as pd

import database as db
import utils
import whatsapp as wa
from auth import current_user


def _course_options(inst):
    rows = db.query_all("SELECT course_id, course_name FROM courses WHERE institute_id=? AND status='ACTIVE'", (inst,))
    return {r["course_name"]: r["course_id"] for r in rows}


def _batch_options(inst, course_id=None):
    if course_id:
        rows = db.query_all("SELECT batch_id, batch_name FROM batches WHERE institute_id=? AND course_id=?", (inst, course_id))
    else:
        rows = db.query_all("SELECT batch_id, batch_name FROM batches WHERE institute_id=?", (inst,))
    return {r["batch_name"]: r["batch_id"] for r in rows}


def _next_seq(inst):
    row = db.query_one("SELECT COUNT(*) c FROM students WHERE institute_id=?", (inst,))
    return (row["c"] or 0) + 1


def render():
    user = current_user()
    inst = user["institute_id"]
    st.markdown("## 👨‍🎓 Student Management")

    tabs = st.tabs(["📋 All Students", "➕ Add Student", "🔍 Search / Filter"])

    # ---------------- All Students ----------------
    with tabs[0]:
        df = pd.DataFrame(db.query_all(
            """SELECT s.student_id, s.student_name, c.course_name, b.batch_name,
                      s.student_mobile, s.parent_mobile, s.payment_status, s.status
               FROM students s
               LEFT JOIN courses c ON c.course_id = s.course_id
               LEFT JOIN batches b ON b.batch_id = s.batch_id
               WHERE s.institute_id=? ORDER BY s.created_at DESC""",
            (inst,)))
        if df.empty:
            st.info("No students added yet. Use the 'Add Student' tab to get started.")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.download_button(
                "⬇️ Export Excel", utils.to_excel_bytes(df, "Students"),
                file_name="students_export.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            st.markdown("---")
            st.markdown("#### View / Edit / Delete a Student")
            ids = df["student_id"].tolist()
            sel = st.selectbox("Select Student ID", ids)
            if sel:
                _student_detail(inst, sel)

    # ---------------- Add Student ----------------
    with tabs[1]:
        courses = _course_options(inst)
        if not courses:
            st.warning("Please add at least one Course before adding students.")
        else:
            with st.form("add_student_form", clear_on_submit=True):
                c1, c2 = st.columns(2)
                with c1:
                    name = st.text_input("Student Name *")
                    father = st.text_input("Father Name")
                    mother = st.text_input("Mother Name")
                    gender = st.selectbox("Gender", ["Male", "Female", "Other"])
                    dob = st.date_input("Date of Birth", value=None, min_value=date(1970, 1, 1), max_value=date.today())
                    mobile = st.text_input("Student Mobile")
                    parent_mobile = st.text_input("Parent Mobile *")
                    whatsapp_num = st.text_input("WhatsApp Number (defaults to Parent Mobile)")
                with c2:
                    email = st.text_input("Email")
                    address = st.text_area("Address")
                    city = st.text_input("City")
                    course_name = st.selectbox("Course *", list(courses.keys()))
                    batches = _batch_options(inst, courses.get(course_name))
                    batch_name = st.selectbox("Batch", ["(none)"] + list(batches.keys()))
                    admission_date = st.date_input("Admission Date", value=date.today())
                    total_fees = st.number_input("Total Fees", min_value=0.0, step=500.0)
                    discount = st.number_input("Discount", min_value=0.0, step=100.0)
                    paid_fees = st.number_input("Paid (initial)", min_value=0.0, step=500.0)
                notes = st.text_area("Notes")
                submitted = st.form_submit_button("💾 Save Student", use_container_width=True)

            if submitted:
                if not name or not parent_mobile:
                    utils.toast_error("Student Name and Parent Mobile are required.")
                elif not utils.is_valid_mobile(parent_mobile):
                    utils.toast_error("Please enter a valid Parent Mobile number.")
                elif not utils.is_valid_email(email):
                    utils.toast_error("Please enter a valid email address.")
                else:
                    net_fees = max(total_fees - discount, 0)
                    pending = max(net_fees - paid_fees, 0)
                    pay_status = "PAID" if pending == 0 else ("PARTIAL" if paid_fees > 0 else "PENDING")
                    student_id = utils.generate_student_id(inst, _next_seq(inst))
                    while db.query_one("SELECT student_id FROM students WHERE student_id=?", (student_id,)):
                        student_id = utils.generate_student_id(inst, _next_seq(inst) + 1)

                    batch_id = batches.get(batch_name) if batch_name != "(none)" else None
                    db.execute(
                        """INSERT INTO students
                           (student_id, institute_id, student_name, father_name, mother_name, gender,
                            dob, student_mobile, parent_mobile, whatsapp_number, email, address, city,
                            course_id, batch_id, admission_date, joining_date, total_fees, discount,
                            net_fees, paid_fees, pending_fees, payment_status, notes, status)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (student_id, inst, name, father, mother, gender,
                         dob.isoformat() if dob else None, mobile, parent_mobile,
                         whatsapp_num or parent_mobile, email, address, city,
                         courses.get(course_name), batch_id,
                         admission_date.isoformat(), admission_date.isoformat(),
                         total_fees, discount, net_fees, paid_fees, pending, pay_status, notes, "ACTIVE"),
                    )
                    if paid_fees > 0:
                        receipt = utils.generate_receipt_number(_next_seq(inst))
                        db.execute(
                            """INSERT INTO fee_payments (institute_id, student_id, receipt_number, amount, payment_mode, payment_date)
                               VALUES (?,?,?,?,?,?)""",
                            (inst, student_id, receipt, paid_fees, "Cash", admission_date.isoformat()))
                    db.execute(
                        """INSERT INTO admissions (institute_id, student_id, course_id, batch_id, admission_date,
                                                    total_fees, discount, net_fees, initial_payment)
                           VALUES (?,?,?,?,?,?,?,?,?)""",
                        (inst, student_id, courses.get(course_name), batch_id, admission_date.isoformat(),
                         total_fees, discount, net_fees, paid_fees))
                    utils.toast_success(f"Student added successfully! Student ID: {student_id}")
                    st.rerun()

    # ---------------- Search / Filter ----------------
    with tabs[2]:
        c1, c2, c3 = st.columns(3)
        with c1:
            q = st.text_input("Search (Name / ID / Mobile)")
        with c2:
            courses_map = _course_options(inst)
            course_f = st.selectbox("Filter by Course", ["All"] + list(courses_map.keys()))
        with c3:
            status_f = st.selectbox("Status", ["All", "ACTIVE", "INACTIVE"])

        sql = """SELECT s.student_id, s.student_name, c.course_name, b.batch_name,
                         s.student_mobile, s.parent_mobile, s.pending_fees, s.status
                  FROM students s
                  LEFT JOIN courses c ON c.course_id=s.course_id
                  LEFT JOIN batches b ON b.batch_id=s.batch_id
                  WHERE s.institute_id=?"""
        params = [inst]
        if q:
            sql += " AND (s.student_name LIKE ? OR s.student_id LIKE ? OR s.student_mobile LIKE ? OR s.parent_mobile LIKE ?)"
            like = f"%{q}%"
            params += [like, like, like, like]
        if course_f != "All":
            sql += " AND c.course_name = ?"
            params.append(course_f)
        if status_f != "All":
            sql += " AND s.status = ?"
            params.append(status_f)

        results = pd.DataFrame(db.query_all(sql, tuple(params)))
        st.dataframe(results, use_container_width=True, hide_index=True)
        if not results.empty:
            st.download_button(
                "⬇️ Export Filtered Results", utils.to_excel_bytes(results, "Students"),
                file_name="students_filtered.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def _student_detail(inst, student_id):
    s = db.query_one("SELECT * FROM students WHERE student_id=? AND institute_id=?", (student_id, inst))
    if not s:
        return
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"**Name:** {s['student_name']}")
        st.markdown(f"**Father:** {s['father_name'] or '-'}")
        st.markdown(f"**Gender:** {s['gender'] or '-'} | **DOB:** {utils.fmt_date(s['dob'])}")
    with c2:
        st.markdown(f"**Mobile:** {s['student_mobile'] or '-'}")
        st.markdown(f"**Parent Mobile:** {s['parent_mobile'] or '-'}")
        st.markdown(f"**Email:** {s['email'] or '-'}")
    with c3:
        st.markdown(f"**Total Fees:** {utils.fmt_currency(s['total_fees'])}")
        st.markdown(f"**Paid:** {utils.fmt_currency(s['paid_fees'])}")
        st.markdown(f"**Pending:** {utils.fmt_currency(s['pending_fees'])}")

    sub_tabs = st.tabs(["✏️ Edit", "📅 Attendance History", "💰 Fee History", "🗑️ Delete"])

    with sub_tabs[0]:
        with st.form(f"edit_{student_id}"):
            name = st.text_input("Student Name", value=s["student_name"])
            mobile = st.text_input("Student Mobile", value=s["student_mobile"] or "")
            parent_mobile = st.text_input("Parent Mobile", value=s["parent_mobile"] or "")
            whatsapp_num = st.text_input("WhatsApp Number", value=s["whatsapp_number"] or "")
            status = st.selectbox("Status", ["ACTIVE", "INACTIVE"], index=0 if s["status"] == "ACTIVE" else 1)
            save = st.form_submit_button("💾 Update")
        if save:
            db.execute(
                """UPDATE students SET student_name=?, student_mobile=?, parent_mobile=?,
                   whatsapp_number=?, status=? WHERE student_id=? AND institute_id=?""",
                (name, mobile, parent_mobile, whatsapp_num, status, student_id, inst))
            utils.toast_success("Student updated.")
            st.rerun()

    with sub_tabs[1]:
        att = pd.DataFrame(db.query_all(
            "SELECT att_date, status FROM attendance WHERE student_id=? ORDER BY att_date DESC", (student_id,)))
        if att.empty:
            st.info("No attendance records yet.")
        else:
            st.dataframe(att, use_container_width=True, hide_index=True)

    with sub_tabs[2]:
        pay = pd.DataFrame(db.query_all(
            "SELECT payment_date, receipt_number, amount, payment_mode FROM fee_payments WHERE student_id=? ORDER BY payment_date DESC",
            (student_id,)))
        if pay.empty:
            st.info("No payment history yet.")
        else:
            st.dataframe(pay, use_container_width=True, hide_index=True)

    with sub_tabs[3]:
        st.warning("Deleting a student removes their record permanently.")
        if utils.confirm_action(f"confirm_del_{student_id}", "I understand this cannot be undone"):
            if st.button("🗑️ Delete Student Permanently", key=f"del_btn_{student_id}"):
                db.execute("DELETE FROM students WHERE student_id=? AND institute_id=?", (student_id, inst))
                utils.toast_success("Student deleted.")
                st.rerun()
