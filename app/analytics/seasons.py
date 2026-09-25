"""Season labels for any practice date, 2022 onward."""
from datetime import date


def season_label(d: date, seasons) -> str:
    for s in seasons:
        if s.start_date <= d <= s.end_date:
            return s.name
    if 5 <= d.month <= 8:
        return f"{d.year} Spring/Summer"
    start_year = d.year if d.month >= 9 else d.year - 1
    return f"{start_year} Fall/Winter"
