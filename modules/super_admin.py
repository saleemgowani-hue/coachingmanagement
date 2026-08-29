"""
modules/super_admin.py
SN COACHING MANAGEMENT SYSTEM

Super Admin panel - lets SN Softech Solutions manage every customer
(tenant) from one place: view all institutes, activate/renew a
subscription directly, suspend/cancel/reactivate a customer, and see
basic usage per tenant.

Deliberately kept OUTSIDE the multi-tenant `users` table and the normal
customer login flow: it authenticates against config.SUPER_ADMIN_USERNAME
/ SUPER_ADMIN_PASSWORD only, so a bug or bypass in tenant-level role
checks can never grant cross-tenant admin access, and a compromised
customer account can never reach this panel.
"""

import pandas as pd
import streamlit as st

import config
import database as db
import license as lic
import utils
from logging_setup import log_event

SESSION_KEY = "super_admin_auth"


def is_authenticated() -> bool:
    return st.session_state.get(SESSION_KEY, False)


def render():
    if not is_authenticated():
        _render_login()
        return
    _render_panel()


def _render_login():
    st.markdown("## 🛡️ Super Admin Login")
    st.caption(f"For {config.COMPANY_NAME} staff only - manages every customer account. "
               "This is a separate login from customer accounts.")

    if not config.SUPER_ADMIN_PASSWORD:
        st.error("Super Admin access is not configured on this deployment. Set "
                 "SUPER_ADMIN_PASSWORD via environment variable or Streamlit secrets to enable it.")
        return

    with st.form("super_admin_login"):
        username = st.text_input("Admin Username")
        password = st.text_input("Admin Password", type="password")
        submit = st.form_submit_button("Sign In", use_container_width=True)

    if submit:
        if username == config.SUPER_ADMIN_USERNAME and password == config.SUPER_ADMIN_PASSWORD:
            st.session_state[SESSION_KEY] = True
            log_event("super_admin_login_success", username=username)
            st.rerun()
        else:
            log_event("super_admin_login_failed", attempted_username=username)
            utils.toast_error("Invalid Super Admin credentials.")


def _render_panel():
    st.markdown("## 🛡️ Super Admin Panel")
    st.caption(f"{config.COMPANY_NAME} — manage every customer tenant from here.")

    if st.button("🚪 Logout of Super Admin"):
        del st.session_state[SESSION_KEY]
        st.rerun()

    overview = lic.all_tenants_overview()
    df = pd.DataFrame(overview)

    st.markdown("---")
    st.markdown("### 📊 Overview")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Tenants", len(df))
    c2.metric("Active", int((df["status"].isin(["ACTIVE_MONTHLY", "ACTIVE_YEARLY"])).sum()) if not df.empty else 0)
    c3.metric("Expired / Not Activated", int((df["status"].isin(["EXPIRED", "NOT_ACTIVATED"])).sum()) if not df.empty else 0)
    c4.metric("Suspended", int(df["is_suspended"].sum()) if not df.empty else 0)

    st.markdown("---")
    st.markdown("### 👥 All Customers (Tenants)")
    if df.empty:
        st.info("No customer accounts yet.")
        return

    view = df[["institute_id", "institute_name", "owner_name", "mobile", "status",
               "plan", "expiry_date", "remaining_days", "student_count",
               "is_demo", "is_suspended", "created_at"]]
    st.dataframe(view, use_container_width=True, hide_index=True)
    st.download_button("⬇️ Export Customer List", utils.to_excel_bytes(view, "Customers"),
                       file_name="all_customers.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    st.markdown("---")
    st.markdown("### 🛠️ Manage a Customer")
    options = {f"{r['institute_name']} ({r['institute_id']}) - {r['status']}": r for r in overview}
    sel = st.selectbox("Select Customer", list(options.keys()))
    row = options[sel]
    inst_id = row["institute_id"]

    if row["is_demo"]:
        st.info("This is the fixed Demo tenant - its subscription is always active and cannot be changed here.")
        return

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"**Institute ID:** {inst_id}")
        st.markdown(f"**Owner:** {row['owner_name']}")
        st.markdown(f"**Mobile:** {row['mobile']}")
    with c2:
        st.markdown(f"**Status:** {row['status']}")
        st.markdown(f"**Plan:** {row['plan'] or '-'}")
        st.markdown(f"**Expiry:** {utils.fmt_date(row['expiry_date']) if row['expiry_date'] else '-'}")
    with c3:
        st.markdown(f"**Days Remaining:** {row['remaining_days']}")
        st.markdown(f"**Students:** {row['student_count']}")
        st.markdown(f"**Suspended:** {'Yes' if row['is_suspended'] else 'No'}")

    tabs = st.tabs(["✅ Activate / Renew / Change Plan", "🚫 Suspend / Cancel", "📈 Usage"])

    with tabs[0]:
        st.caption("Directly issues a subscription for this customer - no licence key needed "
                   "(this bypasses the customer-facing key system, for internal admin use).")
        plan = st.selectbox("Plan", ["MONTHLY", "YEARLY"], key=f"admin_plan_{inst_id}")
        if st.button("Activate / Renew Now", key=f"admin_activate_{inst_id}", use_container_width=True):
            ok, result = lic.admin_activate(inst_id, plan)
            if ok:
                log_event("admin_activated_subscription", institute_id=inst_id, plan=plan)
                utils.toast_success(f"{plan.title()} subscription activated for {row['institute_name']}.")
                st.rerun()
            else:
                utils.toast_error(result)

    with tabs[1]:
        if row["is_suspended"]:
            st.warning(f"Currently suspended. Reason: {row.get('suspension_reason') or '(none given)'}")
            if st.button("♻️ Reactivate Customer", key=f"reactivate_{inst_id}", use_container_width=True):
                lic.set_suspended(inst_id, False)
                log_event("admin_reactivated_customer", institute_id=inst_id)
                utils.toast_success("Customer reactivated.")
                st.rerun()
        else:
            reason = st.text_input("Reason (shown to the customer)", key=f"suspend_reason_{inst_id}")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("🚫 Suspend Customer", key=f"suspend_{inst_id}", use_container_width=True):
                    lic.set_suspended(inst_id, True, reason or "Suspended by admin")
                    log_event("admin_suspended_customer", institute_id=inst_id, reason=reason or "Suspended by admin")
                    utils.toast_success("Customer suspended.")
                    st.rerun()
            with c2:
                if st.button("❌ Cancel Customer", key=f"cancel_{inst_id}", use_container_width=True):
                    lic.set_suspended(inst_id, True, reason or "Subscription cancelled")
                    log_event("admin_cancelled_customer", institute_id=inst_id, reason=reason or "Subscription cancelled")
                    utils.toast_success("Customer cancelled. Their data is preserved and access is blocked.")
                    st.rerun()
        st.caption("Suspending or cancelling never deletes data - the customer's records stay "
                   "intact and become accessible again immediately upon reactivation.")

    with tabs[2]:
        import reports
        sk = reports.student_kpis(inst_id)
        fk = reports.financial_kpis(inst_id)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Students", sk["total"])
        c2.metric("Active Students", sk["active"])
        c3.metric("Total Collection", utils.fmt_currency(fk["total"]))
        c4.metric("Pending Fees", utils.fmt_currency(fk["pending"]))
