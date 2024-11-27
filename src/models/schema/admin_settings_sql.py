class AdminSettingsSQL:
    """Store SQL statements for the admin settings functionalities."""

    initialisation_tables = [
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    ]

    get_setting = """
    SELECT value FROM settings WHERE key = ?;
    """

    set_setting = """
    INSERT INTO settings (key, value) 
    VALUES (?, ?)
    ON CONFLICT(key) DO UPDATE SET value = excluded.value;
    """
