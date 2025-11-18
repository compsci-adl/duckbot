import sqlite3
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
