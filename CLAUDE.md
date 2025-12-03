# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Environment Setup

### Local Development

**Requirements:**
- Python 3.12+ (see `runtime.txt`)
- Docker (for local PostgreSQL)
- Stripe CLI (for webhook testing)

1. Create and activate virtual environment:
   ```bash
   python3 -m venv env
   source env/bin/activate  # macOS/Unix
   # or .\env\Scripts\activate.bat  # Windows
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure environment:
   - Copy `.env.example` to `.env`
   - Fill in Stripe API keys and Google OAuth credentials

4. Run the development server:
   ```bash
   ./scripts/dev.sh              # PostgreSQL on port 5001 (default)
   ./scripts/dev.sh 5000         # PostgreSQL on port 5000
   ./scripts/dev.sh --sqlite     # SQLite for quick testing (no Docker)
   ```

   On first run with PostgreSQL, the script will:
   - Pull and start a PostgreSQL 18 container (`tcsc-postgres`)
   - Migrate data from `app.db` (if present) or create empty tables

### Managing Local PostgreSQL

```bash
docker stop tcsc-postgres     # Stop the container (data persists)
docker start tcsc-postgres    # Restart it
docker rm -f tcsc-postgres    # Delete container and reset data
```

### Stripe Webhook Testing
The `dev.sh` script automatically handles webhook configuration. It:
- Starts Stripe webhook listener
- Extracts and sets `STRIPE_WEBHOOK_SECRET` in `.env`
- Launches Flask with the correct environment

**Manual method** (if needed separately):
```bash
stripe listen --forward-to localhost:5000/webhook
```
This provides a webhook signing secret (`whsec_...`) to set as `STRIPE_WEBHOOK_SECRET`.

### Database Management
- **Local Development:** PostgreSQL via Docker (default) or SQLite (`--sqlite` flag)
- **Production:** PostgreSQL on Render (via `DATABASE_URL` env var)
- **Create New Migration:** `flask db migrate -m "description"`
- **Apply Migrations:** `flask db upgrade`
- **Migration Files:** Located in `migrations/versions/`

### Helper Scripts
- `scripts/dev.sh` - **Recommended** dev startup (PostgreSQL + Stripe + Flask)
- `scripts/migrate_to_postgres.py` - Migrate data from SQLite to PostgreSQL
- `scripts/seed_former_members.py` - Import CSV of former members (sets status='inactive')
- `scripts/seed_former_member_season.py` - Create legacy season linking inactive users

## Architecture Overview

### Application Structure
This is a Flask web application for the Twin Cities Ski Club (TCSC) trip and membership registration system.

**Core Components:**
- **Flask Application Factory:** `app/__init__.py` creates and configures the Flask app
- **Route Blueprints:** Organized in `app/routes/` directory:
  - `main.py` - Homepage and public trip listings
  - `trips.py` - Individual trip registration pages  
  - `payments.py` - Payment processing (Stripe integration)
  - `admin.py` - Admin dashboard and management
  - `auth.py` - Google OAuth authentication
  - `registration.py` - Membership registration forms

**Database Models (`app/models.py`):**
- **Trip:** Ski trip details, pricing, capacity, signup windows
- **Payment:** Stripe payment intents, amounts, statuses, payment type (trip or season)
- **User:** Member profiles with extensive personal information
- **Season:** Membership seasons with registration windows
- **UserSeason:** Many-to-many relationship between users and seasons

### Authentication & Security
- **Admin Access:** Restricted to `@twincitiesskiclub.org` email addresses via Google OAuth
- **Public Access:** Trip registration and membership signup (no authentication required)
- **Payment Security:** Stripe Payment Intents with manual capture (authorization holds)
- **Finance Authorization:** Payment amounts visible only to authorized finance admins (`FINANCE_AUTHORIZED_EMAILS`)

### Admin Interface
The admin dashboard (`/admin`) provides:
- **Tabulator.js Data Grids:** Interactive spreadsheet-style views for Members and Payments
- **Bulk Payment Actions:** Accept (capture) or refund multiple payments at once
- **CSV Export:** Export member and payment data
- **Toast Notifications:** Real-time feedback for admin actions

**Key Admin Static Files:**
- `app/static/admin_users.js` - Member management grid
- `app/static/admin_payments.js` - Payment management grid

### Admin API Endpoints
- `GET /admin/payments/data` - JSON payment data for Tabulator grid
- `POST /admin/payments/bulk-capture` - Capture multiple payment intents
- `POST /admin/payments/bulk-refund` - Refund multiple payments
- `GET /admin/users/data` - JSON user data for Tabulator grid

### Payment Flow Architecture
**Two-tier capture system based on member type:**
- **New Members:** `capture_method='manual'` - card authorized but not charged (lottery system)
- **Returning Members:** `capture_method='automatic'` - card charged immediately

**Payment lifecycle:**
1. **Authorization:** Payment intent created, card validated
2. **Hold Placement:** New members have funds held pending lottery
3. **Manual Capture:** Admins capture payments for lottery-selected new members
4. **Refund/Cancel:** Refund captured payments OR cancel uncaptured authorizations

**Member type determination:** Server-side via `User.is_returning` property (checks for any ACTIVE UserSeason in past seasons)

### Key Integrations
- **Stripe API:** Payment processing, webhooks, refunds
- **Google OAuth:** Admin authentication via Authlib
- **Flask-Migrate:** Database schema versioning with Alembic
- **SQLAlchemy:** ORM with PostgreSQL (production) and SQLite (optional local)

## Configuration

### Environment Variables Required
Check `.env.example` for complete list. Critical variables include:
- `FLASK_SECRET_KEY` - Flask session security
- `STRIPE_PUBLISHABLE_KEY` / `STRIPE_SECRET_KEY` - Payment processing
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` - Admin OAuth
- Database configuration for different environments

### Deployment
- **Production Server:** Configured for Gunicorn (see `Procfile`)
- **Database:** PostgreSQL on Render via `DATABASE_URL` env var (falls back to SQLite if not set)

## Business Logic Notes

### Trip Registration System
- **Public Interface:** Users browse active trips and register with payment authorization
- **Admin Interface:** Manage trips, seasons, users, and payment captures
- **Lottery System:** New members go into lottery; payment holds allow selective acceptance

### Season Management
- **Registration Windows:** Separate periods for returning vs new members
- **Member Status Tracking:** Users can be PENDING_LOTTERY, ACTIVE, or DROPPED per season
- **Historical Data:** Former member verification by email lookup
- **API Endpoint:** `POST /api/is_returning_member` - Frontend can check member status by email

### Status Fields (Two Levels)
- **User.status** (global): `pending`, `active`, `inactive`, `dropped`
- **UserSeason.status** (per-season): `PENDING_LOTTERY`, `ACTIVE`, `DROPPED`

### Data Conventions
- **Prices:** Stored in cents (e.g., $50.00 = 5000), converted from dollars on form input
- **Timestamps:** UTC in database, displayed in US Central (America/Chicago)
- **Member type:** Derived property (`User.is_returning`), not stored as a column

## Important Files
- **Product Specification:** `.cursor/rules/tcsc_registration_spec.mdc` contains detailed business requirements
- **Contributing Guide:** `CONTRIBUTING.md` explains User/UserSeason model and member type logic
- **Constants:** `app/constants.py` - Status enums (`UserStatus`, `UserSeasonStatus`), `StripeEvent` types, `PaymentType`
- **Admin JS:** `app/static/admin_users.js`, `app/static/admin_payments.js` - Tabulator grid implementations
- **Static Assets:** CSS organized in modular structure under `app/static/css/styles/`
- **Templates:** Jinja2 templates in `app/templates/` with admin-specific subdirectory