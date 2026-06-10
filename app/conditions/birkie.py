"""Birkie fever: how the American Birkebeiner is shaping up, as a fever.

The strip's fifth cell reads like the venue temperature cells beside it,
except the number is your Birkie fever (the club song the cell plays on
click: "Birkie fever... fever... fever..."). The reading climbs with the
season phase and the latest Birkie Trail ski-quality report (SkinnySkI,
fetched for the Telemark conditions cell): 98.6 in summer, full-blown 104
when the trail is skiing good in the race window. Date precision is avoided
on purpose: the race's February weekend varies year to year, so the copy
says "late February" rather than encoding a rule that breaks.

Status slugs are the stable machine names; word/detail are voice.

Natural extension if the club wants editorial control (La Nina winters,
early-season judgment calls): an AppConfig override read at request time in
the route, NOT here; this module must stay context-free because the
conditions cache rebuilds in a daemon thread.
"""
from __future__ import annotations

from datetime import date

# SkinnySkI ski-quality strings, ranked. Anything >= GOOD reads as on-track.
_QUALITY_RANK = {
    'excellent': 4,
    'very good': 4,
    'good': 3,
    'fair': 2,
    'poor': 1,
}


def build_birkie_status(today: date, trail_quality: str | None) -> dict:
    """Status dict for the marketing-site strip's fifth cell.

    Returns {status, word, detail}: `status` is the machine slug, `word` the
    fever reading shown at temperature scale, `detail` one line of context.
    """
    month = today.month
    race_year = today.year + 1 if month > 2 else today.year
    rank = _QUALITY_RANK.get((trail_quality or '').strip().lower(), 0)

    # March through September: the next race is a different winter entirely.
    if 3 <= month <= 9:
        return {
            'status': 'early',
            'word': '98.6°',
            'detail': f'No fever yet. Birkie {race_year} talk starts in November.',
        }

    # October through December: shaping up, graded by any early grooming.
    if month >= 10:
        if rank >= 3:
            return {
                'status': 'likely',
                'word': '103°',
                'detail': f'Full-blown already. Birkie Trail skiing {trail_quality} at Telemark.',
            }
        if rank == 2:
            return {
                'status': 'watch',
                'word': '101°',
                'detail': 'Coming on. Early grooming says fair at Telemark.',
            }
        return {
            'status': 'waiting',
            'word': '99.5°',
            'detail': 'Just a tickle. First grooming reports land in December.',
        }

    # January and February: race window.
    if rank >= 3:
        return {
            'status': 'likely',
            'word': '104°',
            'detail': f'Full-blown Birkie fever. Trail skiing {trail_quality} at Telemark.',
        }
    if rank >= 1:
        return {
            'status': 'watch',
            'word': '102°',
            'detail': f'Trail report {trail_quality} at Telemark. Grooming can turn it around.',
        }
    return {
        'status': 'watch',
        'word': '100.4°',
        'detail': 'No word from Telemark yet. Late February race.',
    }
