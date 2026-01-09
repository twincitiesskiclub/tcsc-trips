"""
SkinnySkI trail conditions scraper.

Scrapes trail condition reports from skinnyski.com/trails/reports.asp
with caching and rate limiting.
"""

import logging
import time
import re
from datetime import datetime, timedelta
from typing import Optional
from difflib import SequenceMatcher
import requests
from bs4 import BeautifulSoup

from app.practices.interfaces import TrailCondition

logger = logging.getLogger(__name__)

BASE_URL = "https://www.skinnyski.com"
REPORTS_URL = f"{BASE_URL}/trails/reports.asp"

# Rate limiting
MIN_REQUEST_INTERVAL_SECONDS = 30
_last_request_time = None

# Simple in-memory cache
_cache = {}
CACHE_TTL_HOURS = 2


class RateLimitError(Exception):
    """Raised when rate limit would be exceeded."""
    pass


def _should_rate_limit() -> bool:
    """Check if we should rate limit the next request."""
    global _last_request_time

    if _last_request_time is None:
        return False

    elapsed = time.time() - _last_request_time
    return elapsed < MIN_REQUEST_INTERVAL_SECONDS


def _update_rate_limit():
    """Update the last request timestamp."""
    global _last_request_time
    _last_request_time = time.time()


def _is_cache_valid(cache_entry: dict) -> bool:
    """Check if a cache entry is still valid."""
    if not cache_entry:
        return False

    cached_at = cache_entry.get('cached_at')
    if not cached_at:
        return False

    age = datetime.utcnow() - cached_at
    return age < timedelta(hours=CACHE_TTL_HOURS)


def _fuzzy_match_location(target: str, candidate: str) -> float:
    """
    Calculate fuzzy match score between two location names.

    Returns score between 0.0 and 1.0, where 1.0 is perfect match.
    """
    # Normalize: lowercase, remove extra whitespace
    target = ' '.join(target.lower().split())
    candidate = ' '.join(candidate.lower().split())

    # Direct match
    if target == candidate:
        return 1.0

    # Substring match
    if target in candidate or candidate in target:
        return 0.9

    # Fuzzy match using SequenceMatcher
    return SequenceMatcher(None, target, candidate).ratio()


def _parse_trail_status(status_text: str) -> str:
    """
    Parse trail status text into standardized value.

    Returns: 'all', 'most', 'partial', 'closed', 'unknown'
    """
    status_lower = status_text.lower().strip()

    # Check most specific patterns first to avoid false matches
    if 'closed' in status_lower or 'none open' in status_lower or status_lower == 'none':
        return 'closed'
    elif 'most' in status_lower:
        return 'most'
    elif 'partial' in status_lower or 'some' in status_lower:
        return 'partial'
    elif 'all' in status_lower:
        return 'all'
    elif 'open' in status_lower:
        # Generic "open" without qualifiers means all trails
        return 'all'
    else:
        return 'unknown'


def _parse_ski_quality(quality_text: str) -> str:
    """
    Parse ski quality text into standardized value.

    Returns: 'excellent', 'good', 'fair', 'poor', 'b_skis', 'rock_skis'
    """
    quality_lower = quality_text.lower().strip()

    if 'excellent' in quality_lower:
        return 'excellent'
    elif 'good' in quality_lower:
        return 'good'
    elif 'fair' in quality_lower:
        return 'fair'
    elif 'poor' in quality_lower:
        return 'poor'
    elif 'rock ski' in quality_lower or 'rocks' in quality_lower:
        return 'rock_skis'
    elif 'b ski' in quality_lower or 'b-ski' in quality_lower:
        return 'b_skis'
    else:
        # Default to fair if unclear
        return 'fair'


def _parse_groomed_for(groomed_text: str) -> Optional[str]:
    """
    Parse grooming information.

    Returns: 'classic', 'skate', 'both', or None
    """
    groomed_lower = groomed_text.lower()

    has_classic = 'classic' in groomed_lower
    has_skate = 'skate' in groomed_lower

    if has_classic and has_skate:
        return 'both'
    elif has_classic:
        return 'classic'
    elif has_skate:
        return 'skate'
    else:
        return None


def _parse_report_date(date_text: str) -> Optional[datetime]:
    """
    Parse report date from various formats.

    SkinnySkI uses formats like:
    - "12/27/2025"
    - "Dec 27, 2025"
    - "Yesterday"
    - "Today"
    """
    date_text = date_text.strip()

    # Handle relative dates
    if date_text.lower() == 'today':
        return datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    elif date_text.lower() == 'yesterday':
        return datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)

    # Try common formats
    formats = [
        '%m/%d/%Y',
        '%m/%d/%y',
        '%b %d, %Y',
        '%B %d, %Y',
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_text, fmt)
        except ValueError:
            continue

    logger.warning(f"Failed to parse date: {date_text}")
    return None


def _scrape_trail_reports() -> list[TrailCondition]:
    """
    Scrape all trail reports from SkinnySkI.

    Returns list of TrailCondition objects.
    """
    logger.info("=" * 50)
    logger.info("TRAIL CONDITIONS: Starting SkinnySkI scrape")
    logger.info(f"  URL: {REPORTS_URL}")

    # Check rate limit
    if _should_rate_limit():
        wait_time = max(0, MIN_REQUEST_INTERVAL_SECONDS - (time.time() - _last_request_time))
        if wait_time > 0:
            logger.warning(f"  Rate limit: waiting {wait_time:.1f} seconds")
            time.sleep(wait_time)

    try:
        start_time = time.time()
        logger.info("  Fetching page...")
        response = requests.get(REPORTS_URL, timeout=15)
        elapsed = time.time() - start_time
        logger.info(f"  Response: {response.status_code} in {elapsed:.2f}s ({len(response.content)} bytes)")
        response.raise_for_status()
        _update_rate_limit()

        soup = BeautifulSoup(response.content, 'html.parser')

        reports = []

        # SkinnySkI uses CSS classes for trail reports:
        # - ss-reporting-trail: Container for each report
        # - ss-trailsopen: Trails open status (e.g., "Trails Open: Most")
        # - ss-skirating: Ski quality rating (e.g., "Good skis")
        # - ss-reporting-text: The report text

        # Find all trail report entries
        report_entries = soup.find_all('span', class_='ss-reporting-trail')
        logger.info(f"  Found {len(report_entries)} trail report entries")

        for entry in report_entries:
            try:
                # Get the parent list item to find all associated elements
                parent = entry.find_parent('li') or entry.find_parent('div')
                if not parent:
                    parent = entry

                # Extract date from the start of the text (e.g., "Jan 8 - ")
                entry_text = entry.get_text(strip=True)
                date_match = re.match(r'^(\w+\s+\d+)\s*-\s*', entry_text)
                report_date = None
                if date_match:
                    date_str = date_match.group(1)
                    # Add current year
                    current_year = datetime.utcnow().year
                    try:
                        report_date = datetime.strptime(f"{date_str}, {current_year}", '%b %d, %Y')
                    except ValueError:
                        logger.debug(f"  Could not parse date: {date_str}")

                # Extract location from link
                location_link = entry.find('a', href=True)
                location = location_link.get_text(strip=True) if location_link else None
                if not location:
                    continue

                # Build report URL
                report_url = REPORTS_URL
                if location_link and location_link.get('href'):
                    href = location_link['href']
                    if not href.startswith('http'):
                        report_url = f"{BASE_URL}/{href.lstrip('/')}"
                    else:
                        report_url = href

                # Find trails open status (in ss-trailsopen span)
                trails_open_span = parent.find('span', class_=lambda x: x and 'ss-trailsopen' in x)
                trails_open = 'unknown'
                if trails_open_span:
                    trails_open_text = trails_open_span.get_text(strip=True)
                    # Parse from "Trails Open: Most" format
                    if ':' in trails_open_text:
                        trails_open = _parse_trail_status(trails_open_text.split(':')[-1].strip())
                    else:
                        trails_open = _parse_trail_status(trails_open_text)

                # Find ski quality rating (in ss-skirating span)
                ski_rating_span = parent.find('span', class_=lambda x: x and 'ss-skirating' in x)
                ski_quality = 'fair'
                if ski_rating_span:
                    ski_quality_text = ski_rating_span.get_text(strip=True)
                    ski_quality = _parse_ski_quality(ski_quality_text)

                # Find grooming technique if mentioned (in ss-technique span)
                technique_span = parent.find('span', class_=lambda x: x and 'ss-technique' in x)
                groomed_for = None
                if technique_span:
                    technique_text = technique_span.get_text(strip=True).lower()
                    if 'classic' in technique_text:
                        groomed_for = 'classic'
                    elif 'freestyle' in technique_text or 'skate' in technique_text:
                        groomed_for = 'skate'

                # Find report text
                report_text_span = parent.find('span', class_='ss-reporting-text')
                notes = report_text_span.get_text(strip=True) if report_text_span else None

                # Check for grooming mentions in notes
                groomed = False
                if notes and 'groom' in notes.lower():
                    groomed = True

                # Extract snow depth if mentioned in notes
                snow_depth = None
                if notes:
                    snow_pattern = r'(\d+\.?\d*)\s*(?:inches|in|")\s*(?:of\s*)?(?:new\s*)?(?:snow)?'
                    matches = re.findall(snow_pattern, notes.lower())
                    if matches:
                        try:
                            snow_depth = float(matches[0])
                        except ValueError:
                            pass

                report = TrailCondition(
                    location=location,
                    trails_open=trails_open,
                    ski_quality=ski_quality,
                    groomed=groomed,
                    groomed_for=groomed_for,
                    snow_depth_inches=snow_depth,
                    new_snow_inches=None,
                    report_date=report_date,
                    report_source='SkinnySkI',
                    report_url=report_url,
                    notes=notes  # Full user report text
                )

                reports.append(report)
                logger.info(f"  + {location}: {trails_open} open, {ski_quality} quality")

            except Exception as e:
                logger.warning(f"  Failed to parse report entry: {e}")
                continue

        logger.info(f"TRAIL CONDITIONS: Scraped {len(reports)} reports total")
        logger.info("=" * 50)
        return reports

    except requests.exceptions.RequestException as e:
        logger.error(f"TRAIL CONDITIONS: Failed to scrape - {e}")
        logger.info("=" * 50)
        raise


def get_all_trail_conditions() -> list[TrailCondition]:
    """
    Get all trail condition reports from SkinnySkI.

    Uses caching with 2-hour TTL. Respects rate limits (30 seconds between requests).

    Returns:
        List of TrailCondition objects
    """
    # Check cache
    cache_key = 'all_reports'
    if cache_key in _cache and _is_cache_valid(_cache[cache_key]):
        logger.info("Returning cached trail reports")
        return _cache[cache_key]['data']

    # Scrape fresh data
    reports = _scrape_trail_reports()

    # Update cache
    _cache[cache_key] = {
        'data': reports,
        'cached_at': datetime.utcnow()
    }

    return reports


def get_trail_conditions(location_name: str) -> Optional[TrailCondition]:
    """
    Get trail conditions for a specific location.

    Uses fuzzy matching to find the best matching location from SkinnySkI reports.

    Args:
        location_name: Name of location (e.g., "Theodore Wirth", "Wirth")

    Returns:
        TrailCondition object if found, None otherwise
    """
    logger.info(f"Looking up trail conditions for '{location_name}'")

    # Get all reports (cached)
    all_reports = get_all_trail_conditions()

    if not all_reports:
        logger.warning("No trail reports available")
        return None

    # Find best match using fuzzy matching
    best_match = None
    best_score = 0.0
    MATCH_THRESHOLD = 0.6  # Minimum similarity score

    for report in all_reports:
        score = _fuzzy_match_location(location_name, report.location)

        if score > best_score:
            best_score = score
            best_match = report

    if best_match and best_score >= MATCH_THRESHOLD:
        logger.info(f"Matched '{location_name}' to '{best_match.location}' (score: {best_score:.2f})")
        return best_match
    else:
        logger.warning(f"No trail report found for '{location_name}' (best score: {best_score:.2f})")
        return None


def clear_cache():
    """Clear the trail conditions cache (useful for testing)."""
    global _cache
    _cache = {}
    logger.info("Cleared trail conditions cache")
