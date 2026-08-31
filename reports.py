"""
reports.py
SN COACHING MANAGEMENT SYSTEM
Report queries, KPI aggregation and DataFrame builders for Reports Hub
and the Dashboard. All queries are scoped to a single institute_id.
"""

from datetime import datetime, timedelta, date

import pandas as pd

import database as db


# ---------------------------------------------------------------------
# Core KPIs
# ---------------------------------------------------------------------
def student_kpis(inst):
    total = db.query_one("SELECT COUNT(*) c FROM students WHERE institute_id=?", (inst,))["c"]
    active = db.query_one("SELECT COUNT(*) c FROM students WHERE institute_id=? AND status='ACTIVE'", (inst,))["c"]
    inactive = total - active
    month_start = date.today().replace(day=1).isoformat()
    new_adm = db.query_one(
        "SELECT COUNT(*) c FROM students WHERE institute_id=? AND admission_date >= ?",
        (inst, month_start))["c"]
    return {"total": total, "active": active, "inactive": inactive, "new_admissions": new_adm}


def financial_kpis(inst):
    today = date.today().isoformat()
    month_start = date.today().replace(day=1).isoformat()

    today_coll = db.query_one(
        "SELECT COALESCE(SUM(amount),0) s FROM fee_payments WHERE institute_id=? AND payment_date=?",
        (inst, today))["s"]
    month_coll = db.query_one(
        "SELECT COALESCE(SUM(amount),0) s FROM fee_payments WHERE institute_id=? AND payment_date>=?",
        (inst, month_start))["s"]
    total_coll = db.query_one(
        "SELECT COALESCE(SUM(amount),0) s FROM fee_payments WHERE institute_id=?", (inst,))["s"]
    pending = db.query_one(
        "SELECT COALESCE(SUM(pending_fees),0) s FROM students WHERE institute_id=?", (inst,))["s"]

    return {"today": today_coll, "month": month_coll, "total": total_coll, "pending": pending}


def academic_kpis(inst):
    courses = db.query_one("SELECT COUNT(*) c FROM courses WHERE institute_id=?", (inst,))["c"]
    batches = db.query_one("SELECT COUNT(*) c FROM batches WHERE institute_id=?", (inst,))["c"]
    today = date.today().isoformat()
    today_classes = db.query_one(
        "SELECT COUNT(*) c FROM class_schedule WHERE institute_id=? AND class_date=?", (inst, today))["c"]
    today_att = db.query_one(
        "SELECT COUNT(*) c FROM attendance WHERE institute_id=? AND att_date=?", (inst, today))["c"]
    return {"courses": courses, "batches": batches, "today_classes": today_classes, "today_attendance": today_att}


def birthdays_today(inst):
    today_md = date.today().strftime("%m-%d")
    rows = db.query_all(
        "SELECT * FROM students WHERE institute_id=? AND status='ACTIVE' AND dob IS NOT NULL", (inst,))
    return [r for r in rows if r["dob"] and r["dob"][5:7] + "-" + r["dob"][8:10] == today_md]


def birthdays_upcoming(inst, days=7):
    rows = db.query_all(
        "SELECT * FROM students WHERE institute_id=? AND status='ACTIVE' AND dob IS NOT NULL", (inst,))
    today = date.today()
    upcoming = []
    for r in rows:
        try:
            dob = datetime.strptime(r["dob"][:10], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            continue
        next_bday = dob.replace(year=today.year)
        if next_bday < today:
            next_bday = dob.replace(year=today.year + 1)
        delta = (next_bday - today).days
        if 0 < delta <= days:
            r = dict(r)
            r["days_away"] = delta
            upcoming.append(r)
    return sorted(upcoming, key=lambda x: x["days_away"])


def low_attendance_students(inst, threshold_pct=75, days=30):
    # A single aggregated query instead of two SELECTs per active student -
    # the previous per-student loop meant a coaching centre with hundreds of
    # students issued hundreds of extra round trips just to render the
    # dashboard, which is especially costly against a networked Postgres host.
    since = (date.today() - timedelta(days=days)).isoformat()
    rows = db.query_all(
        """SELECT s.*,
                  COUNT(a.attendance_id) AS total_marked,
                  SUM(CASE WHEN a.status IN ('PRESENT','LATE') THEN 1 ELSE 0 END) AS present_count
           FROM students s
           JOIN attendance a ON a.student_id = s.student_id AND a.att_date >= ?
           WHERE s.institute_id=? AND s.status='ACTIVE'
           GROUP BY s.student_id""",
        (since, inst))
    result = []
    for r in rows:
        total = r["total_marked"]
        present = r["present_count"] or 0
        pct = round((present / total) * 100, 1)
        if pct < threshold_pct:
            row = dict(r)
            row.pop("total_marked", None)
            row.pop("present_count", None)
            row["attendance_pct"] = pct
            result.append(row)
    return sorted(result, key=lambda x: x["attendance_pct"])


def pending_fee_students(inst):
    return db.query_all(
        "SELECT * FROM students WHERE institute_id=? AND pending_fees > 0 ORDER BY pending_fees DESC",
        (inst,))


# ---------------------------------------------------------------------
# Chart data
# ---------------------------------------------------------------------
def monthly_collection_trend(inst, months=6):
    rows = db.query_all(
        """SELECT SUBSTR(payment_date, 1, 7) ym, SUM(amount) total
           FROM fee_payments WHERE institute_id=? GROUP BY ym ORDER BY ym""",
        (inst,))
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame({"month": [], "total": []})
    df = df.tail(months)
    df.columns = ["month", "total"]
    return df


def admission_trend(inst, months=6):
    rows = db.query_all(
        """SELECT SUBSTR(admission_date, 1, 7) ym, COUNT(*) cnt
           FROM students WHERE institute_id=? AND admission_date IS NOT NULL
           GROUP BY ym ORDER BY ym""",
        (inst,))
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame({"month": [], "cnt": []})
    df = df.tail(months)
    df.columns = ["month", "cnt"]
    return df


def attendance_trend(inst, days=14):
    since = (date.today() - timedelta(days=days)).isoformat()
    rows = db.query_all(
        """SELECT att_date,
                  SUM(CASE WHEN status IN ('PRESENT','LATE') THEN 1 ELSE 0 END) present,
                  COUNT(*) total
           FROM attendance WHERE institute_id=? AND att_date>=?
           GROUP BY att_date ORDER BY att_date""",
        (inst, since))
    if not rows:
        return pd.DataFrame({"date": [], "pct": []})
    df = pd.DataFrame(rows)
    df["pct"] = (df["present"] / df["total"] * 100).round(1)
    return df[["att_date", "pct"]].rename(columns={"att_date": "date"})


def course_wise_students(inst):
    rows = db.query_all(
        """SELECT c.course_name, COUNT(s.student_id) cnt
           FROM courses c LEFT JOIN students s
             ON s.course_id = c.course_id AND s.institute_id = c.institute_id AND s.status='ACTIVE'
           WHERE c.institute_id=? GROUP BY c.course_id""",
        (inst,))
    return pd.DataFrame(rows)


def batch_wise_students(inst):
    rows = db.query_all(
        """SELECT b.batch_name, COUNT(s.student_id) cnt
           FROM batches b LEFT JOIN students s
             ON s.batch_id = b.batch_id AND s.institute_id = b.institute_id AND s.status='ACTIVE'
           WHERE b.institute_id=? GROUP BY b.batch_id""",
        (inst,))
    return pd.DataFrame(rows)


def payment_mode_breakdown(inst):
    rows = db.query_all(
        """SELECT COALESCE(payment_mode,'Other') mode, SUM(amount) total
           FROM fee_payments WHERE institute_id=? GROUP BY mode""",
        (inst,))
    return pd.DataFrame(rows)


def pending_fees_by_course(inst):
    rows = db.query_all(
        """SELECT c.course_name, COALESCE(SUM(s.pending_fees),0) pending
           FROM courses c LEFT JOIN students s
             ON s.course_id=c.course_id AND s.institute_id=c.institute_id
           WHERE c.institute_id=? GROUP BY c.course_id""",
        (inst,))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------
# Report table builders (used by Reports Hub)
# ---------------------------------------------------------------------
def report_students(inst):
    rows = db.query_all(
        """SELECT s.student_id, s.student_name, s.father_name, s.gender, s.student_mobile,
                  s.parent_mobile, c.course_name, b.batch_name, s.admission_date,
                  s.total_fees, s.paid_fees, s.pending_fees, s.status
           FROM students s
           LEFT JOIN courses c ON c.course_id=s.course_id
           LEFT JOIN batches b ON b.batch_id=s.batch_id
           WHERE s.institute_id=? ORDER BY s.admission_date DESC""",
        (inst,))
    return pd.DataFrame(rows)


def report_fee_collection(inst, start=None, end=None):
    sql = """SELECT fp.payment_date, fp.receipt_number, s.student_name, fp.amount,
                     fp.payment_mode, fp.notes
              FROM fee_payments fp JOIN students s ON s.student_id = fp.student_id
              WHERE fp.institute_id=?"""
    params = [inst]
    if start:
        sql += " AND fp.payment_date >= ?"
        params.append(start)
    if end:
        sql += " AND fp.payment_date <= ?"
        params.append(end)
    sql += " ORDER BY fp.payment_date DESC"
    return pd.DataFrame(db.query_all(sql, tuple(params)))


def report_pending_fees(inst):
    return pd.DataFrame(pending_fee_students(inst))


def report_attendance(inst, start=None, end=None):
    sql = """SELECT a.att_date, s.student_name, c.course_name, b.batch_name, a.status
              FROM attendance a
              JOIN students s ON s.student_id = a.student_id
              LEFT JOIN courses c ON c.course_id = a.course_id
              LEFT JOIN batches b ON b.batch_id = a.batch_id
              WHERE a.institute_id=?"""
    params = [inst]
    if start:
        sql += " AND a.att_date >= ?"
        params.append(start)
    if end:
        sql += " AND a.att_date <= ?"
        params.append(end)
    sql += " ORDER BY a.att_date DESC"
    return pd.DataFrame(db.query_all(sql, tuple(params)))


def report_courses(inst):
    return pd.DataFrame(db.query_all("SELECT * FROM courses WHERE institute_id=?", (inst,)))


def report_batches(inst):
    rows = db.query_all(
        """SELECT b.batch_name, c.course_name, f.faculty_name, b.room, b.start_time,
                  b.end_time, b.max_students, b.status
           FROM batches b
           LEFT JOIN courses c ON c.course_id=b.course_id
           LEFT JOIN faculty f ON f.faculty_id=b.faculty_id
           WHERE b.institute_id=?""",
        (inst,))
    return pd.DataFrame(rows)


def report_faculty(inst):
    return pd.DataFrame(db.query_all("SELECT * FROM faculty WHERE institute_id=?", (inst,)))


def report_admissions(inst, start=None, end=None):
    sql = """SELECT ad.admission_date, s.student_name, c.course_name, b.batch_name,
                     ad.net_fees, ad.initial_payment
              FROM admissions ad
              JOIN students s ON s.student_id = ad.student_id
              LEFT JOIN courses c ON c.course_id = ad.course_id
              LEFT JOIN batches b ON b.batch_id = ad.batch_id
              WHERE ad.institute_id=?"""
    params = [inst]
    if start:
        sql += " AND ad.admission_date >= ?"
        params.append(start)
    if end:
        sql += " AND ad.admission_date <= ?"
        params.append(end)
    sql += " ORDER BY ad.admission_date DESC"
    return pd.DataFrame(db.query_all(sql, tuple(params)))


def report_payment_mode(inst):
    return payment_mode_breakdown(inst)


def report_birthdays(inst):
    rows = db.query_all(
        "SELECT student_name, dob, student_mobile, whatsapp_number FROM students WHERE institute_id=? AND dob IS NOT NULL",
        (inst,))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------
# Tests / Exams
# ---------------------------------------------------------------------
def test_kpis(inst):
    total_tests = db.query_one("SELECT COUNT(*) c FROM tests WHERE institute_id=?", (inst,))["c"]
    today = date.today().isoformat()
    upcoming = db.query_one(
        "SELECT COUNT(*) c FROM tests WHERE institute_id=? AND test_date >= ?", (inst, today))["c"]
    avg_row = db.query_one(
        """SELECT ROUND(CAST(AVG(r.marks_obtained * 100.0 / t.max_marks) AS NUMERIC), 1) avg_pct
           FROM test_results r JOIN tests t ON t.test_id = r.test_id
           WHERE t.institute_id=?""", (inst,))
    return {"total_tests": total_tests, "upcoming_tests": upcoming,
            "overall_avg_pct": avg_row["avg_pct"] if avg_row and avg_row["avg_pct"] is not None else None}


def report_tests(inst):
    rows = db.query_all(
        """SELECT t.test_id, t.test_name, t.subject, c.course_name, b.batch_name,
                  t.test_date, t.max_marks, t.test_type,
                  (SELECT COUNT(*) FROM test_results r WHERE r.test_id = t.test_id) AS results_entered,
                  (SELECT ROUND(CAST(AVG(r.marks_obtained * 100.0 / t.max_marks) AS NUMERIC), 1)
                     FROM test_results r WHERE r.test_id = t.test_id) AS avg_pct
           FROM tests t
           LEFT JOIN courses c ON c.course_id = t.course_id
           LEFT JOIN batches b ON b.batch_id = t.batch_id
           WHERE t.institute_id=? ORDER BY t.test_date DESC""",
        (inst,))
    return pd.DataFrame(rows)


def report_test_results(inst, start=None, end=None):
    sql = """SELECT t.test_date, t.test_name, t.subject, t.test_type, c.course_name, b.batch_name,
                     s.student_name, r.marks_obtained, t.max_marks,
                     ROUND(CAST(r.marks_obtained * 100.0 / t.max_marks AS NUMERIC), 1) AS percentage
              FROM test_results r
              JOIN tests t ON t.test_id = r.test_id
              JOIN students s ON s.student_id = r.student_id
              LEFT JOIN courses c ON c.course_id = t.course_id
              LEFT JOIN batches b ON b.batch_id = t.batch_id
              WHERE r.institute_id=?"""
    params = [inst]
    if start:
        sql += " AND t.test_date >= ?"
        params.append(start)
    if end:
        sql += " AND t.test_date <= ?"
        params.append(end)
    sql += " ORDER BY t.test_date DESC"
    return pd.DataFrame(db.query_all(sql, tuple(params)))


def batch_wise_test_performance(inst):
    rows = db.query_all(
        """SELECT b.batch_name,
                  COUNT(DISTINCT t.test_id) AS tests_count,
                  ROUND(CAST(AVG(r.marks_obtained * 100.0 / t.max_marks) AS NUMERIC), 1) AS avg_pct
           FROM batches b
           LEFT JOIN tests t ON t.batch_id = b.batch_id AND t.institute_id = b.institute_id
           LEFT JOIN test_results r ON r.test_id = t.test_id
           WHERE b.institute_id=?
           GROUP BY b.batch_id""",
        (inst,))
    return pd.DataFrame(rows)


def subject_wise_test_performance(inst):
    rows = db.query_all(
        """SELECT t.subject,
                  COUNT(DISTINCT t.test_id) AS tests_count,
                  ROUND(CAST(AVG(r.marks_obtained * 100.0 / t.max_marks) AS NUMERIC), 1) AS avg_pct
           FROM tests t
           LEFT JOIN test_results r ON r.test_id = t.test_id
           WHERE t.institute_id=? AND t.subject IS NOT NULL AND t.subject != ''
           GROUP BY t.subject""",
        (inst,))
    return pd.DataFrame(rows)


def top_bottom_performers(inst, n=5):
    rows = db.query_all(
        """SELECT s.student_name, b.batch_name,
                  ROUND(CAST(AVG(r.marks_obtained * 100.0 / t.max_marks) AS NUMERIC), 1) AS avg_pct,
                  COUNT(r.result_id) AS tests_taken
           FROM test_results r
           JOIN tests t ON t.test_id = r.test_id
           JOIN students s ON s.student_id = r.student_id
           LEFT JOIN batches b ON b.batch_id = s.batch_id
           WHERE r.institute_id=?
           GROUP BY s.student_id
           HAVING tests_taken > 0""",
        (inst,))
    df = pd.DataFrame(rows)
    if df.empty:
        return df, df
    df_sorted = df.sort_values("avg_pct", ascending=False)
    return df_sorted.head(n), df_sorted.tail(n).sort_values("avg_pct")
