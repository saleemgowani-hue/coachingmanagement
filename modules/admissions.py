"""modules/admissions.py - Admission workflow log & confirmation messages"""

import streamlit as st
import pandas as pd

import database as db
import utils
import whatsapp as wa
from auth import current_user


def render():
    user = current_user()
    inst = user["institute_id"]
    st.markdown("## 📝 Admission Management")
    st.caption("New admissions are created from **Student Management → Add Student**. "
               "This screen shows the admission log and lets you send confirmation messages.")

    rows = db.query_all(
        """SELECT ad.admission_id, ad.admission_date, s.student_id, s.student_name, s.whatsapp_number,
                  c.course_name, b.batch_name, ad.net_fees, ad.initial_payment
           FROM admissions ad
           JOIN students s ON s.student_id = ad.student_id
           LEFT JOIN courses c ON c.course_id = ad.course_id
           LEFT JOIN batches b ON b.batch_id = ad.batch_id
           WHERE ad.institute_id=? ORDER BY ad.admission_date DESC""",
        (inst,))

    if not rows:
        st.info("No admissions recorded yet.")
        return

    templates = {t["template_name"]: t["template_text"] for t in wa.get_templates(inst)}
    confirm_text = templates.get("Admission Confirmation", wa.DEFAULT_TEMPLATES["Admission Confirmation"])
    institute = db.query_one("SELECT institute_name FROM institutes WHERE institute_id=?", (inst,))
    inst_name = institute["institute_name"] if institute else ""

    for r in rows:
        with st.container():
            c1, c2, c3 = st.columns([3, 2, 1])
            with c1:
                st.markdown(f"**{r['student_name']}** ({r['student_id']}) — {r['course_name'] or '—'} / {r['batch_name'] or '—'}")
                st.caption(f"Admitted: {utils.fmt_date(r['admission_date'])} | Net Fees: {utils.fmt_currency(r['net_fees'])}")
            with c2:
                st.markdown(f"Initial Payment: {utils.fmt_currency(r['initial_payment'])}")
            with c3:
                msg = wa.fill_template(confirm_text, {
                    "PARENT_NAME": "Parent",
                    "STUDENT_NAME": r["student_name"],
                    "COURSE_NAME": r["course_name"] or "",
                    "BATCH_NAME": r["batch_name"] or "",
                    "INSTITUTE_NAME": inst_name,
                })
                link = wa.build_link(r["whatsapp_number"], msg)
                if link:
                    st.link_button("📱 Send Confirmation", link, use_container_width=True)
                else:
                    st.caption("No WhatsApp number")
            st.divider()

    df = pd.DataFrame(rows)
    st.download_button("⬇️ Export Admission Log", utils.to_excel_bytes(df, "Admissions"),
                       file_name="admissions_log.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
