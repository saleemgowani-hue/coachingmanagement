# SN COACHING MANAGEMENT SYSTEM
**Powered by SN Softech Solutions**

A commercial-grade Coaching / Tuition Centre Management System built with
Python and Streamlit. Covers student management, admissions, attendance,
fees, test/exam management, a WhatsApp-Web messaging centre, faculty,
class scheduling, reports, KPI dashboards, role-based users, subscription
licensing (Monthly/Yearly, no free trial), a permanent Demo account, a
cross-tenant Super Admin panel, and database backup/restore.

**One codebase, two deployment modes**, switched purely by configuration
(`DB_BACKEND`) — no code changes needed either way:
- **Offline**: SQLite, runs on a single Windows PC, fully usable with no internet.
- **Online SaaS**: PostgreSQL, multi-tenant, deployable to Streamlit
  Community Cloud (or any host) directly from GitHub.

Every business table already carries an `institute_id` tenant column,
and every query in the app filters by it — read from the authenticated
session only, never from anything a user can edit — so one coaching
centre's data can never be seen by another, on either backend.

See `ONLINE_DEPLOYMENT.md` for the SaaS setup guide, `ADMIN_GUIDE.md` for
the Super Admin panel, and `DEMO_ACCOUNT_GUIDE.md` for the demo login.

---

## 1. Installation

Requires **Python 3.10+**.

```bash
cd sn_coaching
pip install -r requirements.txt
```

## 2. Running the app

**Windows — easiest way:** just double-click **`run.bat`**. On the very
first run it creates a local Python environment, installs everything
in `requirements.txt`, then launches the app and opens it in your
browser. On every run after that it starts in a few seconds. Keep the
black console window open while using the app — closing it stops the
server.

**Manual way (Windows/Mac/Linux):**

```bash
streamlit run app.py
```

Open the URL Streamlit prints (usually `http://localhost:8501`).

The SQLite database is created automatically on first run at
`data/sn_coaching.db` — no manual setup needed.

## 3. First run

There is no default/demo login — the first screen is **Create New
Account**. Fill in your institute details and choose a username/password.
**There is no free trial** — the software stays locked until a valid
Monthly or Yearly licence key is activated. You can either:

- Enter your licence key **right there on the signup form** (Plan +
  Licence Key fields) so the account is created and activated in one
  step, or
- Leave it blank and activate later from **Licence Management** after
  signing in — the account is created either way, just locked until a
  key is entered.

Optionally tick **"Populate with demo/sample data"** to get ~40 sample
students, courses, batches, faculty and attendance/payment history for
evaluation — independent of licence activation, and removable anytime
from **Settings → Demo Data**.

## 4. Licensing system

- **No free trial.** A newly created institute is `NOT_ACTIVATED` and
  locked until a Monthly or Yearly licence key is entered — either on
  the signup form or afterward from **Licence Management**.
- While locked, only **Licence Management**, **Settings** and
  **Logout** are accessible — all data already entered is preserved
  and becomes available again immediately on activation.
- Licence keys are validated against a `licence_keys` table (never a
  single hard-coded key), so real keys can be generated and issued by
  SN Softech Solutions and sold per institute. See the bundled
  `license_keys.xlsx` / `IMPORT_LICENSE_KEYS.bat` for issuing a batch.
- For **evaluation only**, an Admin user can open **Licence Management
  → "Generate Demo Licence Key"** to mint a working Monthly or Yearly
  key locally and activate it immediately.
- The architecture (see `license.py`) is built to support Quarterly,
  Half-Yearly and Lifetime plans later, and to be swapped for
  server-side time/licence verification in a future cloud release —
  today it validates against the local machine clock, as any offline
  desktop app does.

## 5. WhatsApp usage

The WhatsApp Centre and every reminder button use **WhatsApp Web
click-to-chat links** (`wa.me/...`) — there is no WhatsApp Business API
integration in this version. Clicking a "Send" button opens WhatsApp
with the message already typed in; **you always review and press Send
yourself**. The app never claims a message was delivered — only that a
draft was prepared.

## 6. Mobile / Tablet Access (same WiFi network)

By default `run.bat` only opens the app on the computer itself
(`localhost`). To also open it on a phone or tablet on the **same WiFi
network**:

1. Double-click **`START_ON_NETWORK.bat`** instead of `run.bat`.
2. It prints a network address, e.g. `http://192.168.1.5:8501`.
3. On the phone/tablet: connect to the **same WiFi**, open Chrome or
   Safari, and type that address in.
4. Optionally tap **"Add to Home Screen"** so it opens like a regular
   app, full-screen, without browser bars.

The layout automatically adjusts for phone and tablet screen sizes
(KPI cards, sidebar, tables and charts all reflow — no extra setup
needed). Close the console window to stop network access; use plain
`run.bat` again for computer-only, localhost-only use.

**Note:** this only works over the local WiFi network — not over the
internet. Everyone using it must be on the same router/hotspot as the
computer running the app. Make sure Windows Firewall allows Python /
Streamlit through when prompted the first time.

## 7. Backup & restore

**Settings → Backup & Restore**:
- **Create Backup Now** copies the SQLite file and offers it as a
  download.
- **Restore** accepts an uploaded `.db` file and replaces the current
  database — a confirmation checkbox is required first, since this
  overwrites all current data.

## 8. Database backend — SQLite (offline) or PostgreSQL (online SaaS)

Controlled entirely by configuration (see `config.py`), never by editing
code:

| Setting | Offline (default) | Online SaaS |
|---|---|---|
| `DB_BACKEND` | `sqlite` (default if unset) | `postgres` |
| `DATABASE_URL` | not needed | `postgresql://user:pass@host:5432/dbname` |

Set these via environment variables (any host) or `.streamlit/secrets.toml`
(Streamlit Cloud). Every one of the ~100 queries in this codebase is
written once, using `?` placeholders, and works unchanged on both
backends — `database.py` is the only file that knows the difference.
Full setup steps for the online mode are in **`ONLINE_DEPLOYMENT.md`**.

**Design note on why this isn't a full SQLAlchemy ORM:** the online
architecture uses `psycopg2` directly (with a small placeholder-translation
layer) rather than rewriting every query as SQLAlchemy ORM calls. That
would have meant touching all ~15 module files and risking bugs in
already-working business logic — directly against the instruction to
preserve existing functionality. The result still gets you parameterized
queries (no SQL injection risk), environment/secrets-based connection
config, and full PostgreSQL support; a true ORM layer is a reasonable
future upgrade if you outgrow this.

**Migrating existing offline data to the online database:** run
`python migrate_sqlite_to_postgres.py --postgres-url <your Postgres URL>`
— it copies every row from `data/sn_coaching.db` into PostgreSQL,
table by table, without modifying the source file. Tested end-to-end
including login credentials and Test Management data.

## 9. Demo account

A fixed, permanent demo login is auto-created the first time the app
starts (see `DEMO_ACCOUNT_GUIDE.md` for credentials and full details).
It has a permanently active subscription, pre-loaded sample data, and
cannot change its password or institute settings — safe to hand out to
prospective customers.

## 10. Super Admin panel

A separate cross-tenant management panel for SN Softech Solutions staff
— view every customer, activate/renew a subscription without needing a
licence key, suspend/cancel/reactivate an account, and see basic usage
per tenant. Completely separate login from any customer account (see
**`ADMIN_GUIDE.md`**). Not shown to, or reachable by, any customer.

## 11. Backup & restore

**Settings → Backup & Restore**:
- **SQLite (offline):** creates a copy of the `.db` file.
- **PostgreSQL (online):** exports every table to a portable JSON file
  (no `pg_dump` binary required on the host).
- **Restore** accepts the matching backup file and replaces all current
  data — a confirmation checkbox is required first.

## 12. Roles

- **ADMIN** — full access, including User Management and Subscription.
- **MANAGER** — students, courses, batches, attendance, tests, fees,
  reports, WhatsApp.
- **STAFF** — students, attendance, tests, class schedule, WhatsApp,
  birthdays.

Admin creates Manager/Staff logins from **User Management**. The Super
Admin panel is separate from these roles entirely (see section 10).

## 13. Project structure

```
app.py                          Entry point: routing, auth, sidebar, Super Admin gateway
config.py                       Centralized config (pricing, branding, demo creds, DB backend)
database.py                     Dual-backend (SQLite/Postgres) query layer
auth.py                         Sign up / login / password hashing / sessions / demo seeding
license.py                      Subscription state machine + Super Admin activate/suspend
whatsapp.py                     wa.me link builder + message templates
reports.py                      KPI + report queries
utils.py                        Formatting, validation, small UI helpers
logging_setup.py                File + stdout logging (never logs secrets/passwords)
migrate_sqlite_to_postgres.py   One-time offline → online data migration utility
style.css                       Custom theme (multicolour sidebar, KPI cards, etc.)
modules/                        One file per screen, incl. super_admin.py and sample_data.py
data/                            SQLite database file lives here (auto-created, offline only)
backups/                         Local backups saved here
logs/                            app.log (auto-created)
```

## 14. What's fully built vs. simplified in this version

Everything in the spec is implemented and working end-to-end, tested
against **real PostgreSQL** as well as SQLite: sign up, direct-activation
Monthly/Yearly subscriptions (no trial) with a real key table, a
permanent Demo account, a cross-tenant Super Admin panel (activate,
suspend, cancel, reactivate, usage view), graduated expiry warnings
(30/15/7/3/1 days), full KPI dashboard with Plotly charts, Student /
Course / Batch / Faculty CRUD, Admission log with WhatsApp confirmation,
daily Attendance with history and % reports, Test Management (create
tests, enter marks per batch, batch-wise and subject-wise performance
charts, top/bottom performers, WhatsApp result sending), Fee collection
with receipts and a Pending Fees WhatsApp-reminder screen, a WhatsApp
Centre with 9 editable templates and individual/batch/course bulk
sending, Birthday management, Class Schedule, a Reports Hub covering 13
report types with search/sort/Excel export, a separate KPI Report
screen, role-based User Management, Institute Settings with password
change, and backend-aware Backup/Restore.

To keep this focused and reliable rather than sprawling, a few things
are intentionally simpler than a mature commercial product would
eventually have, and are natural next steps:

- **Payment gateway integration** (Razorpay/Stripe/UPI) is not wired up
  — not required per the brief, but `licences`/`subscriptions` are
  already shaped so a webhook can call `license.activate_licence()` or
  `license.admin_activate()` directly once you add one.
- **Print-friendly views** rely on the browser's own print (Ctrl+P) and
  Excel export rather than a dedicated PDF-styled print layout.
- **Photo upload** for students and **logo upload** for the institute
  are not wired up yet (fields exist in the schema).
- **"Forgot Password"** is a placeholder — self-service reset isn't
  implemented; an Admin should create a new user or a future version
  can add email-based reset.
- Subscription validation is clock-based on whichever server runs the
  app (the online host's clock for SaaS, the local PC's clock offline)
  — genuine server-side/third-party time verification is a further
  hardening step, not implemented here.
- Row-level security at the PostgreSQL level (`ROW SECURITY`) is not
  enabled — isolation is enforced entirely in the application layer
  (every query filters by `institute_id`, sourced only from the
  authenticated session). This was verified directly: two tenants
  created in the same database showed zero data overlap across every
  query path tested.

None of the above blocks day-to-day use — they're refinements worth
doing in a future pass.

## 15. Troubleshooting

- **"streamlit: command not found"** — make sure you ran `pip install
  -r requirements.txt` in the same Python environment you're using to
  run the app.
- **Port already in use** — run `streamlit run app.py
  --server.port 8502` (or any free port).
- **Locked out / "Subscription Not Activated"** — go to My Subscription (still
  accessible) and activate a Monthly or Yearly key, or generate a demo
  key there for testing.
- **Restore didn't seem to apply** — after restoring, fully restart the
  Streamlit process so the new database file is loaded fresh.
- **Something looks broken on a page** — the app is built to show a
  friendly error banner with a "Technical details" expander instead of
  a raw traceback. If you hit one, check that panel and, if needed,
  restart the app.
- **Phone/tablet can't reach the network address** — confirm both
  devices are on the same WiFi (not one on WiFi and one on mobile
  data), and allow Python/Streamlit through Windows Firewall if
  prompted. Corporate/guest WiFi networks sometimes block
  device-to-device traffic entirely.

---
*SN COACHING MANAGEMENT SYSTEM — Powered by SN Softech Solutions*
