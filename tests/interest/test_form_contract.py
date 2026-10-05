"""The two forms and the route must agree on field names."""
import re
from pathlib import Path

from app.interest.service import FIELDS, HONEYPOT

ROOT = Path(__file__).resolve().parents[2]
EXPECTED = set(FIELDS) | {HONEYPOT}


def names_in(relative):
    return set(re.findall(r'\bname="([a-z_]+)"', (ROOT / relative).read_text()))


def test_app_partial_posts_the_fields_the_route_reads():
    assert names_in('app/templates/_interest_form.html') == EXPECTED
