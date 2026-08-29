"""modules/settings.py - Institute settings, account, backup/restore, system info"""

import os
from datetime import datetime

import streamlit as st

import database as db
import auth
import utils
from auth import current_user
from modules import sample_data

BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backups")
os.makedirs(BACKUP_DIR, exist_ok=True)

BACKUP_EXT = "json" if db.BACKEND == "postgres" else "db"


def render():
    user = current_user()
    inst = user["institute_id"]
    is_demo = auth.is_demo()
    st.markdown("## ⚙️ Settings")

    tabs = st.tabs(["🏢 Institute", "🔑 Account", "🧪 Demo Data", "💾 Backup & Restore", "ℹ️ Database Info"])

    with tabs[0]:
        row = db.query_one("SELECT * FROM institutes WHERE institute_id=?", (inst,))
        if is_demo:
            st.info("🔒 This is the demo account — institute settings cannot be changed here. "
                    "Sign up for your own account to customize these.")
            st.markdown(f"**Institute Name:** {row['institute_name']}")
            st.markdown(f"**Mobile:** {row['mobile'] or '-'}")
            st.markdown(f"**Email:** {row['email'] or '-'}")
        else:
            with st.form("institute_settings"):
                c1, c2 = st.columns(2)
                with c1:
                    name = st.text_input("Institute Name", value=row["institute_name"])
                    mobile = st.text_input("Mobile", value=row["mobile"] or "")
                    whatsapp_num = st.text_input("WhatsApp Number", value=row["whatsapp_number"] or "")
                    email = st.text_input("Email", value=row["email"] or "")
                    website = st.text_input("Website", value="")
                with c2:
                    address = st.text_area("Address", value=row["address"] or "")
                    gst = st.text_input("GST Number", value=row["gst_number"] or "")
                    currency = st.selectbox("Currency", ["INR", "USD", "EUR", "GBP"],
                                            index=["INR", "USD", "EUR", "GBP"].index(row["currency"] or "INR"))
                    date_format = st.selectbox("Date Format", ["DD-MM-YYYY", "MM-DD-YYYY", "YYYY-MM-DD"],
                                               index=["DD-MM-YYYY", "MM-DD-YYYY", "YYYY-MM-DD"].index(row["date_format"] or "DD-MM-YYYY"))
                footer = st.text_area("Receipt Footer", value=row["receipt_footer"] or "")
                terms = st.text_area("Terms & Conditions", value=row["terms_conditions"] or "")
                save = st.form_submit_button("💾 Save Settings", use_container_width=True)
            if save:
                db.execute(
                    """UPDATE institutes SET institute_name=?, mobile=?, whatsapp_number=?, email=?, address=?,
                       gst_number=?, currency=?, date_format=?, receipt_footer=?, terms_conditions=?
                       WHERE institute_id=?""",
                    (name, mobile, whatsapp_num, email, address, gst, currency, date_format, footer, terms, inst))
                utils.toast_success("Institute settings saved.")
                st.rerun()

    with tabs[1]:
        st.markdown("#### Account")
        st.markdown(f"**Username:** {user['username']}")
        st.markdown(f"**Full Name:** {user['full_name']}")
        st.markdown(f"**Role:** {user['role']}")

        st.markdown("---")
        st.markdown("#### Change Password")
        if is_demo:
            st.warning("🔒 Password changes are disabled for the demo account.")
        else:
            with st.form("change_password_form", clear_on_submit=True):
                current_pw = st.text_input("Current Password", type="password")
                new_pw = st.text_input("New Password", type="password")
                confirm_pw = st.text_input("Confirm New Password", type="password")
                submit = st.form_submit_button("🔑 Update Password", use_container_width=True)
            if submit:
                if new_pw != confirm_pw:
                    utils.toast_error("New passwords do not match.")
                else:
                    ok, msg = auth.change_password(user["user_id"], current_pw, new_pw)
                    if ok:
                        utils.toast_success(msg)
                    else:
                        utils.toast_error(msg)

    with tabs[2]:
        st.markdown("#### Demo / Sample Data")
        st.caption("Loads ~40 sample students with courses, batches, faculty, attendance and "
                   "payment history — useful for demos and training staff. Every demo row is "
                   "tracked, so it can be removed later without touching real student data.")

        demo_count = sample_data.has_demo_data(inst)

        if demo_count > 0:
            st.info(f"📦 Demo data is currently loaded — **{demo_count} tracked record(s)**.")
        else:
            st.caption("No demo data is currently loaded for this institute.")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("📦 Load Demo Data", use_container_width=True, disabled=demo_count > 0):
                with st.spinner("Generating sample students, courses, batches, faculty..."):
                    sample_data.generate(inst)
                utils.toast_success("Demo data loaded.")
                st.rerun()
            if demo_count > 0:
                st.caption("Already loaded — clear it first to reload fresh demo data.")

        with c2:
            st.warning("Removes only demo rows — your real data is not touched.")
            if demo_count > 0 and utils.confirm_action(
                    "confirm_clear_demo", "I understand, remove all demo data"):
                if st.button("🗑️ Clear Demo Data", use_container_width=True):
                    removed = sample_data.clear_demo_data(inst)
                    utils.toast_success(f"Removed {removed} demo record(s).")
                    st.rerun()

    with tabs[3]:
        st.markdown("#### Database Backup")
        if db.BACKEND == "postgres":
            st.caption("Online (PostgreSQL) mode: backup exports every table to a portable JSON file.")
        if st.button("📦 Create Backup Now"):
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(BACKUP_DIR, f"backup_{inst}_{ts}.{BACKUP_EXT}")
            db.backup_database(path)
            utils.toast_success(f"Backup created: {os.path.basename(path)}")
            with open(path, "rb") as f:
                st.download_button("⬇️ Download Backup", f.read(), file_name=os.path.basename(path))

        st.markdown("---")
        st.markdown("#### Restore Database")
        st.warning("Restoring will replace ALL current data with the uploaded backup. This cannot be undone.")
        uploaded = st.file_uploader(f"Upload a .{BACKUP_EXT} backup file", type=[BACKUP_EXT])
        if uploaded and utils.confirm_action("confirm_restore", "I understand this will overwrite all current data"):
            if st.button("♻️ Restore Now"):
                temp_path = os.path.join(BACKUP_DIR, f"restore_temp.{BACKUP_EXT}")
                with open(temp_path, "wb") as f:
                    f.write(uploaded.getbuffer())
                db.restore_database(temp_path)
                utils.toast_success("Database restored. Please refresh the app.")

    with tabs[4]:
        info = db.db_info()
        st.markdown(f"**Database Backend:** {db.BACKEND.upper()}")
        st.markdown(f"**Database Path:** `{info['path']}`")
        st.markdown(f"**Database Size:** {info['size_bytes'] / 1024:.1f} KB")
        st.markdown(f"**Tables:** {', '.join(info['tables'])}")
