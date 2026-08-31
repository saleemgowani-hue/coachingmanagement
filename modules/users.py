"""modules/users.py - User Management (ADMIN only)"""

import streamlit as st
import pandas as pd

import database as db
import utils
import auth
from auth import current_user, hash_password


def render():
    user = current_user()
    inst = user["institute_id"]
    is_demo = auth.is_demo()
    st.markdown("## 👥 User Management")

    if user["role"] != "ADMIN":
        st.warning("Only Admin users can manage staff accounts.")
        return

    tabs = st.tabs(["📋 All Users", "➕ Add User"])

    with tabs[0]:
        df = pd.DataFrame(db.query_all(
            "SELECT user_id, username, full_name, role, status FROM users WHERE institute_id=? ORDER BY user_id",
            (inst,)))
        st.dataframe(df, use_container_width=True, hide_index=True)

        if is_demo:
            st.info("🔒 This is the demo account — adding staff users or changing roles is disabled "
                    "here, since it's a single account shared by everyone exploring the demo. "
                    "Sign up for your own account to manage staff.")
        else:
            st.markdown("#### Update Role / Status")
            editable = df[df["username"] != user["username"]]
            if editable.empty:
                st.caption("No other users to manage yet.")
            else:
                sel = st.selectbox("Select user", editable["username"].tolist())
                row = editable[editable["username"] == sel].iloc[0]
                with st.form("edit_user"):
                    role = st.selectbox("Role", ["ADMIN", "MANAGER", "STAFF"],
                                        index=["ADMIN", "MANAGER", "STAFF"].index(row["role"]))
                    status = st.selectbox("Status", ["ACTIVE", "DISABLED"],
                                          index=0 if row["status"] == "ACTIVE" else 1)
                    save = st.form_submit_button("💾 Update")
                if save:
                    db.execute("UPDATE users SET role=?, status=? WHERE user_id=? AND institute_id=?",
                              (role, status, int(row["user_id"]), inst))
                    utils.toast_success("User updated.")
                    st.rerun()

    with tabs[1]:
        if is_demo:
            st.info("🔒 This is the demo account — creating new staff users is disabled here. "
                    "Sign up for your own account to add staff.")
            return
        with st.form("add_user", clear_on_submit=True):
            full_name = st.text_input("Full Name *")
            username = st.text_input("Username *")
            email = st.text_input("Email")
            role = st.selectbox("Role", ["MANAGER", "STAFF"])
            password = st.text_input("Temporary Password *", type="password")
            submit = st.form_submit_button("💾 Create User", use_container_width=True)
        if submit:
            if not all([full_name, username, password]):
                utils.toast_error("Full Name, Username and Password are required.")
            elif db.query_one("SELECT user_id FROM users WHERE username=?", (username,)):
                utils.toast_error("Username already taken.")
            else:
                db.execute(
                    """INSERT INTO users (institute_id, username, email, password_hash, full_name, role)
                       VALUES (?,?,?,?,?,?)""",
                    (inst, username, email, hash_password(password), full_name, role))
                utils.toast_success(f"User '{username}' created with role {role}.")
                st.rerun()
