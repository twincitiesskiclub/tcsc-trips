"""Fix payment amounts stored as dollars to cents

Revision ID: 747c35858dc6
Revises: 104d18e6f8fb
Create Date: 2025-12-02 15:29:52.033011

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '747c35858dc6'
down_revision = '104d18e6f8fb'
branch_labels = None
depends_on = None


def upgrade():
    # Fix existing payment amounts that were stored as dollars instead of cents
    # Amounts under 10000 (i.e., displaying as < $100) are clearly in dollars
    # and need to be multiplied by 100 to convert to cents
    # This cutoff is safe because real trip payments are $100+ ($295, $220, etc.)
    op.execute("UPDATE payments SET amount = amount * 100 WHERE amount < 10000")


def downgrade():
    # Reverse: divide by 100 for amounts that were converted
    op.execute("UPDATE payments SET amount = amount / 100 WHERE amount >= 10000")
