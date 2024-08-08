import os


from dotenv import load_dotenv

from models import database as DB
from models.schema.skullboard_sql import SkullSQL
from utils import time


class SkullboardDB:
    """Singleton class for the skullboard database"""

    db: DB.DataBase = None  # Database to connect
    threshold: int = -1  # Skulls needed for posting on skullboard
    guild_id: int = -1  # Channel to post skull messages

    def __init__(self):
        """Initialise the skullboard with tables"""
        if not SkullboardDB.db:
            load_dotenv()  # Load environment variables from .env file
            self.threshold = int(str(os.environ.get("REQUIRED_REACTIONS")))
            self.guild_id = int(str(os.environ.get("GUILD_ID")))
            self.db = DB.DataBase(SkullSQL.initialisation_tables, "skull.sqlite")

    async def update_skull_post(self, postID, userID, channelID, day, count):
        """Update a post's skull count in the database"""
        curr_day = time.get_current_day()
        # Do not update posts older than 7 days
        if not curr_day - 7 < day:
            return

        count = min(255, max(count, 0))
        sql = SkullSQL.update_skull_post
        await self.db.execute(sql, (postID, userID, channelID, day, count))

        return

    """Returns histograms of skull ratings for weeks, months, years, and alltime"""

    async def get_7_day_histogram(self):
        """Returns histogram of all skull posts in the past 7 days"""
        sql = SkullSQL.histogram_7
        return await self.db.execute(sql, None, "all")

    async def get_30_day_histogram(self):
        """Returns histogram of all skull posts in the past 30 days"""
        curr_day = time.get_current_day()
        month_ago = curr_day - 31
        sql = SkullSQL.histogram_30
        return await self.db.execute(sql, (month_ago,), "all")

    async def get_365_day_histogram(self):
        """Returns histogram of all skull posts in the past 365 days"""
        sql = SkullSQL.histogram_365
        return await self.db.execute(sql, None, "all")

    async def get_alltime_histogram(self):
        """Returns histogram of all skull posts ever made"""
        sql = SkullSQL.histogram_alltime
        return await self.db.execute(sql, None, "all")

    async def get_7_day_post(self, top_x=5):
        """Returns top skullboard posts this week"""
        sql = SkullSQL.day_7_post
        return await self.db.execute(sql, (top_x), "all")

    async def get_user_rankings(self, top_x=10):
        """Returns the number of posts which reaches the skull threshold for each user (All Time)"""
        sql = SkullSQL.user_rankings
        return await self.db.execute(sql, (self.threshold, top_x), "all")

    # get hall of fame (all time post ranking)
    async def get_HOF(self, top_x=10):
        """Returns the posts with the most skull reactions (All Time)"""
        sql = SkullSQL.hof_rankings
        return await self.db.execute(sql, (self.threshold, top_x), "all")

    async def expire(self):
        """To be called once a day.
        Expire posts:
        - Archive posts older than 7 days
        - Merge histograms from >365 days ago into alltime
        - Update the hall of fame"""
        try:
            await self.expire_posts()
        except Exception as e:
            print("Error expiring data: ", e)
        else:
            print("Successfullly expired data")

    async def expire_posts(self):
        """
        SQL commands for expiration follow the format:
        [origin_table]_expire_[destination_table]
        """
        curr_day = time.get_current_day()
        week_ago = curr_day - 7
        year_ago = curr_day - 365

        # Expiring "posts" table (7 days or older)
        await self.db.execute(SkullSQL.posts_expire_hof, (week_ago, self.threshold))

        await self.db.execute(SkullSQL.posts_expire_users, (week_ago, self.threshold))

        await self.db.execute(SkullSQL.posts_expire_days, (week_ago,))

        await self.db.execute(SkullSQL.posts_expire_delete, (week_ago,))

        # Expiring "hof" (Hall of Fame) table (Only store top 100 posts)
        # i have no idea why this completely bugs out when i put these commands in lists but they do.
        await self.db.execute(SkullSQL.hof_expire_hof_1)
        await self.db.execute(SkullSQL.hof_expire_hof_2)
        await self.db.execute(SkullSQL.hof_expire_hof_3)
        await self.db.execute(SkullSQL.hof_expire_hof_4)

        # Expiring "days" table (365 days or older)
        await self.db.execute(SkullSQL.days_expire_alltime, (year_ago,))

        await self.db.execute(SkullSQL.days_expire_delete, (year_ago,))
