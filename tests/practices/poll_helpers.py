"""Build a mapped DRAFT poll the way open_block_poll does, for tests."""

from app.models import db
from app.practices.availability import create_block_poll, map_sessions


def make_mapped_poll(starts_on, ends_on):
    poll = create_block_poll(starts_on, ends_on)
    map_sessions(poll)
    db.session.commit()
    return poll
