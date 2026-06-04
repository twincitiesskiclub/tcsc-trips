"""Apply normalized activity/type names from curated CSVs.

Usage:
    python scripts/activities_types_apply.py                 # local, dry-run
    python scripts/activities_types_apply.py --commit        # local, write
    PROD_DATABASE_URL=... python scripts/activities_types_apply.py --prod --commit

Reads export_activities.csv / export_types.csv (with normalized_name filled in)
and updates PracticeActivity.name / PracticeType.name. Idempotent: re-running
with the same CSV is a no-op.
"""
import csv
import os
import sys

from app import create_app
from app.models import db
from app.practices.models import PracticeActivity, PracticeType


def _apply(model, path, commit):
    changed = 0
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            obj = db.session.get(model, int(row["id"]))
            if obj is None:
                print(f"  SKIP {model.__name__} id={row['id']} (not found)")
                continue
            new = (row["normalized_name"] or "").strip()
            if new and obj.name != new:
                print(f"  {model.__name__} {obj.id}: {obj.name!r} -> {new!r}")
                obj.name = new
                changed += 1
    return changed


def main():
    use_prod = "--prod" in sys.argv
    commit = "--commit" in sys.argv
    if use_prod:
        os.environ["DATABASE_URL"] = os.environ["PROD_DATABASE_URL"]
    app = create_app()
    with app.app_context():
        total = _apply(PracticeActivity, "export_activities.csv", commit)
        total += _apply(PracticeType, "export_types.csv", commit)
        if commit:
            db.session.commit()
            print(f"Committed {total} name change(s).")
        else:
            db.session.rollback()
            print(f"DRY RUN: {total} name change(s). Re-run with --commit to apply.")


if __name__ == "__main__":
    main()
