# scripts/ui_audit/survey_prod.py
"""Read production for orientation only -- counts and enum distributions.

No rows, no identifying values, nothing written to disk beyond aggregates.
The output tells the seed script which surfaces need to be populated and at
what volume so no admin pane renders empty during capture.

Usage:
    .venv-linux/bin/python -m scripts.ui_audit.survey_prod
"""

import json
import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

REPO = Path(__file__).resolve().parents[2]
load_dotenv(REPO / ".env")

TABLES = [
    "users", "seasons", "user_seasons", "payments", "trips", "tags", "user_tags",
    "events", "event_registrations", "event_price_options", "event_participants",
    "practices", "practice_leads", "practice_rsvps", "practice_locations",
    "practice_activities", "practice_types", "cancellation_requests",
    "newsletters", "newsletter_prompts", "newsletter_submissions",
    "lead_availability_polls", "lead_availability_responses",
    "slack_users", "status_changes",
]

ENUM_COLUMNS = [
    ("users", "status"),
    ("user_seasons", "status"),
    ("payments", "status"),
    ("payments", "payment_type"),
    ("trips", "status"),
    ("events", "status"),
    ("event_registrations", "status"),
    ("practices", "status"),
]


def main() -> None:
    url = os.environ["PROD_DATABASE_URL"]
    out = {"row_counts": {}, "enums": {}}

    with psycopg2.connect(url, connect_timeout=20, sslmode="require") as conn:
        conn.set_session(readonly=True)
        with conn.cursor() as cur:
            for table in TABLES:
                try:
                    cur.execute(f'SELECT count(*) FROM "{table}"')
                    out["row_counts"][table] = cur.fetchone()[0]
                except psycopg2.Error:
                    conn.rollback()
                    out["row_counts"][table] = None  # table absent in prod

            for table, column in ENUM_COLUMNS:
                try:
                    cur.execute(
                        f'SELECT "{column}", count(*) FROM "{table}" GROUP BY 1 ORDER BY 2 DESC'
                    )
                    out["enums"][f"{table}.{column}"] = {
                        str(row[0]): row[1] for row in cur.fetchall()
                    }
                except psycopg2.Error:
                    conn.rollback()
                    out["enums"][f"{table}.{column}"] = None

    dest = REPO / ".ui-audit" / "prod-shape.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=2, sort_keys=True))
    print(f"wrote {dest}")
    print(json.dumps(out["row_counts"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
