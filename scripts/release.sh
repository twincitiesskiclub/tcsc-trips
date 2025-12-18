#!/bin/bash
# Release script for Render deployments
# Handles database migrations, including first-time setup

set -e

echo "=== Release tasks starting ==="
echo "Timestamp: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"

# Check if alembic_version table exists
echo "Checking migration status..."
if ! flask db current 2>/dev/null | grep -q "Rev:"; then
    echo "WARNING: No alembic_version table found."
    echo "This usually means the database was set up outside the migration system."
    echo "Stamping database with current head revision..."

    # Get the current head revision and stamp to it
    # This assumes the database schema is already up-to-date
    HEAD_REV=$(flask db heads 2>/dev/null | grep -oE '^[a-f0-9]+' | head -1)
    if [ -n "$HEAD_REV" ]; then
        echo "Stamping to head revision: $HEAD_REV"
        flask db stamp "$HEAD_REV"
    else
        echo "ERROR: Could not determine head revision"
        exit 1
    fi
else
    CURRENT_REV=$(flask db current 2>/dev/null | grep -oE '[a-f0-9]+' | head -1)
    echo "Current migration revision: $CURRENT_REV"
fi

echo "Running database migrations..."
flask db upgrade

FINAL_REV=$(flask db current 2>/dev/null | grep -oE '[a-f0-9]+' | head -1)
echo "Final migration revision: $FINAL_REV"

echo "=== Release tasks completed ==="
