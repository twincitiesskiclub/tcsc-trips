#!/bin/bash
# Development launch script - starts Stripe webhook listener and Flask app
# Usage: ./scripts/dev.sh [port] [--sqlite]
#
# Options:
#   port      Port to run Flask on (default: 5001)
#   --sqlite  Use SQLite instead of PostgreSQL (for quick local testing)
#
# Examples:
#   ./scripts/dev.sh              # PostgreSQL on port 5001 (default)
#   ./scripts/dev.sh 5000         # PostgreSQL on port 5000
#   ./scripts/dev.sh --sqlite     # SQLite on port 5001
#   ./scripts/dev.sh 5000 --sqlite  # SQLite on port 5000

set -e

# Parse arguments
PORT=5001
USE_SQLITE=false

for arg in "$@"; do
    case $arg in
        --sqlite)
            USE_SQLITE=true
            ;;
        *)
            if [[ $arg =~ ^[0-9]+$ ]]; then
                PORT=$arg
            fi
            ;;
    esac
done

CONTAINER_NAME="tcsc-postgres"
POSTGRES_USER="tcsc"
POSTGRES_PASSWORD="tcsc"
POSTGRES_DB="tcsc_trips"
DATABASE_URL="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:5432/${POSTGRES_DB}"

echo "Starting development environment on port $PORT..."

# Kill any existing processes on the port
lsof -ti:$PORT | xargs kill -9 2>/dev/null || true

# Database setup
if [ "$USE_SQLITE" = true ]; then
    echo "Using SQLite (--sqlite flag)"
else
    echo "Setting up local PostgreSQL..."

    # Check if Docker is running
    if ! docker info > /dev/null 2>&1; then
        echo "Error: Docker is not running. Please start Docker Desktop."
        echo "Or use --sqlite flag to run with SQLite instead."
        exit 1
    fi

    # Check if container exists
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        # Container exists, check if it's running
        if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
            echo "PostgreSQL container already running"
        else
            echo "Starting existing PostgreSQL container..."
            docker start $CONTAINER_NAME
        fi
    else
        # Create new container
        echo "Creating PostgreSQL container..."
        docker run -d \
            --name $CONTAINER_NAME \
            -e POSTGRES_USER=$POSTGRES_USER \
            -e POSTGRES_PASSWORD=$POSTGRES_PASSWORD \
            -e POSTGRES_DB=$POSTGRES_DB \
            -p 5432:5432 \
            postgres:18
    fi

    # Wait for PostgreSQL to be ready
    echo "Waiting for PostgreSQL to be ready..."
    for i in {1..30}; do
        if docker exec $CONTAINER_NAME pg_isready -U $POSTGRES_USER > /dev/null 2>&1; then
            echo "PostgreSQL is ready!"
            break
        fi
        if [ $i -eq 30 ]; then
            echo "Error: PostgreSQL failed to start"
            exit 1
        fi
        sleep 1
    done

    # Check if database has data
    source env/bin/activate
    TABLE_COUNT=$(DATABASE_URL="$DATABASE_URL" python3 -c "
from app import create_app
from app.models import db
app = create_app()
with app.app_context():
    result = db.session.execute(db.text(\"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'\"))
    print(result.scalar())
" 2>/dev/null || echo "0")

    if [ "$TABLE_COUNT" -lt 5 ]; then
        echo "Database empty - running migration from SQLite..."
        if [ -f "app.db" ]; then
            DATABASE_URL="$DATABASE_URL" SQLITE_PATH="./app.db" python scripts/migrate_to_postgres.py
        else
            echo "Warning: No app.db found. Creating empty tables..."
            DATABASE_URL="$DATABASE_URL" flask db upgrade
        fi
    else
        echo "Database already has data ($TABLE_COUNT tables)"
    fi

    export DATABASE_URL
    echo "Using PostgreSQL: $DATABASE_URL"
fi

# Start stripe listener in background and capture the secret
echo "Starting Stripe webhook listener..."
STRIPE_OUTPUT=$(mktemp)
stripe listen --forward-to 127.0.0.1:$PORT/webhook > "$STRIPE_OUTPUT" 2>&1 &
STRIPE_PID=$!

# Wait for stripe to output the secret
sleep 3

# Extract the webhook secret from stripe output
WEBHOOK_SECRET=$(grep -o 'whsec_[a-zA-Z0-9]*' "$STRIPE_OUTPUT" | head -1)

if [ -z "$WEBHOOK_SECRET" ]; then
    echo "Error: Could not get webhook secret from Stripe"
    kill $STRIPE_PID 2>/dev/null || true
    rm "$STRIPE_OUTPUT"
    exit 1
fi

echo "Got webhook secret: ${WEBHOOK_SECRET:0:20}..."

# Update .env file with the new secret
if grep -q "STRIPE_WEBHOOK_SECRET=" .env 2>/dev/null; then
    sed -i '' "s|STRIPE_WEBHOOK_SECRET=.*|STRIPE_WEBHOOK_SECRET=$WEBHOOK_SECRET|" .env
else
    echo "STRIPE_WEBHOOK_SECRET=$WEBHOOK_SECRET" >> .env
fi

echo "Updated .env with webhook secret"

# Export the secret so Flask picks it up (overrides .env)
export STRIPE_WEBHOOK_SECRET="$WEBHOOK_SECRET"

# Tail the stripe output in background
tail -f "$STRIPE_OUTPUT" &
TAIL_PID=$!

# Cleanup function
cleanup() {
    echo ""
    echo "Shutting down..."
    kill $STRIPE_PID 2>/dev/null || true
    kill $TAIL_PID 2>/dev/null || true
    rm "$STRIPE_OUTPUT" 2>/dev/null || true
    # Note: We don't stop the PostgreSQL container so data persists
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start Flask
echo "Starting Flask on port $PORT..."
echo "---"
echo "App: http://127.0.0.1:$PORT"
echo "Admin: http://127.0.0.1:$PORT/admin"
if [ "$USE_SQLITE" = true ]; then
    echo "Database: SQLite"
else
    echo "Database: PostgreSQL (local Docker)"
    echo "Stop PostgreSQL: docker stop $CONTAINER_NAME"
    echo "Reset PostgreSQL: docker rm -f $CONTAINER_NAME"
fi
echo "---"

source env/bin/activate
STRIPE_WEBHOOK_SECRET="$WEBHOOK_SECRET" python3 -m flask run --port $PORT

# Cleanup on exit
cleanup
