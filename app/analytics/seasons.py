"""Season labels for any practice date, 2022 onward.

Labels read "YYYY Spring/Summer" or "YYYY Fall/Winter", the same form as Season.name.
"""
from datetime import date


def season_label(d: date, seasons) -> str:
    for s in seasons:
        if s.start_date <= d <= s.end_date:
            return s.name
    if 5 <= d.month <= 8:
        return f"{d.year} Spring/Summer"
    start_year = d.year if d.month >= 9 else d.year - 1
    return f"{start_year} Fall/Winter"


def season_key(label):
    """Chronological sort key; Fall/Winter follows the same year's Spring/Summer."""
    year, _, kind = label.partition(" ")
    return (int(year), 1 if kind == "Fall/Winter" else 0) if year.isdigit() else (0, 0)


def shift_season(label, years):
    """The same season type `years` later, or None when the label has no year."""
    year, _, kind = (label or "").partition(" ")
    return f"{int(year) + years} {kind}" if year.isdigit() else None


def season_in_progress(label, today) -> bool:
    return label == season_label(today, [])


def short_season_label(label):
    year, _, kind = label.partition(" ")
    names = {"Fall/Winter": "Fall", "Spring/Summer": "Sum"}
    if year.isdigit() and kind in names:
        return f"{names[kind]} {year[-2:]}"
    return label
