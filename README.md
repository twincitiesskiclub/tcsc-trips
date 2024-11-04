# Setup local environment

## Requirements

- Python 3
- [Configured .env file](../README.md)

## How to run

1. Create and activate a new virtual environment

**MacOS / Unix**

```
python3 -m venv env
source env/bin/activate
```

**Windows (PowerShell)**

```
python3 -m venv env
.\env\Scripts\activate.bat
```

2. Install dependencies

```
pip install -r requirements.txt
```

3. Export and run the application

**MacOS / Unix**

```
export FLASK_APP=app.py
python3 -m flask run
```

**Windows (PowerShell)**

```
$env:FLASK_APP=“app.py"
python3 -m flask run
```

4. Go to `localhost:5000` in your browser to see the site. 

# TODO

## Database Implementation
- Implement PostgreSQL/SQLite database for user and trip management
  - Schema:
    ```sql
    payments (
      id,
      payment_intent_id,
      email,
      name,
      amount,
      status,
      trip_id,
      created_at,
      updated_at
    )

    trips (
      id,
      name,
      max_participants,
      registration_start_date,
      registration_end_date,
      created_at,
      updated_at
    )
    ```

## Trip Management
- Implement trip information source
  - Option: Google Sheets integration as source of truth
  - Sync mechanism during build process
  - Managed by trips coordinator
- Add configurable participant limit per trip
- Add registration deadline functionality

## Payment Processing
- Implement Stripe API integration
  - Payment processing for successful lottery selections
  - Automated refund system for unsuccessful entries
  - Webhook handling for payment status updates

## Slack Integration
- Implement Slack workspace sync
  - Channel existence verification
  - Automatic channel addition for selected participants
  - Email to Slack user correlation
  - Notification system for lottery results

## Lottery System
- Implement fair selection process
  - Random selection from qualified registrants
  - Priority handling for auto-selected members (trips team)
  - Automated workflow:
    1. Run lottery selection
    2. Process payments for selected participants
    3. Handle Slack channel additions
    4. Process refunds for unselected participants
    5. Send notification emails

## Admin Interface
- Create protected admin dashboard
  - Implementation options:
    1. IP allowlist for basic protection
  - Features:
    - Trip management
    - User management


