import logging
import os
from collections import Counter
from functools import wraps
from io import BytesIO
from typing import Awaitable, Callable

import aiohttp
from discord import (
    AllowedMentions,
    Client,
    Embed,
    File,
    Interaction,
    Member,
    app_commands,
)
from discord.errors import NotFound
from discord.utils import MISSING
from dotenv import load_dotenv

from constants.colours import LIGHT_GREY
from models.databases.skullboard_database import SkullboardDB
from utils import time
from utils.plotting import get_histogram_image

load_dotenv()
TENOR_API_KEY = os.getenv("TENOR_API_KEY")


class SkullboardManager:
    """Manages discord activities related to the skullboard"""

    def __init__(self, client: Client):
        """Initialise SkullboardManager"""
        self.client = client
        self.db = SkullboardDB()

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

        message_time = time.get_day_from_timestamp(message.created_at)
        message_id = message.id
        channel_id = message.channel.id
        author_id = message.author.id

        try:
            await self.db.update_skull_post(
                message_id, author_id, channel_id, message_time, current_count
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
    def _simplify(url: str) -> str:
        """Simplify URL by removing protocol"""
        return url.replace("http://", "").replace("https://", "")

    @staticmethod
    def get_gif_id(url: str) -> str:
        """Extract Tenor GIF ID from URL"""
        base_url = "tenor.com/view/"
        url = SkullboardManager._simplify(url.casefold())
        if not url.startswith(base_url):
            return None
        gif_name = url.replace(base_url, "")
        gif_id = gif_name.split("-")[-1]
        return gif_id

    @staticmethod
    async def get_gif_url(view_url):
        """Get URL of GIF from a Tenor view URL"""
        gifid = SkullboardManager.get_gif_id(view_url)
        if not gifid:
            logging.warning(f"Invalid Tenor URL: {view_url}")
            return None
        async with aiohttp.ClientSession() as session:
            url = (
                f"https://tenor.googleapis.com/v2/posts?ids={gifid}&key={TENOR_API_KEY}"
            )
            async with session.get(url) as r:
                if r.status == 200:
                    data = await r.json()
                    gif_url = data["results"][0]["media_formats"]["gif"]["url"]
                    return gif_url
                else:
                    logging.error(f"Tenor API error for ID {gifid}: status {r.status}")
                    return None

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
            else:
                logging.warning(
                    f"Failed to retrieve GIF URL for Tenor link: {message.content}"
                )

        elif message.content.strip().startswith(
            "http"
        ) and message.content.strip().endswith(".gif"):
            # Constructing the embed for direct GIF URLs
            embed = Embed(
                timestamp=message.created_at,
                colour=LIGHT_GREY,
            )

            embed.set_image(url=message.content.strip())

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


class Response:
    """Return type of command functions for handling data"""

    def __init__(
        self, embed: Embed = MISSING, img: BytesIO = MISSING, message: str = MISSING
    ):
        """
        Args:
            embed (Embed): Optional Embed object for rich content in the response.
            img (BytesIO): Optional BytesIO object for image attachments in the response.
            message (str): Optional string for plain text message content.

            The default value for each attribute is MISSING, a special default value defined in discord.utils
            to indicate that the attribute is not present.
        """

        self.embed = embed
        self.img = img
        self.message = message


class SkullGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="skull", description="Skullboard queries")
        self.db = SkullboardDB()
        self.skullboard_channel_id = int(str(os.environ.get("SKULLBOARD_CHANNEL_ID")))

    def interaction_handler(func: Callable[[], Awaitable[Response]]):
        """Wrapper to handle skullboard command interactions and errors"""

        @wraps(func)
        async def wrapper(self, interaction: Interaction, *args, **kwargs):
            try:
                await interaction.response.defer(ephemeral=True)

                # Call the original function
                response = await func(self, interaction, *args, **kwargs)

                embed = response.embed
                img = response.img
                message = response.message

                if img:
                    img = File(img, filename="embed.png")
                    if embed == MISSING:
                        embed = Embed()
                    embed.set_image(url="attachment://embed.png")

                await interaction.followup.send(
                    content=message,
                    embed=embed,
                    file=img,
                    allowed_mentions=AllowedMentions().none(),
                    ephemeral=True,
                )

            except NotFound as e:
                """
                Note that for the commands which use interaction.response.defer() method, sporadic 404 errors will be occassionally raised.
                This is a known bug with the discord API/client https://github.com/discord/discord-api-docs/issues/5558
                The exception clauses suppresses this particular error message from being sent to the client or logged, since it does not affect the final message sent.
                """
                IGNORE_404_API_BUG_ERROR_CODE = 10062
                if e.code != IGNORE_404_API_BUG_ERROR_CODE:  # Supress API bug error
                    raise  # Re-raise other NotFound errors
            except Exception as e:
                # Log the exception and send an error message to the user
                logging.exception(
                    f"User {interaction.user.name} triggered an error in {func.__name__} with args: {args} and kwargs: {kwargs}"
                )
                await interaction.followup.send(
                    f"Error:\nEither no data was available for this command, or a serious error occurred.\nType: {str(e)}",
                    ephemeral=True,
                )

        return wrapper

    @app_commands.command(name="about", description="Learn about the Skullboard")
    @interaction_handler
    async def about(self, interaction: Interaction) -> Response:
        skullboard_info = (
            "## 💀 WELCOME TO THE SKULLZONE 💀\n\n"
            "The **Skullboard** is a fun way to track popular posts and active users in the CS Club! 💀\n"
            f"When a post receives a certain number of 💀 reactions, it gets added to <#{self.skullboard_channel_id}>. 💀\n"
            "Users earn a 💀 for their popular posts, and these 💀 contribute to their overall ranking. 💀\n"
        )
        cmds = [
            "`/skull rank` to view the top skullboard users of all-time",
            "`/skull hof` to view the top posts of all-time",
            "`/skull week` to view the top posts of the week",
            "`/skull stats` to view the distribution of skullboard posts from the past week, month, year, or all-time",
            "`/skull user` to show the total number of skullboard posts a user has, compared to other users",
        ]
        cmds = "\n".join(cmds)

        embed = Embed(colour=LIGHT_GREY)
        embed.add_field(name="Commands:", value=cmds)

        response = Response(message=skullboard_info, embed=embed)
        return response

    @app_commands.command(
        name="rank", description="Get top Skullboard users (all-time)"
    )
    @interaction_handler
    async def rank(self, interaction: Interaction):
        rankings = await self.db.get_user_rankings()
        if not rankings:
            raise Exception("Database Error")

        # Warning: description in embed cannot be longer than 2048 characters
        msg = ["### Top Users of All-Time:\n"]

        for user_id, frequency in rankings[:10]:
            # Format the rankings into a readable message
            line = f"💀 {frequency} : <@{user_id}>"
            msg.append(line)
        msg = "\n".join(msg)

        embed = Embed(
            title="💀   TOP SKULLERS   💀",
            colour=LIGHT_GREY,
            description=msg,
        )
        response = Response(embed=embed)
        return response

    @app_commands.command(name="hof", description="Get top Skullboard posts (all-time)")
    @interaction_handler
    async def hof(self, interaction: Interaction) -> Response:
        hof_entries = await self.db.get_HOF()
        if not hof_entries:
            raise Exception("Database Error")
        # Warning: description in embed cannot be longer than 2048 characters
        msg = ["### Top Posts of All-Time:"]

        # The post date is unused, may use in future if needed.
        for post_id, user_id, channel_id, day, frequency in hof_entries[:10]:
            # Format the HoF entries into a readable message
            line = f"💀 {frequency} : https://discord.com/channels/{self.db.guild_id}/{channel_id}/{post_id} from <@{user_id}>"
            msg.append(line)

        msg = "\n".join(msg)
        embed = Embed(
            title="💀   HALL OF FAME   💀",
            colour=LIGHT_GREY,
            description=msg,
        )
        response = Response(embed=embed)
        return response

    @app_commands.command(name="week", description="Get top posts (this week)")
    @interaction_handler
    async def week(self, interaction: Interaction) -> Response:
        hof_entries = await self.db.get_7_day_post()
        hof_entries = [
            (post_id, user_id, channel_id, day, frequency)
            for post_id, user_id, channel_id, day, frequency in hof_entries
            if frequency > 0
        ]
        if not hof_entries:
            raise Exception("Database Error")

        # Warning: description in embed cannot be longer than 2048 characters
        msg = ["### Top Posts This Week:"]

        # The post date is unused, may use in future if needed.
        for post_id, user_id, channel_id, day, frequency in hof_entries[:10]:
            # Format the entries into a readable message
            line = f"💀 {frequency} : https://discord.com/channels/{self.db.guild_id}/{channel_id}/{post_id} from <@{user_id}>"
            msg.append(line)

        msg = "\n".join(msg)
        embed = Embed(
            title="💀   SKULLS OF THE WEEK   💀",
            colour=LIGHT_GREY,
            description=msg,
        )

        response = Response(embed=embed)
        return response

    @app_commands.command(
        name="stats",
        description="Get Skullboard post distributions for week/month/year/all-time",
    )
    @app_commands.choices(
        timeframe=[
            app_commands.Choice(name="week", value="w"),
            app_commands.Choice(name="month", value="m"),
            app_commands.Choice(name="year", value="y"),
            app_commands.Choice(name="alltime", value="a"),
        ]
    )
    @interaction_handler
    async def stats(
        self, interaction: Interaction, timeframe: app_commands.Choice[str]
    ) -> Response:
        data = []
        title = ""
        option = ""
        if timeframe.value == "w":
            option = "This Week's"
            data = await self.db.get_7_day_histogram()
        elif timeframe.value == "m":
            option = "This Month's"
            data = await self.db.get_30_day_histogram()
        elif timeframe.value == "y":
            option = "This Year's"
            data = await self.db.get_365_day_histogram()
        elif timeframe.value == "a":
            option = "All-Time"
            data = await self.db.get_alltime_histogram()
        else:
            raise Exception("Invalid option")
        title += option
        data = [
            (count, frequency)
            for count, frequency in data
            if count > 0 and frequency > 0
        ]  # only including post/counts for more than 0 reactions and 0 posts

        if not data:
            raise Exception("Database Error")

        title += " Post Distribution"

        # Collecting stats
        count = sum([y for x, y in data])  # number of posts in total
        # number of posts meeting or exceeding threshold
        above_threshold = sum([y for x, y in data if x >= self.db.threshold])
        # percentile of posts meeting or exceeding threshold
        percentile = round(100 * above_threshold / count, 1)

        msg = [
            f"### {title}:",
            f"Count: **{count}**",
            f"Over threshold: {above_threshold}/{count} = **{percentile}%**",
        ]
        msg = "\n".join(msg)

        # generate a histogram of skull reaction counts for posts in the time period
        img = get_histogram_image(
            data=data,
            xlabel="Number of Reactions",
            ylabel="Number of Posts",
            title=f"{option} Distribution of Skull-Reacted Posts (Histogram)",
        )

        explanation = (
            "How to Read Histogram:\n"
            "If the histogram shows bars at 1, 3, and 5 reactions on the x-axis, "
            "with values of 15, 10, and 5 posts on the y-axis respectively, "
            "it indicates that 15 posts received 1 reaction, "
            "10 posts received 3 reactions, "
            "and 5 posts received 5 reactions."
        )

        embed = Embed(
            title="💀   SKULL STATS   💀",
            colour=LIGHT_GREY,
            description=msg,
        )
        embed.set_footer(text=explanation)

        response = Response(img=img, embed=embed)
        return response

    @app_commands.command(name="user", description="Get Skullboard stats for a user")
    @interaction_handler
    async def user(self, interaction: Interaction, member: Member) -> Response:
        user_id = member.id
        user_name = member.name

        data = await self.db.get_user_rankings(999999)  # get all
        data = [(u_id, freq) for u_id, freq in data if freq > 0]

        if not data:
            raise Exception("Database Error")

        user = [(u_id, freq) for u_id, freq in data if u_id == user_id]
        if not user:
            user = [(user_id, 0)]
        _, user_skull_count = user[0]

        # skull stats
        # count the number of users
        count = len(data)
        # number of skullboarded posts for each user
        values = [freq for _, freq in data]
        # how many users have as much or more skull reaction posts than the user
        above_count = len([1 for val in values if val >= user_skull_count])
        # top percentile of skull reactions
        percentile = round(100 * above_count / count, 1)

        title = f"User Stats for {user_name}"

        msg = [
            f"### {title}:",
            f"Skullboard Posts: **{user_skull_count}**",
            f"Percentile: {above_count}/{count} = **Top {percentile}% of Users**",
        ]
        msg = "\n".join(msg)

        # generate a histogram of skull post counts of each user
        frequency = list(Counter(values).items())
        img = get_histogram_image(
            data=frequency,
            xlabel="Number of Posts Sent To The Skullboard",
            ylabel="Number of Users",
            title=f"Distribution of User Skullboard Post Counts (Histogram), {user_name} Highlighted",
            vline=user_skull_count,
        )

        explanation = (
            "How to Read Histogram:\n"
            "If the histogram shows bars at 5, 10, and 15 Skullboard posts on the x axis, "
            "with values of 7, 12, and 8 users on the y axis respectively, "
            "it indicates that 7 users have 5 posts sent to the Skullboard, "
            "12 users have 10 posts sent to the Skullboard, "
            "and 8 users have 15 posts sent to the Skullboard. "
            "A vertical line at x=10 indicates the user belongs to the group of 12 that have 8 Skullboard posts each."
        )

        embed = Embed(
            title="💀   SKULLER STATS   💀",
            colour=LIGHT_GREY,
            description=msg,
        )
        embed.set_footer(text=explanation)

        response = Response(embed=embed, img=img)
        return response


skullboard_group = SkullGroup()
