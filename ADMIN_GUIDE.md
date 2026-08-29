# SUPER ADMIN GUIDE
## SN Coaching Management System

The Super Admin panel is a **cross-tenant** management screen for SN
Softech Solutions staff — it can see and manage every customer
(coaching centre) account. It is completely separate from customer
logins: it authenticates against `SUPER_ADMIN_USERNAME` /
`SUPER_ADMIN_PASSWORD` (config/secrets), never against the `users`
table, so no bug in a customer's role permissions can ever expose it,
and no customer can ever reach it.

## Logging in

On the app's login screen, select **Super Admin** (alongside "Sign In"
and "Create New Account") and enter the admin username/password set in
your configuration or Streamlit secrets. If `SUPER_ADMIN_PASSWORD` was
never set, the panel refuses all logins — set it before relying on this
feature.

## What you can do

### View every customer
A table of every institute (tenant): name, owner, mobile, subscription
status, plan, expiry, days remaining, student count, and whether it's
demo/suspended. Exportable to Excel.

### Activate / Renew / Change Plan
Select a customer, pick Monthly or Yearly, click **Activate/Renew Now**.
This is an **admin-issued** activation — it does not consume a
pre-generated licence key from the `licence_keys` table, since an
internal admin action doesn't need one. Use this for manually renewing
a customer who paid you directly (e.g. bank transfer, cash), or for
switching their plan.

### Suspend a customer
Enter an optional reason and click **Suspend Customer**. Their account
is immediately locked (they see a "Account Suspended" screen with your
reason) but **no data is deleted**. Reactivating restores full access
to the exact same data instantly.

### Cancel a customer
Functionally identical to Suspend (locks access, preserves data) — a
separate button so the reason/intent is recorded distinctly for your
own records.

### Reactivate a customer
If already suspended/cancelled, a **Reactivate Customer** button
appears instead — clears the suspension and restores access immediately.

### View usage
Per-customer basic KPIs (total/active students, total collection,
pending fees) — a quick health check without needing to log in as them.

## Notes

- The Demo tenant is shown in the list but cannot be modified from
  here — its subscription is permanently active by design.
- Every admin action (activate, suspend, cancel, reactivate) is written
  to `logs/app.log` with the institute ID and reason, but never with
  any password or secret.
- Suspending/cancelling never deletes rows from any table — this was
  verified directly: a suspended tenant's students, fees, attendance,
  and test data all remain queryable via `institute_id`, and reappear
  in the app immediately on reactivation.
