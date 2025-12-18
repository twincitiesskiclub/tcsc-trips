#!/bin/bash
# Release script for Render deployments
set -e

echo "=== Release tasks starting ==="
echo "Timestamp: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"

echo "Running database migrations..."
flask db upgrade

echo "=== Release tasks completed ==="
