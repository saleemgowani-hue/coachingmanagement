"""modules/dashboard.py - Main KPI dashboard"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

import reports
import license as lic
import utils
from auth import current_user


def kpi_card(label, value, icon, css_class):
    st.markdown(
        f"""
        <div class="kpi-card {css_class}">
            <div class="kpi-icon">{icon}</div>
            <div class="kpi-value">{value}</div>
            <div class="kpi-label">{label}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render():
    user = current_user()
    inst = user["institute_id"]

    status = lic.get_status(inst)
    st.markdown(f"## 🏠 Dashboard")

    top = st.columns([2, 1, 1, 1])
    with top[0]:
        st.markdown(f"**Institute:** {user['institute_name']}")
        st.markdown(f"**User:** {user['full_name']} ({user['role']})")
    with top[1]:
        st.markdown(f"**Date:** {utils.fmt_date(utils.today_iso())}")
    with top[2]:
        plan_label = status["plan"] or "—"
        st.markdown(f"**Plan:** {plan_label}")
    with top[3]:
        if status["status"] in ("ACTIVE_MONTHLY", "ACTIVE_YEARLY"):
            st.markdown(f"🟢 **{status['remaining_days']} day(s) remaining**")
        else:
            st.markdown("🔴 **Licence issue**")

    st.markdown("---")

    # Student KPIs
    sk = reports.student_kpis(inst)
    st.markdown("#### 👨‍🎓 Student KPIs")
    c = st.columns(4)
    with c[0]: kpi_card("Total Students", sk["total"], "👥", "kpi-blue")
    with c[1]: kpi_card("Active Students", sk["active"], "✅", "kpi-blue")
    with c[2]: kpi_card("New Admissions (MTD)", sk["new_admissions"], "🆕", "kpi-blue")
    with c[3]: kpi_card("Inactive Students", sk["inactive"], "⛔", "kpi-blue")

    # Financial KPIs
    fk = reports.financial_kpis(inst)
    st.markdown("#### 💰 Financial KPIs")
    c = st.columns(4)
    with c[0]: kpi_card("Today's Collection", utils.fmt_currency(fk["today"]), "💵", "kpi-green")
    with c[1]: kpi_card("This Month", utils.fmt_currency(fk["month"]), "📈", "kpi-green")
    with c[2]: kpi_card("Total Collection", utils.fmt_currency(fk["total"]), "🏦", "kpi-green")
    with c[3]: kpi_card("Pending Fees", utils.fmt_currency(fk["pending"]), "⏳", "kpi-green")

    # Academic KPIs
    ak = reports.academic_kpis(inst)
    st.markdown("#### 📚 Academic KPIs")
    c = st.columns(4)
    with c[0]: kpi_card("Total Courses", ak["courses"], "📘", "kpi-purple")
    with c[1]: kpi_card("Total Batches", ak["batches"], "👥", "kpi-purple")
    with c[2]: kpi_card("Today's Classes", ak["today_classes"], "🗓️", "kpi-purple")
    with c[3]: kpi_card("Today's Attendance", ak["today_attendance"], "📝", "kpi-purple")

    # Test KPIs
    tk = reports.test_kpis(inst)
    st.markdown("#### 📋 Test KPIs")
    c = st.columns(3)
    with c[0]: kpi_card("Total Tests", tk["total_tests"], "📋", "kpi-purple")
    with c[1]: kpi_card("Upcoming Tests", tk["upcoming_tests"], "🗓️", "kpi-purple")
    with c[2]: kpi_card("Overall Average", f"{tk['overall_avg_pct']}%" if tk["overall_avg_pct"] is not None else "—", "📈", "kpi-purple")

    # Other KPIs
    bday_today = reports.birthdays_today(inst)
    bday_upcoming = reports.birthdays_upcoming(inst)
    low_att = reports.low_attendance_students(inst)
    pending_students = reports.pending_fee_students(inst)
    st.markdown("#### 🔔 Other KPIs")
    c = st.columns(4)
    with c[0]: kpi_card("Today's Birthdays", len(bday_today), "🎂", "kpi-orange")
    with c[1]: kpi_card("Upcoming Birthdays", len(bday_upcoming), "🎉", "kpi-orange")
    with c[2]: kpi_card("Low Attendance", len(low_att), "⚠️", "kpi-orange")
    with c[3]: kpi_card("Pending Fee Students", len(pending_students), "💳", "kpi-orange")

    st.markdown("---")
    st.markdown("#### 📊 Analytics")

    row1 = st.columns(2)
    with row1[0]:
        df = reports.monthly_collection_trend(inst)
        if not df.empty:
            fig = px.bar(df, x="month", y="total", title="Monthly Fee Collection",
                         color_discrete_sequence=["#2E7D32"])
            fig.update_layout(margin=dict(t=40, b=10, l=10, r=10), height=320)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No fee collection data yet.")

    with row1[1]:
        df = reports.admission_trend(inst)
        if not df.empty:
            fig = px.line(df, x="month", y="cnt", markers=True, title="Admission Trend",
                          color_discrete_sequence=["#1565C0"])
            fig.update_layout(margin=dict(t=40, b=10, l=10, r=10), height=320)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No admission data yet.")

    row2 = st.columns(2)
    with row2[0]:
        df = reports.attendance_trend(inst)
        if not df.empty:
            fig = px.line(df, x="date", y="pct", markers=True, title="Attendance Trend (%)",
                          color_discrete_sequence=["#6A1B9A"])
            fig.update_layout(margin=dict(t=40, b=10, l=10, r=10), height=320)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No attendance data yet.")

    with row2[1]:
        df = reports.course_wise_students(inst)
        if not df.empty and df["cnt"].sum() > 0:
            fig = px.pie(df, names="course_name", values="cnt", hole=0.45,
                        title="Course-wise Students")
            fig.update_layout(margin=dict(t=40, b=10, l=10, r=10), height=320)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No course enrolment data yet.")

    row3 = st.columns(2)
    with row3[0]:
        df = reports.batch_wise_students(inst)
        if not df.empty and df["cnt"].sum() > 0:
            fig = px.bar(df, x="batch_name", y="cnt", title="Batch-wise Students",
                         color_discrete_sequence=["#EF6C00"])
            fig.update_layout(margin=dict(t=40, b=10, l=10, r=10), height=320)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No batch data yet.")

    with row3[1]:
        df = reports.payment_mode_breakdown(inst)
        if not df.empty:
            fig = px.pie(df, names="mode", values="total", title="Payment Mode Breakdown")
            fig.update_layout(margin=dict(t=40, b=10, l=10, r=10), height=320)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No payment data yet.")

    df = reports.pending_fees_by_course(inst)
    if not df.empty and df["pending"].sum() > 0:
        fig = px.bar(df, x="course_name", y="pending", title="Pending Fees by Course",
                     color_discrete_sequence=["#C62828"])
        fig.update_layout(margin=dict(t=40, b=10, l=10, r=10), height=320)
        st.plotly_chart(fig, use_container_width=True)
