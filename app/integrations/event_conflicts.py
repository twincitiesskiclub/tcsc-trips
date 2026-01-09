"""
Event conflict detection for ski practices.

Scrapes race calendars and venue closures to identify conflicts with scheduled practices.
"""

import logging
import re
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
    - "Jan.4" or "Jan 4" (no year - assumes current year)
    - "12/27/2025"
    - "Dec 27, 2025"
    - "Saturday, December 27, 2025"
    """
    date_text = date_text.strip()
    current_year = datetime.utcnow().year

    # Handle "Jan.4" or "Jan.14" format (SkinnySkI uses this)
    dot_match = re.match(r'^(\w{3})\.(\d{1,2})$', date_text)
    if dot_match:
        month_str = dot_match.group(1)
        day_str = dot_match.group(2)
        try:
            return datetime.strptime(f"{month_str} {day_str}, {current_year}", '%b %d, %Y')
        except ValueError:
            pass

    # Handle "Jan 4" format (no year)
    short_match = re.match(r'^(\w{3})\s+(\d{1,2})$', date_text)
    if short_match:
        month_str = short_match.group(1)
        day_str = short_match.group(2)
        try:
            return datetime.strptime(f"{month_str} {day_str}, {current_year}", '%b %d, %Y')
        except ValueError:
            pass

    # Try common formats with year
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

    logger.debug(f"Could not parse race date: {date_text}")
    return None


def _scrape_skinnyski_races() -> list[EventConflict]:
    """
    Scrape race calendar from SkinnySkI.

    Returns list of EventConflict objects for races.
    """
    logger.info("=" * 50)
    logger.info("EVENT CONFLICTS: Starting SkinnySkI race calendar scrape")
    logger.info(f"  URL: {SKINNYSKI_CALENDAR_URL}")

    source = 'skinnyski_races'

    # Check rate limit
    if _should_rate_limit(source):
        wait_time = max(0, MIN_REQUEST_INTERVAL_SECONDS - (time.time() - _last_request_time[source]))
        if wait_time > 0:
            logger.warning(f"  Rate limit: waiting {wait_time:.1f} seconds")
            time.sleep(wait_time)

    try:
        start_time = time.time()
        logger.info("  Fetching page...")
        response = requests.get(SKINNYSKI_CALENDAR_URL, timeout=15)
        elapsed = time.time() - start_time
        logger.info(f"  Response: {response.status_code} in {elapsed:.2f}s ({len(response.content)} bytes)")
        response.raise_for_status()
        _update_rate_limit(source)

        soup = BeautifulSoup(response.content, 'html.parser')

        races = []

        # SkinnySkI uses CSS classes for event calendar:
        # - ss-eventcalendar-entry: Container for each event
        # - ss-eventcalendar-date: Date like "Jan.4" or "Jan.2-4"
        # - ss-eventcalendar-title: Race name and link, with location in parentheses

        # Find all event entries
        event_entries = soup.find_all('div', class_='ss-eventcalendar-entry')
        logger.info(f"  Found {len(event_entries)} event entries")

        for entry in event_entries:
            try:
                # Extract date
                date_div = entry.find('div', class_='ss-eventcalendar-date')
                if not date_div:
                    continue

                date_text = date_div.get_text(strip=True)
                # Handle date ranges like "Jan.2-4" by taking the first date
                if '-' in date_text:
                    date_text = date_text.split('-')[0]

                # Parse date like "Jan.4" or "Jan 4"
                race_date = _parse_race_date(date_text)
                if not race_date:
                    # Try adding current year explicitly
                    date_match = re.match(r'(\w+)\.?(\d+)', date_text)
                    if date_match:
                        month_str = date_match.group(1)
                        day_str = date_match.group(2)
                        current_year = datetime.utcnow().year
                        try:
                            race_date = datetime.strptime(f"{month_str} {day_str}, {current_year}", '%b %d, %Y')
                        except ValueError:
                            logger.debug(f"  Could not parse date: {date_text}")
                            continue

                if not race_date:
                    continue

                # Extract title and location
                title_div = entry.find('div', class_='ss-eventcalendar-title')
                if not title_div:
                    continue

                # Get race name from link
                title_link = title_div.find('a', href=True)
                if not title_link:
                    continue

                race_name = title_link.get_text(strip=True)
                if not race_name:
                    continue

                # Build race URL
                race_url = SKINNYSKI_CALENDAR_URL
                href = title_link.get('href', '')
                if href:
                    if href.startswith('http'):
                        race_url = href
                    elif href.startswith('/'):
                        race_url = f"https://www.skinnyski.com{href}"

                # Extract location - it appears in parentheses after the link
                # e.g., "(Saint Paul, MN)"
                title_text = title_div.get_text(strip=True)
                location_name = None
                location_match = re.search(r'\(([^)]+)\)', title_text)
                if location_match:
                    location_name = location_match.group(1)

                # Also check for dedicated location div
                if not location_name:
                    location_div = entry.find('div', class_='ss-eventcalendar-location')
                    if location_div:
                        location_name = location_div.get_text(strip=True)

                race = EventConflict(
                    name=race_name,
                    event_type='race',
                    date=race_date,
                    location=location_name,
                    affects_practice=True,  # Conservative: assume races affect practice
                    source='SkinnySkI',
                    url=race_url,
                    notes=None
                )

                races.append(race)
                logger.info(f"  + {race_name}: {race_date.strftime('%b %d')} at {location_name or 'unknown'}")

            except Exception as e:
                logger.warning(f"  Failed to parse event entry: {e}")
                continue

        logger.info(f"EVENT CONFLICTS: Scraped {len(races)} races total")
        logger.info("=" * 50)
        return races

    except requests.exceptions.RequestException as e:
        logger.error(f"EVENT CONFLICTS: Failed to scrape - {e}")
        logger.info("=" * 50)
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
