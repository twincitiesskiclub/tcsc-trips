# TCSC Trips & Membership Registration

A Flask web application for the Twin Cities Ski Club (TCSC) trip registration and membership management system.

## Features

- **Trip Registration:** Public signup for ski trips with Stripe payment processing
- **Membership Management:** Season-based membership with lottery system for new members
- **Admin Dashboard:** Manage trips, members, and payments via interactive data grids
- **Payment Processing:** Two-tier system (automatic for returning members, manual capture for lottery)

## Requirements

- Python 3.12+
- [Docker](https://www.docker.com/products/docker-desktop/) (for local PostgreSQL)
- [Stripe CLI](https://stripe.com/docs/stripe-cli) (for local webhook testing)
- Google OAuth credentials (for admin access)

## Quick Start

1. **Clone and setup environment:**
   ```bash
   git clone <repo-url>
   cd tcsc-trips
   python3 -m venv env
   source env/bin/activate  # Windows: .\env\Scripts\activate.bat
   pip install -r requirements.txt
   ```

2. **Configure environment:**
   - Copy `.env.example` to `.env`
   - Fill in Stripe API keys and Google OAuth credentials

3. **Run the development server:**
   ```bash
   ./scripts/dev.sh
   ```
   This starts PostgreSQL via Docker, Flask on port 5001, and automatically configures Stripe webhooks.

   On first run, it will:
   - Pull and start a PostgreSQL 18 container
   - Migrate data from `app.db` (if present) or create empty tables

4. **Access the app:**
   - Public site: http://localhost:5001
   - Admin dashboard: http://localhost:5001/admin (requires @twincitiesskiclub.org Google login)

## Development

### Dev Script Options

```bash
./scripts/dev.sh              # PostgreSQL on port 5001 (default)
./scripts/dev.sh 5000         # PostgreSQL on port 5000
./scripts/dev.sh --sqlite     # SQLite for quick testing (no Docker needed)
```

### Managing Local PostgreSQL

```bash
docker stop tcsc-postgres     # Stop the container (data persists)
docker start tcsc-postgres    # Restart it
docker rm -f tcsc-postgres    # Delete container and reset data
```

### Running Manually

If you need to run components separately:

```bash
# Terminal 1: Stripe webhook listener
stripe listen --forward-to localhost:5000/webhook

# Terminal 2: Flask app (with PostgreSQL)
export DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips
export STRIPE_WEBHOOK_SECRET=whsec_...  # from stripe listen output
python3 -m flask run
```

### Database Migrations

```bash
flask db migrate -m "description"  # Create migration
flask db upgrade                   # Apply migrations
```

### Project Structure

```
app/
├── __init__.py          # Flask app factory
├── models.py            # SQLAlchemy models (User, Trip, Payment, Season)
├── constants.py         # Status enums, Stripe events, PaymentType
├── routes/
│   ├── admin.py         # Admin dashboard & API
│   ├── payments.py      # Stripe payment processing
│   ├── trips.py         # Trip registration
│   └── registration.py  # Membership signup
├── static/
│   ├── admin_users.js   # Member management grid (Tabulator)
│   └── admin_payments.js # Payment management grid (Tabulator)
└── templates/
    └── admin/           # Admin dashboard templates
```

### Key Concepts

- **Member Types:** `NEW` (first-time), `RETURNING` (active in past season), `FORMER` (inactive)
- **Payment Types:** `trip` or `season` - stored in `payment_type` field
- **Lottery System:** New members get `manual` capture; admins approve via bulk capture
- **Status Levels:** Global `User.status` + per-season `UserSeason.status`

See `CLAUDE.md` for detailed architecture documentation.

## Contributing

1. Create a feature branch from `main`
2. Make changes and test locally with `./scripts/dev.sh`
3. Submit a pull request

Admin access requires a `@twincitiesskiclub.org` email. For local testing without admin features, you can still access public registration pages.
