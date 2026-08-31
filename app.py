"""
app.py
SN COACHING MANAGEMENT SYSTEM
Powered by SN Softech Solutions

Main Streamlit entry point: routing, authentication screens, licence
gating and the sidebar navigation.
"""

import os

import streamlit as st

import database as db
import auth
import config
import license as lic
import utils
import whatsapp as wa
from logging_setup import log_error
from modules import (
    dashboard, students, courses, batches, admissions, attendance, fees,
    whatsapp_centre, birthdays, schedule, faculty, reports_page, users,
    settings, license_page, notifications, sample_data, tests, super_admin,
)

st.set_page_config(
    page_title="SN Coaching Management System",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

@st.cache_resource
def _run_startup_tasks():
    # These are one-time, process-wide setup (schema DDL, template/demo-
    # account backfills) - idempotent, but not free. Without caching,
    # Streamlit was re-running all three DB round trips on every single
    # rerun (i.e. every click/input from every user), which was both a
    # major source of the app's overall slowness and, on Postgres, put
    # enough load on the connection pool to occasionally hand out a
    # stale/dead connection and crash app boot.
    db.init_db()
    wa.ensure_default_templates_for_all_institutes()
    auth.ensure_demo_account()


_run_startup_tasks()


@st.cache_resource(ttl=3600)
def _run_demo_data_cleanup():
    # Re-checked at most once an hour (Streamlit re-runs this once the
    # cached value's TTL expires) rather than on every rerun. Looks up the
    # fixed demo institute itself rather than accepting one as an argument,
    # so this can never be pointed at a real customer's data by mistake -
    # see sample_data.clear_stale_real_data() for why this exists.
    demo_inst = db.query_one("SELECT institute_id FROM institutes WHERE is_demo=1 LIMIT 1")
    if demo_inst:
        sample_data.clear_stale_real_data(demo_inst["institute_id"])


_run_demo_data_cleanup()


def load_css():
    css_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "style.css")
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


load_css()


# =======================================================================
# AUTH SCREENS (Sign Up / Login)
# =======================================================================
def render_auth_screens():
    st.markdown(
        """
        <div style="text-align:center; padding: 20px 0 10px 0;">
            <h1 style="margin-bottom:0;">🎓 SN COACHING MANAGEMENT SYSTEM</h1>
            <p style="color:#666; margin-top:4px;">Powered by SN Softech Solutions</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _, center, _ = st.columns([1, 2, 1])
    with center:
        mode = st.radio("", ["Sign In", "Create New Account", "Super Admin"],
                        horizontal=True, label_visibility="collapsed")

        if mode == "Super Admin":
            super_admin.render()
            return

        if mode == "Sign In":
            with st.form("login_form", clear_on_submit=True):
                st.markdown("### Login")
                username = st.text_input("Username / Email")
                password = st.text_input("Password", type="password")
                c1, c2 = st.columns(2)
                submit = c1.form_submit_button("Sign In", use_container_width=True)
                c2.form_submit_button("Forgot Password", use_container_width=True, disabled=True)
            if submit:
                ok, msg = auth.login(username, password)
                if ok:
                    st.rerun()
                else:
                    utils.toast_error(msg)
            st.caption("Forgot Password is not available in this offline demo build — contact your "
                       "administrator or SN Softech Solutions support.")
            with st.expander("👀 Just want to explore? Try the demo account"):
                st.markdown(f"**Username:** `{config.DEMO_USERNAME}`  \n**Password:** `{config.DEMO_PASSWORD}`")
                st.caption("Pre-loaded with sample data. Password and account settings can't be changed on this account.")

        else:
            with st.form("signup_form"):
                st.markdown("### Create Account")
                c1, c2 = st.columns(2)
                with c1:
                    institute_name = st.text_input("Institute Name *")
                    owner_name = st.text_input("Owner Name *")
                    mobile = st.text_input("Mobile Number *")
                    whatsapp_num = st.text_input("WhatsApp Number")
                with c2:
                    email = st.text_input("Email")
                    username = st.text_input("Username *")
                    password = st.text_input("Password *", type="password")
                    confirm = st.text_input("Confirm Password *", type="password")

                st.markdown("---")
                st.markdown("##### Activate Licence (recommended — start using immediately)")
                st.caption("There is no free trial. Enter your Monthly or Yearly licence key now "
                           "to start right away, or leave blank and activate later from "
                           "Licence Management — the account stays locked until then.")
                lc1, lc2 = st.columns(2)
                with lc1:
                    licence_plan = st.selectbox("Plan", ["(activate later)", "MONTHLY", "YEARLY"])
                with lc2:
                    licence_key_input = st.text_input("Licence Key", placeholder="SNM-XXXX-XXXX-XXXX")

                gen_demo = st.checkbox("Populate with demo/sample data (recommended for evaluation)", value=True)
                submit = st.form_submit_button("Create Account", use_container_width=True)

            if submit:
                if password != confirm:
                    utils.toast_error("Passwords do not match.")
                elif len(password) < 6:
                    utils.toast_error("Password must be at least 6 characters.")
                elif not utils.is_valid_mobile(mobile):
                    utils.toast_error("Please enter a valid mobile number.")
                else:
                    ok, result = auth.create_account(
                        institute_name, owner_name, mobile, whatsapp_num, email, username, password)
                    if ok:
                        institute_id = result
                        if gen_demo:
                            sample_data.generate(institute_id)

                        if licence_plan != "(activate later)" and licence_key_input:
                            act_ok, act_result = lic.activate_licence(institute_id, licence_key_input, licence_plan)
                            if act_ok:
                                utils.toast_success(
                                    f"Account created and {licence_plan.title()} licence activated! "
                                    f"Your Institute ID is {institute_id} — please sign in.")
                            else:
                                utils.toast_error(
                                    f"Account created (Institute ID: {institute_id}), but the licence "
                                    f"key could not be activated: {act_result}. Please sign in and "
                                    f"activate from Licence Management.")
                        else:
                            utils.toast_success(
                                f"Account created! Your Institute ID is {institute_id}. "
                                f"Please sign in and activate a licence key to start using the software.")
                    else:
                        utils.toast_error(result)


# =======================================================================
# SIDEBAR / NAVIGATION
# =======================================================================
MENU = [
    ("dashboard", "🏠 Dashboard"),
    ("students", "👨‍🎓 Student Management"),
    ("courses", "📚 Course Management"),
    ("batches", "👥 Batch Management"),
    ("admissions", "📝 Admission"),
    ("attendance", "📅 Attendance"),
    ("tests", "📋 Test Management"),
    ("fees", "💰 Fees Management"),
    ("whatsapp", "📱 WhatsApp Centre"),
    ("birthdays", "🎂 Birthday Management"),
    ("schedule", "📆 Class Schedule"),
    ("faculty", "👨‍🏫 Faculty Management"),
    ("reports", "📊 Reports & Analytics"),
    ("kpi", "📈 KPI Report"),
    ("notifications", "🔔 Notifications"),
    ("users", "👥 User Management"),
    ("settings", "⚙️ Settings"),
    ("license", "🔐 My Subscription"),
]

PAGE_RENDERERS = {
    "dashboard": dashboard.render,
    "students": students.render,
    "courses": courses.render,
    "batches": batches.render,
    "admissions": admissions.render,
    "attendance": attendance.render,
    "tests": tests.render,
    "fees": fees.render,
    "whatsapp": whatsapp_centre.render,
    "birthdays": birthdays.render,
    "schedule": schedule.render,
    "faculty": faculty.render,
    "reports": reports_page.render,
    "kpi": reports_page.render_kpi_report,
    "notifications": notifications.render,
    "users": users.render,
    "settings": settings.render,
    "license": license_page.render,
}


def render_sidebar():
    user = auth.current_user()
    status = lic.get_status(user["institute_id"])

    st.sidebar.markdown(
        f"""<div class="sidebar-brand">🎓 SN COACHING MS</div>
            <div class="sidebar-sub">{user['institute_name']}<br/>{user['full_name']} · {user['role']}</div>""",
        unsafe_allow_html=True,
    )

    if status["status"] == "NOT_ACTIVATED":
        st.sidebar.error("🔒 Subscription Not Activated")
    elif status["status"] == "SUSPENDED":
        st.sidebar.error("🚫 Account Suspended")
    elif status["status"] == "EXPIRED":
        st.sidebar.error("🔒 Subscription Expired")
    elif status["status"] in ("ACTIVE_MONTHLY", "ACTIVE_YEARLY"):
        st.sidebar.success(f"{status['plan'].title()} Plan\n{status['remaining_days']} day(s) remaining")

    st.sidebar.markdown("---")

    locked = lic.is_locked(user["institute_id"])
    current_page = st.session_state.get("page", "dashboard")

    for key, label in MENU:
        if locked and key not in ("license", "settings"):
            continue
        if not locked and not auth.can_access(key) and key != "license":
            continue
        if st.sidebar.button(label, key=f"nav_{key}", use_container_width=True):
            st.session_state["page"] = key
            st.rerun()

    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 Logout", use_container_width=True):
        auth.logout()
        st.rerun()

    return current_page


# =======================================================================
# MAIN
# =======================================================================
def main():
    if not auth.is_logged_in():
        render_auth_screens()
        return

    user = auth.current_user()
    page = render_sidebar()

    if lic.is_locked(user["institute_id"]) and page not in ("license", "settings"):
        license_page.render_locked_screen()
        return

    if page == "license" and lic.is_locked(user["institute_id"]):
        license_page.render_locked_screen()
        return

    renderer = PAGE_RENDERERS.get(page, dashboard.render)

    if page != "license" and not auth.can_access(page):
        st.error("You do not have permission to access this section.")
        return

    try:
        renderer()
    except Exception as exc:  # pragma: no cover - defensive UI guard
        log_error("page_render_failed", exc, page=page, institute_id=user.get("institute_id"))
        st.error("Something went wrong loading this page. Please try again or contact support.")
        with st.expander("Technical details (for support)"):
            st.code(str(exc))


if __name__ == "__main__":
    main()
