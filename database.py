"""
database.py
SN COACHING MANAGEMENT SYSTEM

Dual-backend data layer:
- SQLite  (config.DB_BACKEND == "sqlite", the default - offline/local use)
- PostgreSQL (config.DB_BACKEND == "postgres" - online multi-tenant SaaS,
  connection string from config.DATABASE_URL / DATABASE_URL env var /
  Streamlit secrets)

Every other file in this project (all of modules/*.py, reports.py,
whatsapp.py, auth.py, license.py) talks to the database ONLY through
query_all() / query_one() / execute() / executemany() below, using "?"
placeholders exactly as SQLite expects. That is deliberate: it means the
~100 existing queries across the whole codebase never had to change to
support Postgres - this module translates "?" to psycopg2's "%s" style
under the hood when running against Postgres, so business logic written
once keeps working unchanged on both backends.

Multi-tenancy note: every business table already carries institute_id
(the tenant column). Every query in this codebase filters by it, and it
is always read from the authenticated session (auth.current_user()) -
never taken from user-editable input - so one tenant can never fetch or
write another tenant's rows by tampering with a form field or URL.
"""

import os
import json
import decimal
from contextlib import contextmanager

import config

DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DB_PATH = os.path.join(DB_DIR, "sn_coaching.db")
os.makedirs(DB_DIR, exist_ok=True)

BACKEND = config.DB_BACKEND  # "sqlite" or "postgres"

if BACKEND == "postgres":
    try:
        import psycopg2
        import psycopg2.extras
        import psycopg2.pool
    except ImportError as exc:
        raise ImportError(
            "DB_BACKEND is set to 'postgres' but the 'psycopg2-binary' package "
            "is not installed in this environment. On Streamlit Community "
            "Cloud: confirm requirements.txt (in the repo root) contains "
            "'psycopg2-binary>=2.9.9', then use 'Manage app' -> the ⋮ menu -> "
            "'Reboot app' to force a clean reinstall of dependencies. "
            "Locally: run 'pip install -r requirements.txt' again."
        ) from exc
else:
    import sqlite3


def _prep(sql: str) -> str:
    """Translate SQLite-style '?' placeholders to psycopg2-style '%s'
    when running against Postgres. Every query in this codebase uses
    '?' only as a bind-parameter placeholder, never as literal text, so
    a plain replace is safe here."""
    if BACKEND == "postgres":
        return sql.replace("?", "%s")
    return sql


# ---------------------------------------------------------------------
# Connection handling
#
# SQLite: a fresh connection is opened per call - this is genuinely cheap
# (local file I/O, no handshake), exactly as before.
#
# Postgres: connections are checked out from a persistent pool instead of
# opened fresh each time. Opening a brand-new authenticated TLS connection
# to a REMOTE database for every single query is the single biggest cause
# of slowness once this app talks to a real network-hosted Postgres host
# (e.g. Neon) rather than a local SQLite file - a typical page here issues
# dozens of small queries, and paying a full TCP+TLS+auth handshake for
# every one of them adds up to seconds of pure connection overhead before
# any actual query work happens. Reusing pooled connections eliminates
# nearly all of that overhead on the common path.
# ---------------------------------------------------------------------
_pg_pool = None


def _get_pg_pool():
    global _pg_pool
    if _pg_pool is None:
        if not config.DATABASE_URL:
            raise RuntimeError(
                "DB_BACKEND is 'postgres' but DATABASE_URL is not set. "
                "Set it via environment variable or Streamlit secrets."
            )
        _pg_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1, maxconn=10,
            dsn=config.DATABASE_URL,
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
    return _pg_pool


def get_connection():
    if BACKEND == "postgres":
        return _get_pg_pool().getconn()

    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # WAL mode lets one device write while others keep reading, and
    # busy_timeout makes SQLite wait (instead of failing instantly) if two
    # devices happen to write in the same instant - important once the app
    # is opened from a laptop and a phone/tablet at the same time. Some
    # filesystems (certain network/container-mounted storage, some cloud
    # hosts) don't support WAL's shared-memory locking - fall back to the
    # universally-supported default journal mode there instead of crashing.
    try:
        conn.execute("PRAGMA journal_mode = WAL")
    except sqlite3.OperationalError:
        pass
    conn.execute("PRAGMA busy_timeout = 8000")
    return conn


def _release_connection(conn, broken: bool = False):
    """Returns a connection after use. For Postgres, `broken=True` closes
    and discards it instead of returning it to the pool - used when a
    pooled connection turned out to be dead (e.g. closed server-side after
    sitting idle), so a bad connection is never handed out again."""
    if BACKEND == "postgres":
        _get_pg_pool().putconn(conn, close=broken)
    else:
        conn.close()


def _is_stale_connection_error(exc) -> bool:
    if BACKEND != "postgres":
        return False
    return isinstance(exc, (psycopg2.OperationalError, psycopg2.InterfaceError))


@contextmanager
def db_cursor(commit=False):
    conn = get_connection()
    broken = False
    try:
        cur = conn.cursor()
        yield cur
        if commit:
            conn.commit()
    except Exception:
        broken = True  # don't return a connection to the pool mid-error - safer to discard and reconnect
        raise
    finally:
        _release_connection(conn, broken=broken)


def _normalize_row(row: dict) -> dict:
    """Postgres returns decimal.Decimal for NUMERIC/CAST(...AS NUMERIC)
    results, while SQLite returns plain floats for the same computations.
    Mixing Decimal and float in later arithmetic raises TypeError, so every
    row is normalized here - the one place both backends funnel through -
    keeping every caller's behaviour identical regardless of backend."""
    if BACKEND != "postgres":
        return row
    for k, v in row.items():
        if isinstance(v, decimal.Decimal):
            row[k] = float(v)
    return row


def query_all(sql, params=()):
    # Reads are always safe to retry: a SELECT has no side effects, so if a
    # pooled connection turns out to be stale (e.g. Neon closed it after
    # sitting idle), silently retrying once on a fresh connection is
    # transparent to the caller and avoids a spurious crash.
    for attempt in (1, 2):
        conn = get_connection()
        broken = False
        try:
            cur = conn.cursor()
            cur.execute(_prep(sql), params)
            return [_normalize_row(dict(r)) for r in cur.fetchall()]
        except Exception as exc:
            broken = True
            if attempt == 1 and _is_stale_connection_error(exc):
                continue
            raise
        finally:
            _release_connection(conn, broken=broken)


def query_one(sql, params=()):
    for attempt in (1, 2):
        conn = get_connection()
        broken = False
        try:
            cur = conn.cursor()
            cur.execute(_prep(sql), params)
            row = cur.fetchone()
            return _normalize_row(dict(row)) if row else None
        except Exception as exc:
            broken = True
            if attempt == 1 and _is_stale_connection_error(exc):
                continue
            raise
        finally:
            _release_connection(conn, broken=broken)


def execute(sql, params=()):
    """INSERT/UPDATE/DELETE - returns lastrowid (best-effort on Postgres:
    uses lastval(), which only succeeds if the statement just executed
    touched a SERIAL/IDENTITY column - harmless None otherwise).

    Writes are not auto-retried on a stale connection (unlike the reads
    above) - retrying a write after an ambiguous failure risks a double
    write, so a genuinely dead connection here just raises clearly, same
    as before pooling. Pooling still speeds up the common (non-stale)
    case by reusing an already-authenticated connection."""
    conn = get_connection()
    broken = False
    try:
        cur = conn.cursor()
        cur.execute(_prep(sql), params)
        lastrowid = None
        if BACKEND == "postgres":
            try:
                cur.execute("SELECT lastval()")
                lastrowid = cur.fetchone()["lastval"]
            except Exception:
                conn.rollback()
                cur = conn.cursor()
                cur.execute(_prep(sql), params)  # statement itself already ran once; this path only
                lastrowid = None                  # hits when lastval() itself errors (no sequence touched)
        else:
            lastrowid = cur.lastrowid
        conn.commit()
        return lastrowid
    except Exception:
        broken = True
        raise
    finally:
        _release_connection(conn, broken=broken)


def executemany(sql, param_list):
    conn = get_connection()
    broken = False
    try:
        cur = conn.cursor()
        cur.executemany(_prep(sql), param_list)
        conn.commit()
    except Exception:
        broken = True
        raise
    finally:
        _release_connection(conn, broken=broken)


# ---------------------------------------------------------------------
# Schema - written once in SQLite dialect, auto-translated for Postgres
# (the only real syntax difference this schema uses is the auto-
# incrementing primary key declaration).
# ---------------------------------------------------------------------
SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS institutes (
    institute_id TEXT PRIMARY KEY,
    institute_name TEXT NOT NULL,
    owner_name TEXT NOT NULL,
    mobile TEXT NOT NULL,
    whatsapp_number TEXT,
    email TEXT,
    address TEXT,
    logo_path TEXT,
    gst_number TEXT,
    receipt_footer TEXT,
    terms_conditions TEXT,
    currency TEXT DEFAULT 'INR',
    date_format TEXT DEFAULT 'DD-MM-YYYY',
    is_suspended INTEGER DEFAULT 0,
    suspension_reason TEXT,
    is_demo INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    institute_id TEXT NOT NULL,
    username TEXT UNIQUE NOT NULL,
    email TEXT,
    password_hash TEXT NOT NULL,
    full_name TEXT,
    role TEXT NOT NULL DEFAULT 'ADMIN',   -- ADMIN, MANAGER, STAFF
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    is_demo INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (institute_id) REFERENCES institutes(institute_id)
);

CREATE TABLE IF NOT EXISTS licences (
    licence_id INTEGER PRIMARY KEY AUTOINCREMENT,
    institute_id TEXT NOT NULL,
    licence_key TEXT,
    plan TEXT NOT NULL,          -- MONTHLY, YEARLY
    status TEXT NOT NULL,        -- ACTIVE_MONTHLY, ACTIVE_YEARLY, EXPIRED
    activation_date TEXT,
    expiry_date TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (institute_id) REFERENCES institutes(institute_id)
);

CREATE TABLE IF NOT EXISTS licence_keys (
    licence_key TEXT PRIMARY KEY,
    plan TEXT NOT NULL,          -- MONTHLY, YEARLY
    is_used INTEGER DEFAULT 0,
    used_by_institute TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS courses (
    course_id INTEGER PRIMARY KEY AUTOINCREMENT,
    institute_id TEXT NOT NULL,
    course_name TEXT NOT NULL,
    course_code TEXT,
    duration TEXT,
    course_fees REAL DEFAULT 0,
    description TEXT,
    status TEXT DEFAULT 'ACTIVE',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (institute_id) REFERENCES institutes(institute_id)
);

CREATE TABLE IF NOT EXISTS faculty (
    faculty_id INTEGER PRIMARY KEY AUTOINCREMENT,
    institute_id TEXT NOT NULL,
    faculty_name TEXT NOT NULL,
    mobile TEXT,
    whatsapp_number TEXT,
    email TEXT,
    subject TEXT,
    joining_date TEXT,
    salary REAL DEFAULT 0,
    address TEXT,
    status TEXT DEFAULT 'ACTIVE',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (institute_id) REFERENCES institutes(institute_id)
);

CREATE TABLE IF NOT EXISTS batches (
    batch_id INTEGER PRIMARY KEY AUTOINCREMENT,
    institute_id TEXT NOT NULL,
    batch_name TEXT NOT NULL,
    course_id INTEGER,
    faculty_id INTEGER,
    room TEXT,
    start_date TEXT,
    end_date TEXT,
    class_days TEXT,
    start_time TEXT,
    end_time TEXT,
    max_students INTEGER DEFAULT 30,
    status TEXT DEFAULT 'ACTIVE',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (institute_id) REFERENCES institutes(institute_id),
    FOREIGN KEY (course_id) REFERENCES courses(course_id),
    FOREIGN KEY (faculty_id) REFERENCES faculty(faculty_id)
);

CREATE TABLE IF NOT EXISTS students (
    student_id TEXT PRIMARY KEY,
    institute_id TEXT NOT NULL,
    student_name TEXT NOT NULL,
    father_name TEXT,
    mother_name TEXT,
    gender TEXT,
    dob TEXT,
    student_mobile TEXT,
    parent_mobile TEXT,
    whatsapp_number TEXT,
    email TEXT,
    address TEXT,
    city TEXT,
    course_id INTEGER,
    batch_id INTEGER,
    admission_date TEXT,
    joining_date TEXT,
    total_fees REAL DEFAULT 0,
    discount REAL DEFAULT 0,
    net_fees REAL DEFAULT 0,
    paid_fees REAL DEFAULT 0,
    pending_fees REAL DEFAULT 0,
    payment_status TEXT DEFAULT 'PENDING',
    photo_path TEXT,
    notes TEXT,
    status TEXT DEFAULT 'ACTIVE',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (institute_id) REFERENCES institutes(institute_id),
    FOREIGN KEY (course_id) REFERENCES courses(course_id),
    FOREIGN KEY (batch_id) REFERENCES batches(batch_id)
);

CREATE TABLE IF NOT EXISTS admissions (
    admission_id INTEGER PRIMARY KEY AUTOINCREMENT,
    institute_id TEXT NOT NULL,
    student_id TEXT NOT NULL,
    course_id INTEGER,
    batch_id INTEGER,
    admission_date TEXT,
    total_fees REAL DEFAULT 0,
    discount REAL DEFAULT 0,
    net_fees REAL DEFAULT 0,
    initial_payment REAL DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (institute_id) REFERENCES institutes(institute_id),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);

CREATE TABLE IF NOT EXISTS tests (
    test_id INTEGER PRIMARY KEY AUTOINCREMENT,
    institute_id TEXT NOT NULL,
    test_name TEXT NOT NULL,
    subject TEXT,
    course_id INTEGER,
    batch_id INTEGER,
    test_date TEXT,
    max_marks REAL NOT NULL DEFAULT 100,
    test_type TEXT DEFAULT 'Unit Test',
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (institute_id) REFERENCES institutes(institute_id),
    FOREIGN KEY (course_id) REFERENCES courses(course_id),
    FOREIGN KEY (batch_id) REFERENCES batches(batch_id)
);

CREATE TABLE IF NOT EXISTS test_results (
    result_id INTEGER PRIMARY KEY AUTOINCREMENT,
    institute_id TEXT NOT NULL,
    test_id INTEGER NOT NULL,
    student_id TEXT NOT NULL,
    marks_obtained REAL,
    remarks TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (institute_id) REFERENCES institutes(institute_id),
    FOREIGN KEY (test_id) REFERENCES tests(test_id),
    FOREIGN KEY (student_id) REFERENCES students(student_id),
    UNIQUE(test_id, student_id)
);

CREATE TABLE IF NOT EXISTS attendance (
    attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
    institute_id TEXT NOT NULL,
    student_id TEXT NOT NULL,
    batch_id INTEGER,
    course_id INTEGER,
    att_date TEXT NOT NULL,
    status TEXT NOT NULL,
    marked_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (institute_id) REFERENCES institutes(institute_id),
    FOREIGN KEY (student_id) REFERENCES students(student_id),
    UNIQUE(student_id, att_date)
);

CREATE TABLE IF NOT EXISTS fee_payments (
    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    institute_id TEXT NOT NULL,
    student_id TEXT NOT NULL,
    receipt_number TEXT,
    amount REAL NOT NULL,
    payment_mode TEXT,
    payment_date TEXT,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (institute_id) REFERENCES institutes(institute_id),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);

CREATE TABLE IF NOT EXISTS class_schedule (
    schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
    institute_id TEXT NOT NULL,
    course_id INTEGER,
    batch_id INTEGER,
    faculty_id INTEGER,
    class_date TEXT,
    start_time TEXT,
    end_time TEXT,
    room TEXT,
    topic TEXT,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (institute_id) REFERENCES institutes(institute_id)
);

CREATE TABLE IF NOT EXISTS whatsapp_templates (
    template_id INTEGER PRIMARY KEY AUTOINCREMENT,
    institute_id TEXT NOT NULL,
    template_name TEXT NOT NULL,
    template_text TEXT NOT NULL,
    is_default INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (institute_id) REFERENCES institutes(institute_id)
);

CREATE TABLE IF NOT EXISTS whatsapp_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    institute_id TEXT NOT NULL,
    student_id TEXT,
    template_used TEXT,
    message_text TEXT,
    sent_by TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (institute_id) REFERENCES institutes(institute_id)
);

CREATE TABLE IF NOT EXISTS notifications (
    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
    institute_id TEXT NOT NULL,
    title TEXT,
    message TEXT,
    is_read INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (institute_id) REFERENCES institutes(institute_id)
);

CREATE TABLE IF NOT EXISTS settings (
    setting_key TEXT NOT NULL,
    institute_id TEXT NOT NULL,
    setting_value TEXT,
    PRIMARY KEY (setting_key, institute_id)
);

CREATE TABLE IF NOT EXISTS demo_data_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    institute_id TEXT NOT NULL,
    table_name TEXT NOT NULL,
    record_id TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_students_institute ON students(institute_id);
CREATE INDEX IF NOT EXISTS idx_students_course ON students(course_id);
CREATE INDEX IF NOT EXISTS idx_students_batch ON students(batch_id);
CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(att_date);
CREATE INDEX IF NOT EXISTS idx_attendance_student ON attendance(student_id);
CREATE INDEX IF NOT EXISTS idx_payments_student ON fee_payments(student_id);
CREATE INDEX IF NOT EXISTS idx_users_institute ON users(institute_id);
CREATE INDEX IF NOT EXISTS idx_tests_institute ON tests(institute_id);
CREATE INDEX IF NOT EXISTS idx_tests_batch ON tests(batch_id);
CREATE INDEX IF NOT EXISTS idx_test_results_test ON test_results(test_id);
CREATE INDEX IF NOT EXISTS idx_test_results_student ON test_results(student_id);
"""

# Postgres uses SERIAL instead of SQLite's INTEGER PRIMARY KEY AUTOINCREMENT.
# Everything else in the schema above (TEXT, REAL, DEFAULT, FOREIGN KEY,
# UNIQUE, CREATE INDEX IF NOT EXISTS) is valid standard SQL Postgres accepts
# as-is, so a single targeted substitution is all that's needed.
SCHEMA_POSTGRES = SCHEMA_SQLITE.replace(
    "INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY"
)

# All tables that carry a tenant column, in a safe deletion order (children
# before parents) - used by the tenant-isolation self-check and by the
# Postgres JSON backup/restore routines below.
ALL_TENANT_TABLES_DELETE_ORDER = [
    "whatsapp_logs", "notifications", "demo_data_log",
    "fee_payments", "test_results", "attendance", "admissions",
    "class_schedule", "whatsapp_templates", "students",
    "tests", "batches", "faculty", "courses",
    "licences", "licence_keys", "users", "settings", "institutes",
]
ALL_TABLES_INSERT_ORDER = list(reversed(ALL_TENANT_TABLES_DELETE_ORDER))

# Same tables, minus tenant IDENTITY (institutes, users, licences,
# licence_keys) - used to wipe a tenant's business DATA while keeping the
# tenant record and its login intact (used for the demo tenant's periodic
# reset, so the demo login itself is never deleted).
_IDENTITY_TABLES = {"institutes", "users", "licences", "licence_keys", "settings"}
BUSINESS_DATA_TABLES_DELETE_ORDER = [t for t in ALL_TENANT_TABLES_DELETE_ORDER if t not in _IDENTITY_TABLES]


def init_db():
    schema = SCHEMA_POSTGRES if BACKEND == "postgres" else SCHEMA_SQLITE

    if BACKEND != "postgres":
        conn = get_connection()
        try:
            conn.executescript(schema)
            conn.commit()
        finally:
            _release_connection(conn)
        _run_migrations()
        return

    # Postgres: retried once on a fresh connection if the pooled connection
    # handed out turns out to be dead (e.g. a serverless host like Neon
    # closed it after sitting idle) - without this, a stale connection here
    # crashed the whole app at boot instead of just reconnecting, since this
    # runs on every Streamlit rerun and so hits the pool far more often than
    # a typical query.
    for attempt in (1, 2):
        conn = get_connection()
        broken = False
        try:
            cur = conn.cursor()
            cur.execute(schema)
            conn.commit()
            break
        except psycopg2.Error as exc:
            broken = True
            stale = _is_stale_connection_error(exc)
            if not stale:
                # Under concurrent Streamlit sessions, two processes can both
                # run "CREATE TABLE/INDEX IF NOT EXISTS" for a brand-new
                # table at the same instant - Postgres's system catalog
                # isn't fully race-proof for this, and one loses with a
                # duplicate-key error even though the *table* itself ends up
                # created correctly by the other. Safe to ignore: this is
                # pure schema DDL with no data-dependent logic, and the
                # desired end state (schema exists) is achieved either way -
                # only possible on the very first-ever run, before any
                # table exists; once schema exists this can never recur.
                try:
                    conn.rollback()
                except psycopg2.Error:
                    pass  # connection is already dead - nothing to roll back
        finally:
            _release_connection(conn, broken=broken)

        if not (stale and attempt == 1):
            break

    _run_migrations()


def _run_migrations():
    """Idempotently adds columns introduced after a database was first
    created, so existing installs (offline .db files or already-provisioned
    Postgres databases) pick up new features without losing data."""
    additions = [
        ("institutes", "is_suspended", "INTEGER DEFAULT 0"),
        ("institutes", "suspension_reason", "TEXT"),
        ("institutes", "is_demo", "INTEGER DEFAULT 0"),
        ("users", "is_demo", "INTEGER DEFAULT 0"),
    ]
    if BACKEND == "postgres":
        for table, col, coltype in additions:
            execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {coltype}")
    else:
        for table, col, coltype in additions:
            existing_cols = {r["name"] for r in query_all(f"PRAGMA table_info({table})")}
            if col not in existing_cols:
                execute(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}")


# ---------------------------------------------------------------------
# Backup / restore
# ---------------------------------------------------------------------
def backup_database(dest_path):
    """SQLite: simple file copy. Postgres: table-by-table JSON export
    (portable, needs no pg_dump binary on the host) covering every
    tenant-relevant table."""
    if BACKEND == "sqlite":
        import shutil
        shutil.copy2(DB_PATH, dest_path)
        return dest_path

    dump = {}
    for table in ALL_TABLES_INSERT_ORDER:
        dump[table] = query_all(f"SELECT * FROM {table}")
    with open(dest_path, "w") as f:
        json.dump(dump, f, default=str)
    return dest_path


def restore_database(src_path):
    """SQLite: simple file copy. Postgres: reads the JSON export produced
    by backup_database() and reloads every table (clearing existing rows
    first) inside the same tenant-table set."""
    if BACKEND == "sqlite":
        import shutil
        shutil.copy2(src_path, DB_PATH)
        return True

    with open(src_path) as f:
        dump = json.load(f)

    for table in ALL_TENANT_TABLES_DELETE_ORDER:
        execute(f"DELETE FROM {table}")

    for table in ALL_TABLES_INSERT_ORDER:
        rows = dump.get(table, [])
        for row in rows:
            cols = list(row.keys())
            placeholders = ",".join(["?"] * len(cols))
            col_list = ",".join(cols)
            execute(f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})",
                   tuple(row[c] for c in cols))
    return True


def db_info():
    if BACKEND == "postgres":
        tables = query_all(
            "SELECT table_name AS name FROM information_schema.tables WHERE table_schema='public'")
        size_row = query_one("SELECT pg_database_size(current_database()) AS size")
        size = size_row["size"] if size_row else 0
        return {"path": config.DATABASE_URL.split("@")[-1] if config.DATABASE_URL else "(not set)",
                "size_bytes": size, "tables": [t["name"] for t in tables]}

    size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
    tables = query_all("SELECT name FROM sqlite_master WHERE type='table'")
    return {"path": DB_PATH, "size_bytes": size, "tables": [t["name"] for t in tables]}
