"""seed dry tri 2026 draft event

Revision ID: d4e7f9a1b2c3
Revises: c8f4a2d6e901
Create Date: 2026-07-24 00:00:00.000000

"""
from datetime import datetime

from alembic import op
import sqlalchemy as sa

from app.events.seeds import build_dry_tri_2026


# revision identifiers, used by Alembic.
revision = "d4e7f9a1b2c3"
down_revision = "c8f4a2d6e901"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    metadata = sa.MetaData()
    events = sa.Table("events", metadata, autoload_with=bind)
    price_options_table = sa.Table(
        "event_price_options",
        metadata,
        autoload_with=bind,
    )

    payload = build_dry_tri_2026()
    existing_id = bind.execute(
        sa.select(events.c.id)
        .where(events.c.slug == payload["slug"])
        .limit(1)
    ).scalar_one_or_none()
    if existing_id is not None:
        return

    price_options = payload.pop("price_options")
    migration_now = datetime.utcnow()
    event_id = bind.execute(
        sa.insert(events)
        .values(
            **payload,
            created_at=migration_now,
            updated_at=migration_now,
        )
        .returning(events.c.id)
    ).scalar_one()

    bind.execute(
        sa.insert(price_options_table),
        [
            {
                **price_option,
                "event_id": event_id,
            }
            for price_option in price_options
        ],
    )


def downgrade():
    # The slug may have predated this idempotent migration, so deleting it
    # here could remove user-owned data.
    pass
