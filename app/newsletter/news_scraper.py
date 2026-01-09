"""
News scrapers for the Weekly Dispatch newsletter.

Scrapes local ski news from:
- SkinnySkI (www.skinnyski.com) - News articles, race results
- Loppet Foundation (www.loppet.org) - Trail conditions, events, programs
- Three Rivers Parks (www.threeriversparks.org) - Elm Creek, Hyland conditions

Uses caching and rate limiting to be a good web citizen.
"""

import logging
import re
import time
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urljoin

import requests
import yaml
from bs4 import BeautifulSoup
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from requests.exceptions import RequestException

from app.newsletter.interfaces import NewsItem, NewsSource

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

# Rate limiting - 30 seconds between requests per source
MIN_REQUEST_INTERVAL_SECONDS = 30

# Cache TTL - 2 hours
CACHE_TTL_HOURS = 2

# User agent for requests
USER_AGENT = "TCSC Newsletter Bot/1.0 (Twin Cities Ski Club; contact@twincitiesskiclub.org)"

# Default request timeout
REQUEST_TIMEOUT_SECONDS = 15

# =============================================================================
# Rate Limiting State (per source)
# =============================================================================

_last_request_times: dict[str, float] = {}
_cache: dict[str, dict] = {}


# =============================================================================
# Configuration Loading
# =============================================================================

def _load_config() -> dict:
    """
    Load newsletter configuration from YAML file.

    Returns:
        Configuration dictionary with news_sources settings.
    """
    try:
        with open('config/newsletter.yaml') as f:
            config = yaml.safe_load(f)
        return config.get('newsletter', {})
    except FileNotFoundError:
        logger.warning("config/newsletter.yaml not found, using defaults")
        return {}
    except yaml.YAMLError as e:
        logger.error(f"Failed to parse newsletter config: {e}")
        return {}


def _get_source_config(source_name: str) -> dict:
    """
    Get configuration for a specific news source.

    Args:
        source_name: One of 'skinnyski', 'loppet', 'three_rivers'

    Returns:
        Source configuration dict with enabled, url, max_articles.
    """
    config = _load_config()
    sources = config.get('news_sources', {})
    return sources.get(source_name, {})


def _is_source_enabled(source_name: str) -> bool:
    """Check if a news source is enabled in configuration."""
    source_config = _get_source_config(source_name)
    return source_config.get('enabled', False)


# =============================================================================
# Rate Limiting & Caching
# =============================================================================

def _should_rate_limit(source: str) -> bool:
    """
    Check if we should rate limit requests to a specific source.

    Args:
        source: Source identifier (e.g., 'skinnyski')

    Returns:
        True if we should wait before making a request.
    """
    last_time = _last_request_times.get(source)
    if last_time is None:
        return False
    elapsed = time.time() - last_time
    return elapsed < MIN_REQUEST_INTERVAL_SECONDS


def _wait_for_rate_limit(source: str) -> None:
    """Wait for rate limit to expire for a specific source."""
    last_time = _last_request_times.get(source)
    if last_time is not None:
        elapsed = time.time() - last_time
        wait_time = max(0, MIN_REQUEST_INTERVAL_SECONDS - elapsed)
        if wait_time > 0:
            logger.info(f"Rate limit for {source}: waiting {wait_time:.1f}s")
            time.sleep(wait_time)


def _update_rate_limit(source: str) -> None:
    """Update the last request timestamp for a source."""
    _last_request_times[source] = time.time()


def _get_cached(cache_key: str) -> Optional[list[NewsItem]]:
    """
    Get cached news items if still valid.

    Args:
        cache_key: Cache key for the source

    Returns:
        List of NewsItem if cache is valid, None otherwise.
    """
    entry = _cache.get(cache_key)
    if not entry:
        return None

    cached_at = entry.get('cached_at')
    if not cached_at:
        return None

    age = datetime.utcnow() - cached_at
    if age >= timedelta(hours=CACHE_TTL_HOURS):
        return None

    logger.info(f"Cache hit for {cache_key} (age: {age})")
    return entry.get('data')


def _set_cached(cache_key: str, data: list[NewsItem]) -> None:
    """Store news items in cache."""
    _cache[cache_key] = {
        'data': data,
        'cached_at': datetime.utcnow()
    }


def clear_cache(source: Optional[str] = None) -> None:
    """
    Clear the news cache.

    Args:
        source: If provided, only clear cache for this source.
                If None, clear all cached news.
    """
    global _cache
    if source:
        cache_key = f"news_{source}"
        if cache_key in _cache:
            del _cache[cache_key]
            logger.info(f"Cleared cache for {source}")
    else:
        _cache = {}
        logger.info("Cleared all news cache")


# =============================================================================
# HTTP Request Helper
# =============================================================================

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type(RequestException)
)
def _fetch_page(url: str, source: str) -> BeautifulSoup:
    """
    Fetch and parse an HTML page with retry logic.

    Respects rate limits and includes appropriate headers.

    Args:
        url: URL to fetch
        source: Source identifier for rate limiting

    Returns:
        BeautifulSoup object for the page

    Raises:
        RequestException: If all retries fail
    """
    _wait_for_rate_limit(source)

    headers = {
        'User-Agent': USER_AGENT,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }

    logger.info(f"Fetching {url}")
    start_time = time.time()

    response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()

    elapsed = time.time() - start_time
    _update_rate_limit(source)

    logger.info(f"  Response: {response.status_code} in {elapsed:.2f}s ({len(response.content)} bytes)")

    return BeautifulSoup(response.content, 'html.parser')


# =============================================================================
# Date Parsing Helpers
# =============================================================================

def _parse_date(date_str: str) -> Optional[datetime]:
    """
    Parse a date string from various formats.

    Handles common formats found on ski news sites:
    - "January 8, 2026"
    - "Jan 8, 2026"
    - "1/8/2026"
    - "2026-01-08"
    - "Today"
    - "Yesterday"
    - "3 days ago"

    Args:
        date_str: Date string to parse

    Returns:
        datetime object or None if parsing fails
    """
    if not date_str:
        return None

    date_str = date_str.strip()
    now = datetime.utcnow()

    # Handle relative dates
    lower = date_str.lower()
    if lower == 'today':
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif lower == 'yesterday':
        return now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)

    # Handle "X days ago" patterns
    days_ago_match = re.match(r'(\d+)\s*days?\s*ago', lower)
    if days_ago_match:
        days = int(days_ago_match.group(1))
        return now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days)

    # Handle "X hours ago" patterns
    hours_ago_match = re.match(r'(\d+)\s*hours?\s*ago', lower)
    if hours_ago_match:
        hours = int(hours_ago_match.group(1))
        return now - timedelta(hours=hours)

    # Try common date formats
    formats = [
        '%B %d, %Y',      # January 8, 2026
        '%b %d, %Y',      # Jan 8, 2026
        '%m/%d/%Y',       # 1/8/2026
        '%m/%d/%y',       # 1/8/26
        '%Y-%m-%d',       # 2026-01-08
        '%d %B %Y',       # 8 January 2026
        '%d %b %Y',       # 8 Jan 2026
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    # Try parsing month/day without year (assume current year)
    month_day_formats = [
        '%B %d',    # January 8
        '%b %d',    # Jan 8
    ]

    for fmt in month_day_formats:
        try:
            parsed = datetime.strptime(date_str, fmt)
            # Use current year
            return parsed.replace(year=now.year)
        except ValueError:
            continue

    logger.debug(f"Failed to parse date: {date_str}")
    return None


def _is_recent(published_at: Optional[datetime], since: datetime) -> bool:
    """Check if a publication date is recent enough."""
    if published_at is None:
        # If we can't determine date, include it
        return True
    return published_at >= since


# =============================================================================
# SkinnySkI News Scraper
# =============================================================================

def scrape_skinnyski_news(since: datetime, max_articles: int = 5) -> list[NewsItem]:
    """
    Scrape news articles from SkinnySkI.

    SkinnySkI is the primary source for Minnesota ski news,
    covering race results, trail updates, and community news.

    Args:
        since: Only include articles published after this datetime
        max_articles: Maximum number of articles to return (default 5)

    Returns:
        List of NewsItem objects from SkinnySkI
    """
    source_name = 'skinnyski'

    if not _is_source_enabled(source_name):
        logger.info("SkinnySkI scraper disabled in config")
        return []

    # Check cache first
    cache_key = f"news_{source_name}"
    cached = _get_cached(cache_key)
    if cached is not None:
        # Filter by date and limit
        filtered = [item for item in cached if _is_recent(item.published_at, since)]
        return filtered[:max_articles]

    source_config = _get_source_config(source_name)
    base_url = source_config.get('news_url', 'https://www.skinnyski.com/')

    logger.info("=" * 50)
    logger.info(f"SKINNYSKI: Starting news scrape from {base_url}")

    items: list[NewsItem] = []

    try:
        soup = _fetch_page(base_url, source_name)

        # SkinnySkI homepage has news items in various sections
        # Look for headline entries with ss-headline class
        headline_entries = soup.find_all('span', class_='ss-headline')
        logger.info(f"  Found {len(headline_entries)} headline entries")

        for entry in headline_entries[:max_articles * 2]:  # Get extra for filtering
            try:
                # Find the link within the headline
                link = entry.find('a', href=True)
                if not link:
                    continue

                title = link.get_text(strip=True)
                if not title:
                    continue

                # Build full URL
                href = link['href']
                if not href.startswith('http'):
                    url = urljoin(base_url, href)
                else:
                    url = href

                # Try to find date - usually in parent or sibling elements
                parent = entry.find_parent(['li', 'div', 'tr'])
                published_at = None
                summary = None

                if parent:
                    # Look for date patterns in parent text
                    parent_text = parent.get_text()

                    # SkinnySkI often uses "Mon DD -" format at start
                    date_match = re.search(r'(\w+\s+\d+)\s*[-:]', parent_text)
                    if date_match:
                        date_str = date_match.group(1)
                        current_year = datetime.utcnow().year
                        published_at = _parse_date(f"{date_str}, {current_year}")

                    # Try to extract summary from any text span
                    text_span = parent.find('span', class_='ss-headline-text')
                    if text_span:
                        summary = text_span.get_text(strip=True)[:300]

                # Filter by date
                if not _is_recent(published_at, since):
                    continue

                item = NewsItem(
                    source=NewsSource.SKINNYSKI,
                    title=title,
                    url=url,
                    summary=summary,
                    published_at=published_at
                )
                items.append(item)
                logger.info(f"  + {title[:60]}...")

            except Exception as e:
                logger.warning(f"  Failed to parse headline entry: {e}")
                continue

        # Also look for news blurbs (ss-newsblurb class)
        news_blurbs = soup.find_all('span', class_='ss-newsblurb')
        logger.info(f"  Found {len(news_blurbs)} news blurbs")

        for blurb in news_blurbs[:max_articles]:
            try:
                link = blurb.find('a', href=True)
                if not link:
                    continue

                title = link.get_text(strip=True)
                if not title or len(title) < 10:
                    continue

                href = link['href']
                if not href.startswith('http'):
                    url = urljoin(base_url, href)
                else:
                    url = href

                # Skip if we already have this URL
                if any(item.url == url for item in items):
                    continue

                # Get summary from blurb text
                blurb_text = blurb.get_text(strip=True)
                summary = blurb_text[:300] if blurb_text else None

                item = NewsItem(
                    source=NewsSource.SKINNYSKI,
                    title=title,
                    url=url,
                    summary=summary,
                    published_at=None  # Blurbs often lack dates
                )
                items.append(item)
                logger.info(f"  + {title[:60]}...")

            except Exception as e:
                logger.warning(f"  Failed to parse news blurb: {e}")
                continue

        # Cache all items before filtering
        _set_cached(cache_key, items)

        # Filter by date and limit
        filtered = [item for item in items if _is_recent(item.published_at, since)]
        result = filtered[:max_articles]

        logger.info(f"SKINNYSKI: Returning {len(result)} news items")
        logger.info("=" * 50)

        return result

    except RequestException as e:
        logger.error(f"SKINNYSKI: Failed to scrape - {e}")
        logger.info("=" * 50)
        return []


# =============================================================================
# Loppet Foundation News Scraper
# =============================================================================

def scrape_loppet_news(since: datetime, max_articles: int = 3) -> list[NewsItem]:
    """
    Scrape news and events from Loppet Foundation.

    The Loppet Foundation manages Theodore Wirth Park trails
    and hosts major events like the City of Lakes Loppet.

    Args:
        since: Only include articles published after this datetime
        max_articles: Maximum number of articles to return (default 3)

    Returns:
        List of NewsItem objects from Loppet Foundation
    """
    source_name = 'loppet'

    if not _is_source_enabled(source_name):
        logger.info("Loppet scraper disabled in config")
        return []

    # Check cache first
    cache_key = f"news_{source_name}"
    cached = _get_cached(cache_key)
    if cached is not None:
        filtered = [item for item in cached if _is_recent(item.published_at, since)]
        return filtered[:max_articles]

    source_config = _get_source_config(source_name)
    base_url = source_config.get('url', 'https://www.loppet.org/')

    logger.info("=" * 50)
    logger.info(f"LOPPET: Starting news scrape from {base_url}")

    items: list[NewsItem] = []

    try:
        soup = _fetch_page(base_url, source_name)

        # Loppet.org uses WordPress-style structure
        # Look for article elements, blog entries, event listings
        article_selectors = [
            'article',
            '.post',
            '.blog-post',
            '.news-item',
            '.event-item',
        ]

        articles_found = []
        for selector in article_selectors:
            found = soup.select(selector)
            if found:
                articles_found.extend(found)
                logger.info(f"  Found {len(found)} elements matching '{selector}'")

        # Also look for any links in main content area
        main_content = soup.find(['main', 'article', '#content', '.content'])
        if main_content:
            # Find news-like links
            for link in main_content.find_all('a', href=True):
                href = link['href']
                text = link.get_text(strip=True)

                # Skip navigation, social, etc.
                if not text or len(text) < 15:
                    continue
                if any(skip in href.lower() for skip in ['facebook', 'twitter', 'instagram', '#', 'mailto:']):
                    continue

                # Look for news/blog/event URLs
                if any(keyword in href.lower() for keyword in ['news', 'blog', 'event', 'update', 'trail']):
                    if not href.startswith('http'):
                        url = urljoin(base_url, href)
                    else:
                        url = href

                    # Skip duplicates
                    if any(item.url == url for item in items):
                        continue

                    # Try to find associated date
                    parent = link.find_parent(['li', 'div', 'article'])
                    published_at = None
                    summary = None

                    if parent:
                        # Look for date element
                        date_elem = parent.find(['time', '.date', '.post-date'])
                        if date_elem:
                            date_str = date_elem.get('datetime') or date_elem.get_text(strip=True)
                            published_at = _parse_date(date_str)

                        # Try to get excerpt/summary
                        excerpt = parent.find(['.excerpt', '.summary', 'p'])
                        if excerpt:
                            summary = excerpt.get_text(strip=True)[:300]

                    # Filter by date
                    if not _is_recent(published_at, since):
                        continue

                    item = NewsItem(
                        source=NewsSource.LOPPET,
                        title=text,
                        url=url,
                        summary=summary,
                        published_at=published_at
                    )
                    items.append(item)
                    logger.info(f"  + {text[:60]}...")

                    if len(items) >= max_articles * 2:
                        break

        # Look for event listings specifically
        events_section = soup.find(class_=re.compile(r'event', re.I))
        if events_section:
            for event_link in events_section.find_all('a', href=True)[:max_articles]:
                try:
                    href = event_link['href']
                    title = event_link.get_text(strip=True)

                    if not title or len(title) < 10:
                        continue

                    if not href.startswith('http'):
                        url = urljoin(base_url, href)
                    else:
                        url = href

                    # Skip if already have this URL
                    if any(item.url == url for item in items):
                        continue

                    item = NewsItem(
                        source=NewsSource.LOPPET,
                        title=title,
                        url=url,
                        summary=None,
                        published_at=None
                    )
                    items.append(item)
                    logger.info(f"  + Event: {title[:60]}...")

                except Exception as e:
                    logger.warning(f"  Failed to parse event: {e}")
                    continue

        # Cache all items
        _set_cached(cache_key, items)

        # Filter and limit
        filtered = [item for item in items if _is_recent(item.published_at, since)]
        result = filtered[:max_articles]

        logger.info(f"LOPPET: Returning {len(result)} news items")
        logger.info("=" * 50)

        return result

    except RequestException as e:
        logger.error(f"LOPPET: Failed to scrape - {e}")
        logger.info("=" * 50)
        return []


# =============================================================================
# Three Rivers Parks Scraper
# =============================================================================

def scrape_three_rivers_news(since: datetime, max_articles: int = 3) -> list[NewsItem]:
    """
    Scrape news and trail updates from Three Rivers Park District.

    Three Rivers manages Elm Creek and Hyland Lake ski areas,
    popular destinations for Twin Cities skiers.

    Args:
        since: Only include articles published after this datetime
        max_articles: Maximum number of articles to return (default 3)

    Returns:
        List of NewsItem objects from Three Rivers Parks
    """
    source_name = 'three_rivers'

    if not _is_source_enabled(source_name):
        logger.info("Three Rivers scraper disabled in config")
        return []

    # Check cache first
    cache_key = f"news_{source_name}"
    cached = _get_cached(cache_key)
    if cached is not None:
        filtered = [item for item in cached if _is_recent(item.published_at, since)]
        return filtered[:max_articles]

    source_config = _get_source_config(source_name)
    base_url = source_config.get('url', 'https://www.threeriversparks.org/')

    logger.info("=" * 50)
    logger.info(f"THREE_RIVERS: Starting news scrape from {base_url}")

    items: list[NewsItem] = []

    try:
        soup = _fetch_page(base_url, source_name)

        # Three Rivers uses a custom CMS
        # Look for news/blog sections and activity updates
        content_selectors = [
            '.news-item',
            '.blog-post',
            '.activity-card',
            '.event-card',
            'article',
        ]

        for selector in content_selectors:
            elements = soup.select(selector)
            if elements:
                logger.info(f"  Found {len(elements)} elements matching '{selector}'")
                for elem in elements[:max_articles]:
                    try:
                        link = elem.find('a', href=True)
                        if not link:
                            continue

                        title_elem = elem.find(['h2', 'h3', 'h4', '.title'])
                        title = title_elem.get_text(strip=True) if title_elem else link.get_text(strip=True)

                        if not title or len(title) < 10:
                            continue

                        href = link['href']
                        if not href.startswith('http'):
                            url = urljoin(base_url, href)
                        else:
                            url = href

                        # Skip duplicates
                        if any(item.url == url for item in items):
                            continue

                        # Look for date
                        date_elem = elem.find(['time', '.date', '.post-date'])
                        published_at = None
                        if date_elem:
                            date_str = date_elem.get('datetime') or date_elem.get_text(strip=True)
                            published_at = _parse_date(date_str)

                        # Get excerpt
                        excerpt_elem = elem.find(['.excerpt', '.summary', 'p'])
                        summary = excerpt_elem.get_text(strip=True)[:300] if excerpt_elem else None

                        # Filter by date
                        if not _is_recent(published_at, since):
                            continue

                        item = NewsItem(
                            source=NewsSource.THREE_RIVERS,
                            title=title,
                            url=url,
                            summary=summary,
                            published_at=published_at
                        )
                        items.append(item)
                        logger.info(f"  + {title[:60]}...")

                    except Exception as e:
                        logger.warning(f"  Failed to parse content item: {e}")
                        continue

        # Look for ski/winter specific links if we haven't found much
        if len(items) < max_articles:
            # Search for links containing ski-related keywords
            ski_keywords = ['ski', 'winter', 'snow', 'trail', 'elm creek', 'hyland']

            for link in soup.find_all('a', href=True):
                href = link['href'].lower()
                text = link.get_text(strip=True)

                # Check if link relates to skiing
                if any(kw in href or kw in text.lower() for kw in ski_keywords):
                    if len(text) < 15:
                        continue
                    if any(skip in href for skip in ['#', 'mailto:', 'tel:']):
                        continue

                    full_url = urljoin(base_url, link['href'])

                    # Skip duplicates
                    if any(item.url == full_url for item in items):
                        continue

                    item = NewsItem(
                        source=NewsSource.THREE_RIVERS,
                        title=text,
                        url=full_url,
                        summary=None,
                        published_at=None
                    )
                    items.append(item)
                    logger.info(f"  + Ski-related: {text[:60]}...")

                    if len(items) >= max_articles * 2:
                        break

        # Cache all items
        _set_cached(cache_key, items)

        # Filter and limit
        filtered = [item for item in items if _is_recent(item.published_at, since)]
        result = filtered[:max_articles]

        logger.info(f"THREE_RIVERS: Returning {len(result)} news items")
        logger.info("=" * 50)

        return result

    except RequestException as e:
        logger.error(f"THREE_RIVERS: Failed to scrape - {e}")
        logger.info("=" * 50)
        return []


# =============================================================================
# Aggregate Scraper
# =============================================================================

def scrape_all_news(since: datetime) -> list[NewsItem]:
    """
    Scrape news from all configured sources.

    Combines results from SkinnySkI, Loppet, and Three Rivers
    sorted by publication date (newest first).

    Args:
        since: Only include articles published after this datetime

    Returns:
        Combined list of NewsItem from all sources, sorted by date
    """
    logger.info("=" * 60)
    logger.info(f"NEWS SCRAPER: Collecting news since {since.isoformat()}")
    logger.info("=" * 60)

    all_items: list[NewsItem] = []
    errors: list[str] = []

    # Load config for max_articles per source
    config = _load_config()
    sources_config = config.get('news_sources', {})

    # Scrape each source
    sources = [
        ('skinnyski', scrape_skinnyski_news, sources_config.get('skinnyski', {}).get('max_articles', 5)),
        ('loppet', scrape_loppet_news, sources_config.get('loppet', {}).get('max_articles', 3)),
        ('three_rivers', scrape_three_rivers_news, sources_config.get('three_rivers', {}).get('max_articles', 3)),
    ]

    for source_name, scraper_func, max_articles in sources:
        try:
            items = scraper_func(since, max_articles)
            all_items.extend(items)
            logger.info(f"  {source_name}: {len(items)} items")
        except Exception as e:
            error_msg = f"{source_name}: {str(e)}"
            errors.append(error_msg)
            logger.error(f"  Failed to scrape {source_name}: {e}")

    # Sort by publication date (newest first), with None dates last
    def sort_key(item: NewsItem) -> tuple:
        if item.published_at is None:
            return (0, datetime.min)  # Put undated items last
        return (1, item.published_at)

    all_items.sort(key=sort_key, reverse=True)

    logger.info("=" * 60)
    logger.info(f"NEWS SCRAPER: Total {len(all_items)} items from all sources")
    if errors:
        logger.warning(f"  Errors: {', '.join(errors)}")
    logger.info("=" * 60)

    return all_items


# =============================================================================
# Utility Functions
# =============================================================================

def get_scraper_status() -> dict:
    """
    Get status information about the news scrapers.

    Returns dict with:
    - sources: List of source status dicts
    - cache_entries: Number of cached entries
    - cache_age: Age of oldest cache entry
    """
    config = _load_config()
    sources_config = config.get('news_sources', {})

    sources_status = []
    for source_name in ['skinnyski', 'loppet', 'three_rivers']:
        source_cfg = sources_config.get(source_name, {})
        cache_key = f"news_{source_name}"
        cached_entry = _cache.get(cache_key)

        status = {
            'name': source_name,
            'enabled': source_cfg.get('enabled', False),
            'max_articles': source_cfg.get('max_articles', 3),
            'cached': cached_entry is not None,
            'cache_age_minutes': None,
            'last_request': None,
        }

        if cached_entry and cached_entry.get('cached_at'):
            age = datetime.utcnow() - cached_entry['cached_at']
            status['cache_age_minutes'] = int(age.total_seconds() / 60)

        if source_name in _last_request_times:
            elapsed = time.time() - _last_request_times[source_name]
            status['last_request'] = int(elapsed)

        sources_status.append(status)

    return {
        'sources': sources_status,
        'cache_entries': len(_cache),
        'rate_limit_seconds': MIN_REQUEST_INTERVAL_SECONDS,
        'cache_ttl_hours': CACHE_TTL_HOURS,
    }
