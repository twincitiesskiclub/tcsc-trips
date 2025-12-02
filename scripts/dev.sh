#!/bin/bash
# Development launch script - starts Stripe webhook listener and Flask app
# Usage: ./scripts/dev.sh

set -e

PORT=${1:-5001}

echo "Starting development environment on port $PORT..."

# Kill any existing processes on the port
lsof -ti:$PORT | xargs kill -9 2>/dev/null || true

# Start stripe listener in background and capture the secret
echo "Starting Stripe webhook listener..."
STRIPE_OUTPUT=$(mktemp)
stripe listen --forward-to localhost:$PORT/webhook > "$STRIPE_OUTPUT" 2>&1 &
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
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start Flask
echo "Starting Flask on port $PORT..."
echo "---"
echo "App: http://127.0.0.1:$PORT"
echo "Admin: http://127.0.0.1:$PORT/admin"
echo "---"

source env/bin/activate
STRIPE_WEBHOOK_SECRET="$WEBHOOK_SECRET" python3 -m flask run --port $PORT

# Cleanup on exit
cleanup
