#!/usr/bin/env python3
"""Link trip registrations made before a member's scholarship DM went out.

The trip form refuses a second registration on the same trip, so a member who
already held a spot can't enter their code. This marks the code as held/used
by that registration. It does not change the amount: refund the scholarship in
Stripe after the roster is captured.

Usage (dry run first, then --apply):
    TCSC_MIGRATION_ONLY=1 SLACK_APP_TOKEN= DATABASE_URL=$PROD_DATABASE_URL \\
        python scripts/link_scholarship_registrations.py 123 456
    ... python scripts/link_scholarship_registrations.py 123 456 --apply
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from app import create_app
from app.trips.scholarships import link_registrations


def main(argv):
    apply = "--apply" in argv
    ids = [int(arg) for arg in argv if arg != "--apply"]
    if not ids:
        print(__doc__)
        return 2
    with create_app().app_context():
        for line in link_registrations(ids, dry_run=not apply):
            print(line)
    if not apply:
        print("dry run, nothing written (pass --apply)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
