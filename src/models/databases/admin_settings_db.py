import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from models.schema.admin_settings_sql import AdminSettingsSQL


class AdminSettingsDB:
    def __init__(self, db_path: str = "db/admin_settings.db"):
        # Ensure the data directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self.db_path = db_path
        self.init_db()

    def get_db_connection(self):
        return sqlite3.connect(self.db_path)

    def init_db(self):
        """Initialise the database with tables and default values from .env"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()

            # Create tables
            for statement in AdminSettingsSQL.initialisation_tables:
                cursor.execute(statement)

            # Migration: ensure recurrence_rule column exists in synced_events
            try:
                cursor.execute(
                    "ALTER TABLE synced_events ADD COLUMN recurrence_rule TEXT;"
                )
            except Exception:
                pass

            conn.commit()

    def get_setting(self, key: str, guild_id: str = None) -> str:
        """Get a setting value from the database"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            if guild_id is None:
                cursor.execute(AdminSettingsSQL.get_setting, (key,))
            else:
                cursor.execute(AdminSettingsSQL.get_guild_setting, (key, str(guild_id)))
            result = cursor.fetchone()
            return result[0] if result else None

    def set_setting(self, key: str, value: str, guild_id: str = None):
        """Set a setting value in the database"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            if guild_id is None:
                cursor.execute(AdminSettingsSQL.set_setting, (key, value))
            else:
                cursor.execute(
                    AdminSettingsSQL.set_guild_setting, (key, str(guild_id), value)
                )
            conn.commit()

    def get_server_settings(self, guild_id: str):
        """Return skullboard_channel_id and required_reactions for a guild as a tuple (channel_id, required_reactions).
        Returns (None, None) if not set.
        """
        channel_id = self.get_setting("SKULLBOARD_CHANNEL_ID", guild_id=str(guild_id))
        required = self.get_setting("REQUIRED_REACTIONS", guild_id=str(guild_id))
        if required is not None:
            try:
                required = int(required)
            except Exception:
                required = None
        return (channel_id, required)

    def set_server_settings(
        self, guild_id: str, skullboard_channel_id: str, required_reactions: int
    ):
        """Insert or update per-guild skullboard settings."""
        # Use the general set_setting helper to write guild-scoped keys
        self.set_setting(
            "SKULLBOARD_CHANNEL_ID",
            str(skullboard_channel_id) if skullboard_channel_id is not None else "",
            guild_id=str(guild_id),
        )
        # Store required reactions as a string
        if required_reactions is not None:
            self.set_setting(
                "REQUIRED_REACTIONS", str(required_reactions), guild_id=str(guild_id)
            )

    def is_event_sync_enabled(self, guild_id: str) -> bool:
        """Check if event sync is enabled for a guild. Disabled by default."""
        val = self.get_setting("EVENT_SYNC_ENABLED", guild_id=str(guild_id))
        return val is not None and val.lower() in ("true", "1", "yes", "on")

    def set_event_sync_enabled(self, guild_id: str, enabled: bool):
        """Enable or disable event sync for a guild."""
        self.set_setting(
            "EVENT_SYNC_ENABLED", "true" if enabled else "false", guild_id=str(guild_id)
        )

    @staticmethod
    def _row_to_synced_event(row):
        if not row:
            return None
        return {
            "cms_id": row[0],
            "guild_id": row[1],
            "discord_event_id": row[2],
            "event_type": row[3],
            "name": row[4],
            "description": row[5],
            "location": row[6],
            "start_time": row[7],
            "end_time": row[8],
            "image_url": row[9],
            "image_hash": row[10],
            "cms_updated_at": row[11],
            "last_synced_at": row[12],
            "recurrence_rule": row[13] if len(row) > 13 else None,
        }

    def get_synced_event(self, cms_id: str, guild_id: str):
        """Fetch a synced event by its CMS ID and Guild ID."""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                AdminSettingsSQL.get_synced_event, (str(cms_id), str(guild_id))
            )
            row = cursor.fetchone()
            return self._row_to_synced_event(row)

    def get_synced_events_by_guild(self, guild_id: str):
        """Fetch all synced events for a specific guild."""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                AdminSettingsSQL.get_synced_events_by_guild, (str(guild_id),)
            )
            rows = cursor.fetchall()
            return [self._row_to_synced_event(r) for r in rows]

    def get_synced_event_by_discord_id(self, discord_event_id: int, guild_id: str):
        """Fetch a synced event by Discord scheduled event ID."""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                AdminSettingsSQL.get_synced_event_by_discord_id,
                (int(discord_event_id), str(guild_id)),
            )
            row = cursor.fetchone()
            return self._row_to_synced_event(row)

    def upsert_synced_event(
        self,
        cms_id: str,
        guild_id: str,
        discord_event_id: int,
        event_type: str,
        name: str,
        description: str,
        location: str,
        start_time: str,
        end_time: str,
        image_url: str | None,
        image_hash: str | None,
        cms_updated_at: str | None,
        last_synced_at: str,
        recurrence_rule: str | None = None,
    ):
        """Insert or update a synced event record."""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                AdminSettingsSQL.upsert_synced_event,
                (
                    str(cms_id),
                    str(guild_id),
                    int(discord_event_id),
                    str(event_type),
                    str(name),
                    description,
                    str(location),
                    str(start_time),
                    str(end_time),
                    image_url,
                    image_hash,
                    cms_updated_at,
                    str(last_synced_at),
                    recurrence_rule,
                ),
            )
            conn.commit()

    def delete_synced_event(self, cms_id: str, guild_id: str):
        """Delete a synced event record by CMS ID and Guild ID."""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                AdminSettingsSQL.delete_synced_event, (str(cms_id), str(guild_id))
            )
            conn.commit()

    def delete_synced_event_by_discord_id(self, discord_event_id: int, guild_id: str):
        """Delete a synced event record by Discord scheduled event ID."""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                AdminSettingsSQL.delete_synced_event_by_discord_id,
                (int(discord_event_id), str(guild_id)),
            )
            conn.commit()

    def clear_passed_synced_events(
        self, before_time: datetime | None = None, guild_id: str | None = None
    ) -> int:
        """Delete synced event records whose end_time has passed (before `before_time`, defaults to now UTC).

        Returns the number of deleted records.
        """
        if before_time is None:
            before_time = datetime.now(timezone.utc)
        elif before_time.tzinfo is None:
            before_time = before_time.replace(tzinfo=timezone.utc)

        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            if guild_id is not None:
                cursor.execute(
                    AdminSettingsSQL.get_synced_events_by_guild, (str(guild_id),)
                )
            else:
                cursor.execute(AdminSettingsSQL.get_all_synced_events)
            rows = cursor.fetchall()

            deleted_count = 0
            for r in rows:
                event_dict = self._row_to_synced_event(r)
                if not event_dict:
                    continue
                end_str = event_dict.get("end_time")
                if not end_str:
                    continue
                try:
                    end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                    if end_dt.tzinfo is None:
                        end_dt = end_dt.replace(tzinfo=timezone.utc)
                    if end_dt <= before_time:
                        cursor.execute(
                            AdminSettingsSQL.delete_synced_event,
                            (event_dict["cms_id"], event_dict["guild_id"]),
                        )
                        deleted_count += 1
                except Exception:
                    logging.exception(
                        f"Failed to parse end_time '{end_str}' for synced event cleanup"
                    )

            conn.commit()
            return deleted_count
