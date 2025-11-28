# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Environment Setup

### Local Development
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

3. Set up environment and run:
   ```bash
   export FLASK_APP=app.py
   python3 -m flask run
   ```

### Stripe Webhook Testing (Local Development)
To test Stripe webhooks locally:
```bash
stripe listen --forward-to localhost:5000/webhook
```
This provides a webhook signing secret (`whsec_...`) to set as `STRIPE_WEBHOOK_SECRET`.

### Database Management
- **Initialize/Migrate Database:** `flask db upgrade`
- **Create New Migration:** `flask db migrate -m "description"`
- **Database Location:** Production/dev databases in `/var/lib/`, testing in `app/instance/`
- **Migration Files:** Located in `migrations/versions/`

### Helper Scripts
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
- **Payment:** Stripe payment intents, amounts, statuses
- **User:** Member profiles with extensive personal information
- **Season:** Membership seasons with registration windows
- **UserSeason:** Many-to-many relationship between users and seasons

### Authentication & Security
- **Admin Access:** Restricted to `@twincitiesskiclub.org` email addresses via Google OAuth
- **Public Access:** Trip registration and membership signup (no authentication required)
- **Payment Security:** Stripe Payment Intents with manual capture (authorization holds)

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
- **SQLAlchemy:** ORM for SQLite database

## Configuration

### Environment Variables Required
Check `.env.example` for complete list. Critical variables include:
- `FLASK_SECRET_KEY` - Flask session security
- `STRIPE_PUBLISHABLE_KEY` / `STRIPE_SECRET_KEY` - Payment processing
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` - Admin OAuth
- Database configuration for different environments

### Deployment
- **Production Server:** Configured for Gunicorn (see `Procfile`)
- **Database:** Environment-specific SQLite files via `app/config.py`

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
- **Static Assets:** CSS organized in modular structure under `app/static/css/styles/`
- **Templates:** Jinja2 templates in `app/templates/` with admin-specific subdirectory