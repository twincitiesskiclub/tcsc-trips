#!/usr/bin/env python3
"""
One-time migration script to import practice data from Airtable to PostgreSQL.

This script:
1. Fetches all records from Airtable tables
2. Maps Airtable records to SQLAlchemy models
3. Handles relationships (resolves Airtable record links)
4. Inserts into PostgreSQL
5. Is idempotent (skips existing records based on airtable_id)

NOTE: The PracticePerson model has been deprecated and removed.
Practice leads are now linked directly to User records via user_id.
The migrate_people() and _link_practice_leads() methods are preserved
for reference but skip actual operations.

Usage:
    python scripts/migrate_from_airtable.py

Environment variables required:
    - AIRTABLE_PAT (Personal Access Token)
    - AIRTABLE_BASE_ID (optional, defaults to TCSC base)
"""

import sys
import os
import re
from datetime import datetime
from pyairtable import Api


def dms_to_decimal(dms_str):
    """Convert DMS (Degrees Minutes Seconds) to decimal degrees.

    Handles formats like:
    - 44°58'50.4"
    - 93°19'08.0"W
    - 44.9806667 (already decimal, returns as-is)

    Returns None if parsing fails.
    """
    if not dms_str:
        return None

    # If it's already a number, return it
    try:
        return float(dms_str)
    except (ValueError, TypeError):
        pass

    # Try to parse DMS format
    # Pattern: degrees°minutes'seconds"[direction]
    pattern = r"(\d+)[°](\d+)['\x27](\d+(?:\.\d+)?)[\"'\x22]?\s*([NSEW])?"
    match = re.match(pattern, str(dms_str).strip())

    if not match:
        print(f"  ! Warning: Could not parse coordinate: {dms_str}")
        return None

    degrees = float(match.group(1))
    minutes = float(match.group(2))
    seconds = float(match.group(3))
    direction = match.group(4)

    decimal = degrees + minutes / 60 + seconds / 3600

    # Make negative for South or West
    if direction in ('S', 'W'):
        decimal = -decimal

    return round(decimal, 7)

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.models import db
from app.practices.models import (
    SocialLocation,
    PracticeLocation,
    PracticeActivity,
    PracticeType,
    Practice,
    PracticeLead
)

# Airtable configuration
AIRTABLE_BASE_ID = os.environ.get('AIRTABLE_BASE_ID', 'appcCexUqENg9rvJt')
AIRTABLE_PAT = os.environ.get('AIRTABLE_PAT')

if not AIRTABLE_PAT:
    print("Error: AIRTABLE_PAT environment variable is required")
    print("Set it before running this script:")
    print("  export AIRTABLE_PAT=your_personal_access_token")
    sys.exit(1)

# Airtable table IDs
TABLES = {
    'practices': 'tblmWU89AWwJhgmUP',
    'practice_locations': 'tbleGNQsPCcwtlhZj',
    'social_locations': 'tbltwcxQx5d7qJKMO',
    'people': 'tbljS82sYfGoznkDY',
    'activities': 'tblBajMjoN1EqFiYl',
    'types': 'tblK4lagA1yX6wbw9',
}


class AirtableMigrator:
    """Migrate data from Airtable to PostgreSQL."""

    def __init__(self, app):
        self.app = app
        self.api = Api(AIRTABLE_PAT)
        self.base = self.api.base(AIRTABLE_BASE_ID)

        # Caches to map Airtable record IDs to database IDs
        self.social_location_map = {}
        self.practice_location_map = {}
        self.activity_map = {}
        self.type_map = {}
        self.person_map = {}
        self.practice_map = {}

    def run(self):
        """Execute the migration in the correct order."""
        with self.app.app_context():
            print("Starting Airtable migration...")

            # Migrate in dependency order
            self.migrate_social_locations()
            self.migrate_practice_locations()
            self.migrate_activities()
            self.migrate_types()
            self.migrate_people()
            self.migrate_practices()

            print("\nMigration complete!")

    def migrate_social_locations(self):
        """Migrate social locations (no dependencies)."""
        print("\n1. Migrating social locations...")
        table = self.base.table(TABLES['social_locations'])
        records = table.all()

        for record in records:
            airtable_id = record['id']
            fields = record['fields']

            # Skip if already migrated
            existing = SocialLocation.query.filter_by(airtable_id=airtable_id).first()
            if existing:
                self.social_location_map[airtable_id] = existing.id
                print(f"  - Skipping {fields.get('Social Location', 'Unknown')} (already exists)")
                continue

            location = SocialLocation(
                name=fields.get('Social Location', 'Unknown'),
                address=fields.get('Address'),
                google_maps_url=fields.get('Google Maps URL'),
                airtable_id=airtable_id
            )
            db.session.add(location)
            db.session.flush()

            self.social_location_map[airtable_id] = location.id
            print(f"  + Created {location.name}")

        db.session.commit()
        print(f"  Total: {len(records)} social locations")

    def migrate_practice_locations(self):
        """Migrate practice locations (depends on social locations)."""
        print("\n2. Migrating practice locations...")
        table = self.base.table(TABLES['practice_locations'])
        records = table.all()

        for record in records:
            airtable_id = record['id']
            fields = record['fields']

            # Skip if already migrated
            existing = PracticeLocation.query.filter_by(airtable_id=airtable_id).first()
            if existing:
                self.practice_location_map[airtable_id] = existing.id
                print(f"  - Skipping {fields.get('Practice Location', 'Unknown')} (already exists)")
                continue

            # Resolve social location link
            social_location_id = None
            social_links = fields.get('Social Location', [])
            if social_links and len(social_links) > 0:
                social_airtable_id = social_links[0]
                social_location_id = self.social_location_map.get(social_airtable_id)

            # Convert DMS coordinates to decimal
            lat_raw = fields.get('Latitude')
            lon_raw = fields.get('Longitude')
            latitude = dms_to_decimal(lat_raw)
            longitude = dms_to_decimal(lon_raw)

            location = PracticeLocation(
                name=fields.get('Practice Location', 'Unknown'),
                spot=fields.get('Spot'),
                address=fields.get('Address'),
                google_maps_url=fields.get('Google Maps URL'),
                latitude=latitude,
                longitude=longitude,
                parking_notes=fields.get('Parking Notes'),
                social_location_id=social_location_id,
                airtable_id=airtable_id
            )
            db.session.add(location)
            db.session.flush()

            self.practice_location_map[airtable_id] = location.id
            print(f"  + Created {location.name}")

        db.session.commit()
        print(f"  Total: {len(records)} practice locations")

    def migrate_activities(self):
        """Migrate practice activities (no dependencies)."""
        print("\n3. Migrating practice activities...")
        table = self.base.table(TABLES['activities'])
        records = table.all()

        for record in records:
            airtable_id = record['id']
            fields = record['fields']

            # Skip if already migrated
            existing = PracticeActivity.query.filter_by(airtable_id=airtable_id).first()
            if existing:
                self.activity_map[airtable_id] = existing.id
                print(f"  - Skipping {fields.get('Practice Activity', 'Unknown')} (already exists)")
                continue

            # Get the name, skip if empty/unknown
            # Airtable field is 'Activity' not 'Practice Activity'
            name = fields.get('Activity', '').strip()
            if not name:
                print(f"  ! Skipping record with empty name: {airtable_id}")
                continue

            # Check if name already exists (avoid duplicate constraint violation)
            existing_by_name = PracticeActivity.query.filter_by(name=name).first()
            if existing_by_name:
                self.activity_map[airtable_id] = existing_by_name.id
                print(f"  - Linking to existing {name}")
                continue

            # Parse gear required - Airtable field is 'Gear' (array)
            gear_required = []
            gear_text = fields.get('Gear', [])
            if isinstance(gear_text, str) and gear_text:
                gear_required = [g.strip() for g in gear_text.split('\n') if g.strip()]
            elif isinstance(gear_text, list):
                gear_required = gear_text

            activity = PracticeActivity(
                name=name,
                gear_required=gear_required,
                airtable_id=airtable_id
            )
            db.session.add(activity)
            db.session.flush()

            self.activity_map[airtable_id] = activity.id
            print(f"  + Created {activity.name}")

        db.session.commit()
        print(f"  Total: {len(records)} activities")

    def migrate_types(self):
        """Migrate practice types (no dependencies)."""
        print("\n4. Migrating practice types...")
        table = self.base.table(TABLES['types'])
        records = table.all()

        for record in records:
            airtable_id = record['id']
            fields = record['fields']

            # Skip if already migrated
            existing = PracticeType.query.filter_by(airtable_id=airtable_id).first()
            if existing:
                self.type_map[airtable_id] = existing.id
                print(f"  - Skipping {fields.get('Practice Type', 'Unknown')} (already exists)")
                continue

            # Get the name, skip if empty
            # Airtable field is 'Name' not 'Practice Type'
            name = fields.get('Name', '').strip()
            if not name:
                print(f"  ! Skipping record with empty name: {airtable_id}")
                continue

            # Check if name already exists
            existing_by_name = PracticeType.query.filter_by(name=name).first()
            if existing_by_name:
                self.type_map[airtable_id] = existing_by_name.id
                print(f"  - Linking to existing {name}")
                continue

            # Parse fitness goals - Airtable field is 'Fitness Goal' (array)
            fitness_goals = []
            goals_text = fields.get('Fitness Goal', [])
            if isinstance(goals_text, str) and goals_text:
                fitness_goals = [g.strip() for g in goals_text.split('\n') if g.strip()]
            elif isinstance(goals_text, list):
                fitness_goals = goals_text

            practice_type = PracticeType(
                name=name,
                fitness_goals=fitness_goals,
                has_intervals=fields.get('Intervals', False),
                airtable_id=airtable_id
            )
            db.session.add(practice_type)
            db.session.flush()

            self.type_map[airtable_id] = practice_type.id
            print(f"  + Created {practice_type.name}")

        db.session.commit()
        print(f"  Total: {len(records)} practice types")

    def migrate_people(self):
        """DEPRECATED: PracticePerson model has been removed.

        Practice leads are now linked directly to User records.
        This method is preserved for reference but does nothing.
        """
        print("\n5. Migrating people... SKIPPED (PracticePerson deprecated)")
        print("  Note: Practice leads should be linked to User records manually")

    def migrate_practices(self):
        """Migrate practices with all relationships."""
        print("\n6. Migrating practices...")
        table = self.base.table(TABLES['practices'])
        records = table.all()

        for record in records:
            airtable_id = record['id']
            fields = record['fields']

            # Skip if already migrated
            existing = Practice.query.filter_by(airtable_id=airtable_id).first()
            if existing:
                self.practice_map[airtable_id] = existing.id
                print(f"  - Skipping practice on {fields.get('Date', 'Unknown')} (already exists)")
                continue

            # Parse date
            date_str = fields.get('Date')
            if not date_str:
                print(f"  ! Skipping practice {airtable_id} (no date)")
                continue

            try:
                # Handle multiple date formats from Airtable
                if 'T' in date_str:
                    # ISO format: 2025-09-18T23:15:00.000Z
                    practice_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                else:
                    # Simple date: 2025-09-18
                    practice_date = datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                print(f"  ! Skipping practice {airtable_id} (invalid date: {date_str})")
                continue

            # Resolve location
            location_id = None
            location_links = fields.get('Practice Location', [])
            if location_links and len(location_links) > 0:
                location_airtable_id = location_links[0]
                location_id = self.practice_location_map.get(location_airtable_id)

            # Create practice
            practice = Practice(
                date=practice_date,
                day_of_week=fields.get('Day', practice_date.strftime('%A')),
                status='scheduled',  # Default status
                location_id=location_id,
                warmup_description=fields.get('Warmup'),
                workout_description=fields.get('Workout'),
                cooldown_description=fields.get('Cooldown'),
                has_social=fields.get('Social', False),
                is_dark_practice=fields.get('Darkness', False),
                airtable_id=airtable_id
            )
            db.session.add(practice)
            db.session.flush()

            self.practice_map[airtable_id] = practice.id

            # Link activities
            activity_links = fields.get('Practice Activity', [])
            for activity_airtable_id in activity_links:
                activity_id = self.activity_map.get(activity_airtable_id)
                if activity_id:
                    activity = PracticeActivity.query.get(activity_id)
                    if activity:
                        practice.activities.append(activity)

            # Link practice types
            type_links = fields.get('Practice Type', [])
            for type_airtable_id in type_links:
                type_id = self.type_map.get(type_airtable_id)
                if type_id:
                    practice_type = PracticeType.query.get(type_id)
                    if practice_type:
                        practice.practice_types.append(practice_type)

            # Link leads/coaches/assists
            self._link_practice_leads(practice, fields.get('Lead', []), 'lead')
            self._link_practice_leads(practice, fields.get('Coach', []), 'coach')
            self._link_practice_leads(practice, fields.get('Assist', []), 'assist')

            print(f"  + Created practice on {practice.date.strftime('%Y-%m-%d')}")

        db.session.commit()
        print(f"  Total: {len(records)} practices")

    def _link_practice_leads(self, practice, person_airtable_ids, role):
        """DEPRECATED: PracticePerson model has been removed.

        Practice leads should be linked to User records via user_id.
        This method is preserved for reference but does nothing.
        """
        # Skip - PracticePerson deprecated, leads should use user_id
        pass


def main():
    """Main entry point."""
    app = create_app()
    migrator = AirtableMigrator(app)

    try:
        migrator.run()
    except KeyboardInterrupt:
        print("\n\nMigration interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nError during migration: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
