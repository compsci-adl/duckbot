import os

from dotenv import load_dotenv

from models.database import Database
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
            load_dotenv()  # Load environment variables from .env file
            self.threshold = int(os.environ.get("REQUIRED_REACTIONS", 0))
            self.guild_id = int(os.environ.get("GUILD_ID", -1))
            super().__init__(SkullSQL.initialisation_tables, "skull.sqlite")
            self.initialised = True

    @Database.crash_handler
    async def update_skull_post(self, postID, userID, channelID, day, count):
        """Update a post's skull count in the Database"""
        curr_day = time.get_current_day()
        # Do not update posts older than 7 days
        if not curr_day - 7 < day:
            return

        count = min(255, max(count, 0))
        params = (postID, userID, channelID, day, count)
        sql = SkullSQL.update_skull_post
        await self.execute(sql, params)
        return

    @Database.crash_handler
    async def get_7_day_histogram(self):
        """Returns histogram of all skull posts in the past 7 days"""
        sql = SkullSQL.histogram_7
        return await self.execute(sql, None, "all")

    @Database.crash_handler
    async def get_30_day_histogram(self):
        """Returns histogram of all skull posts in the past 30 days"""
        curr_day = time.get_current_day()
        month_ago = curr_day - 31
        sql = SkullSQL.histogram_30
        return await self.execute(sql, (month_ago,), "all")

    @Database.crash_handler
    async def get_365_day_histogram(self):
        """Returns histogram of all skull posts in the past 365 days"""
        sql = SkullSQL.histogram_365
        return await self.execute(sql, None, "all")

    @Database.crash_handler
    async def get_alltime_histogram(self):
        """Returns histogram of all skull posts ever made"""
        sql = SkullSQL.histogram_alltime
        return await self.execute(sql, None, "all")

    @Database.crash_handler
    async def get_7_day_post(self, top_x=5):
        """Returns top skullboard posts this week"""
        sql = SkullSQL.day_7_post
        return await self.execute(sql, (top_x), "all")

    @Database.crash_handler
    async def get_user_rankings(self, top_x=10):
        """Returns the number of posts which reaches the skull threshold for each user (All Time)"""
        sql = SkullSQL.user_rankings
        return await self.execute(sql, (self.threshold, top_x), "all")

    @Database.crash_handler
    async def get_HOF(self, top_x=10):
        """Returns the posts with the most skull reactions (All Time)"""
        sql = SkullSQL.hof_rankings
        return await self.execute(sql, (self.threshold, top_x), "all")

    @Database.crash_handler
    async def expire(self):
        """
        SQL commands for expiration follow the format:
        [origin_table]_expire_[destination_table]
        """
        curr_day = time.get_current_day()
        week_ago = curr_day - 7
        year_ago = curr_day - 365

        # Expiring "posts" table (7 days or older)
        await self.execute(SkullSQL.posts_expire_hof, (week_ago, self.threshold))
        await self.execute(SkullSQL.posts_expire_users, (week_ago, self.threshold))
        await self.execute(SkullSQL.posts_expire_days, (week_ago,))
        await self.execute(SkullSQL.posts_expire_delete, (week_ago,))

        # Expiring "hof" (Hall of Fame) table (Only store top 100 posts)
        # i have no idea why this completely bugs out when i put these commands in lists but they do.
        await self.execute(SkullSQL.hof_expire_hof_1)
        await self.execute(SkullSQL.hof_expire_hof_2)
        await self.execute(SkullSQL.hof_expire_hof_3)
        await self.execute(SkullSQL.hof_expire_hof_4)

        # Expiring "days" table (365 days or older)
        await self.execute(SkullSQL.days_expire_alltime, (year_ago,))
        await self.execute(SkullSQL.days_expire_delete, (year_ago,))
