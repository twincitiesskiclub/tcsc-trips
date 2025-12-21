"""Add emoji and gradient columns to tags

Revision ID: 88054c86f617
Revises: 36f58dc97c0c
Create Date: 2025-12-20 23:14:02.745624

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '88054c86f617'
down_revision = '36f58dc97c0c'
branch_labels = None
depends_on = None

# Seed data for existing tags (from hardcoded JavaScript constants)
TAG_METADATA = {
    # Leadership
    'PRESIDENT': ('👑', 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'),
    'VICE_PRESIDENT': ('⭐', 'linear-gradient(135deg, #5e60ce 0%, #6930c3 100%)'),
    'TREASURER': ('💰', 'linear-gradient(135deg, #4c6ef5 0%, #7048e8 100%)'),
    'SECRETARY': ('📝', 'linear-gradient(135deg, #5c7cfa 0%, #845ef7 100%)'),
    'AUDITOR': ('🔍', 'linear-gradient(135deg, #748ffc 0%, #9775fa 100%)'),
    'BOARD_MEMBER': ('🏛️', 'linear-gradient(135deg, #4263eb 0%, #5f3dc4 100%)'),
    'FRIEND_OF_BOARD': ('🤝', 'linear-gradient(135deg, #91a7ff 0%, #b197fc 100%)'),
    # Coaching
    'HEAD_COACH': ('🎿', 'linear-gradient(135deg, #0ca678 0%, #12b886 100%)'),
    'ASSISTANT_COACH': ('⛷️', 'linear-gradient(135deg, #20c997 0%, #38d9a9 100%)'),
    'PRACTICES_DIRECTOR': ('📋', 'linear-gradient(135deg, #099268 0%, #0ca678 100%)'),
    'PRACTICES_LEAD': ('🏁', 'linear-gradient(135deg, #12b886 0%, #20c997 100%)'),
    'WAX_MANAGER': ('✨', 'linear-gradient(135deg, #38d9a9 0%, #63e6be 100%)'),
    # Activities
    'TRIP_LEAD': ('🧭', 'linear-gradient(135deg, #f76707 0%, #fd7e14 100%)'),
    'ADVENTURES': ('🏔️', 'linear-gradient(135deg, #e8590c 0%, #f76707 100%)'),
    'SOCIAL': ('🎉', 'linear-gradient(135deg, #e64980 0%, #f06595 100%)'),
    'SOCIAL_COMMITTEE': ('🎊', 'linear-gradient(135deg, #d6336c 0%, #e64980 100%)'),
    'MARKETING': ('📣', 'linear-gradient(135deg, #f06595 0%, #faa2c1 100%)'),
    'APPAREL': ('👕', 'linear-gradient(135deg, #f783ac 0%, #fcc2d7 100%)'),
}


def upgrade():
    # Add new columns
    with op.batch_alter_table('tags', schema=None) as batch_op:
        batch_op.add_column(sa.Column('emoji', sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column('gradient', sa.String(length=200), nullable=True))

    # Populate existing tags with emoji and gradient values
    conn = op.get_bind()
    for name, (emoji, gradient) in TAG_METADATA.items():
        conn.execute(
            sa.text("UPDATE tags SET emoji = :emoji, gradient = :gradient WHERE name = :name"),
            {"emoji": emoji, "gradient": gradient, "name": name}
        )


def downgrade():
    with op.batch_alter_table('tags', schema=None) as batch_op:
        batch_op.drop_column('gradient')
        batch_op.drop_column('emoji')
