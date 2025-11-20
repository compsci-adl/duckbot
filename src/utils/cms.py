from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import requests

from utils import cms_helpers

BASE_CMS_URL = "https://cms.csclub.org.au/api"
CACHE_TTL = 86400  # 1 day

EVENTS_ENDPOINT = "events"
COMMITTEE_ENDPOINT = "committee-members"
PROJECTS_ENDPOINT = "projects"
SPONSORS_ENDPOINT = "sponsors"

_memory_cache = {}
_cache_times = {}


def _fetch_from_cms(
    endpoint: str, params: Dict[str, Any] | None = None, timeout: int = 50
) -> Optional[Dict[str, Any]]:
    """Fetch raw JSON data from the CMS API endpoint with optional query params."""
    url = f"{BASE_CMS_URL}/{endpoint.lstrip('/')}"
    try:
        # Ensure a default limit for CMS queries unless explicitly provided by callers
        if params is None:
            params = {"limit": 500}
        elif "limit" not in params:
            # Don't mutate caller's dict
            params = dict(params)
            params["limit"] = 500

        if params:
            resp = requests.get(url, params=params, timeout=timeout)
        else:
            resp = requests.get(url, timeout=timeout)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        return None
    return None


def _get_cached(
    endpoint: str, params: Dict[str, Any] | None, cache_key: str, force: bool = False
) -> Optional[Dict[str, Any]]:
    """Get cached CMS data for the given endpoint and params, or fetch if stale/missing."""
    now = datetime.now(timezone.utc)
    if not force and cache_key in _memory_cache and cache_key in _cache_times:
        if (now - _cache_times[cache_key]).total_seconds() < CACHE_TTL:
            return _memory_cache[cache_key]

    resp = _fetch_from_cms(endpoint, params=params)
    if resp is not None:
        _memory_cache[cache_key] = resp
        _cache_times[cache_key] = now
        return resp

    # Fallback to stale cache on failure
    if cache_key in _memory_cache:
        return _memory_cache[cache_key]

    return None


def _parse_iso(dt_str: str) -> Optional[datetime]:
    """Parse an ISO datetime string into a datetime object, handling 'Z' suffix."""
    if not dt_str:
        return None
    try:
        if dt_str.endswith("Z"):
            dt_str = dt_str.replace("Z", "+00:00")
        return datetime.fromisoformat(dt_str)
    except Exception:
        return None


def get_cached_events(force: bool = False) -> Optional[Dict[str, Any]]:
    """Return cached events data from CMS, fetching if needed."""
    return _get_cached(EVENTS_ENDPOINT, params=None, cache_key="events", force=force)


def get_upcoming_events(limit: int = 50, force: bool = False) -> List[Dict[str, Any]]:
    """Return a list of upcoming events sorted by date."""
    data = get_cached_events(force=force)
    if not data:
        return []
    docs = data.get("docs", [])
    events = []
    now = datetime.now(timezone.utc)
    for d in docs:
        date_field = d.get("date") or (d.get("time") or {}).get("start")
        dt = _parse_iso(date_field) if date_field else None
        if dt is None:
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if dt >= now:
            d_copy = dict(d)
            d_copy["_parsed_date"] = dt
            events.append(d_copy)
    events.sort(key=lambda x: x["_parsed_date"])
    return events[:limit]


def get_upcoming_events_page(
    limit: int = 50, page: int = 1, force: bool = False
) -> Dict[str, Any]:
    """Return upcoming events paginated locally with the same metadata as get_past_events.

    This uses the cached events payload, filters to events with date >= now and paginates locally.
    """
    data = get_cached_events(force=force)
    if not data:
        return {"docs": [], "page": page, "totalPages": 0, "totalDocs": 0}
    docs = data.get("docs", [])
    events = []
    now = datetime.now(timezone.utc)
    for d in docs:
        date_field = d.get("date") or (d.get("time") or {}).get("start")
        dt = _parse_iso(date_field) if date_field else None
        if dt is None:
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if dt >= now:
            d_copy = dict(d)
            d_copy["_parsed_date"] = dt
            events.append(d_copy)
    events.sort(key=lambda x: x["_parsed_date"])
    total_docs = len(events)
    total_pages = (total_docs + limit - 1) // limit if total_docs > 0 else 1
    start_idx = (page - 1) * limit
    docs_page = events[start_idx : start_idx + limit]
    return {
        "docs": docs_page,
        "page": page,
        "totalPages": total_pages,
        "totalDocs": total_docs,
    }


def get_past_events(
    limit: int = 50, page: int = 1, year: int | None = None, force: bool = False
) -> Dict[str, Any]:
    """Return a paginated dict with keys: docs, page, totalPages, totalDocs.

    - If `year` is provided, filter events by year and paginate locally.
    - Otherwise, request the CMS with page and limit params and return the server-side pagination metadata.
    """
    if year is None:
        params = {"page": page, "limit": limit}
        cache_key = f"events_page_{page}_limit_{limit}"
        data = _get_cached(
            EVENTS_ENDPOINT, params=params, cache_key=cache_key, force=force
        )
        if not data:
            return {"docs": [], "page": page, "totalPages": 0, "totalDocs": 0}
        # Server-side pagination
        docs = data.get("docs", [])
        page_num = data.get("page", page)
        total_pages = data.get("totalPages", 1)
        total_docs = data.get("totalDocs", len(docs))
        # Normalise docs: add parsed date
        events = []
        for d in docs:
            date_field = d.get("date") or (d.get("time") or {}).get("start")
            dt = _parse_iso(date_field) if date_field else None
            if dt is not None:
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                d_copy = dict(d)
                d_copy["_parsed_date"] = dt
                events.append(d_copy)
            else:
                events.append(d)
        return {
            "docs": events,
            "page": page_num,
            "totalPages": total_pages,
            "totalDocs": total_docs,
        }
    else:
        data = get_cached_events(force=force)
        if not data:
            return {"docs": [], "page": page, "totalPages": 0, "totalDocs": 0}
        docs = data.get("docs", [])
        events = []
        for doc in docs:
            date_field = doc.get("date") or (doc.get("time") or {}).get("start")
            dt = _parse_iso(date_field) if date_field else None
            if dt is None:
                continue
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt.year == year:
                d_copy = dict(doc)
                d_copy["_parsed_date"] = dt
                events.append(d_copy)
        events.sort(key=lambda x: x["_parsed_date"], reverse=True)
        total_docs = len(events)
        total_pages = (total_docs + limit - 1) // limit
        start_idx = (page - 1) * limit
        docs_page = events[start_idx : start_idx + limit]
        return {
            "docs": docs_page,
            "page": page,
            "totalPages": total_pages,
            "totalDocs": total_docs,
        }


def get_committee_members(limit: int = 50, force: bool = False) -> List[Dict[str, Any]]:
    """Return a list of committee members from CMS."""
    data = _get_cached(
        COMMITTEE_ENDPOINT, params=None, cache_key="committee", force=force
    )
    if not data:
        return []
    docs = data.get("docs", [])
    return docs[:limit]


def get_committee_summary(max_items: int = 50) -> str:
    """Return a summary string of committee members."""
    members = get_committee_members(limit=max_items)
    if not members:
        return "No committee members found."
    return cms_helpers.summarise_docs(
        members,
        title_key="name",
        desc_keys=["role"],
        max_items=max_items,
        desc_limit=200,
        prefix="Committee members:",
    )


def get_projects(limit: int = 50, force: bool = False) -> List[Dict[str, Any]]:
    """Return a list of open-source projects from CMS."""
    data = _get_cached(
        PROJECTS_ENDPOINT, params=None, cache_key="projects", force=force
    )
    if not data:
        return []
    docs = data.get("docs", [])
    return docs[:limit]


def get_projects_summary(max_items: int = 50) -> str:
    """Return a summary string of open-source projects."""
    projects = get_projects(limit=max_items)
    if not projects:
        return "No open-source projects listed."
    return cms_helpers.summarise_docs(
        projects,
        title_key="title",
        desc_keys=["description"],
        max_items=max_items,
        desc_limit=200,
        prefix="Open-source projects:",
    )


def get_sponsors(limit: int = 50, force: bool = False) -> List[Dict[str, Any]]:
    """Return a list of sponsors from CMS."""
    data = _get_cached(
        SPONSORS_ENDPOINT, params=None, cache_key="sponsors", force=force
    )
    if not data:
        return []
    docs = data.get("docs", [])
    return docs[:limit]


def get_sponsors_summary(max_items: int = 50) -> str:
    """Return a summary string of sponsors."""
    sponsors = get_sponsors(limit=max_items)
    if not sponsors:
        return "No sponsors listed."
    groups = cms_helpers.group_and_sort_sponsors(sponsors)
    parts = ["Sponsors:"]
    order = ["gold", "silver", "bronze", "other"]
    for tier in order:
        items = groups.get(tier, [])
        if items:
            parts.append(tier.capitalize() + ":")
            for i in items:
                parts.append(f"- {i}")
    return "\n".join(parts)


def _ordinal(n: int) -> str:
    """Return ordinal string for an integer n (e.g., 1 -> '1st')."""
    if 10 <= (n % 100) <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def fmt_iso_to_adelaide_friendly(dt_str: str) -> str:
    """Return a friendly Adelaide datetime string like '6:30pm on 23rd of September'."""
    if not dt_str:
        return ""
    try:
        s = dt_str
        if s.endswith("Z"):
            s = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        adelaide_tz = ZoneInfo("Australia/Adelaide")
        dt = dt.astimezone(adelaide_tz)
        time_part = dt.strftime("%I:%M%p").lstrip("0").lower()
        day = _ordinal(dt.day)
        month = dt.strftime("%B")
        return f"{time_part} on {day} of {month}"
    except Exception:
        return dt_str


def fmt_time_range_friendly(
    start_str: str, end_str: str, date_override: str | None = None
) -> str:
    """Return a friendly time range in Adelaide timezone. Uses `date_override` to prefer the `date` field for displayed day."""
    if not start_str and not end_str:
        return ""

    def _parse_to_adelaide(dt_str: str):
        if not dt_str:
            return None
        s = dt_str
        if s.endswith("Z"):
            s = s.replace("Z", "+00:00")
        try:
            d = datetime.fromisoformat(s)
        except Exception:
            return None
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(ZoneInfo("Australia/Adelaide"))

    start_dt = _parse_to_adelaide(start_str)
    end_dt = _parse_to_adelaide(end_str)
    date_dt = _parse_to_adelaide(date_override) if date_override else None

    if start_dt is None and end_dt is not None:
        time_part = end_dt.strftime("%I:%M%p").lstrip("0").lower()
        day = _ordinal(end_dt.day)
        month = end_dt.strftime("%B")
        return f"Ends at {time_part} on {day} of {month}"

    if start_dt is not None and end_dt is None:
        time_part = start_dt.strftime("%I:%M%p").lstrip("0").lower()
        day = _ordinal(start_dt.day)
        month = start_dt.strftime("%B")
        return f"{time_part} on {day} of {month}"

    if start_dt is not None and end_dt is not None:
        start_time = start_dt.strftime("%I:%M%p").lstrip("0").lower()
        end_time = end_dt.strftime("%I:%M%p").lstrip("0").lower()
        if date_dt is not None:
            day = _ordinal(date_dt.day)
            month = date_dt.strftime("%B")
            return f"{start_time} to {end_time} on {day} of {month}"
        start_day = start_dt.date()
        end_day = end_dt.date()
        if start_day == end_day:
            day = _ordinal(start_dt.day)
            month = start_dt.strftime("%B")
            return f"{start_time} to {end_time} on {day} of {month}"
        else:
            sday = _ordinal(start_dt.day)
            smonth = start_dt.strftime("%B")
            eday = _ordinal(end_dt.day)
            emonth = end_dt.strftime("%B")
            return f"{start_time} on {sday} of {smonth} to {end_time} on {eday} of {emonth}"

    return ""
