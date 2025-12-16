#!/bin/bash
# Release script for Render deployments
# Handles database migrations, including first-time setup

set -e

echo "Running release tasks..."

# Check if alembic_version table exists
if ! flask db current 2>/dev/null | grep -q "Rev:"; then
    echo "No alembic_version table found. Stamping database to current state..."
    # Stamp to the migration before social_events (the last migration that was applied manually)
    flask db stamp d0b36a24fc23
fi

echo "Running database migrations..."
flask db upgrade

echo "Release tasks completed."
