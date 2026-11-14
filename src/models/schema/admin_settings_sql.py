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
        """,
        """
        CREATE TABLE IF NOT EXISTS synced_events (
            cms_id TEXT NOT NULL,
            guild_id TEXT NOT NULL,
            discord_event_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            location TEXT,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            image_url TEXT,
            image_hash TEXT,
            cms_updated_at TEXT,
            last_synced_at TEXT NOT NULL,
            recurrence_rule TEXT,
            PRIMARY KEY (cms_id, guild_id)
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_synced_events_discord_id ON synced_events(discord_event_id);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_synced_events_guild_id ON synced_events(guild_id);
        """,
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

    get_synced_event = """
    SELECT cms_id, guild_id, discord_event_id, event_type, name, description, location, start_time, end_time, image_url, image_hash, cms_updated_at, last_synced_at, recurrence_rule
    FROM synced_events WHERE cms_id = ? AND guild_id = ?;
    """

    get_synced_events_by_guild = """
    SELECT cms_id, guild_id, discord_event_id, event_type, name, description, location, start_time, end_time, image_url, image_hash, cms_updated_at, last_synced_at, recurrence_rule
    FROM synced_events WHERE guild_id = ?;
    """

    get_synced_event_by_discord_id = """
    SELECT cms_id, guild_id, discord_event_id, event_type, name, description, location, start_time, end_time, image_url, image_hash, cms_updated_at, last_synced_at, recurrence_rule
    FROM synced_events WHERE discord_event_id = ? AND guild_id = ?;
    """

    upsert_synced_event = """
    INSERT INTO synced_events (
        cms_id, guild_id, discord_event_id, event_type, name,
        description, location, start_time, end_time,
        image_url, image_hash, cms_updated_at, last_synced_at,
        recurrence_rule
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(cms_id, guild_id) DO UPDATE SET
        discord_event_id = excluded.discord_event_id,
        event_type = excluded.event_type,
        name = excluded.name,
        description = excluded.description,
        location = excluded.location,
        start_time = excluded.start_time,
        end_time = excluded.end_time,
        image_url = excluded.image_url,
        image_hash = excluded.image_hash,
        cms_updated_at = excluded.cms_updated_at,
        last_synced_at = excluded.last_synced_at,
        recurrence_rule = excluded.recurrence_rule;
    """

    delete_synced_event = """
    DELETE FROM synced_events WHERE cms_id = ? AND guild_id = ?;
    """

    delete_synced_event_by_discord_id = """
    DELETE FROM synced_events WHERE discord_event_id = ? AND guild_id = ?;
    """

    get_all_synced_events = """
    SELECT cms_id, guild_id, discord_event_id, event_type, name, description, location, start_time, end_time, image_url, image_hash, cms_updated_at, last_synced_at, recurrence_rule
    FROM synced_events;
    """

    delete_passed_synced_events = """
    DELETE FROM synced_events WHERE end_time < ?;
    """

    delete_passed_synced_events_by_guild = """
    DELETE FROM synced_events WHERE end_time < ? AND guild_id = ?;
    """
