from __future__ import annotations

from typing import Any, Dict, List


def summarise_docs(
    docs: List[Dict[str, Any]],
    title_key: str = "title",
    desc_keys: List[str] = ["details", "description"],
    max_items: int = 100,
    desc_limit: int = 200,
    prefix: str | None = None,
) -> str:
    """Return a curated summary string from docs.

    - `title_key` is the key used for titles.
    - `desc_keys` is the list of keys tried to extract description text.
    - `max_items` limit the amount of docs to include.
    - `desc_limit` truncates long descriptions.
    """
    if not docs:
        return ""
    parts = [prefix or ""]
    count = 0
    for d in docs:
        if count >= max_items:
            break
        title = d.get(title_key, "Untitled")
        desc = ""
        for k in desc_keys:
            desc = d.get(k)
            if desc:
                break
        if not desc:
            desc = ""
        # Sanitise
        if isinstance(desc, str):
            desc = desc.replace("\n", " ").strip()
            if len(desc) > desc_limit:
                desc = desc[: desc_limit - 3] + "..."
        if prefix is None and count == 0:
            parts.append("- {}: {}".format(title, desc))
        else:
            parts.append("- {}: {}".format(title, desc))
        count += 1
    return "\n".join([p for p in parts if p is not None and p != ""]).strip()


def group_and_sort_sponsors(docs: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """Group sponsors into gold/silver/bronze/other and sort alphabetically.

    Returns a mapping tier->list of company entries (name + optional website)
    """
    groups = {"gold": [], "silver": [], "bronze": [], "other": []}
    for s in docs:
        name = s.get("Company name") or s.get("companyName") or s.get("name") or ""
        tier = (s.get("sponsor tier") or s.get("tier") or "").lower().strip()
        website = (
            s.get("website link") or s.get("website") or s.get("website_link") or ""
        )
        entry = name + (f" — {website}" if website else "")
        if "gold" in tier:
            groups["gold"].append(entry)
        elif "silver" in tier:
            groups["silver"].append(entry)
        elif "bronze" in tier:
            groups["bronze"].append(entry)
        else:
            groups["other"].append(entry)
    for key, items in groups.items():
        items.sort(key=lambda s: s.lower())
    return groups
