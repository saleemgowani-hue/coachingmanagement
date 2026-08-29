# ONLINE DEPLOYMENT GUIDE
## SN Coaching Management System — Online SaaS (PostgreSQL)

This guide walks through taking the **same codebase** used for the
offline version and running it as a hosted, multi-tenant SaaS on
Streamlit Community Cloud with a PostgreSQL database. No code changes
are needed — only configuration.

---

## 1. What you'll need

- A GitHub account (free)
- A PostgreSQL database. Any of these work:
  - [Supabase](https://supabase.com) (free tier, easiest to start with)
  - [Neon](https://neon.tech) (free tier, serverless Postgres)
  - Render, Railway, or your own PostgreSQL server
- A [Streamlit Community Cloud](https://streamlit.io/cloud) account (free)

## 2. Create the PostgreSQL database

Using Supabase (or any provider), create a new project/database and
copy its connection string. It looks like:

```
postgresql://<user>:<password>@<host>:5432/<database>
```

Keep this safe — it goes into Streamlit secrets in step 5, **never**
into any file you commit to GitHub.

## 3. Push the code to GitHub

```bash
cd sn_coaching
git init
git add .
git commit -m "Initial commit - SN Coaching Management System (online)"
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

The included `.gitignore` already excludes `data/`, `backups/`, `logs/`,
`.streamlit/secrets.toml`, and `__pycache__/` — none of your local test
data, backups, or secrets will be pushed.

## 4. Deploy on Streamlit Community Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in
   with GitHub.
2. Click **New app**, pick your repository, branch `main`, and set the
   main file path to `app.py`.
3. **Before clicking Deploy**, open **Advanced settings → Secrets** and
   paste in the configuration from the next step.

## 5. Configure secrets

In the Streamlit Cloud app's **Settings → Secrets** (or locally, create
`.streamlit/secrets.toml` — never commit this file), paste:

```toml
DB_BACKEND = "postgres"
DATABASE_URL = "postgresql://<user>:<password>@<host>:5432/<database>"

COMPANY_NAME = "SN Softech Solutions"
PRODUCT_NAME = "SN Coaching Management System"
SUPPORT_EMAIL = "support@yourcompany.com"
SUPPORT_WHATSAPP = "9993199719"

MONTHLY_PRICE = "999"
YEARLY_PRICE = "9999"

DEMO_USERNAME = "demo"
DEMO_PASSWORD = "choose-a-demo-password"
DEMO_INSTITUTE_NAME = "Demo Coaching Centre"

SUPER_ADMIN_USERNAME = "superadmin"
SUPER_ADMIN_PASSWORD = "choose-a-strong-password-here"
```

**Important:** `SUPER_ADMIN_PASSWORD` has no default — if you leave it
blank, the Super Admin panel refuses to log anyone in (fails safe,
rather than falling back to a guessable default). Set a strong,
unique password here.

## 6. First run

Once deployed, the app creates its own database schema automatically on
first load (`database.init_db()` runs at startup — safe to run every
time, it only creates what's missing). Open the app URL:

- Sign up for a real coaching centre account, **or**
- Log in with the Demo credentials you set above to explore first, **or**
- Go to **Super Admin** (on the login screen) with your
  `SUPER_ADMIN_USERNAME` / `SUPER_ADMIN_PASSWORD` to manage customers.

## 7. Issuing licence keys to real customers

Same mechanism as offline: generate keys with
`license.generate_licence_key()` (via the in-app "Generate Demo Licence
Key" admin tool, or your own script against the same database), or use
the **Super Admin panel → Activate/Renew** to directly activate a
customer's subscription without needing a pre-generated key at all.

## 8. Migrating existing offline customers

If a customer already has an offline installation with real data and
wants to move online:

```bash
python migrate_sqlite_to_postgres.py \
  --sqlite-path /path/to/their/data/sn_coaching.db \
  --postgres-url "postgresql://<user>:<password>@<host>:5432/<database>"
```

This copies every row (students, fees, tests, attendance, everything)
into the same shared PostgreSQL database as a new, fully isolated
tenant — their `institute_id` and all foreign keys are preserved
exactly, so nothing needs re-entering.

## 9. Security notes

- Every table carries `institute_id`; every query filters by it, always
  read from the authenticated session — never from a URL parameter or
  form field a customer could edit. This was verified directly with two
  simultaneous tenants sharing one database.
- Passwords are salted + hashed (PBKDF2-HMAC-SHA256, 200,000 iterations)
  — never stored in plain text, on either backend.
- `DATABASE_URL` and `SUPER_ADMIN_PASSWORD` live only in Streamlit
  secrets (or your host's environment variables) — never in code, never
  committed to GitHub.
- The app's logs (`logs/app.log`, or your host's log capture) record
  events like logins and subscription changes but are built to never
  include passwords, password hashes, or the database URL.

## 10. Ongoing operation

- **Backups:** Settings → Backup & Restore exports every table to a
  JSON file — download it periodically and store it somewhere safe.
  Your PostgreSQL provider likely also offers automatic backups/point-
  in-time recovery — check their dashboard.
- **Scaling:** Streamlit Community Cloud's free tier is fine for
  starting out; for higher traffic, look at Streamlit Cloud's paid
  tiers or self-hosting via `streamlit run app.py` behind your own
  reverse proxy, pointed at the same `DATABASE_URL`.
- **Custom domain / branding:** handled at the hosting level (Streamlit
  Cloud settings or your reverse proxy) — the app itself already reads
  `COMPANY_NAME` / `PRODUCT_NAME` from config for in-app branding.
