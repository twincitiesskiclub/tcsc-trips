"""Export current practice activity + type names to CSV for normalization review.

Usage:
    python scripts/activities_types_export.py            # uses DATABASE_URL (local)
    PROD_DATABASE_URL=... python scripts/activities_types_export.py --prod

Writes export_activities.csv and export_types.csv with current names so they
can be curated into display-ready forms before scripts/activities_types_apply.py.
"""
import csv
import os
import sys

from dotenv import load_dotenv

from app import create_app
from app.models import db
from app.practices.models import PracticeActivity, PracticeType


def main():
    load_dotenv()
    use_prod = "--prod" in sys.argv
    if use_prod:
        prod_url = os.environ.get("PROD_DATABASE_URL")
        if not prod_url:
            raise SystemExit("PROD_DATABASE_URL not set - add it to .env")
        os.environ["DATABASE_URL"] = prod_url
    app = create_app()
    with app.app_context():
        with open("export_activities.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["id", "current_name", "normalized_name"])
            for a in db.session.query(PracticeActivity).order_by(PracticeActivity.id):
                w.writerow([a.id, a.name, a.name])
        with open("export_types.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["id", "current_name", "normalized_name"])
            for t in db.session.query(PracticeType).order_by(PracticeType.id):
                w.writerow([t.id, t.name, t.name])
    print("Wrote export_activities.csv and export_types.csv")


if __name__ == "__main__":
    main()
