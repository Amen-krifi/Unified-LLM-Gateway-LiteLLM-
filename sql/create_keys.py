import json
import os
import sys

import psycopg2
import requests

DATABASE_URL = os.environ.get("DATABASE_URL")
GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://localhost:4000")
MASTER_KEY = os.environ.get("LITELLM_MASTER_KEY")
DRY_RUN = "--dry-run" in sys.argv


def load_departments():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT name, monthly_budget_usd, rpm_limit, tpm_limit "
                "FROM departments ORDER BY id"
            )
            return cur.fetchall()
    finally:
        conn.close()


def main():
    if not DATABASE_URL:
        sys.exit("Set DATABASE_URL first.")
    if not DRY_RUN and not MASTER_KEY:
        sys.exit("Set LITELLM_MASTER_KEY first (or use --dry-run).")

    keys = {}
    for name, budget, rpm, tpm in load_departments():
        payload = {
            "key_alias": f"dept-{name.lower()}",
            "max_budget": float(budget),
            "budget_duration": "30d",
            "rpm_limit": rpm,
            "tpm_limit": tpm,
            "metadata": {"department": name},
        }
        if DRY_RUN:
            print(name, "->", json.dumps(payload))
            continue
        response = requests.post(
            f"{GATEWAY_URL}/key/generate",
            headers={"Authorization": f"Bearer {MASTER_KEY}"},
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        keys[name] = response.json()["key"]
        print(f"{name}: key created")

    if keys:
        with open("keys.json", "w") as f:
            json.dump(keys, f, indent=2)
        print("Keys saved in keys.json (never commit this file).")


if __name__ == "__main__":
    main()