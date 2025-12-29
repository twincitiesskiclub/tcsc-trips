"""
Scheduled routines for practice monitoring.

These routines are called by the scheduler (or manually via admin endpoints):

- morning_check: Daily 7am evaluation of today's practices
- pre_practice: 48h workout nudge, 24h lead confirmation check
- weekly_summary: Sunday evening preview of upcoming week
"""

from app.agent.routines.morning_check import run_morning_check
from app.agent.routines.pre_practice import run_48h_check, run_24h_check
from app.agent.routines.weekly_summary import run_weekly_summary

__all__ = [
    'run_morning_check',
    'run_48h_check',
    'run_24h_check',
    'run_weekly_summary',
]
