#!/usr/bin/env python3
"""
Migrate data from SQLite to PostgreSQL.

Usage:
    1. Set DATABASE_URL to point to the target PostgreSQL database
    2. Set SQLITE_PATH to the SQLite database file (default: /var/lib/app.db)
    3. Run: python scripts/migrate_to_postgres.py

The script will:
    1. Create all tables in PostgreSQL using SQLAlchemy
    2. Read all data from SQLite
    3. Insert data into PostgreSQL, preserving IDs and relationships
    4. Reset PostgreSQL sequences to avoid ID conflicts
"""

import os
import sys
import sqlite3

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app import create_app
from app.models import (
    db, Payment, Trip, SlackUser, User, Season, UserSeason,
    Role, UserRole, Committee, UserCommittee, StatusChange
)


def get_sqlite_connection(sqlite_path):
    """Connect to SQLite database."""
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    return conn


def get_table_columns(sqlite_conn, table_name):
    """Get column names for a table."""
    cursor = sqlite_conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    return [row[1] for row in cursor.fetchall()]


def migrate_table(sqlite_conn, pg_session, table_name, model_class):
    """
    Migrate a single table from SQLite to PostgreSQL.

    Args:
        sqlite_conn: SQLite connection
        pg_session: PostgreSQL session
        table_name: Name of the table
        model_class: SQLAlchemy model class
    """
    cursor = sqlite_conn.cursor()
    cursor.execute(f"SELECT * FROM {table_name}")
    rows = cursor.fetchall()

    if not rows:
        print(f"  {table_name}: 0 rows (empty)")
        return 0

    columns = [description[0] for description in cursor.description]

    count = 0
    for row in rows:
        data = dict(zip(columns, row))
        # Create model instance
        instance = model_class(**data)
        pg_session.merge(instance)  # merge to handle existing records
        count += 1

    print(f"  {table_name}: {count} rows migrated")
    return count


def reset_sequences(pg_engine, table_sequences):
    """
    Reset PostgreSQL sequences to max(id) + 1 for each table.

    This prevents ID conflicts when inserting new records after migration.
    """
    with pg_engine.connect() as conn:
        for table_name, sequence_name in table_sequences.items():
            result = conn.execute(text(f"SELECT MAX(id) FROM {table_name}"))
            max_id = result.scalar() or 0
            conn.execute(text(f"SELECT setval('{sequence_name}', {max_id + 1}, false)"))
        conn.commit()
    print("  Sequences reset successfully")


def verify_counts(sqlite_conn, pg_session):
    """Verify row counts match between SQLite and PostgreSQL."""
    tables = [
        ('roles', Role),
        ('committees', Committee),
        ('seasons', Season),
        ('trips', Trip),
        ('slack_users', SlackUser),
        ('users', User),
        ('payments', Payment),
        ('user_seasons', UserSeason),
        ('user_roles', UserRole),
        ('user_committees', UserCommittee),
        ('status_changes', StatusChange),
    ]

    print("\nVerifying row counts:")
    all_match = True
    for table_name, model_class in tables:
        cursor = sqlite_conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        sqlite_count = cursor.fetchone()[0]

        pg_count = pg_session.query(model_class).count()

        status = "OK" if sqlite_count == pg_count else "MISMATCH"
        if sqlite_count != pg_count:
            all_match = False
        print(f"  {table_name}: SQLite={sqlite_count}, PostgreSQL={pg_count} [{status}]")

    return all_match


def main():
    # Configuration
    sqlite_path = os.getenv('SQLITE_PATH', '/var/lib/app.db')
    database_url = os.getenv('DATABASE_URL')

    if not database_url:
        print("ERROR: DATABASE_URL environment variable must be set")
        sys.exit(1)

    if not os.path.exists(sqlite_path):
        print(f"ERROR: SQLite database not found at {sqlite_path}")
        sys.exit(1)

    # Fix Render's postgres:// URL
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)

    print(f"Source: {sqlite_path}")
    print(f"Target: {database_url.split('@')[1] if '@' in database_url else 'PostgreSQL'}")
    print()

    # Connect to SQLite
    print("Connecting to SQLite...")
    sqlite_conn = get_sqlite_connection(sqlite_path)

    # Create Flask app with PostgreSQL
    print("Initializing Flask app with PostgreSQL...")
    os.environ['DATABASE_URL'] = database_url
    app = create_app('production')

    with app.app_context():
        # Create tables in PostgreSQL
        print("Creating tables in PostgreSQL...")
        db.create_all()

        # Migration order matters due to foreign keys
        print("\nMigrating data...")

        # Tables without foreign keys first
        migrate_table(sqlite_conn, db.session, 'roles', Role)
        migrate_table(sqlite_conn, db.session, 'committees', Committee)
        migrate_table(sqlite_conn, db.session, 'seasons', Season)
        migrate_table(sqlite_conn, db.session, 'trips', Trip)
        migrate_table(sqlite_conn, db.session, 'slack_users', SlackUser)

        # Commit independent tables
        db.session.commit()

        # Tables with foreign keys
        migrate_table(sqlite_conn, db.session, 'users', User)
        db.session.commit()

        migrate_table(sqlite_conn, db.session, 'payments', Payment)
        migrate_table(sqlite_conn, db.session, 'user_seasons', UserSeason)
        migrate_table(sqlite_conn, db.session, 'user_roles', UserRole)
        migrate_table(sqlite_conn, db.session, 'user_committees', UserCommittee)
        migrate_table(sqlite_conn, db.session, 'status_changes', StatusChange)

        # Final commit
        db.session.commit()

        # Reset sequences for tables with auto-increment IDs
        print("\nResetting PostgreSQL sequences...")
        table_sequences = {
            'payments': 'payments_id_seq',
            'trips': 'trips_id_seq',
            'slack_users': 'slack_users_id_seq',
            'users': 'users_id_seq',
            'seasons': 'seasons_id_seq',
            'roles': 'roles_id_seq',
            'committees': 'committees_id_seq',
            'status_changes': 'status_changes_id_seq',
        }
        reset_sequences(db.engine, table_sequences)

        # Verify migration
        if verify_counts(sqlite_conn, db.session):
            print("\nMigration completed successfully! All counts match.")
        else:
            print("\nWARNING: Some row counts don't match. Please investigate.")

    sqlite_conn.close()


if __name__ == '__main__':
    main()
