"""
migrate_sqlite_to_postgres.py
SN COACHING MANAGEMENT SYSTEM

One-time utility to copy an existing OFFLINE SQLite database
(data/sn_coaching.db) into an ONLINE PostgreSQL database, table by table,
preserving every row and ID exactly. Useful if a customer who started on
the offline version wants to move to the online SaaS version later, or
if you (SN Softech Solutions) want to consolidate an offline install into
your hosted database.

USAGE
    python migrate_sqlite_to_postgres.py --sqlite-path data/sn_coaching.db --postgres-url postgresql://user:pass@host:5432/dbname
    (or set DATABASE_URL as an environment variable and omit --postgres-url)

This does NOT touch the source SQLite file - it only reads from it.
Run it against an EMPTY (freshly initialized) Postgres database; if
tables already contain data, rows are still inserted, which may
produce primary-key conflicts (the migration stops and reports the
first table that failed - it will not partially corrupt data. Insertion
happens table by table using the same tenant-safe FK dependency order
used internally by database.py's backup/restore.

Nothing here is run automatically - the online and offline databases
stay fully independent unless you deliberately run this script.
"""

import argparse
import os
import sqlite3
import sys


def _read_sqlite(sqlite_path: str, table: str) -> list[dict]:
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(f"SELECT * FROM {table}")
        return [dict(r) for r in cur.fetchall()]
    except sqlite3.OperationalError:
        return []  # table doesn't exist in this SQLite file (older schema version)
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Migrate an offline SQLite database into online PostgreSQL.")
    parser.add_argument("--sqlite-path", default=os.path.join("data", "sn_coaching.db"),
                        help="Path to the source SQLite .db file (default: data/sn_coaching.db)")
    parser.add_argument("--postgres-url", default=os.environ.get("DATABASE_URL", ""),
                        help="Destination PostgreSQL connection string (or set DATABASE_URL env var)")
    args = parser.parse_args()

    if not os.path.exists(args.sqlite_path):
        print(f"ERROR: SQLite file not found at {args.sqlite_path}")
        sys.exit(1)
    if not args.postgres_url:
        print("ERROR: no PostgreSQL URL given. Pass --postgres-url or set DATABASE_URL.")
        sys.exit(1)

    # Force the destination side of database.py to talk to Postgres for this run,
    # regardless of what config.py / the environment says otherwise.
    os.environ["DB_BACKEND"] = "postgres"
    os.environ["DATABASE_URL"] = args.postgres_url

    import database as db  # imported AFTER setting env vars above

    print(f"Source (SQLite):      {args.sqlite_path}")
    print(f"Destination (Postgres): {args.postgres_url.split('@')[-1]}")
    print()
    print("Creating schema on destination (safe if it already exists)...")
    db.init_db()

    total_rows = 0
    for table in db.ALL_TABLES_INSERT_ORDER:
        rows = _read_sqlite(args.sqlite_path, table)
        if not rows:
            print(f"  {table:<22} 0 rows (skipped)")
            continue
        for row in rows:
            cols = list(row.keys())
            placeholders = ",".join(["?"] * len(cols))
            col_list = ",".join(cols)
            try:
                db.execute(f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})",
                          tuple(row[c] for c in cols))
            except Exception as exc:
                print(f"\nERROR inserting into {table}: {exc}")
                print("Migration stopped - no further tables were touched after this point.")
                sys.exit(1)
        print(f"  {table:<22} {len(rows)} row(s) migrated")
        total_rows += len(rows)

    print()
    print(f"Done. {total_rows} total row(s) migrated into PostgreSQL.")
    print("The original SQLite file was not modified.")


if __name__ == "__main__":
    main()
