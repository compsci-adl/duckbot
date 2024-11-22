import os
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

            # Initialise with default values from .env
            default_settings = {
                "GUILD_ID": os.getenv("GUILD_ID", ""),
                "SKULLBOARD_CHANNEL_ID": os.getenv("SKULLBOARD_CHANNEL_ID", ""),
                "REQUIRED_REACTIONS": os.getenv("REQUIRED_REACTIONS", "3")
            }

            # Only set defaults if the settings don't exist
            for key, value in default_settings.items():
                cursor.execute(
                    "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                    (key, value)
                )
            
            conn.commit()

    def get_setting(self, key: str) -> str:
        """Get a setting value from the database"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(AdminSettingsSQL.get_setting, (key,))
            result = cursor.fetchone()
            return result[0] if result else None

    def set_setting(self, key: str, value: str):
        """Set a setting value in the database"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(AdminSettingsSQL.set_setting, (key, value))
            conn.commit() 