import asyncio
import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import discord
from discord.enums import EntityType, EventStatus, PrivacyLevel
from discord.http import Route

from models.databases.admin_settings_db import AdminSettingsDB
from utils import cms

ADELAIDE_TZ = ZoneInfo("Australia/Adelaide")


@dataclass
class NormalizedEvent:
    cms_id: str
    event_type: str  # 'main' or 'common'
    name: str
    description: str
    location: str
    start_time: datetime
    end_time: datetime
    image_url: Optional[str]
    cms_updated_at: Optional[str]
    recurrence_rule: Optional[Dict[str, Any]] = None


@dataclass
class SyncResult:
    guild_id: str
    guild_name: str
    created: int = 0
    updated: int = 0
    cancelled: int = 0
    unchanged: int = 0
    cleared: int = 0
    errors: List[str] = field(default_factory=list)
    details: List[str] = field(default_factory=list)


class EventSyncManager:
    """Synchronizes CS Club events from Payload CMS to Discord Scheduled Events."""

    def __init__(self, bot: discord.Client, db: Optional[AdminSettingsDB] = None):
        self.bot = bot
        self.db = db or AdminSettingsDB()
        self.sync_task: Optional[asyncio.Task] = None
        self._sync_lock = asyncio.Lock()

    def _format_main_event_description(self, doc: Dict[str, Any]) -> str:
        """Format description for a main event from CMS doc, including links if present."""
        details = (doc.get("details") or doc.get("description") or "").strip()

        link = doc.get("link")
        if isinstance(link, dict):
            url = link.get("Link") or link.get("url") or ""
            text = link.get("displayText") or url
            if url:
                link_line = (
                    f"Link: [{text}]({url})" if text and text != url else f"Link: {url}"
                )
                details = f"{details}\n\n{link_line}".strip() if details else link_line
        elif isinstance(link, str) and link.strip():
            details = (
                f"{details}\n\nLink: {link.strip()}".strip()
                if details
                else f"Link: {link.strip()}"
            )

        # Discord scheduled event description limit is 1000 characters
        if len(details) > 1000:
            details = details[:997] + "..."
        return details

    def _normalize_main_event(self, doc: Dict[str, Any]) -> Optional[NormalizedEvent]:
        """Normalize a main event doc from CMS into a NormalizedEvent."""
        if doc.get("_status") != "published":
            return None

        event_id = str(doc.get("id", "")).strip()
        if not event_id:
            return None

        title = (doc.get("title") or "CS Club Event").strip()[:100]

        time_info = doc.get("time") or {}
        date_str = doc.get("date")
        start_time_str = time_info.get("start")
        end_time_str = time_info.get("end")

        date_dt = cms._parse_iso(date_str) if date_str else None
        start_time_dt = cms._parse_iso(start_time_str) if start_time_str else None
        end_time_dt = cms._parse_iso(end_time_str) if end_time_str else None

        if date_dt:
            date_adl = (
                date_dt
                if date_dt.tzinfo is not None
                else date_dt.replace(tzinfo=timezone.utc)
            ).astimezone(ADELAIDE_TZ)

            if start_time_dt:
                start_adl = (
                    start_time_dt
                    if start_time_dt.tzinfo is not None
                    else start_time_dt.replace(tzinfo=timezone.utc)
                ).astimezone(ADELAIDE_TZ)
                start_dt_adl = datetime(
                    date_adl.year,
                    date_adl.month,
                    date_adl.day,
                    start_adl.hour,
                    start_adl.minute,
                    start_adl.second,
                    tzinfo=ADELAIDE_TZ,
                )
            else:
                start_dt_adl = datetime(
                    date_adl.year,
                    date_adl.month,
                    date_adl.day,
                    date_adl.hour,
                    date_adl.minute,
                    date_adl.second,
                    tzinfo=ADELAIDE_TZ,
                )

            if end_time_dt:
                end_adl = (
                    end_time_dt
                    if end_time_dt.tzinfo is not None
                    else end_time_dt.replace(tzinfo=timezone.utc)
                ).astimezone(ADELAIDE_TZ)
                end_dt_adl = datetime(
                    date_adl.year,
                    date_adl.month,
                    date_adl.day,
                    end_adl.hour,
                    end_adl.minute,
                    end_adl.second,
                    tzinfo=ADELAIDE_TZ,
                )
                if end_dt_adl <= start_dt_adl:
                    # Overnight event ending the next morning
                    end_dt_adl += timedelta(days=1)
            else:
                end_dt_adl = start_dt_adl + timedelta(hours=2)

            start_dt = start_dt_adl.astimezone(timezone.utc)
            end_dt = end_dt_adl.astimezone(timezone.utc)
        elif start_time_dt:
            # Fallback if doc has no 'date' but has 'time.start'
            start_dt = (
                start_time_dt
                if start_time_dt.tzinfo is not None
                else start_time_dt.replace(tzinfo=timezone.utc)
            ).astimezone(timezone.utc)
            if end_time_dt:
                end_dt = (
                    end_time_dt
                    if end_time_dt.tzinfo is not None
                    else end_time_dt.replace(tzinfo=timezone.utc)
                ).astimezone(timezone.utc)
            else:
                end_dt = start_dt + timedelta(hours=2)
        else:
            return None

        # Discord external events require end_time > start_time
        if end_dt <= start_dt:
            end_dt = start_dt + timedelta(hours=2)

        location = (doc.get("location") or "CS Club / University of Adelaide").strip()[
            :100
        ]
        description = self._format_main_event_description(doc)

        banner = doc.get("banner")
        banner_url = None
        if isinstance(banner, dict):
            banner_url = banner.get("url")
        elif isinstance(banner, str):
            banner_url = banner

        return NormalizedEvent(
            cms_id=event_id,
            event_type="main",
            name=title,
            description=description,
            location=location,
            start_time=start_dt,
            end_time=end_dt,
            image_url=banner_url,
            cms_updated_at=doc.get("updatedAt"),
        )

    def _normalize_common_events(self, doc: Dict[str, Any]) -> List[NormalizedEvent]:
        """Normalize a common recurring event doc into a single combined recurring NormalizedEvent."""
        if doc.get("_status") != "published":
            return []

        doc_id = str(doc.get("id", "")).strip()
        doc_name = (doc.get("name") or "Friday Night Games").strip()[:100]
        upcoming_dates = doc.get("upcomingDates") or []

        banner = doc.get("banner")
        banner_url = None
        if isinstance(banner, dict):
            banner_url = banner.get("url")
        elif isinstance(banner, str):
            banner_url = banner

        # Default description if not provided in doc
        doc_desc = (doc.get("description") or doc.get("details") or "").strip()
        if not doc_desc:
            name_lower = doc_name.lower()
            if "food" in name_lower:
                doc_desc = (
                    "Friday Night Games with Food in the Duck Lounge (EM110)!\n\n"
                    "Join us from 5:00 PM for weekly games, Nintendo Switch, board games, "
                    "and FREE FOOD for all CS Club members!"
                )
            elif (
                "friday night" in name_lower
                or "fng" in name_lower
                or "game" in name_lower
            ):
                doc_desc = (
                    "Friday Night Games in the Duck Lounge (EM110)!\n\n"
                    "Join us from 5:00 PM for weekly games, Nintendo Switch, board games, "
                    "and hanging out with fellow members!"
                )
            else:
                doc_desc = f"{doc_name} in the Duck Lounge (EM110)! Join us for CS Club games and fun."

        if len(doc_desc) > 1000:
            doc_desc = doc_desc[:997] + "..."

        location = (doc.get("location") or "Duck Lounge (EM110)").strip()[:100]

        valid_dates = []
        for entry in upcoming_dates:
            date_str = entry.get("date")
            if not date_str:
                continue

            dt = cms._parse_iso(date_str)
            if not dt:
                continue

            # Convert to Adelaide timezone to determine date
            dt_adelaide = dt if dt.tzinfo is None else dt.astimezone(ADELAIDE_TZ)
            # Normalise start to 5:00 PM (17:00) Adelaide time, duration 4 hours (until 21:00)
            start_adelaide = datetime(
                dt_adelaide.year,
                dt_adelaide.month,
                dt_adelaide.day,
                17,
                0,
                0,
                tzinfo=ADELAIDE_TZ,
            )
            end_adelaide = datetime(
                dt_adelaide.year,
                dt_adelaide.month,
                dt_adelaide.day,
                21,
                0,
                0,
                tzinfo=ADELAIDE_TZ,
            )
            valid_dates.append((start_adelaide, end_adelaide))

        now_adelaide = datetime.now(ADELAIDE_TZ)
        weekday = 4  # Default to Friday
        if valid_dates:
            weekday = valid_dates[0][0].weekday()

        # Find the next upcoming occurrence of this weekday starting from now
        days_ahead = (weekday - now_adelaide.weekday()) % 7
        next_date = now_adelaide.date() + timedelta(days=days_ahead)
        target_start_adelaide = datetime(
            next_date.year, next_date.month, next_date.day, 17, 0, 0, tzinfo=ADELAIDE_TZ
        )
        target_end_adelaide = datetime(
            next_date.year, next_date.month, next_date.day, 21, 0, 0, tzinfo=ADELAIDE_TZ
        )
        # If the calculated start time for today has already passed, advance to the next week's occurrence
        if target_start_adelaide <= now_adelaide:
            target_start_adelaide += timedelta(days=7)
            target_end_adelaide += timedelta(days=7)

        start_utc = target_start_adelaide.astimezone(timezone.utc)
        end_utc = target_end_adelaide.astimezone(timezone.utc)
        weekday = target_start_adelaide.weekday()

        # Recurrence rule: repeats weekly on this weekday
        recurrence_rule = {
            "start": start_utc.isoformat(),
            "frequency": 2,  # 2 = WEEKLY
            "interval": 1,  # 1 = every week
            "by_weekday": [weekday],
        }

        return [
            NormalizedEvent(
                cms_id=f"common_{doc_id}",
                event_type="common",
                name=doc_name,
                description=doc_desc,
                location=location,
                start_time=start_utc,
                end_time=end_utc,
                image_url=banner_url,
                cms_updated_at=doc.get("updatedAt"),
                recurrence_rule=recurrence_rule,
            )
        ]

    def fetch_all_normalized_events(self, force: bool = True) -> List[NormalizedEvent]:
        """Fetch all upcoming published events from both main events and common events endpoints."""
        normalized: List[NormalizedEvent] = []
        now = datetime.now(timezone.utc)

        # 1. Main events
        main_docs = cms.get_all_events(force=force)
        for doc in main_docs:
            ev = self._normalize_main_event(doc)
            if ev and ev.end_time > now:
                normalized.append(ev)

        # 2. Common recurring events (e.g. Friday Night Games)
        common_docs = cms.get_common_events(force=force)
        for doc in common_docs:
            sub_events = self._normalize_common_events(doc)
            for ev in sub_events:
                if ev.end_time > now:
                    normalized.append(ev)

        # Sort chronologically
        normalized.sort(key=lambda x: x.start_time)
        return normalized

    async def _resolve_guild_scheduled_events(
        self, guild: discord.Guild
    ) -> Dict[int, discord.ScheduledEvent]:
        """Fetch scheduled events from guild cache or Discord API, keyed by event ID."""
        try:
            fetched = await guild.fetch_scheduled_events()
            return {e.id: e for e in fetched}
        except Exception as e:
            logging.warning(
                f"Failed to fetch scheduled events for guild {guild.id} via API ({e}); falling back to cache."
            )
            return {e.id: e for e in guild.scheduled_events}

    async def sync_guild_events(
        self, guild: discord.Guild, force_cms: bool = True, check_enabled: bool = True
    ) -> SyncResult:
        """Synchronize all upcoming events to a specific Discord guild."""
        res = SyncResult(guild_id=str(guild.id), guild_name=guild.name)

        # Feature is disabled by default; requires explicit enablement per guild
        if check_enabled and not self.db.is_event_sync_enabled(str(guild.id)):
            msg = (
                f"Event synchronization is disabled for {guild.name}. "
                "Enable it with '/admin set event-sync enabled:True'."
            )
            logging.info(msg)
            res.errors.append(msg)
            return res

        # Check permissions
        if not guild.me.guild_permissions.manage_events:
            msg = f"Bot lacks 'Manage Events' permission in guild {guild.name} ({guild.id})."
            logging.warning(msg)
            res.errors.append(msg)
            return res

        now = datetime.now(timezone.utc)
        normalized_events = self.fetch_all_normalized_events(force=force_cms)
        logging.info(
            f"Syncing {len(normalized_events)} upcoming CMS event(s) to guild {guild.name} ({guild.id})"
        )

        discord_events = await self._resolve_guild_scheduled_events(guild)
        cms_ids_seen = set()

        for ev in normalized_events:
            cms_ids_seen.add(ev.cms_id)
            try:
                await self._sync_single_event(guild, ev, discord_events, now, res)
            except Exception as e:
                err_msg = f"Error syncing event '{ev.name}' ({ev.cms_id}): {e}"
                logging.exception(err_msg)
                res.errors.append(err_msg)
            # Small delay to respect Discord rate limits
            await asyncio.sleep(0.5)

        # Cancel / cleanup events that were previously synced but no longer exist in CMS
        try:
            await self._cleanup_orphaned_events(
                guild, cms_ids_seen, discord_events, now, res
            )
        except Exception as e:
            err_msg = f"Error cleaning up orphaned events for guild {guild.id}: {e}"
            logging.exception(err_msg)
            res.errors.append(err_msg)

        # Clear passed events from database (where end_time <= now)
        try:
            cleared_count = self.db.clear_passed_synced_events(
                before_time=now, guild_id=str(guild.id)
            )
            res.cleared = cleared_count
            if cleared_count > 0:
                res.details.append(
                    f"Cleared {cleared_count} passed event(s) from database"
                )
                logging.info(
                    f"Cleared {cleared_count} passed event(s) from DB for guild {guild.id}"
                )
        except Exception as e:
            err_msg = (
                f"Error clearing passed events from database for guild {guild.id}: {e}"
            )
            logging.exception(err_msg)
            res.errors.append(err_msg)

        logging.info(
            f"Event sync complete for {guild.name}: Created={res.created}, "
            f"Updated={res.updated}, Cancelled={res.cancelled}, Unchanged={res.unchanged}, "
            f"Cleared={res.cleared}, Errors={len(res.errors)}"
        )
        return res

    async def _sync_single_event(
        self,
        guild: discord.Guild,
        ev: NormalizedEvent,
        discord_events: Dict[int, discord.ScheduledEvent],
        now: datetime,
        res: SyncResult,
    ):
        guild_id_str = str(guild.id)
        db_record = self.db.get_synced_event(ev.cms_id, guild_id_str)

        existing_discord_event: Optional[discord.ScheduledEvent] = None
        if db_record:
            discord_id = db_record["discord_event_id"]
            existing_discord_event = discord_events.get(discord_id)

        # Fallback reconciliation: check if an event with matching name and start time exists on Discord
        # Only apply fallback reconciliation for non-recurring events; recurring series must be created
        # with recurrence_rule and any untracked existing events with that name are separate instances to replace.
        if not existing_discord_event and not ev.recurrence_rule:
            for d_ev in discord_events.values():
                if d_ev.status in (EventStatus.completed, EventStatus.cancelled):
                    continue
                time_diff = abs((d_ev.start_time - ev.start_time).total_seconds())
                if d_ev.name == ev.name and time_diff < 300:  # Within 5 minutes
                    existing_discord_event = d_ev
                    logging.info(
                        f"Matched existing Discord scheduled event '{d_ev.name}' ({d_ev.id}) to CMS ID {ev.cms_id}"
                    )
                    break

        # If the tracked Discord event was cancelled or completed, treat it as missing
        # if the event is upcoming, so a fresh event is scheduled on Discord.
        if existing_discord_event and existing_discord_event.status in (
            EventStatus.completed,
            EventStatus.cancelled,
        ):
            if ev.start_time > now:
                logging.info(
                    f"Existing Discord event '{existing_discord_event.name}' ({existing_discord_event.id}) "
                    f"has status {existing_discord_event.status.name}. Treating as missing to re-create."
                )
                existing_discord_event = None
            else:
                return

        # Check image and compute hash
        image_bytes: Optional[bytes] = None
        image_hash: Optional[str] = None
        if ev.image_url:
            image_bytes = cms.fetch_image_bytes(ev.image_url)
            if image_bytes:
                image_hash = hashlib.sha256(image_bytes).hexdigest()

        # If event does not exist on Discord: create it (if start_time is in the future)
        if not existing_discord_event:
            # Discord API rejects creating scheduled events in the past
            if ev.start_time <= now:
                logging.info(
                    f"Skipping creation of past event '{ev.name}' (start {ev.start_time} <= now {now})"
                )
                return

            new_event = await self._create_scheduled_event(
                guild=guild,
                name=ev.name,
                description=ev.description,
                start_time=ev.start_time,
                end_time=ev.end_time,
                location=ev.location,
                image_bytes=image_bytes,
                recurrence_rule=ev.recurrence_rule,
                reason=f"CS Club CMS Event Sync ({ev.cms_id})",
            )
            discord_events[new_event.id] = new_event

            # If this is a recurring series, cancel any separate instances with the same name
            if ev.recurrence_rule:
                for d_ev in list(discord_events.values()):
                    if (
                        d_ev.id != new_event.id
                        and d_ev.name == ev.name
                        and d_ev.status == EventStatus.scheduled
                    ):
                        try:
                            await d_ev.cancel()
                            logging.info(
                                f"Cancelled separate event '{d_ev.name}' ({d_ev.id}) in favor of recurring series"
                            )
                            res.cancelled += 1
                            res.details.append(
                                f"Cancelled separate event: {d_ev.name} ({d_ev.id})"
                            )
                        except Exception as e:
                            logging.error(
                                f"Failed to cancel separate event {d_ev.id}: {e}"
                            )

            target_recurrence_json = (
                json.dumps(ev.recurrence_rule, sort_keys=True)
                if ev.recurrence_rule
                else None
            )
            self.db.upsert_synced_event(
                cms_id=ev.cms_id,
                guild_id=guild_id_str,
                discord_event_id=new_event.id,
                event_type=ev.event_type,
                name=ev.name,
                description=ev.description,
                location=ev.location,
                start_time=ev.start_time.isoformat(),
                end_time=ev.end_time.isoformat(),
                image_url=ev.image_url,
                image_hash=image_hash,
                cms_updated_at=ev.cms_updated_at,
                last_synced_at=now.isoformat(),
                recurrence_rule=target_recurrence_json,
            )
            res.created += 1
            recur_info = " (recurring series)" if ev.recurrence_rule else ""
            res.details.append(
                f"Created: {ev.name}{recur_info} ({ev.start_time.strftime('%Y-%m-%d %H:%M UTC')})"
            )
            logging.info(
                f"Created Discord scheduled event '{ev.name}' ({new_event.id}) for guild {guild.id}"
            )
            return

        # Event already exists: check if description, image, title, location, or times need updating
        if existing_discord_event.status in (
            EventStatus.completed,
            EventStatus.cancelled,
        ):
            # Already finished or cancelled on Discord; do not edit
            return

        # If this is a recurring series, cancel any stray separate instances with the same name
        if ev.recurrence_rule:
            for d_ev in list(discord_events.values()):
                if (
                    d_ev.id != existing_discord_event.id
                    and d_ev.name == ev.name
                    and d_ev.status == EventStatus.scheduled
                ):
                    try:
                        await d_ev.cancel()
                        logging.info(
                            f"Cancelled separate event '{d_ev.name}' ({d_ev.id}) in favor of recurring series"
                        )
                        res.cancelled += 1
                        res.details.append(
                            f"Cancelled separate event: {d_ev.name} ({d_ev.id})"
                        )
                    except Exception as e:
                        logging.error(f"Failed to cancel separate event {d_ev.id}: {e}")

        needs_edit = False
        edit_kwargs: Dict[str, Any] = {}

        if existing_discord_event.name != ev.name:
            edit_kwargs["name"] = ev.name
            needs_edit = True

        current_desc = existing_discord_event.description or ""
        if current_desc != ev.description:
            edit_kwargs["description"] = ev.description
            needs_edit = True

        current_loc = existing_discord_event.location or ""
        if current_loc != ev.location:
            edit_kwargs["location"] = ev.location
            needs_edit = True

        # Check recurrence rule
        target_recurrence_json = (
            json.dumps(ev.recurrence_rule, sort_keys=True)
            if ev.recurrence_rule
            else None
        )
        stored_recurrence_json = db_record.get("recurrence_rule") if db_record else None
        if target_recurrence_json != stored_recurrence_json:
            edit_kwargs["recurrence_rule"] = ev.recurrence_rule
            needs_edit = True

        # Check times: recurring series manage their own occurrences on Discord once created
        if not ev.recurrence_rule:
            if existing_discord_event.start_time != ev.start_time:
                # Only update start_time if it's still in the future or event is scheduled
                if (
                    ev.start_time > now
                    and existing_discord_event.status == EventStatus.scheduled
                ):
                    edit_kwargs["start_time"] = ev.start_time
                    needs_edit = True

            if existing_discord_event.end_time != ev.end_time:
                edit_kwargs["end_time"] = ev.end_time
                needs_edit = True
        elif target_recurrence_json != stored_recurrence_json:
            if ev.start_time > now:
                edit_kwargs["start_time"] = ev.start_time
                edit_kwargs["end_time"] = ev.end_time
                needs_edit = True

        # Check image update
        stored_hash = db_record.get("image_hash") if db_record else None
        if image_bytes and (image_hash != stored_hash or stored_hash is None):
            edit_kwargs["image"] = image_bytes
            needs_edit = True

        if needs_edit:
            edit_kwargs["reason"] = f"CS Club CMS Event Sync Update ({ev.cms_id})"
            await self._edit_scheduled_event(
                guild=guild,
                event=existing_discord_event,
                edit_kwargs=edit_kwargs,
                recurrence_rule=ev.recurrence_rule,
                reason=edit_kwargs["reason"],
            )
            res.updated += 1
            fields_updated = [k for k in edit_kwargs if k != "reason"]
            res.details.append(
                f"Updated: {ev.name} (fields: {', '.join(fields_updated)})"
            )
            logging.info(
                f"Updated Discord scheduled event '{ev.name}' ({existing_discord_event.id}): {fields_updated}"
            )
        else:
            res.unchanged += 1

        # Keep database record up to date
        self.db.upsert_synced_event(
            cms_id=ev.cms_id,
            guild_id=guild_id_str,
            discord_event_id=existing_discord_event.id,
            event_type=ev.event_type,
            name=ev.name,
            description=ev.description,
            location=ev.location,
            start_time=ev.start_time.isoformat(),
            end_time=ev.end_time.isoformat(),
            image_url=ev.image_url,
            image_hash=image_hash
            or (db_record.get("image_hash") if db_record else None),
            cms_updated_at=ev.cms_updated_at,
            last_synced_at=now.isoformat(),
            recurrence_rule=target_recurrence_json,
        )

    async def _create_scheduled_event(
        self,
        guild: discord.Guild,
        name: str,
        description: str,
        start_time: datetime,
        end_time: datetime,
        location: str,
        image_bytes: Optional[bytes] = None,
        recurrence_rule: Optional[Dict[str, Any]] = None,
        reason: Optional[str] = None,
    ) -> discord.ScheduledEvent:
        """Create a scheduled event via Discord HTTP client, supporting recurrence_rule."""
        payload: Dict[str, Any] = {
            "name": name,
            "scheduled_start_time": start_time.isoformat(),
            "scheduled_end_time": end_time.isoformat(),
            "entity_type": EntityType.external.value,
            "privacy_level": PrivacyLevel.guild_only.value,
            "entity_metadata": {"location": location},
        }
        if description:
            payload["description"] = description
        if image_bytes:
            payload["image"] = discord.utils._bytes_to_base64_data(image_bytes)
        if recurrence_rule:
            payload["recurrence_rule"] = recurrence_rule

        try:
            route = Route(
                "POST", "/guilds/{guild_id}/scheduled-events", guild_id=guild.id
            )
            data = await guild._state.http.request(route, json=payload, reason=reason)
            return discord.ScheduledEvent(state=guild._state, data=data)
        except Exception as e:
            if recurrence_rule:
                logging.warning(
                    f"Creating scheduled event with recurrence_rule failed ({e}); retrying without recurrence_rule."
                )
                payload.pop("recurrence_rule", None)
                route = Route(
                    "POST", "/guilds/{guild_id}/scheduled-events", guild_id=guild.id
                )
                data = await guild._state.http.request(
                    route, json=payload, reason=reason
                )
                return discord.ScheduledEvent(state=guild._state, data=data)
            raise

    async def _edit_scheduled_event(
        self,
        guild: discord.Guild,
        event: discord.ScheduledEvent,
        edit_kwargs: Dict[str, Any],
        recurrence_rule: Optional[Dict[str, Any]] = None,
        reason: Optional[str] = None,
    ) -> discord.ScheduledEvent:
        """Edit a scheduled event via HTTP payload."""
        payload: Dict[str, Any] = {}
        if "name" in edit_kwargs:
            payload["name"] = edit_kwargs["name"]
        if "description" in edit_kwargs:
            payload["description"] = edit_kwargs["description"]
        if "location" in edit_kwargs:
            payload["entity_metadata"] = {"location": edit_kwargs["location"]}
        if "start_time" in edit_kwargs:
            payload["scheduled_start_time"] = edit_kwargs["start_time"].isoformat()
        if "end_time" in edit_kwargs:
            payload["scheduled_end_time"] = edit_kwargs["end_time"].isoformat()
        if "image" in edit_kwargs:
            img = edit_kwargs["image"]
            payload["image"] = (
                discord.utils._bytes_to_base64_data(img) if img is not None else img
            )
        if recurrence_rule:
            payload["recurrence_rule"] = recurrence_rule

        route = Route(
            "PATCH",
            "/guilds/{guild_id}/scheduled-events/{guild_scheduled_event_id}",
            guild_id=guild.id,
            guild_scheduled_event_id=event.id,
        )
        data = await guild._state.http.request(route, json=payload, reason=reason)
        s = discord.ScheduledEvent(state=guild._state, data=data)
        s._users = getattr(event, "_users", None)
        return s

    async def _cleanup_orphaned_events(
        self,
        guild: discord.Guild,
        cms_ids_seen: set,
        discord_events: Dict[int, discord.ScheduledEvent],
        now: datetime,
        res: SyncResult,
    ):
        """Cancel scheduled events that were removed or unpublished from CMS."""
        guild_id_str = str(guild.id)
        synced_records = self.db.get_synced_events_by_guild(guild_id_str)

        for record in synced_records:
            cms_id = record["cms_id"]
            if cms_id not in cms_ids_seen:
                # Event is no longer upcoming in CMS
                discord_id = record["discord_event_id"]
                d_ev = discord_events.get(discord_id)
                if d_ev and d_ev.status == EventStatus.scheduled:
                    try:
                        await d_ev.cancel()
                        res.cancelled += 1
                        res.details.append(f"Cancelled removed event: {record['name']}")
                        logging.info(
                            f"Cancelled Discord scheduled event '{record['name']}' ({discord_id}) as it was removed from CMS"
                        )
                    except Exception as e:
                        logging.error(
                            f"Failed to cancel orphaned Discord event {discord_id}: {e}"
                        )
                self.db.delete_synced_event(cms_id, guild_id_str)

    async def sync_all_guilds(self, force_cms: bool = True) -> List[SyncResult]:
        """Sync events across all configured/accessible guilds."""
        async with self._sync_lock:
            results = []
            target_guild_id = os.environ.get("GUILD_ID", "").strip()

            guilds_to_sync: List[discord.Guild] = []
            if target_guild_id:
                try:
                    g = self.bot.get_guild(int(target_guild_id))
                    if g:
                        guilds_to_sync.append(g)
                except ValueError:
                    logging.warning(
                        f"Invalid GUILD_ID environment variable: {target_guild_id}"
                    )

            if not guilds_to_sync:
                guilds_to_sync = [
                    g
                    for g in self.bot.guilds
                    if g.me and g.me.guild_permissions.manage_events
                ]

            enabled_guilds = [
                g for g in guilds_to_sync if self.db.is_event_sync_enabled(str(g.id))
            ]
            if not enabled_guilds:
                logging.debug("No guilds have event synchronization enabled.")
                return []

            for guild in enabled_guilds:
                res = await self.sync_guild_events(
                    guild, force_cms=force_cms, check_enabled=True
                )
                results.append(res)

            return results

    async def _run_sync_loop(self, interval_minutes: int = 60):
        """Background loop executing sync periodically."""
        logging.info(
            f"Started EventSync background loop (interval={interval_minutes}m)"
        )
        # Small startup delay to allow Discord connection to settle
        await asyncio.sleep(10)
        while True:
            try:
                await self.sync_all_guilds(force_cms=True)
            except asyncio.CancelledError:
                break
            except Exception:
                logging.exception("Exception during periodic event sync loop")
            await asyncio.sleep(interval_minutes * 60)

    def start_sync_loop(self, interval_minutes: int = 60):
        """Start the background sync loop task if not already running."""
        if self.sync_task is None or self.sync_task.done():
            self.sync_task = self.bot.loop.create_task(
                self._run_sync_loop(interval_minutes)
            )
            logging.info("EventSync loop task launched.")

    def stop_sync_loop(self):
        """Cancel the background sync loop task."""
        if self.sync_task and not self.sync_task.done():
            self.sync_task.cancel()
            self.sync_task = None
            logging.info("EventSync loop task stopped.")

    def clear_passed_events(
        self, before_time: Optional[datetime] = None, guild_id: Optional[str] = None
    ) -> int:
        """Delete synced event records whose end_time has passed from the database."""
        return self.db.clear_passed_synced_events(
            before_time=before_time, guild_id=guild_id
        )
