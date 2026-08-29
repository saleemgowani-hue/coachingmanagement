"""modules/fees.py - Fees Management, collection and pending-fee follow-up"""

from datetime import date

import streamlit as st
import pandas as pd

import database as db
import utils
import whatsapp as wa
from auth import current_user


def render():
    user = current_user()
    inst = user["institute_id"]
    st.markdown("## 💰 Fees Management")

    tabs = st.tabs(["💵 Collect Fees", "⏳ Pending Fees", "📜 Payment History", "📈 Collection Summary"])

    # ---------------- Collect Fees ----------------
    with tabs[0]:
        students = db.query_all(
            "SELECT student_id, student_name, pending_fees FROM students WHERE institute_id=? AND status='ACTIVE' ORDER BY student_name",
            (inst,))
        options = {f"{s['student_name']} ({s['student_id']}) — Pending: {utils.fmt_currency(s['pending_fees'])}": s["student_id"] for s in students}
        if not options:
            st.info("No active students found.")
        else:
            sel = st.selectbox("Select Student", list(options.keys()))
            student_id = options[sel]
            s = db.query_one("SELECT * FROM students WHERE student_id=?", (student_id,))
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Fees", utils.fmt_currency(s["net_fees"]))
            c2.metric("Paid So Far", utils.fmt_currency(s["paid_fees"]))
            c3.metric("Pending", utils.fmt_currency(s["pending_fees"]))

            with st.form("collect_fee"):
                amount = st.number_input("Amount to Collect", min_value=0.0, step=100.0, max_value=float(s["pending_fees"] or 0) or None)
                mode = st.selectbox("Payment Mode", ["Cash", "UPI", "Bank Transfer", "Other"])
                pay_date = st.date_input("Payment Date", value=date.today())
                notes = st.text_input("Notes")
                submit = st.form_submit_button("💾 Record Payment", use_container_width=True)
            if submit:
                if amount <= 0:
                    utils.toast_error("Enter a valid amount.")
                else:
                    row_count = db.query_one("SELECT COUNT(*) c FROM fee_payments WHERE institute_id=?", (inst,))["c"]
                    receipt = utils.generate_receipt_number(row_count + 1)
                    db.execute(
                        """INSERT INTO fee_payments (institute_id, student_id, receipt_number, amount, payment_mode, payment_date, notes)
                           VALUES (?,?,?,?,?,?,?)""",
                        (inst, student_id, receipt, amount, mode, pay_date.isoformat(), notes))
                    new_paid = (s["paid_fees"] or 0) + amount
                    new_pending = max((s["net_fees"] or 0) - new_paid, 0)
                    pay_status = "PAID" if new_pending == 0 else "PARTIAL"
                    db.execute(
                        "UPDATE students SET paid_fees=?, pending_fees=?, payment_status=? WHERE student_id=?",
                        (new_paid, new_pending, pay_status, student_id))
                    utils.toast_success(f"Payment recorded. Receipt #{receipt}")
                    _receipt_view(inst, s, amount, mode, pay_date, receipt, new_paid, new_pending)

    # ---------------- Pending Fees ----------------
    with tabs[1]:
        rows = db.query_all(
            """SELECT s.student_id, s.student_name, s.father_name AS parent_name, s.whatsapp_number,
                      s.net_fees, s.paid_fees, s.pending_fees
               FROM students s WHERE s.institute_id=? AND s.pending_fees > 0 ORDER BY s.pending_fees DESC""",
            (inst,))
        if not rows:
            st.success("No pending fees. All students are up to date! 🎉")
        else:
            templates = {t["template_name"]: t["template_text"] for t in wa.get_templates(inst)}
            reminder_text = templates.get("Fee Reminder", wa.DEFAULT_TEMPLATES["Fee Reminder"])
            institute = db.query_one("SELECT institute_name FROM institutes WHERE institute_id=?", (inst,))
            inst_name = institute["institute_name"] if institute else ""

            for r in rows:
                with st.container():
                    c1, c2, c3 = st.columns([3, 2, 1])
                    with c1:
                        st.markdown(f"**{r['student_name']}** ({r['student_id']})")
                        st.caption(f"Pending: {utils.fmt_currency(r['pending_fees'])}")
                    with c2:
                        st.markdown(f"WhatsApp: {r['whatsapp_number'] or '—'}")
                    with c3:
                        msg = wa.fill_template(reminder_text, {
                            "STUDENT_NAME": r["student_name"],
                            "PENDING_AMOUNT": f"{r['pending_fees']:.2f}",
                            "INSTITUTE_NAME": inst_name,
                        })
                        link = wa.build_link(r["whatsapp_number"], msg)
                        if link:
                            st.link_button("📱 Send Reminder", link, use_container_width=True)
                        else:
                            st.caption("No WhatsApp number")
                    st.divider()

            df = pd.DataFrame(rows)
            st.download_button("⬇️ Export Pending Fees", utils.to_excel_bytes(df, "Pending Fees"),
                               file_name="pending_fees.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # ---------------- Payment History ----------------
    with tabs[2]:
        df = pd.DataFrame(db.query_all(
            """SELECT fp.payment_date, fp.receipt_number, s.student_name, fp.amount, fp.payment_mode
               FROM fee_payments fp JOIN students s ON s.student_id=fp.student_id
               WHERE fp.institute_id=? ORDER BY fp.payment_date DESC""",
            (inst,)))
        if df.empty:
            st.info("No payments recorded yet.")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.download_button("⬇️ Export Excel", utils.to_excel_bytes(df, "Payments"),
                               file_name="payment_history.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # ---------------- Collection Summary ----------------
    with tabs[3]:
        by_course = pd.DataFrame(db.query_all(
            """SELECT c.course_name, COALESCE(SUM(fp.amount),0) collected
               FROM fee_payments fp
               JOIN students s ON s.student_id = fp.student_id
               LEFT JOIN courses c ON c.course_id = s.course_id
               WHERE fp.institute_id=? GROUP BY c.course_id""", (inst,)))
        by_batch = pd.DataFrame(db.query_all(
            """SELECT b.batch_name, COALESCE(SUM(fp.amount),0) collected
               FROM fee_payments fp
               JOIN students s ON s.student_id = fp.student_id
               LEFT JOIN batches b ON b.batch_id = s.batch_id
               WHERE fp.institute_id=? GROUP BY b.batch_id""", (inst,)))
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### Course-wise Collection")
            st.dataframe(by_course, use_container_width=True, hide_index=True)
        with c2:
            st.markdown("#### Batch-wise Collection")
            st.dataframe(by_batch, use_container_width=True, hide_index=True)


def _receipt_view(inst, s, amount, mode, pay_date, receipt, new_paid, new_pending):
    institute = db.query_one("SELECT * FROM institutes WHERE institute_id=?", (inst,))
    st.markdown("---")
    st.markdown("### 🧾 Fee Receipt")
    st.markdown(
        f"""
        <div class="receipt-box">
            <h3>{institute['institute_name']}</h3>
            <p>{institute['address'] or ''}</p>
            <hr/>
            <p><b>Receipt No:</b> {receipt} &nbsp;&nbsp; <b>Date:</b> {utils.fmt_date(pay_date)}</p>
            <p><b>Student:</b> {s['student_name']} ({s['student_id']})</p>
            <p><b>Amount Paid:</b> {utils.fmt_currency(amount)} via {mode}</p>
            <p><b>Total Paid Till Date:</b> {utils.fmt_currency(new_paid)}</p>
            <p><b>Pending Balance:</b> {utils.fmt_currency(new_pending)}</p>
            <hr/>
            <p style="text-align:right;">Authorized Signature</p>
            <p style="text-align:center; font-size:0.85em; color:#888;">{institute.get('receipt_footer') or 'Thank you!'}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("Use your browser's print function (Ctrl+P) to print this receipt.")
