"""
modules/sample_data.py
Optional demo data generator for demonstrations.

Every row this module inserts is also logged into `demo_data_log`
(table_name + record_id), so `clear_demo_data()` can remove exactly
those rows later - regardless of how much real data has been added
in the meantime - without ever touching genuine student/course/fee
records.
"""

import random
from datetime import date, timedelta

import database as db
import utils

FIRST_NAMES = ["Aarav", "Vivaan", "Aditya", "Ishaan", "Kabir", "Ananya", "Diya",
               "Myra", "Sara", "Anika", "Rohan", "Priya", "Sanya", "Karan", "Neha"]
LAST_NAMES = ["Sharma", "Verma", "Gupta", "Iyer", "Nair", "Reddy", "Singh",
              "Mehta", "Joshi", "Kapoor", "Das", "Chowdhury"]
COURSES = [("Abacus", "ABC", "6 months", 6000), ("Spoken English", "SPE", "3 months", 4000),
           ("Computer Basics", "COMP", "4 months", 5000), ("Coding for Kids", "CODE", "6 months", 8000),
           ("Competitive Exam Prep", "COMPX", "12 months", 15000)]

# Deletion order matters: children (tables that reference other tables via
# a foreign key) must be removed before the parents they point to.
CLEAR_ORDER = [
    ("fee_payments", "payment_id"),
    ("admissions", "admission_id"),
    ("attendance", "attendance_id"),
    ("test_results", "result_id"),
    ("students", "student_id"),
    ("tests", "test_id"),
    ("batches", "batch_id"),
    ("faculty", "faculty_id"),
    ("courses", "course_id"),
]


def _log(institute_id, table_name, record_id):
    db.execute(
        "INSERT INTO demo_data_log (institute_id, table_name, record_id) VALUES (?, ?, ?)",
        (institute_id, table_name, str(record_id)),
    )


def _unique_student_id(seq_start: int) -> str:
    """student_id is a global primary key across all institutes, so guard
    against collisions if demo data is generated more than once."""
    seq = seq_start
    while True:
        sid = f"DEMO{date.today().strftime('%y')}{seq:04d}"
        if not db.query_one("SELECT student_id FROM students WHERE student_id=?", (sid,)):
            return sid
        seq += 1


def has_demo_data(institute_id: str) -> int:
    """Returns the number of demo rows currently on file for this institute."""
    row = db.query_one(
        "SELECT COUNT(*) c FROM demo_data_log WHERE institute_id=?", (institute_id,))
    return row["c"] if row else 0


def generate(institute_id: str):
    course_ids = []
    for name, code, dur, fees in COURSES:
        cid = db.execute(
            "INSERT INTO courses (institute_id, course_name, course_code, duration, course_fees) VALUES (?,?,?,?,?)",
            (institute_id, name, code, dur, fees))
        course_ids.append(cid)
        _log(institute_id, "courses", cid)

    faculty_ids = []
    for i in range(4):
        fname = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        fid = db.execute(
            """INSERT INTO faculty (institute_id, faculty_name, mobile, whatsapp_number, subject, joining_date, salary)
               VALUES (?,?,?,?,?,?,?)""",
            (institute_id, fname, f"9{random.randint(100000000,999999999)}",
             f"9{random.randint(100000000,999999999)}", random.choice(["Maths", "English", "Computer", "Science"]),
             (date.today() - timedelta(days=random.randint(30, 800))).isoformat(), random.randint(15000, 35000)))
        faculty_ids.append(fid)
        _log(institute_id, "faculty", fid)

    batch_ids = []
    for i in range(6):
        bname = f"Batch {chr(65+i)}"
        bid = db.execute(
            """INSERT INTO batches (institute_id, batch_name, course_id, faculty_id, room, start_date,
               class_days, start_time, end_time, max_students)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (institute_id, bname, random.choice(course_ids), random.choice(faculty_ids),
             f"Room {i+1}", date.today().isoformat(), "Mon,Wed,Fri",
             f"{16+i}:00", f"{17+i}:00", 25))
        batch_ids.append(bid)
        _log(institute_id, "batches", bid)

    # A couple of tests per batch, so Test Management reports have data to show.
    SUBJECTS = ["Mathematics", "English", "Science", "Computer Science"]
    tests_by_batch = {bid: [] for bid in batch_ids}
    for bid in batch_ids:
        for t in range(2):
            subject = random.choice(SUBJECTS)
            test_type = random.choice(["Unit Test", "Monthly Test", "Mock Test"])
            test_date = (date.today() - timedelta(days=random.randint(1, 30))).isoformat()
            tid = db.execute(
                """INSERT INTO tests (institute_id, test_name, subject, course_id, batch_id,
                   test_date, max_marks, test_type)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (institute_id, f"{test_type} {t + 1}", subject,
                 db.query_one("SELECT course_id FROM batches WHERE batch_id=?", (bid,))["course_id"],
                 bid, test_date, 100, test_type))
            tests_by_batch[bid].append(tid)
            _log(institute_id, "tests", tid)

    for i in range(40):
        name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        sid = _unique_student_id(i + 1000)
        course_id = random.choice(course_ids)
        batch_id = random.choice(batch_ids)
        total = random.choice([4000, 5000, 6000, 8000, 15000])
        discount = random.choice([0, 0, 500, 1000])
        net = total - discount
        paid = round(net * random.choice([1.0, 0.7, 0.5, 0.3, 0]), 2)
        pending = round(net - paid, 2)
        status = "PAID" if pending == 0 else ("PARTIAL" if paid > 0 else "PENDING")
        admission_date = (date.today() - timedelta(days=random.randint(0, 200))).isoformat()
        dob = (date.today() - timedelta(days=random.randint(365*6, 365*17))).isoformat()

        db.execute(
            """INSERT INTO students (student_id, institute_id, student_name, father_name, gender, dob,
               student_mobile, parent_mobile, whatsapp_number, email, city, course_id, batch_id,
               admission_date, joining_date, total_fees, discount, net_fees, paid_fees, pending_fees,
               payment_status, status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (sid, institute_id, name, f"{random.choice(LAST_NAMES)} Sr.", random.choice(["Male", "Female"]),
             dob, f"9{random.randint(100000000,999999999)}", f"9{random.randint(100000000,999999999)}",
             f"9{random.randint(100000000,999999999)}", "", random.choice(["Mumbai", "Pune", "Delhi", "Bangalore"]),
             course_id, batch_id, admission_date, admission_date, total, discount, net, paid, pending,
             status, "ACTIVE"))
        _log(institute_id, "students", sid)

        if paid > 0:
            receipt = utils.generate_receipt_number(i + 1)
            pid = db.execute(
                """INSERT INTO fee_payments (institute_id, student_id, receipt_number, amount, payment_mode, payment_date)
                   VALUES (?,?,?,?,?,?)""",
                (institute_id, sid, receipt, paid, random.choice(["Cash", "UPI", "Bank Transfer"]), admission_date))
            _log(institute_id, "fee_payments", pid)

        aid = db.execute(
            """INSERT INTO admissions (institute_id, student_id, course_id, batch_id, admission_date,
               total_fees, discount, net_fees, initial_payment) VALUES (?,?,?,?,?,?,?,?,?)""",
            (institute_id, sid, course_id, batch_id, admission_date, total, discount, net, paid))
        _log(institute_id, "admissions", aid)

        for d in range(10):
            att_date = (date.today() - timedelta(days=d)).isoformat()
            st_status = random.choices(["PRESENT", "ABSENT", "LATE"], weights=[75, 15, 10])[0]
            try:
                att_id = db.execute(
                    """INSERT INTO attendance (institute_id, student_id, batch_id, course_id, att_date, status)
                       VALUES (?,?,?,?,?,?)""",
                    (institute_id, sid, batch_id, course_id, att_date, st_status))
                _log(institute_id, "attendance", att_id)
            except Exception:
                pass

        for tid in tests_by_batch.get(batch_id, []):
            marks = round(random.uniform(30, 100), 0)
            rid = db.execute(
                "INSERT INTO test_results (institute_id, test_id, student_id, marks_obtained) VALUES (?,?,?,?)",
                (institute_id, tid, sid, marks))
            _log(institute_id, "test_results", rid)

    return True


def clear_demo_data(institute_id: str) -> int:
    """Deletes every row this module has ever inserted for this institute,
    in a foreign-key-safe order, then clears the log itself. Returns the
    number of rows removed. Real data added by the institute is untouched."""
    removed = 0
    for table_name, pk_col in CLEAR_ORDER:
        rows = db.query_all(
            "SELECT record_id FROM demo_data_log WHERE institute_id=? AND table_name=?",
            (institute_id, table_name))
        for r in rows:
            db.execute(f"DELETE FROM {table_name} WHERE {pk_col} = ?", (r["record_id"],))
            removed += 1

    db.execute("DELETE FROM demo_data_log WHERE institute_id=?", (institute_id,))
    return removed
