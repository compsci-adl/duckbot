class AdminSettingsSQL:
    """Store SQL statements for the admin settings functionalities."""

    initialisation_tables = [
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT NOT NULL,
            guild_id TEXT,
            value TEXT NOT NULL,
            PRIMARY KEY (key, guild_id)
        );
        """
    ]

    get_setting = """
    SELECT value FROM settings WHERE key = ? AND guild_id IS NULL;
    """

    set_setting = """
    INSERT INTO settings (key, guild_id, value)
    VALUES (?, NULL, ?)
    ON CONFLICT(key, guild_id) DO UPDATE SET value = excluded.value;
    """

    get_guild_setting = """
    SELECT value FROM settings WHERE key = ? AND guild_id = ?;
    """

    set_guild_setting = """
    INSERT INTO settings (key, guild_id, value)
    VALUES (?, ?, ?)
    ON CONFLICT(key, guild_id) DO UPDATE SET value = excluded.value;
    """
