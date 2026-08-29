"""modules/reports_page.py - Reports & Analytics Hub"""

from datetime import date, timedelta

import streamlit as st

import reports
import utils
from auth import current_user

REPORT_OPTIONS = {
    "Student Report": lambda inst, s, e: reports.report_students(inst),
    "Admission Report": lambda inst, s, e: reports.report_admissions(inst, s, e),
    "Fee Collection Report": lambda inst, s, e: reports.report_fee_collection(inst, s, e),
    "Pending Fee Report": lambda inst, s, e: reports.report_pending_fees(inst),
    "Attendance Report": lambda inst, s, e: reports.report_attendance(inst, s, e),
    "Test Results Report": lambda inst, s, e: reports.report_test_results(inst, s, e),
    "Batch-wise Test Performance": lambda inst, s, e: reports.batch_wise_test_performance(inst),
    "Subject-wise Test Performance": lambda inst, s, e: reports.subject_wise_test_performance(inst),
    "Course Report": lambda inst, s, e: reports.report_courses(inst),
    "Batch Report": lambda inst, s, e: reports.report_batches(inst),
    "Faculty Report": lambda inst, s, e: reports.report_faculty(inst),
    "Birthday Report": lambda inst, s, e: reports.report_birthdays(inst),
    "Payment Mode Report": lambda inst, s, e: reports.report_payment_mode(inst),
}


def render():
    user = current_user()
    inst = user["institute_id"]
    st.markdown("## 📊 Reports & Analytics")

    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        report_name = st.selectbox("Select Report", list(REPORT_OPTIONS.keys()))
    with c2:
        start = st.date_input("From", value=date.today() - timedelta(days=90), key="rep_start")
    with c3:
        end = st.date_input("To", value=date.today(), key="rep_end")

    df = REPORT_OPTIONS[report_name](inst, start.isoformat(), end.isoformat())

    if df is None or df.empty:
        st.info("No data available for this report / date range.")
        return

    search = st.text_input("🔍 Quick search within report")
    if search:
        mask = df.apply(lambda row: row.astype(str).str.contains(search, case=False).any(), axis=1)
        df = df[mask]

    sort_col = st.selectbox("Sort by", ["(none)"] + list(df.columns))
    if sort_col != "(none)":
        df = df.sort_values(sort_col)

    st.dataframe(df, use_container_width=True, hide_index=True)

    st.download_button(
        f"⬇️ Export '{report_name}' to Excel",
        utils.to_excel_bytes(df, report_name[:30]),
        file_name=f"{report_name.replace(' ', '_').lower()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    st.caption("For a print-friendly view, expand the table and use your browser's print (Ctrl+P) — "
               "or export to Excel for a formatted printout.")


def render_kpi_report():
    inst = current_user()["institute_id"]
    st.markdown("## 📈 KPI Report")

    sk = reports.student_kpis(inst)
    fk = reports.financial_kpis(inst)
    ak = reports.academic_kpis(inst)

    st.markdown("#### Student KPI")
    c = st.columns(5)
    growth = round((sk["new_admissions"] / sk["total"] * 100), 1) if sk["total"] else 0
    for col, (label, val) in zip(c, [
        ("Total Students", sk["total"]), ("Active", sk["active"]),
        ("New Admissions", sk["new_admissions"]), ("Inactive", sk["inactive"]),
        ("Growth %", f"{growth}%"),
    ]):
        col.metric(label, val)

    st.markdown("#### Financial KPI")
    c = st.columns(4)
    for col, (label, val) in zip(c, [
        ("Today's Collection", utils.fmt_currency(fk["today"])),
        ("Monthly Collection", utils.fmt_currency(fk["month"])),
        ("Total Collection", utils.fmt_currency(fk["total"])),
        ("Pending Fees", utils.fmt_currency(fk["pending"])),
    ]):
        col.metric(label, val)

    st.markdown("#### Operational KPI")
    c = st.columns(4)
    for col, (label, val) in zip(c, [
        ("Courses", ak["courses"]), ("Batches", ak["batches"]),
        ("Today's Classes", ak["today_classes"]), ("Today's Attendance", ak["today_attendance"]),
    ]):
        col.metric(label, val)
