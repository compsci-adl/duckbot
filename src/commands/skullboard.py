import os
import requests
import re

from discord import Embed, Client
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta

from constants.colours import LIGHT_GREY

import datetime as dt

from discord import app_commands, Interaction

from commands import database as DB


# Adelaide timezone (UTC+9:30)
tz = timezone(timedelta(hours=9.5))


# Gets current day since 1970
def get_current_day():
    # Converts to Adelaide time
    now = datetime.now(tz)
    epoch = datetime(1970, 1, 1, tzinfo=tz)
    days_since_epoch = (now - epoch).days
    return days_since_epoch


# Gets current day of timestamp since 1970
def get_day_from_timestamp(timestamp: datetime):
    # Converts to Adelaide time
    epoch = datetime(1970, 1, 1, tzinfo=tz)
    days_since_epoch = (timestamp - epoch).days
    return days_since_epoch


class SkullBoardDB: 
    db: DB.DataBase = None
    threshold: int = -1
    guild_id: int = -1
    def __init__(self):
        """Initialise the skullboard with tables"""
        tables = [
            """
    CREATE TABLE IF NOT EXISTS alltime (
    bucket INTEGER PRIMARY KEY,
    frequency INTEGER
    );""",
            """CREATE TABLE IF NOT EXISTS posts (
    postId INTEGER PRIMARY KEY,
    userId INTEGER,
    channelId INTEGER,
    day INTEGER,
    frequency INTEGER
    );""",
            """CREATE TABLE IF NOT EXISTS days (
    day INTEGER,
    bucket INTEGER,
    frequency INTEGER,
    PRIMARY KEY (day, bucket)
    );""",
            """CREATE TABLE IF NOT EXISTS users (
    userId INTEGER PRIMARY KEY,
    frequency INTEGER
    );
    """,
            """CREATE TABLE IF NOT EXISTS hof (
    postId INTEGER PRIMARY KEY,
    userId INTEGER,
    channelId INTEGER,
    day INTEGER,
    frequency INTEGER
    );""",
        ]
        
        if not SkullBoardDB.db:
            load_dotenv()  # Load environment variables from .env file
            SkullBoardDB.threshold = int(str(os.environ.get("REQUIRED_REACTIONS")))
            SkullBoardDB.guild_id = int(str(os.environ.get("GUILD_ID")))
            SkullBoardDB.db = DB.DataBase(tables, "skull.sqlite")

    async def update_skull_post(self,postID, userID, channelID, day, count):
        """Update a post's skull count in DB"""
        curr_day = get_current_day()
        #Do not update posts older than 7 days
        if not curr_day - 7 < day:
            return
        count = min(255, max(count, 0))
        sql = """INSERT INTO posts(postId, userId, channelId, day, frequency)
        VALUES(?,?,?,?,?)
        ON CONFLICT(postId) DO UPDATE SET
        frequency = excluded.frequency;
        """
        await self.db.execute(sql, (postID, userID, channelID, day, count))
            
        return

    async def expire(self):
        """Expire posts: Archive posts older than 7 days, update the hall of fame"""
        try:
            await self.expire_posts()

        except Exception as e:
            print("Error expiring data: ", e)
        else:
            print("Successfullly expired data")

    """Histograms of skull ratings for weeks,months,years, and alltime"""
    async def get_7_day_histogram(self):
        sql = """SELECT frequency AS bucket,
       COUNT(frequency) AS count
FROM   posts
GROUP BY bucket;"""
        return await self.db.execute(sql, None, "all")

    async def get_30_day_histogram(self):
        curr_day = get_current_day()
        month_ago = curr_day - 31
        sql = f"""SELECT bucket, SUM(count) as COUNT
FROM
(
select bucket,SUM(frequency) as count
from days
where day > {month_ago}
group by bucket
    union all
SELECT frequency AS bucket,
       COUNT(frequency) AS count
FROM   posts
GROUP BY frequency
) AS t
where bucket > 0
GROUP BY bucket;"""
        return await self.db.execute(sql, None, "all")

    async def get_365_day_histogram(self):
        sql = """SELECT bucket, SUM(count) as COUNT
            FROM
            (
            select bucket,SUM(frequency) as count
            from days
            group by bucket
                union all
            SELECT frequency AS bucket,
                COUNT(frequency) AS count
            FROM   posts
            GROUP BY bucket
            ) AS t
            where bucket > 0
            GROUP BY bucket;"""
        return await self.db.execute(sql, None, "all")

    async def get_alltime_histogram(self):
        sql = """
SELECT bucket, SUM(count) as COUNT
FROM
(
select bucket,SUM(frequency) as count
from days
group by bucket
    union all
SELECT frequency AS bucket,
    COUNT(frequency) AS count
FROM   posts
GROUP BY bucket
UNION all
select bucket,frequency as count
From alltime
) AS t
where bucket > 0
GROUP BY bucket;
"""

        return await self.db.execute(sql, None, "all")

    # get post of the week rank
    async def get_7_day_post(self, top_x=5):
        sql = f"""SELECT * FROM posts
ORDER BY frequency DESC, day ASC
LIMIT {top_x};
"""
        return await self.db.execute(sql, None, "all")



    async def get_user_rankings(self,top_x=10):
        """Returns the counts of posts each user has which reaches the skull threshold"""
        sql = f"""
        SELECT userId, SUM(frequency) as total_frequency
        FROM (
            SELECT userId, COUNT(*) AS frequency
            FROM posts
            WHERE frequency >= {self.threshold}
            GROUP BY userId
            
            UNION ALL
            
            SELECT userId, frequency
            FROM users
        )
        GROUP BY userId
        ORDER BY total_frequency DESC
        LIMIT {top_x};
        """

        return await self.db.execute(sql, None, "all")

    # get hall of fame (all time post ranking)
    async def get_HOF(self,top_x=10):
        """Returns the posts qwith the most skull reactions"""
        sql = f"""
SELECT postId, userId, channelId, day, frequency 
FROM (
    SELECT postId, userId, channelId, day, frequency 
    FROM posts
    WHERE frequency >= {self.threshold}
    
    UNION ALL
    
    SELECT postId, userId, channelId, day, frequency
    FROM hof
)
ORDER BY 
    frequency DESC,
    day DESC
LIMIT {top_x};
"""

        return await self.db.execute(sql, None, "all")

    async def expire_posts(self):
        """Call once a day to commit long term posts older than 7 days"""
        curr_day = get_current_day()
        week_ago = curr_day - 7

        # Expire into HOF
        hof_sql = """
        INSERT INTO hof (postId, userId, channelId, day, frequency)
        SELECT postId, userId, channelId, day, frequency
        FROM posts
        WHERE day <= ? AND frequency >= ?;
        """
        await self.db.execute(hof_sql, (week_ago, self.threshold))

        # Clean HOF
        hof_clean_sqls = [
            """
            CREATE TABLE top_posts AS
            SELECT postId, userId, channelId, day, frequency
            FROM hof
            ORDER BY frequency DESC, day DESC
            LIMIT 100;
            """,
            "DELETE FROM hof;",
            """
            INSERT INTO hof (postId, userId, channelId, day, frequency)
            SELECT postId, userId, channelId, day, frequency
            FROM top_posts;
            """,
            "DROP TABLE top_posts;",
        ]
        for sql in hof_clean_sqls:
            await self.db.execute(sql)

        # Expire into users
        users_sql = """
        INSERT INTO users (userId, frequency)
        SELECT userId, COUNT(*) AS frequency
        FROM posts
        WHERE day <= ? AND frequency >= ?
        GROUP BY userId
        ON CONFLICT(userId) DO UPDATE SET frequency = users.frequency + excluded.frequency;
        """
        await self.db.execute(users_sql, (week_ago, self.threshold))

        # Expire into days
        days_sql = """
        INSERT INTO days (day, bucket, frequency)
        SELECT day, frequency AS bucket, COUNT(*) AS frequency
        FROM posts
        WHERE day <= ? AND frequency > 0
        GROUP BY day, frequency;
        """
        await self.db.execute(days_sql, (week_ago,))

        # Remove expired posts
        delete_sql = "DELETE FROM posts WHERE day <= ?;"
        await self.db.execute(delete_sql, (week_ago,))


        #move days into alltime
        year_ago = curr_day - 365
        alltime_sql = f"""
INSERT INTO alltime (bucket, frequency)
SELECT bucket, SUM(frequency) AS total_frequency
FROM days
WHERE day < {year_ago}
GROUP BY bucket
ON CONFLICT(bucket) DO UPDATE SET frequency = alltime.frequency + EXCLUDED.frequency;
"""
        await self.db.execute(alltime_sql)

        delete_sql = f"""
DELETE FROM days
WHERE day < {year_ago};
"""
        await self.db.execute(delete_sql)




class SkullboardManager:
    db: SkullBoardDB = None # shared instance
    def __init__(self, client: Client):
        """Initialise SkullboardManager"""
        self.client = client
        if not SkullboardManager.db:
            SkullboardManager.db = SkullBoardDB()

    async def get_reaction_count(self, message, emoji):
        """Get count of a specific emoji reaction on a message"""
        return next(
            (
                reaction.count
                for reaction in message.reactions
                if reaction.emoji == emoji
            ),
            0,
        )

    async def handle_skullboard(self, message, skullboard_channel_id):
        """Handle reactions and update/delete skullboard messages"""
        skullboard_channel = self.client.get_channel(skullboard_channel_id)
        if not skullboard_channel:
            return

        emoji = "💀"
        current_count = await self.get_reaction_count(message, emoji)

        await self.update_or_send_skullboard_message(
            skullboard_channel, message, current_count, emoji
        )

    async def update_or_send_skullboard_message(
        self, channel, message, current_count, emoji
    ):
        """Update or send skullboard message"""
        skullboard_message_id = None
        message_jump_url = message.jump_url

        message_time = get_day_from_timestamp(message.created_at)
        message_id = message.id
        channel_id = message.channel.id
        author_id = message.author.id

        try:
            await self.db.update_skull_post(
                message_id, author_id,channel_id, message_time, current_count
            )
        except Exception as e:
            print("Could not update skull post for ", message_id)
            print("Error:", e)

        async for skullboard_message in channel.history(limit=100):
            if message_jump_url in skullboard_message.content:
                skullboard_message_id = skullboard_message.id
                break

        if current_count >= self.db.threshold:
            if skullboard_message_id:
                await self.edit_or_send_skullboard_message(
                    channel,
                    message,
                    current_count,
                    emoji,
                    send=False,
                    skullboard_message_id=skullboard_message_id,
                )
            else:
                await self.edit_or_send_skullboard_message(
                    channel, message, current_count, emoji, send=True
                )
        elif skullboard_message_id:
            skullboard_message = await channel.fetch_message(skullboard_message_id)
            await skullboard_message.delete()

    @staticmethod
    async def get_gif_url(view_url):
        """Get URL of GIF from a Tenor view URL"""
        # Get the page content
        page_content = requests.get(view_url).text

        # Regex to find the URL on the media.tenor.com domain that ends with .gif
        regex = r"(?i)\b((https?://media1[.]tenor[.]com/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))[.]gif)"

        # Find and return the first match
        match = re.findall(regex, page_content)

        return match[0][0] if match else None

    async def edit_or_send_skullboard_message(
        self,
        channel,
        message,
        current_count,
        emoji,
        send=False,
        skullboard_message_id=None,
    ):
        """Edit or send a skullboard message"""
        # Fetch user's nickname and avatar url
        guild = self.client.get_guild(message.guild.id)
        member = guild.get_member(message.author.id)
        user_nickname = member.nick if member.nick else message.author.name
        user_avatar_url = message.author.avatar.url if message.author.avatar else ""

        # Constructing the message content
        message_jump_url = message.jump_url
        message_content = f"{emoji} {current_count} | {message_jump_url}"

        # Constructing the embed
        embed = Embed(
            description=f"{message.content}\n\n",
            timestamp=message.created_at,
            colour=LIGHT_GREY,
        )

        if message.content.startswith("https://tenor.com/view/"):
            # Constructing the embed
            embed = Embed(
                timestamp=message.created_at,
                colour=LIGHT_GREY,
            )

            # Find the URL of the gif
            gif_url = await self.get_gif_url(message.content)

            if gif_url:
                embed.set_image(url=gif_url)

        # Set user nickname and thumbnail
        embed.set_author(name=user_nickname, icon_url=user_avatar_url)

        # Add images, stickers, and attachments
        if message.stickers:
            # Replace the pattern with just the format type
            format_type = str(message.stickers[0].format).split(".", maxsplit=1)[-1]

            sticker_id = message.stickers[0].id
            sticker_url = (
                f"https://media.discordapp.net/stickers/{sticker_id}.{format_type}"
            )
            embed.set_image(url=sticker_url)

        if message.attachments:
            attachment = message.attachments[0]
            if attachment.content_type.startswith("video"):
                embed.add_field(name="", value=attachment.url)
            else:
                embed.set_image(url=attachment.url)

        # Determine if sending or editing the message
        if send:
            await channel.send(message_content, embed=embed)
        else:
            skullboard_message = await channel.fetch_message(skullboard_message_id)
            await skullboard_message.edit(content=message_content, embed=embed)


class SkullGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="skull", description="Skullboard queries")
        self.add_command(SkullStatGroup())

    @app_commands.command(name="about", description="Learn about the Skullboard")
    async def about(self, interaction: Interaction):
        skullboard_info = (
            "The Skullboard is a fun way to track popular posts and active users in our community.\n\n"
            "When a post receives a certain number of 💀 reactions, it gets added to the Skullboard.\n"
            "Users earn 'skulls' for their popular posts, and these skulls contribute to their overall ranking.\n\n"
            "Use `/skull stats rank` to see the current user rankings, and `/skull stats hof` to view the Hall of Fame!"
        )
        await interaction.response.send_message(skullboard_info)

class SkullStatGroup(app_commands.Group):
    db : SkullBoardDB = None
    

    def __init__(self):
        super().__init__(name="stats", description="Get stats about the skullboard")
        if not SkullStatGroup.db:
            SkullStatGroup.db = SkullBoardDB()

    @app_commands.command(name="rank", description="Provides ranking of users")
    async def rank(self, interaction: Interaction):
        try:
            rankings = await SkullStatGroup.db.get_user_rankings()
            if not rankings:
                await interaction.response.send_message("No rankings available at the moment.")
                return

            # Format the rankings into a more readable message
            msg = "User Ranking by number of posts sent to the skullboard:\n"
            for i, (user_id, frequency) in enumerate(rankings[:10], start=1):
                #silent mention
                msg += f"{i}. 💀 {frequency} : <@!{user_id}>\n"

            await interaction.response.send_message(msg)
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {str(e)}")

    @app_commands.command(name="hof", description="Hall of fame rankings for the top posts")
    async def hof(self, interaction: Interaction):
        try:
            hof_entries = await self.db.get_HOF()
            if not hof_entries:
                await interaction.response.send_message("The Hall of Fame is empty.")
                return

            # Format the HoF entries into a more readable message
            msg = "Hall of Fame:\n"
            for i, (post_id, user_id, channel_id,day, frequency) in enumerate(hof_entries, start=1):
                #silent mention
                msg += f"{i}. 💀 {frequency} : https://discord.com/channels/{self.db.guild_id}/{channel_id}/{post_id} from <@!{user_id}>\n"

            await interaction.response.send_message(msg)
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {str(e)}")

skullboard_group = SkullGroup()
