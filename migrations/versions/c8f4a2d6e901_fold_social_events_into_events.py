"""fold social events into events

Revision ID: c8f4a2d6e901
Revises: b433791f5783
Create Date: 2026-07-24 00:00:00.000000

"""
from datetime import date, datetime

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c8f4a2d6e901"
down_revision = "b433791f5783"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Some release-lifecycle checks use a deliberately minimal legacy schema.
    # If the retired table is already absent, there is no data left to fold.
    if not inspector.has_table("social_events"):
        payment_columns = {
            column["name"]
            for column in inspector.get_columns("payments")
        }
        if "social_event_id" in payment_columns:
            for foreign_key in inspector.get_foreign_keys("payments"):
                if (
                    foreign_key["constrained_columns"]
                    == ["social_event_id"]
                ):
                    op.drop_constraint(
                        foreign_key["name"],
                        "payments",
                        type_="foreignkey",
                    )
            op.drop_column("payments", "social_event_id")
        return

    metadata = sa.MetaData()
    social_events = sa.Table(
        "social_events",
        metadata,
        autoload_with=bind,
    )
    events = sa.Table("events", metadata, autoload_with=bind)
    price_options = sa.Table(
        "event_price_options",
        metadata,
        autoload_with=bind,
    )
    registrations = sa.Table(
        "event_registrations",
        metadata,
        autoload_with=bind,
    )
    participants = sa.Table(
        "event_participants",
        metadata,
        autoload_with=bind,
    )
    payments = sa.Table("payments", metadata, autoload_with=bind)

    migration_now = datetime.utcnow()
    event_targets = {}
    social_rows = bind.execute(
        sa.select(social_events).order_by(social_events.c.id)
    ).mappings()
    for social in social_rows:
        if social["status"] == "draft":
            status = "draft"
        elif (
            social["status"] == "active"
            and social["signup_end"] > migration_now
        ):
            status = "active"
        else:
            status = "closed"

        event_id = bind.execute(
            sa.insert(events)
            .values(
                slug=social["slug"],
                name=social["name"],
                description=social["description"],
                location=social["location"],
                event_date=social["event_date"],
                signup_start=social["signup_start"],
                signup_end=social["signup_end"],
                capacity=social["max_participants"],
                status=status,
                audience="internal",
                details_url=None,
                discount_code=None,
                custom_questions=[],
                template_key="social",
                created_at=social["created_at"],
                updated_at=social["updated_at"],
            )
            .returning(events.c.id)
        ).scalar_one()
        price_option_id = bind.execute(
            sa.insert(price_options)
            .values(
                event_id=event_id,
                name="Registration",
                description=None,
                price_cents=social["price"],
                member_price_cents=None,
                participant_roles=["Participant"],
                sort_order=0,
                active=True,
            )
            .returning(price_options.c.id)
        ).scalar_one()
        event_targets[social["id"]] = (event_id, price_option_id)

    payment_rows = bind.execute(
        sa.select(payments)
        .where(payments.c.social_event_id.is_not(None))
        .order_by(payments.c.id)
    ).mappings()
    for payment in payment_rows:
        event_id, price_option_id = event_targets[
            payment["social_event_id"]
        ]
        status = {
            "succeeded": "confirmed",
            "refunded": "refunded",
        }.get(payment["status"], "cancelled")
        registration_id = bind.execute(
            sa.insert(registrations)
            .values(
                event_id=event_id,
                price_option_id=price_option_id,
                contact_email=payment["email"],
                contact_phone="",
                team_name=None,
                emergency_contact_name="",
                emergency_contact_phone="",
                answers={},
                amount_cents=payment["amount"],
                discount_applied=False,
                status=status,
                payment_intent_id=payment["payment_intent_id"],
                created_at=payment["created_at"],
                updated_at=payment["created_at"],
            )
            .returning(registrations.c.id)
        ).scalar_one()
        bind.execute(
            sa.insert(participants).values(
                registration_id=registration_id,
                position=1,
                role_label="Participant",
                name=payment["name"],
                date_of_birth=date(1900, 1, 1),
                email=payment["email"],
                phone="",
            )
        )
        bind.execute(
            sa.update(payments)
            .where(payments.c.id == payment["id"])
            .values(
                event_registration_id=registration_id,
                payment_type="event",
            )
        )

    inspector = sa.inspect(bind)
    for foreign_key in inspector.get_foreign_keys("payments"):
        if foreign_key["constrained_columns"] == ["social_event_id"]:
            op.drop_constraint(
                foreign_key["name"],
                "payments",
                type_="foreignkey",
            )
    op.drop_column("payments", "social_event_id")
    op.drop_table("social_events")


def downgrade():
    # The original social-event rows cannot be reconstructed without loss.
    raise NotImplementedError("lossy migration")
