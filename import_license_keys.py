"""
import_license_keys.py
SN COACHING MANAGEMENT SYSTEM

Loads the keys from license_keys_batch.json into this app's own
database (data/sn_coaching.db) so they become valid to activate from
the Licence Management screen. Safe to run more than once — existing
keys are skipped, never overwritten.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import database as db

BATCH_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "license_keys_batch.json")


def main():
    if not os.path.exists(BATCH_FILE):
        print(f"[ERROR] Could not find {BATCH_FILE}")
        return

    with open(BATCH_FILE) as f:
        data = json.load(f)

    db.init_db()

    added, skipped = 0, 0
    for plan, keys in data.items():
        for key in keys:
            existing = db.query_one("SELECT licence_key FROM licence_keys WHERE licence_key = ?", (key,))
            if existing:
                skipped += 1
                continue
            db.execute(
                "INSERT INTO licence_keys (licence_key, plan, is_used) VALUES (?, ?, 0)",
                (key, plan),
            )
            added += 1

    print(f"Done. {added} new key(s) loaded, {skipped} already present and skipped.")


if __name__ == "__main__":
    main()
