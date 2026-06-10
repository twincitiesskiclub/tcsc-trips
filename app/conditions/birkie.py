"""Birkie likelihood: how the American Birkebeiner is shaping up from here.

A deliberately honest, calendar-plus-grooming heuristic: the season phase
sets the frame and the latest Birkie Trail ski-quality report (SkinnySkI,
fetched for the Double OO conditions cell) grades it. Date precision is
avoided on purpose: the race's February weekend varies year to year, so the
copy says "late February" rather than encoding a rule that breaks.

Voice: the big status word and the detail line read as ONE sentence when
the strip renders them stacked ("Praying / for snow. ..."), in club
register. Keep that grammar when editing copy. Status slugs are the stable
machine names; only word/detail are voice.

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
    short display headline, `detail` the rest of the sentence.
    """
    month = today.month
    race_year = today.year + 1 if month > 2 else today.year
    rank = _QUALITY_RANK.get((trail_quality or '').strip().lower(), 0)

    # March through September: the next race is a different winter entirely.
    if 3 <= month <= 9:
        return {
            'status': 'early',
            'word': 'Praying',
            'detail': f'for snow. Birkie {race_year} talk starts in November.',
        }

    # October through December: shaping up, graded by any early grooming.
    if month >= 10:
        if rank >= 3:
            return {
                'status': 'likely',
                'word': "It's on",
                'detail': f'already. Birkie Trail skiing {trail_quality} at OO.',
            }
        if rank == 2:
            return {
                'status': 'watch',
                'word': 'Hopeful',
                'detail': 'Early grooming says fair. Late February race.',
            }
        return {
            'status': 'waiting',
            'word': 'Waiting',
            'detail': 'on snow. First grooming reports land in December.',
        }

    # January and February: race window.
    if rank >= 3:
        return {
            'status': 'likely',
            'word': "It's on",
            'detail': f'Birkie Trail skiing {trail_quality} at OO.',
        }
    if rank >= 1:
        return {
            'status': 'watch',
            'word': 'Iffy',
            'detail': f'Trail report {trail_quality} at OO. Grooming can turn it around.',
        }
    return {
        'status': 'watch',
        'word': 'No word',
        'detail': 'from OO yet. Late February race.',
    }
