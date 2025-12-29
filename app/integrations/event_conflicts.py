"""
Event conflict detection for ski practices.

Scrapes race calendars and venue closures to identify conflicts with scheduled practices.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Optional
import requests
from bs4 import BeautifulSoup

from app.practices.interfaces import EventConflict

logger = logging.getLogger(__name__)

# SkinnySkI race calendar
SKINNYSKI_CALENDAR_URL = "https://www.skinnyski.com/racing/calendar.asp"

# Rate limiting
MIN_REQUEST_INTERVAL_SECONDS = 30
_last_request_time = {}

# Simple in-memory cache
_cache = {}
CACHE_TTL_HOURS = 12  # Race calendars update infrequently


def _should_rate_limit(source: str) -> bool:
    """Check if we should rate limit the next request for a source."""
    if source not in _last_request_time:
        return False

    elapsed = time.time() - _last_request_time[source]
    return elapsed < MIN_REQUEST_INTERVAL_SECONDS


def _update_rate_limit(source: str):
    """Update the last request timestamp for a source."""
    _last_request_time[source] = time.time()


def _is_cache_valid(cache_entry: dict) -> bool:
    """Check if a cache entry is still valid."""
    if not cache_entry:
        return False

    cached_at = cache_entry.get('cached_at')
    if not cached_at:
        return False

    age = datetime.utcnow() - cached_at
    return age < timedelta(hours=CACHE_TTL_HOURS)


def _parse_race_date(date_text: str) -> Optional[datetime]:
    """
    Parse race date from various formats used in race calendars.

    Common formats:
    - "12/27/2025"
    - "Dec 27, 2025"
    - "Saturday, December 27, 2025"
    """
    date_text = date_text.strip()

    # Try common formats
    formats = [
        '%m/%d/%Y',
        '%m/%d/%y',
        '%b %d, %Y',
        '%B %d, %Y',
        '%A, %B %d, %Y',
        '%a, %b %d, %Y',
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_text, fmt)
        except ValueError:
            continue

    logger.warning(f"Failed to parse race date: {date_text}")
    return None


def _scrape_skinnyski_races() -> list[EventConflict]:
    """
    Scrape race calendar from SkinnySkI.

    Returns list of EventConflict objects for races.
    """
    logger.info("Scraping SkinnySkI race calendar")

    source = 'skinnyski_races'

    # Check rate limit
    if _should_rate_limit(source):
        wait_time = max(0, MIN_REQUEST_INTERVAL_SECONDS - (time.time() - _last_request_time[source]))
        if wait_time > 0:
            logger.warning(f"Rate limit: waiting {wait_time:.1f} seconds")
            time.sleep(wait_time)

    try:
        response = requests.get(SKINNYSKI_CALENDAR_URL, timeout=15)
        response.raise_for_status()
        _update_rate_limit(source)

        soup = BeautifulSoup(response.content, 'html.parser')

        races = []

        # Look for race listings
        # SkinnySkI typically uses tables or divs with race information
        # We'll look for common patterns

        # Try finding tables first
        tables = soup.find_all('table')

        for table in tables:
            rows = table.find_all('tr')

            for row in rows:
                cells = row.find_all(['td', 'th'])

                if len(cells) < 2:
                    continue

                try:
                    # Extract race information
                    # Typical structure: Date | Race Name | Location
                    date_cell = cells[0]
                    name_cell = cells[1] if len(cells) > 1 else cells[0]
                    location_cell = cells[2] if len(cells) > 2 else None

                    date_text = date_cell.get_text(strip=True)
                    race_date = _parse_race_date(date_text)

                    if not race_date:
                        continue

                    race_name = name_cell.get_text(strip=True)
                    if not race_name or race_name.lower() in ['date', 'race', 'event']:
                        # Skip header rows
                        continue

                    location_name = location_cell.get_text(strip=True) if location_cell else None

                    # Extract URL if present
                    race_url = SKINNYSKI_CALENDAR_URL
                    link = name_cell.find('a', href=True)
                    if link:
                        href = link['href']
                        if href.startswith('http'):
                            race_url = href
                        elif href.startswith('/'):
                            race_url = f"https://www.skinnyski.com{href}"
                        else:
                            race_url = f"https://www.skinnyski.com/{href}"

                    # Determine if this affects practice
                    # Races typically block trail access at popular venues
                    affects_practice = True  # Conservative: assume races affect practice

                    race = EventConflict(
                        name=race_name,
                        event_type='race',
                        date=race_date,
                        location=location_name,
                        affects_practice=affects_practice,
                        source='SkinnySkI',
                        url=race_url,
                        notes=None
                    )

                    races.append(race)
                    logger.debug(f"Parsed race: {race_name} on {race_date.date()}")

                except Exception as e:
                    logger.warning(f"Failed to parse race row: {e}")
                    continue

        # Also check for div-based listings
        race_divs = soup.find_all('div', class_=lambda x: x and 'race' in x.lower())

        for div in race_divs:
            try:
                # Look for date pattern
                date_elem = div.find(class_=lambda x: x and 'date' in x.lower())
                if date_elem:
                    date_text = date_elem.get_text(strip=True)
                    race_date = _parse_race_date(date_text)

                    if race_date:
                        # Extract name and location
                        name_elem = div.find(class_=lambda x: x and 'name' in x.lower())
                        race_name = name_elem.get_text(strip=True) if name_elem else div.get_text(strip=True)[:100]

                        location_elem = div.find(class_=lambda x: x and 'location' in x.lower())
                        location_name = location_elem.get_text(strip=True) if location_elem else None

                        # Get URL
                        race_url = SKINNYSKI_CALENDAR_URL
                        link = div.find('a', href=True)
                        if link:
                            href = link['href']
                            if href.startswith('http'):
                                race_url = href
                            elif href.startswith('/'):
                                race_url = f"https://www.skinnyski.com{href}"

                        race = EventConflict(
                            name=race_name,
                            event_type='race',
                            date=race_date,
                            location=location_name,
                            affects_practice=True,
                            source='SkinnySkI',
                            url=race_url,
                            notes=None
                        )

                        races.append(race)

            except Exception as e:
                logger.warning(f"Failed to parse race div: {e}")
                continue

        logger.info(f"Scraped {len(races)} races from SkinnySkI")
        return races

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to scrape SkinnySkI calendar: {e}")
        # Return empty list rather than failing
        return []


def _get_cached_conflicts() -> list[EventConflict]:
    """
    Get cached event conflicts from all sources.

    Returns:
        List of EventConflict objects
    """
    cache_key = 'all_conflicts'

    if cache_key in _cache and _is_cache_valid(_cache[cache_key]):
        logger.info("Returning cached event conflicts")
        return _cache[cache_key]['data']

    # Scrape fresh data from all sources
    all_conflicts = []

    # SkinnySkI races
    try:
        races = _scrape_skinnyski_races()
        all_conflicts.extend(races)
    except Exception as e:
        logger.error(f"Failed to fetch SkinnySkI races: {e}")

    # Future: Add other sources here
    # - Venue calendars (Wirth, Loppet Foundation, etc.)
    # - MNLA events
    # - Park closure notices

    # Update cache
    _cache[cache_key] = {
        'data': all_conflicts,
        'cached_at': datetime.utcnow()
    }

    logger.info(f"Cached {len(all_conflicts)} total event conflicts")
    return all_conflicts


def get_event_conflicts(date: datetime, location_name: Optional[str] = None) -> list[EventConflict]:
    """
    Get event conflicts for a specific date and optionally a location.

    Args:
        date: Date to check for conflicts
        location_name: Optional location name to filter by (fuzzy match)

    Returns:
        List of EventConflict objects for the specified date
    """
    logger.info(f"Checking event conflicts for {date.date()}"
               f"{f' at {location_name}' if location_name else ''}")

    # Get all cached conflicts
    all_conflicts = _get_cached_conflicts()

    # Filter by date (same day)
    target_date = date.date()
    matching_conflicts = [
        conflict for conflict in all_conflicts
        if conflict.date.date() == target_date
    ]

    # If location specified, filter by location
    if location_name:
        location_lower = location_name.lower()
        location_matches = []

        for conflict in matching_conflicts:
            if not conflict.location:
                # No location info, keep it (might affect any location)
                location_matches.append(conflict)
                continue

            conflict_location_lower = conflict.location.lower()

            # Fuzzy match: check if either name contains the other
            if (location_lower in conflict_location_lower or
                conflict_location_lower in location_lower):
                location_matches.append(conflict)

        matching_conflicts = location_matches

    logger.info(f"Found {len(matching_conflicts)} event conflicts")
    return matching_conflicts


def clear_cache():
    """Clear the event conflicts cache (useful for testing)."""
    global _cache
    _cache = {}
    logger.info("Cleared event conflicts cache")
