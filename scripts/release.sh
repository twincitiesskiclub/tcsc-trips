#!/bin/bash
# Release script for Render deployments
set -e

echo "=== Release tasks starting ==="
echo "Timestamp: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"

echo "Running database migrations..."
env \
  TCSC_MIGRATION_ONLY=1 \
  SLACK_BOT_TOKEN= \
  SLACK_APP_TOKEN= \
  SLACK_SIGNING_SECRET= \
  flask db upgrade

echo "=== Release tasks completed ==="
