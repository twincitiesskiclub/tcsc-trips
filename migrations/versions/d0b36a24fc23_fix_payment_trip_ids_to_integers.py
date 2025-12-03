"""fix_payment_trip_ids_to_integers

Convert trip_id values in payments table from slug strings to integer IDs.
SQLite's flexible typing allowed string slugs to be stored in the INTEGER column.
This migration maps each slug to its corresponding trip ID.

Revision ID: d0b36a24fc23
Revises: 747c35858dc6
Create Date: 2025-12-02 22:42:43.914184

"""
from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = 'd0b36a24fc23'
down_revision = '747c35858dc6'
branch_labels = None
depends_on = None


def upgrade():
    # Map trip slugs to their integer IDs
    # These mappings come from the trips table in the database
    slug_to_id = {
        'training-trip': 1,
        'birkie': 2,
        'sisu-ski-fest': 3,
        'pre-birkie': 4,
        'great-bear-chase': 5,
        'cuyuna': 6,
        'north-shore': 8,
        '50kum': 9,
    }

    conn = op.get_bind()
    for slug, trip_id in slug_to_id.items():
        conn.execute(
            text("UPDATE payments SET trip_id = :trip_id WHERE trip_id = :slug"),
            {'trip_id': trip_id, 'slug': slug}
        )


def downgrade():
    # Reverse mapping: convert integer IDs back to slugs
    id_to_slug = {
        1: 'training-trip',
        2: 'birkie',
        3: 'sisu-ski-fest',
        4: 'pre-birkie',
        5: 'great-bear-chase',
        6: 'cuyuna',
        8: 'north-shore',
        9: '50kum',
    }

    conn = op.get_bind()
    for trip_id, slug in id_to_slug.items():
        conn.execute(
            text("UPDATE payments SET trip_id = :slug WHERE trip_id = :trip_id"),
            {'trip_id': trip_id, 'slug': slug}
        )
