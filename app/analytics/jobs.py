"""The bot-only nightly archive, rebuild, and weather pipeline."""
import logging

from app.analytics.archive import sync_recent
from app.analytics.rebuild import rebuild
from app.analytics.weather import fetch_missing_weather
from app.models import db
from app.slack.client import get_slack_client

logger = logging.getLogger(__name__)


def run_nightly() -> dict:
    """Commit the archive before rebuilding; stop at the first failed step."""
    step = "sync"
    try:
        logger.info("Analytics nightly: sync")
        synced = sync_recent(get_slack_client())
        db.session.commit()
        step = "rebuild"
        logger.info("Analytics nightly: rebuild")
        rebuilt = rebuild()
        db.session.commit()
        step = "weather"
        logger.info("Analytics nightly: weather")
        weather = fetch_missing_weather()
    except Exception as exc:
        db.session.rollback()
        logger.exception("Analytics nightly %s failed: %s", step, exc)
        return {"step": step, "ok": False, "error": str(exc)}
    return {"step": "done", "ok": True, "sync": synced, "rebuild": rebuilt, "weather": weather}
