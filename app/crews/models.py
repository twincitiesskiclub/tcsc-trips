"""Crew tables: one config row per season, any number of drafts."""
from datetime import datetime

from sqlalchemy.dialects.postgresql import JSONB

from app.models import db


class CrewConfig(db.Model):
    """Inputs for a season's crews: settings, member overrides, rules, speedy group."""
    __tablename__ = "crew_configs"

    id = db.Column(db.Integer, primary_key=True)
    season_id = db.Column(db.Integer, db.ForeignKey("seasons.id", ondelete="CASCADE"),
                          nullable=False, unique=True)
    settings = db.Column(JSONB, nullable=False, default=dict)   # crews, levels, board_rule, speedy_channel
    overrides = db.Column(JSONB, nullable=False, default=dict)  # "user_id" -> {gender, thot, board}
    rules = db.Column(JSONB, nullable=False, default=list)      # [{kind, a, b, crew}]
    speedy_user_ids = db.Column(JSONB, nullable=False, default=list)
    speedy_refreshed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    season = db.relationship("Season")


class CrewDraft(db.Model):
    """One draw. members is a snapshot so a draft keeps its numbers if the roster moves."""
    __tablename__ = "crew_drafts"

    id = db.Column(db.Integer, primary_key=True)
    season_id = db.Column(db.Integer, db.ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False)
    label = db.Column(db.String(120), nullable=False)
    seed = db.Column(db.Integer)
    status = db.Column(db.String(10), nullable=False, default="draft")  # draft | final
    settings = db.Column(JSONB, nullable=False, default=dict)
    rules = db.Column(JSONB, nullable=False, default=list)
    members = db.Column(JSONB, nullable=False, default=list)
    crew_names = db.Column(JSONB, nullable=False, default=dict)  # "1" -> name
    score = db.Column(db.Float)
    created_by = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    season = db.relationship("Season")

    __table_args__ = (
        db.CheckConstraint("status IN ('draft','final')", name="ck_crew_draft_status"),
        db.Index("uq_crew_draft_one_final", "season_id", unique=True,
                 postgresql_where=db.text("status = 'final'")),
        db.Index("ix_crew_drafts_season", "season_id"),
    )
