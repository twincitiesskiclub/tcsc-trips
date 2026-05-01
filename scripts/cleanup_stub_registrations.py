#!/usr/bin/env python3
"""Clean up stub User registrations for a given season.

A "stub" registration is a UserSeason whose linked User has none of:
date_of_birth, phone, tshirt_size, emergency_contact_name. These rows
result from the legacy bug where a Stripe payment-intent webhook created
a User row before the form POST submitted personal info — when the form
POST then failed (e.g., closed registration window), the User stayed in
that empty state and the PaymentIntent stayed in 'requires_capture'.

For each stub the script:
  1. Prints user, user_season, and linked Payment details.
  2. Prompts y/N.
  3. On 'y':
     - If a linked Payment exists with Stripe status 'requires_capture',
       cancels the PaymentIntent in Stripe and updates Payment.status.
     - Deletes the UserSeason row.
     - Deletes the User row only if there are no other user_seasons
       and no other payments. Otherwise leaves the User intact.
  4. Commits per user so partial runs are safe.

Usage:
    python scripts/cleanup_stub_registrations.py <season_id>

Set DATABASE_URL in env (or .env) before running. For production:
    DATABASE_URL=postgresql://... python scripts/cleanup_stub_registrations.py 4
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import stripe
from dotenv import load_dotenv

load_dotenv()

from app import create_app
from app.models import db, User, UserSeason, Payment, Season


def find_stub_user_seasons(season_id):
    """Return UserSeason rows for the season whose User has no personal info."""
    return (
        UserSeason.query
        .join(User, User.id == UserSeason.user_id)
        .filter(UserSeason.season_id == season_id)
        .filter(User.date_of_birth.is_(None))
        .filter((User.phone.is_(None)) | (User.phone == ''))
        .filter((User.tshirt_size.is_(None)) | (User.tshirt_size == ''))
        .filter((User.emergency_contact_name.is_(None)) | (User.emergency_contact_name == ''))
        .all()
    )


def find_linked_payment(user, season_id):
    """Find the most recent Payment for this user+season, by user_id or email."""
    by_user = (
        Payment.query
        .filter_by(user_id=user.id, season_id=season_id)
        .order_by(Payment.created_at.desc())
        .first()
    )
    if by_user:
        return by_user
    return (
        Payment.query
        .filter_by(email=user.email, season_id=season_id)
        .order_by(Payment.created_at.desc())
        .first()
    )


def cancel_payment_intent(payment):
    """Cancel the Stripe PaymentIntent if it's still in requires_capture.

    Returns the new local Payment.status value (or current value if no change).
    """
    if not payment:
        return None
    try:
        intent = stripe.PaymentIntent.retrieve(payment.payment_intent_id)
    except stripe.error.StripeError as exc:
        print(f"    Stripe retrieve failed: {exc}")
        return payment.status
    print(f"    Stripe status: {intent.status}")
    if intent.status != 'requires_capture':
        print(f"    Not capturable; leaving as-is.")
        return payment.status
    try:
        cancelled = stripe.PaymentIntent.cancel(payment.payment_intent_id)
        print(f"    Cancelled. New Stripe status: {cancelled.status}")
        return cancelled.status
    except stripe.error.StripeError as exc:
        print(f"    Stripe cancel failed: {exc}")
        return payment.status


def cleanup_one(user_season):
    """Cancel hold, delete UserSeason, and conditionally delete User."""
    user = user_season.user
    payment = find_linked_payment(user, user_season.season_id)

    print(f"\nUser #{user.id}  {user.email}  ({user.first_name} {user.last_name})")
    print(f"  UserSeason: season={user_season.season_id} status={user_season.status} type={user_season.registration_type}")
    if payment:
        print(f"  Payment #{payment.id}: ${payment.amount/100:.2f} status={payment.status} pi={payment.payment_intent_id}")
    else:
        print("  Payment: (none found)")

    confirm = input("  Cancel + delete this stub? (y/N): ").strip().lower()
    if confirm != 'y':
        print("  Skipped.")
        return

    if payment:
        new_status = cancel_payment_intent(payment)
        if new_status and new_status != payment.status:
            payment.status = new_status

    db.session.delete(user_season)

    other_seasons = UserSeason.query.filter(
        UserSeason.user_id == user.id,
        UserSeason.season_id != user_season.season_id,
    ).count()
    other_payments = Payment.query.filter(
        Payment.user_id == user.id,
    ).count()
    if other_seasons == 0 and other_payments == 0:
        db.session.delete(user)
        print(f"  Deleted User #{user.id} and UserSeason.")
    else:
        print(
            f"  Deleted UserSeason. Kept User #{user.id} "
            f"(other_seasons={other_seasons}, other_payments={other_payments})."
        )

    db.session.commit()


def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/cleanup_stub_registrations.py <season_id>")
        sys.exit(1)
    try:
        season_id = int(sys.argv[1])
    except ValueError:
        print("season_id must be an integer")
        sys.exit(1)

    stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
    if not stripe.api_key:
        print("STRIPE_SECRET_KEY is not set")
        sys.exit(1)

    app = create_app()
    with app.app_context():
        season = Season.query.get(season_id)
        if not season:
            print(f"Season #{season_id} not found")
            sys.exit(1)
        print(f"Scanning Season #{season.id} '{season.name}' for stub registrations...")

        stubs = find_stub_user_seasons(season_id)
        if not stubs:
            print("No stub registrations found.")
            return

        print(f"Found {len(stubs)} stub registration(s).")
        for us in stubs:
            try:
                cleanup_one(us)
            except Exception as exc:
                db.session.rollback()
                print(f"  ERROR: {exc}")
                continue


if __name__ == '__main__':
    main()
