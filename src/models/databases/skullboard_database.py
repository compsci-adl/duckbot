from models.database import Database
from models.databases.admin_settings_db import AdminSettingsDB
from models.schema.skullboard_sql import SkullSQL
from utils import time


class SkullboardDB(Database):
    """Singleton class for the skullboard Database"""

    _instance = None

    def __new__(cls, *args, **kwargs):
        """A new instance points to the original instance, if it exists"""
        if not cls._instance:
            cls._instance = super(SkullboardDB, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialise the skullboard with tables"""
        # Initialise ONCE
        if not hasattr(self, "initialised"):
            # Use admin settings DB to fetch per-guild thresholds when needed
            self.admin_db = AdminSettingsDB()
            super().__init__(SkullSQL.initialisation_tables, "skull.sqlite")
            self.initialised = True

    @Database.crash_handler
    async def update_skull_post(self, postID, userID, channelID, day, count, guild_id):
        """Update a post's skull count in the Database"""
        curr_day = time.get_current_day()
        # Do not update posts older than 7 days
        if not curr_day - 7 < day:
            return

        count = min(255, max(count, 0))
        params = (postID, userID, channelID, day, count, guild_id)
        sql = SkullSQL.update_skull_post
        await self.execute(sql, params)
        return

    @Database.crash_handler
    async def get_7_day_histogram(self, guild_id: str):
        """Returns histogram of all skull posts in the past 7 days"""
        sql = SkullSQL.histogram_7
        return await self.execute(sql, (str(guild_id),), "all")

    @Database.crash_handler
    async def get_30_day_histogram(self, guild_id: str):
        """Returns histogram of all skull posts in the past 30 days"""
        curr_day = time.get_current_day()
        month_ago = curr_day - 31
        sql = SkullSQL.histogram_30
        return await self.execute(sql, (month_ago, str(guild_id), str(guild_id)), "all")

    @Database.crash_handler
    async def get_365_day_histogram(self, guild_id: str):
        """Returns histogram of all skull posts in the past 365 days"""
        sql = SkullSQL.histogram_365
        return await self.execute(sql, (str(guild_id), str(guild_id)), "all")

    @Database.crash_handler
    async def get_alltime_histogram(self, guild_id: str):
        """Returns histogram of all skull posts ever made"""
        sql = SkullSQL.histogram_alltime
        return await self.execute(
            sql, (str(guild_id), str(guild_id), str(guild_id)), "all"
        )

    @Database.crash_handler
    async def get_7_day_post(self, top_x=5, guild_id: str = None):
        """Returns top skullboard posts this week"""
        sql = SkullSQL.day_7_post
        return await self.execute(sql, (str(guild_id), top_x), "all")

    @Database.crash_handler
    async def get_user_rankings(self, top_x=10, guild_id: str = None):
        """Returns the number of posts which reaches the skull threshold for each user (All Time)"""
        sql = SkullSQL.user_rankings
        # fetch threshold from admin settings
        _, threshold = self.admin_db.get_server_settings(str(guild_id))
        threshold = threshold or 0
        return await self.execute(
            sql, (threshold, str(guild_id), str(guild_id), top_x), "all"
        )

    @Database.crash_handler
    async def get_HOF(self, top_x=10, guild_id: str = None):
        """Returns the posts with the most skull reactions (All Time)"""
        sql = SkullSQL.hof_rankings
        _, threshold = self.admin_db.get_server_settings(str(guild_id))
        threshold = threshold or 0
        return await self.execute(
            sql, (threshold, str(guild_id), str(guild_id), top_x), "all"
        )

    @Database.crash_handler
    async def add_reactor_post(self, postID, reactorID, guild_id):
        """Record that a user reacted to a post with a skull"""
        sql = SkullSQL.insert_reactor_post
        return await self.execute(sql, (postID, reactorID, guild_id))

    @Database.crash_handler
    async def remove_reactor_post(self, postID, reactorID, guild_id):
        """Remove a reactor record when a user removes their skull reaction"""
        sql = SkullSQL.delete_reactor_post
        return await self.execute(sql, (postID, reactorID, guild_id))

    @Database.crash_handler
    async def get_reactor_rankings(self, top_x=10, guild_id: str = None):
        """Returns the top reactors (All Time)"""
        sql = SkullSQL.reactor_rankings
        return await self.execute(sql, (str(guild_id), str(guild_id), top_x), "all")

    @Database.crash_handler
    async def get_reactor_progress(self, guild_id: str, channel_id: str):
        """Get scanning progress for a given channel in a guild.

        Returns a tuple (last_message_id, completed) or None.
        """
        sql = SkullSQL.reactor_progress_get
        return await self.execute(sql, (str(guild_id), str(channel_id)), "one")

    @Database.crash_handler
    async def add_reactor_count(self, reactorID, guild_id, amount: int = 1):
        """Increment the aggregated reactor count for a user in a guild."""
        sql = SkullSQL.increment_reactor
        return await self.execute(sql, (reactorID, str(guild_id), int(amount)))

    @Database.crash_handler
    async def decrement_reactor_count(self, reactorID, guild_id, amount: int = 1):
        """Decrement the aggregated reactor count for a user in a guild (floor at 0)."""
        sql = SkullSQL.decrement_reactor
        await self.execute(sql, (int(amount), int(amount), reactorID, str(guild_id)))
        # Clean up any zero-or-negative rows
        await self.execute(SkullSQL.delete_zero_reactors, None)

    @Database.crash_handler
    async def aggregate_and_clear_reactor_posts(self):
        """Aggregate all temporary `reactor_posts` into `reactors` and clear the temporary table."""
        # Aggregate per-reactor/guild counts into reactors
        await self.execute(SkullSQL.aggregate_reactor_posts_all, None)
        # Remove all temporary reactor_posts rows
        await self.execute(SkullSQL.clear_reactor_posts, None)

    @Database.crash_handler
    async def mark_all_reactor_progress_completed(self):
        """Mark all reactor_progress rows as completed (used after a full backfill)."""
        return await self.execute(SkullSQL.mark_all_reactor_progress_completed, None)

    @Database.crash_handler
    async def set_reactor_progress(
        self, guild_id: str, channel_id: str, last_message_id: int, completed: int = 0
    ):
        """Set scanning progress for a given channel in a guild."""
        sql = SkullSQL.reactor_progress_set
        return await self.execute(
            sql,
            (
                str(guild_id),
                str(channel_id),
                int(last_message_id or 0),
                int(bool(completed)),
            ),
        )

    @Database.crash_handler
    async def expire(self):
        """
        SQL commands for expiration follow the format:
        [origin_table]_expire_[destination_table]
        """
        curr_day = time.get_current_day()
        week_ago = curr_day - 7
        year_ago = curr_day - 365

        # Determine all guild_ids present in any table
        sql_guilds = """
        SELECT DISTINCT guildId FROM posts
        UNION
        SELECT DISTINCT guildId FROM hof
        UNION
        SELECT DISTINCT guildId FROM days
        UNION
        SELECT DISTINCT guildId FROM alltime
        ;
        """
        rows = await self.execute(sql_guilds, None, "all")
        guilds = [str(r[0]) for r in rows] if rows else []

        # Run expiry per-guild so thresholds are applied per-server
        for gid in guilds:
            _, threshold = self.admin_db.get_server_settings(gid)
            threshold = threshold or 0

            # Expiring "posts" table (7 days or older) for this guild
            await self.execute(SkullSQL.posts_expire_hof, (week_ago, threshold, gid))
            await self.execute(SkullSQL.posts_expire_users, (week_ago, threshold, gid))

            # Aggregate reactor counts for expired posts and cleanup reactor_posts
            await self.execute(SkullSQL.posts_expire_reactors, (week_ago, gid))
            await self.execute(
                SkullSQL.posts_expire_reactor_posts_delete, (week_ago, gid)
            )
            await self.execute(SkullSQL.posts_expire_days, (week_ago, gid))
            await self.execute(SkullSQL.posts_expire_delete, (week_ago, gid))

            # Expire hof for this guild (keep top 100 per guild)
            await self.execute(SkullSQL.hof_expire_hof_1, (gid,))
            await self.execute(SkullSQL.hof_expire_hof_2, (gid,))
            await self.execute(SkullSQL.hof_expire_hof_3)
            await self.execute(SkullSQL.hof_expire_hof_4)

            # Expiring "days" table (365 days or older) for this guild
            await self.execute(SkullSQL.days_expire_alltime, (year_ago, gid))
            await self.execute(SkullSQL.days_expire_delete, (year_ago, gid))
