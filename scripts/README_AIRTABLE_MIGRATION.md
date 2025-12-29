# Airtable to PostgreSQL Migration

This directory contains the one-time migration script to import practice management data from Airtable into the PostgreSQL database.

## Prerequisites

1. Ensure you have created and applied the practice management models migration:
   ```bash
   flask db upgrade
   ```

2. Install required dependency:
   ```bash
   pip install pyairtable>=2.0.0
   ```

## Running the Migration

The migration script is idempotent and can be safely run multiple times. It will skip any records that have already been migrated (based on the `airtable_id` field).

```bash
# From the project root directory
python scripts/migrate_from_airtable.py
```

## What Gets Migrated

The script migrates data in the following order (respecting dependencies):

1. **Social Locations** (post-practice venues)
   - Table: `tbltwcxQx5d7qJKMO`
   - Fields: Social Location, Address, Google Maps URL

2. **Practice Locations** (practice venues)
   - Table: `tbleGNQsPCcwtlhZj`
   - Fields: Practice Location, Spot, Address, Google Maps URL, Latitude, Longitude, Parking Notes
   - Links: Social Location

3. **Practice Activities** (e.g., Classic Skiing, Skate Skiing)
   - Table: `tblBajMjoN1EqFiYl`
   - Fields: Practice Activity, Gear Required

4. **Practice Types** (e.g., Intervals, Distance, Technique)
   - Table: `tblK4lagA1yX6wbw9`
   - Fields: Practice Type, Fitness Goals, Intervals flag

5. **People** (leads, coaches, assistants)
   - Table: `tbljS82sYfGoznkDY`
   - Fields: Short Name, Slack User ID, Email

6. **Practices** (the main practice records)
   - Table: `tblmWU89AWwJhgmUP`
   - Fields: Date, Day, Practice Activity, Practice Type, Practice Location, Warmup, Workout, Cooldown, Social, Darkness
   - Links: Practice Location, Practice Activities (multiple), Practice Types (multiple), Lead (multiple), Coach (multiple), Assist (multiple)

## Data Mapping

### Airtable → PostgreSQL Field Mapping

#### Social Locations
- `Social Location` → `name`
- `Address` → `address`
- `Google Maps URL` → `google_maps_url`
- Airtable record ID → `airtable_id`

#### Practice Locations
- `Practice Location` → `name`
- `Spot` → `spot`
- `Address` → `address`
- `Google Maps URL` → `google_maps_url`
- `Latitude` → `latitude`
- `Longitude` → `longitude`
- `Parking Notes` → `parking_notes`
- `Social Location` link → `social_location_id`
- Airtable record ID → `airtable_id`

#### Practice Activities
- `Practice Activity` → `name`
- `Gear Required` (multiline text) → `gear_required` (JSON array)
- Airtable record ID → `airtable_id`

#### Practice Types
- `Practice Type` → `name`
- `Fitness Goals` (multiline text) → `fitness_goals` (JSON array)
- `Intervals` (checkbox) → `has_intervals`
- Airtable record ID → `airtable_id`

#### People
- `Short Name` → `short_name`
- `Slack User ID` → `slack_user_id`
- `Email` → `email`
- Airtable record ID → `airtable_id`
- Note: `user_id` is left NULL for now (manual linking can be done later)

#### Practices
- `Date` → `date` (parsed as datetime)
- `Day` → `day_of_week`
- `Practice Location` link → `location_id`
- `Warmup` → `warmup_description`
- `Workout` → `workout_description`
- `Cooldown` → `cooldown_description`
- `Social` (checkbox) → `has_social`
- `Darkness` (checkbox) → `is_dark_practice`
- `Practice Activity` links → many-to-many via `practice_activities_junction`
- `Practice Type` links → many-to-many via `practice_types_junction`
- `Lead` links → `practice_leads` table with `role='lead'`
- `Coach` links → `practice_leads` table with `role='coach'`
- `Assist` links → `practice_leads` table with `role='assist'`
- Airtable record ID → `airtable_id`
- Default `status` → `'scheduled'`

## Idempotency

The script is designed to be idempotent:
- It checks for existing records by `airtable_id` before inserting
- Skipped records are logged with a message
- Only new records are created
- Safe to run multiple times (e.g., after adding new Airtable records)

## Credentials

The script uses these Airtable credentials (can be overridden via environment variables):

- **Base ID:** `appcCexUqENg9rvJt` (default, or set `AIRTABLE_BASE_ID`)
- **PAT:** `pato1T828JSeSAvxN...` (default, or set `AIRTABLE_PAT`)

## Post-Migration Tasks

After running the migration:

1. **Link PracticePerson to User records:**
   - The `user_id` field on `practice_people` is NULL for all migrated records
   - You can manually link people to User records by matching on email or Slack User ID
   - Example SQL:
     ```sql
     UPDATE practice_people pp
     SET user_id = u.id
     FROM users u
     WHERE pp.email = u.email AND pp.user_id IS NULL;
     ```

2. **Verify data:**
   - Check that all expected records were migrated
   - Review any skipped records (logged during migration)
   - Verify relationships (locations, activities, types, leads)

3. **Update practice statuses:**
   - All practices are migrated with `status='scheduled'`
   - Update statuses as needed for past/completed practices

## Troubleshooting

### Missing records
If some records are missing after migration:
- Check the console output for error messages
- Verify that the Airtable credentials are correct
- Ensure the table IDs match your Airtable base structure

### Relationship issues
If relationships aren't linking correctly:
- Ensure all dependency tables were migrated first (the script handles this order)
- Check that Airtable record IDs are consistent
- Review the console output for warnings about unresolved links

### Re-running after errors
If the migration fails partway through:
- The script is idempotent, so you can safely re-run it
- Already-migrated records will be skipped
- The migration will continue from where it left off
