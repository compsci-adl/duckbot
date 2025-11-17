import os

from models.databases.admin_settings_db import AdminSettingsDB


def get_setting_with_fallback(key: str, default: str = None) -> str:
    """Get a setting from the database, falling back to env vars if not found"""
    db = AdminSettingsDB()
    value = db.get_setting(key)
    if value is None:
        value = os.getenv(key, default)
    return value
