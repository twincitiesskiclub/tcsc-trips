#!/usr/bin/env python3
"""Add PRACTICES_LEAD tag to specified users.

Usage:
    python scripts/add_practice_leads.py          # Dry run (default)
    python scripts/add_practice_leads.py --commit # Actually make changes
"""

import os
import sys
from dotenv import load_dotenv

# Load .env first to get other config
load_dotenv()

# Override DATABASE_URL with production database
PROD_DB_URL = "postgresql://heidi:c1y7XzSne5jVDEOVRBy4ODUoHWDJv8jK@dpg-d4nrbauuk2gs73frosqg-a.oregon-postgres.render.com/tcsc_trips_db_6k97"
os.environ['DATABASE_URL'] = PROD_DB_URL

from app import create_app
from app.models import db, User, Tag, UserTag

# 59 practice lead email addresses
EMAILS = [
    "aeklein6@gmail.com",
    "allin.lauren@gmail.com",
    "anisa.lester@gmail.com",
    "annapmeyer@duck.com",
    "anthonycotter4@gmail.com",
    "audgrussell@gmail.com",
    "augiewitski@gmail.com",
    "brian.tang@aya.yale.edu",
    "camdensikes@proton.me",
    "carolinebehlinghess@gmail.com",
    "cdkorby@gmail.com",
    "cvcccell@gmail.com",
    "daisyrichmond714@gmail.com",
    "danielle.ungurian@gmail.com",
    "deanjac99@gmail.com",
    "emily.culver96@gmail.com",
    "emma.l.schneider@gmail.com",
    "emmakeiski@gmail.com",
    "ericwurst1@gmail.com",
    "frenier.chris@gmail.com",
    "gjhaire17@gmail.com",
    "graceneumiller@gmail.com",
    "gunnarmaples@gmail.com",
    "hardtwill@gmail.com",
    "harringtonj21@gmail.com",
    "holmes717@gmail.com",
    "hrdelker@gmail.com",
    "jaco1560@umn.edu",
    "jehauch@gmail.com",
    "jrebischke@gmail.com",
    "jsbransky@gmail.com",
    "jul.a.reich@gmail.com",
    "kaogrady18@gmail.com",
    "kellekat002@gmail.com",
    "kjskierrunner@gmail.com",
    "klein.henry97@gmail.com",
    "knerczuk@gmail.com",
    "kohl.evan@gmail.com",
    "kristine919@q.com",
    "lund0999@gmail.com",
    "matthewland0798@gmail.com",
    "mberg1503@gmail.com",
    "mnjohnson@q.com",
    "nalexlgude@gmail.com",
    "nathanaorf@gmail.com",
    "nelsethompson@gmail.com",
    "nicholas.m.richards@outlook.com",
    "oggage@comcast.net",
    "olivia.fox0224@gmail.com",
    "p8052s@gmail.com",
    "rebecca.kolstad@finnsisu.com",
    "robrutscher@gmail.com",
    "ryanjrogers70@gmail.com",
    "samuel.abegglen@gmail.com",
    "sarahmwall2@gmail.com",
    "simonpeterson76@gmail.com",
    "sophiaweiss1@gmail.com",
    "tylergregory23@outlook.com",
    "vanmiegheml@yahoo.com",
]


def main():
    dry_run = '--commit' not in sys.argv

    if dry_run:
        print("=== DRY RUN MODE (use --commit to apply changes) ===\n")
    else:
        print("=== COMMIT MODE - Changes will be saved ===\n")

    app = create_app()
    with app.app_context():
        # Find PRACTICES_LEAD tag
        tag = Tag.query.filter_by(name='PRACTICES_LEAD').first()
        if not tag:
            print("ERROR: PRACTICES_LEAD tag not found in database")
            sys.exit(1)

        print(f"Found tag: {tag.display_name} (id={tag.id})\n")

        stats = {'added': 0, 'already_has': 0, 'not_found': 0}

        # Process each email
        for email in EMAILS:
            email_lower = email.strip().lower()
            user = User.get_by_email(email_lower)

            if not user:
                print(f"NOT FOUND: {email}")
                stats['not_found'] += 1
                continue

            # Check if user already has tag
            existing = UserTag.query.filter_by(
                user_id=user.id, tag_id=tag.id
            ).first()

            if existing:
                print(f"ALREADY HAS TAG: {email} ({user.first_name} {user.last_name})")
                stats['already_has'] += 1
                continue

            # Add tag
            if not dry_run:
                user_tag = UserTag(user_id=user.id, tag_id=tag.id)
                db.session.add(user_tag)

            print(f"ADDED: {email} ({user.first_name} {user.last_name})")
            stats['added'] += 1

        # Commit if not dry run
        if not dry_run:
            db.session.commit()

        # Print summary
        print(f"\n{'=' * 50}")
        print(f"SUMMARY:")
        print(f"  Added:        {stats['added']}")
        print(f"  Already had:  {stats['already_has']}")
        print(f"  Not found:    {stats['not_found']}")
        print(f"  Total emails: {len(EMAILS)}")

        if dry_run:
            print(f"\n[DRY RUN - no changes made. Use --commit to apply]")
        else:
            print(f"\nChanges committed to database!")


if __name__ == '__main__':
    main()
