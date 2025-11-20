from __future__ import annotations

import difflib
import logging
import re
from typing import Optional

from utils import cms


def matches_any(tokens: list[str], keywords: list[str], cutoff: float = 0.8) -> bool:
    """Return True if any token approximately matches any keyword.

    Uses difflib.get_close_matches for fuzzy matching (typos) and exact matching too.
    """
    keywords_lower = [k.lower() for k in keywords]
    for t in tokens:
        # exact checks faster than fuzzy
        if t in keywords_lower:
            return True
        # fuzzy check
        matches = difflib.get_close_matches(t, keywords_lower, n=1, cutoff=cutoff)
        if matches:
            return True
    return False


def _shorten(s: str, n: int) -> str:
    """Shorten string s to at most n characters, adding ellipsis if truncated."""
    if not s:
        return s
    s = s.replace("\n", " ")
    if len(s) <= n:
        return s
    return s[: n - 3] + "..."


def build_cms_context_for_query(message: str, char_limit: Optional[int] = None) -> str:
    """Compose a small CMS context block for a user's query.

    This will only include CMS data if the query references those topics, to
    avoid preloading huge system contexts. The returned string is truncated to
    char_limit characters.
    """
    if not message:
        return ""
    char_limit = 3000
    text = message.lower()
    tokens = re.findall(r"\w+", text)
    parts: list[str] = []

    try:
        # Upcoming events
        if matches_any(
            tokens,
            [
                "event",
                "events",
                "workshop",
                "upcoming",
                "fng",
            ],
        ):
            upcoming = cms.get_upcoming_events(limit=10)
            if upcoming:
                up_parts = ["Upcoming events:"]
                for ev in upcoming:
                    title = ev.get("title", "Untitled").strip()
                    time_info = ev.get("time") or {}
                    start = time_info.get("start") or ev.get("date") or ""
                    end = time_info.get("end") or ""
                    time_range = cms.fmt_time_range_friendly(start, end, ev.get("date"))
                    loc = (ev.get("location") or "").strip()
                    desc = _shorten(
                        ev.get("details") or ev.get("description") or "", 120
                    )
                    up_parts.append(f"- {title} | {time_range} | {loc} | {desc}")
                parts.append("\n".join(up_parts))

        # Past events
        if matches_any(
            tokens,
            [
                "past",
                "last",
                "recent",
                "event",
                "events",
            ],
        ):
            past_result = cms.get_past_events(limit=50, page=1)
            past = past_result.get("docs", [])
            if past:
                p_parts = ["Recent past events:"]
                for ev in past:
                    title = ev.get("title", "Untitled").strip()
                    time_info = ev.get("time") or {}
                    start = time_info.get("start") or ev.get("date") or ""
                    time_range = cms.fmt_time_range_friendly(start, "", ev.get("date"))
                    desc = _shorten(
                        ev.get("details") or ev.get("description") or "", 120
                    )
                    p_parts.append(f"- {title} | {time_range} | {desc}")
                parts.append("\n".join(p_parts))

        # Committee members
        if matches_any(
            tokens,
            [
                "committee",
                "committee members",
                "committee list",
                "commitee",
                "comittee",
            ],
        ):
            csum = cms.get_committee_summary(max_items=100)
            if csum:
                parts.append(csum)

        # Projects
        if matches_any(
            tokens, ["project", "projects", "open", "open source", "open-source"]
        ):
            psum = cms.get_projects_summary(max_items=100)
            if psum:
                parts.append(psum)

        # Sponsors
        if matches_any(tokens, ["sponsor", "sponsors", "company", "sponser"]):
            ssum = cms.get_sponsors_summary(max_items=100)
            if ssum:
                parts.append(ssum)

    except Exception:
        logging.exception("Failed to assemble CMS RAG context for query")

    if not parts:
        return ""

    ctx = "\n\n".join(parts)
    if len(ctx) > char_limit:
        ctx = ctx[: char_limit - 3] + "..."
    return ctx
