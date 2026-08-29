"""modules/license_page.py - My Subscription / Licence Management screen"""

import streamlit as st

import config
import license as lic
import auth
import utils
from auth import current_user


def render():
    user = current_user()
    inst = user["institute_id"]
    st.markdown("## 🔐 My Subscription")

    status = lic.get_status(inst)
    _status_banner(status)
    _expiry_warning(status)

    if auth.is_demo():
        st.info("🔒 This is the demo account — its subscription is permanently active for "
                "demonstration purposes and cannot be modified. Sign up for your own account "
                "to get a real Monthly or Yearly licence.")
        return

    if status["status"] == "SUSPENDED":
        st.error(f"This account has been suspended by {config.COMPANY_NAME}."
                 + (f" Reason: {status.get('suspension_reason')}" if status.get("suspension_reason") else "")
                 + f" Please contact support at {config.SUPPORT_EMAIL} or WhatsApp {config.SUPPORT_WHATSAPP}.")
        return

    available = lic.count_available_keys()
    total_available = available["MONTHLY"] + available["YEARLY"]
    if total_available > 0:
        st.caption(f"📋 {available['MONTHLY']} unused Monthly key(s) and "
                   f"{available['YEARLY']} unused Yearly key(s) currently loaded "
                   f"in this database and ready to activate.")
    else:
        st.warning("⚠️ No licence keys are currently loaded in this database. If you have a key "
                   "batch (e.g. from `license_keys_batch.json`), run **IMPORT_LICENSE_KEYS.bat** "
                   "first — a key that hasn't been imported here will always show as Invalid, "
                   "even if it's a genuine key from your Excel sheet.")

    st.markdown("---")
    st.markdown(f"### Renew / Activate Subscription")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"#### 📅 Monthly Plan — 30 Days")
        st.caption(f"{config.CURRENCY_SYMBOL}{config.MONTHLY_PRICE:,.0f} / month")
        key1 = st.text_input("Licence Key", key="monthly_key", placeholder="SNM-XXXX-XXXX-XXXX")
        if st.button("Activate Monthly Licence", use_container_width=True):
            _activate(inst, key1, "MONTHLY")
    with c2:
        st.markdown(f"#### 🗓️ Yearly Plan — 365 Days")
        st.caption(f"{config.CURRENCY_SYMBOL}{config.YEARLY_PRICE:,.0f} / year")
        key2 = st.text_input("Licence Key", key="yearly_key", placeholder="SNY-XXXX-XXXX-XXXX")
        if st.button("Activate Yearly Licence", use_container_width=True):
            _activate(inst, key2, "YEARLY")

    if user["role"] == "ADMIN":
        st.markdown("---")
        with st.expander("🛠️ Generate Demo Licence Key (for testing / demonstration only)"):
            st.caption("In production, licence keys would be issued by SN Softech Solutions after purchase.")
            plan = st.selectbox("Plan", ["MONTHLY", "YEARLY"])
            if st.button("Generate Key"):
                key = lic.generate_licence_key(plan)
                st.code(key)
                utils.toast_success("Demo licence key generated — copy it into the activation field above.")

    st.markdown("---")
    st.markdown("### 📞 Contact Support")
    st.markdown(f"**{config.COMPANY_NAME}**\n\nEmail: {config.SUPPORT_EMAIL}  \nWhatsApp: {config.SUPPORT_WHATSAPP}")


def _activate(inst, key, plan):
    if not key:
        utils.toast_error("Please enter a licence key.")
        return
    ok, result = lic.activate_licence(inst, key, plan)
    if ok:
        utils.toast_success(f"{plan.title()} licence activated successfully!")
        st.rerun()
    else:
        utils.toast_error(result)


def _status_banner(status):
    if status["status"] == "NOT_ACTIVATED":
        st.info("🔑 **SUBSCRIPTION NOT ACTIVATED** — enter a Monthly or Yearly licence key below to start using the software.")
    elif status["status"] == "ACTIVE_MONTHLY":
        st.success(f"🟢 **Plan:** MONTHLY &nbsp; | &nbsp; **Status:** ACTIVE\n\n"
                   f"Expiry: {utils.fmt_date(status['expiry_date'])} — "
                   f"**{status['remaining_days']} day(s) remaining.**")
    elif status["status"] == "ACTIVE_YEARLY":
        st.success(f"🟢 **Plan:** YEARLY &nbsp; | &nbsp; **Status:** ACTIVE\n\n"
                   f"Expiry: {utils.fmt_date(status['expiry_date'])} — "
                   f"**{status['remaining_days']} day(s) remaining.**")
    elif status["status"] == "EXPIRED":
        st.error("🔴 **SUBSCRIPTION EXPIRED** — please renew below to continue.")
    elif status["status"] == "SUSPENDED":
        st.error("🔴 **ACCOUNT SUSPENDED**")
    else:
        st.error("🔴 **No valid subscription found.**")


def _expiry_warning(status):
    """Shows a graduated warning as an active subscription approaches expiry,
    at the 30/15/7/3/1 day thresholds."""
    if status["status"] not in ("ACTIVE_MONTHLY", "ACTIVE_YEARLY"):
        return
    remaining = status["remaining_days"]
    thresholds = sorted(config.EXPIRY_WARNING_DAYS)
    if remaining > thresholds[-1]:
        return
    if remaining <= 1:
        st.error(f"⚠️ Your subscription expires in {remaining} day(s)! Renew now to avoid interruption.")
    elif remaining <= 3:
        st.warning(f"⚠️ Only {remaining} days remaining — renew soon to avoid any interruption.")
    elif remaining <= 7:
        st.warning(f"Your subscription expires in {remaining} days.")
    elif remaining <= 15:
        st.info(f"Your subscription expires in {remaining} days.")
    elif remaining <= 30:
        st.info(f"Heads up: your subscription expires in {remaining} days.")


def render_locked_screen():
    """Shown app-wide until a valid, non-suspended subscription is active -
    only subscription/settings/logout remain accessible."""
    status = lic.get_status(current_user()["institute_id"])
    if status["status"] == "SUSPENDED":
        st.markdown("# 🚫 ACCOUNT SUSPENDED")
        st.error(f"This account has been suspended. Please contact {config.COMPANY_NAME} support to resolve this.")
    elif status["status"] == "NOT_ACTIVATED":
        st.markdown("# 🔑 ACTIVATE YOUR SUBSCRIPTION TO GET STARTED")
        st.info("There is no free trial — please enter a Monthly or Yearly licence key below to "
                 "start using SN Coaching Management System. Your account and any data you've "
                 "already added are saved and waiting.")
    else:
        st.markdown("# 🔒 SUBSCRIPTION EXPIRED")
        st.error("Please renew your subscription to continue using SN Coaching Management System. "
                 "Your data is safe and will be fully restored once you renew.")
    render()
