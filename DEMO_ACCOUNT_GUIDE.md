# DEMO ACCOUNT GUIDE
## SN Coaching Management System

A permanent demo login is created automatically the first time the app
starts (`auth.ensure_demo_account()`, called once at startup — safe to
run repeatedly, it does nothing once the account already exists).

## Credentials

Set via configuration (`config.py`, environment variables, or Streamlit
secrets):

| Setting | Default | Purpose |
|---|---|---|
| `DEMO_USERNAME` | `demo` | Login username |
| `DEMO_PASSWORD` | `demo@1234` | Login password |
| `DEMO_INSTITUTE_NAME` | `Demo Coaching Centre` | Shown inside the app |

**Change these from the defaults before showing the software to real
prospective customers** — set them via environment variables (offline)
or Streamlit secrets (online).

The login screen also shows these credentials directly in a "Just want
to explore?" expander, so prospects can self-serve without asking you.

## What the demo account can do

Everything a normal ADMIN can do on their own data: add/edit students,
courses, batches, admissions, attendance, tests and marks, fees,
WhatsApp messaging, reports, and browse the full pre-loaded sample
dataset (~40 students, courses, batches, faculty, attendance, fee and
test history — the same generator used for evaluation data elsewhere in
the app).

## What the demo account cannot do

- **Change its password** — blocked at the `auth.change_password()`
  level itself (checked against the database record, not just hidden in
  the UI), so it can't be bypassed by calling the function directly.
- **Edit institute settings** (name, mobile, email, address, etc.) —
  Settings → Institute shows read-only info instead of the edit form.
- **Modify its subscription** — My Subscription shows a permanent
  "always active" message with no activation form.
- **Delete its account or change its tenant ID** — no such feature
  exists in the app for any account, demo or otherwise.

## How the permanent subscription works

The demo tenant is flagged `institutes.is_demo = 1`. `license.py`
checks this flag first, before looking at the `licences` table at all,
and returns a synthetic "active forever" status — so the demo account
never needs a real licence key and can never expire, without consuming
a slot in your licence key inventory.

## Resetting demo data

If the demo data gets messy from public use, an Admin (including the
demo account itself) can go to **Settings → Demo Data → Clear Demo
Data**, then **Load Demo Data** again — this only touches rows tagged
as demo-generated, verified to leave any other data untouched.
