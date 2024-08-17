import os
import requests
import re

from discord import (
    Client,
    Interaction,
    AllowedMentions,
    Embed,
    Member,
    app_commands,
    File,
)
import logging

from collections import Counter
from models.databases.skullboard_database import SkullboardDB
from utils import time
from constants.colours import LIGHT_GREY
from utils.plotting import get_histogram_image


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
        self.db = SkullboardDB()
        self.skullboard_channel_id = int(str(os.environ.get("SKULLBOARD_CHANNEL_ID")))

    @app_commands.command(name="about", description="Learn about the Skullboard")
    async def about(self, interaction: Interaction):
        skullboard_info = (
            "## 💀 WELCOME TO THE SKULLZONE 💀\n\n"
            "The **Skullboard** is a fun way to track popular posts and active users in the CS Club! 💀\n"
            f"When a post receives a certain number of 💀 reactions, it gets added to <#{self.skullboard_channel_id}>. 💀\n"
            "Users earn a 💀 for their popular posts, and these 💀 contribute to their overall ranking. 💀\n"
        )
        cmds = [
            "`/skull rank` to view current user rankings",
            "`/skull hof` to view the Hall of Fame",
        ]
        cmds = "\n".join(cmds)

        embed = Embed(colour=LIGHT_GREY)
        embed.add_field(name="Commands:", value=cmds)
        await interaction.response.send_message(
            skullboard_info,
            embed=embed,
            allowed_mentions=AllowedMentions().none(),
            ephemeral=True,
        )

    @app_commands.command(name="rank", description="Get top users (all-time)")
    async def rank(self, interaction: Interaction):
        try:
            rankings = await self.db.get_user_rankings()
            if not rankings:
                await interaction.response.send_message(
                    "Database error or empty user rankings - check the logs.",
                    ephemeral=True,
                )
                return

            # Warning: description in embed cannot be longer than 2048 characters
            msg = ["### Top Users of All-Time:\n"]

            for user_id, frequency in rankings[:10]:
                # Format the rankings into a readable message
                line = f"💀 {frequency} : <@{user_id}>"
                msg.append(line)
            msg = "\n".join(msg)

            embed = Embed(
                title="💀💀💀   TOP SKULLERS   💀💀💀",
                colour=LIGHT_GREY,
                description=msg,
            )

            await interaction.response.send_message(
                embed=embed, allowed_mentions=AllowedMentions().none(), ephemeral=True
            )

        except Exception as e:
            logging.exception("Rank")
            await interaction.response.send_message(
                f"An error occurred: {str(e)}", ephemeral=True
            )

    @app_commands.command(name="hof", description="Get top posts (all-time)")
    async def hof(self, interaction: Interaction):
        try:
            hof_entries = await self.db.get_HOF()
            if not hof_entries:
                await interaction.response.send_message(
                    "Database error or empty Hall of Fame - check the logs.",
                    ephemeral=True,
                )
                return

            # Warning: description in embed cannot be longer than 2048 characters
            msg = ["### Top Posts of All-Time:"]

            # The post date is unused, may use in future if needed.
            for post_id, user_id, channel_id, day, frequency in hof_entries[:10]:
                # Format the HoF entries into a readable message
                line = f"💀 {frequency} : https://discord.com/channels/{self.db.guild_id}/{channel_id}/{post_id} from <@{user_id}>"
                msg.append(line)

            msg = "\n".join(msg)
            embed = Embed(
                title="💀💀💀   HALL OF FAME   💀💀💀",
                colour=LIGHT_GREY,
                description=msg,
            )

            await interaction.response.send_message(
                embed=embed, allowed_mentions=AllowedMentions().none(), ephemeral=True
            )

        except Exception as e:
            logging.exception("Hof")
            await interaction.response.send_message(
                f"An error occurred: {str(e)}", ephemeral=True
            )

    @app_commands.command(name="week", description="Get top posts (this week)")
    async def week(self, interaction: Interaction):
        try:
            hof_entries = await self.db.get_7_day_post()
            hof_entries = [
                (post_id, user_id, channel_id, day, frequency)
                for post_id, user_id, channel_id, day, frequency in hof_entries
                if frequency > 0
            ]
            if not hof_entries:
                await interaction.response.send_message(
                    "Database error or no posts saved - check the logs.",
                    ephemeral=True,
                )
                return

            # Warning: description in embed cannot be longer than 2048 characters
            msg = ["### Top Posts This Week:"]

            # The post date is unused, may use in future if needed.
            for post_id, user_id, channel_id, day, frequency in hof_entries[:10]:
                # Format the entries into a readable message
                line = f"💀 {frequency} : https://discord.com/channels/{self.db.guild_id}/{channel_id}/{post_id} from <@{user_id}>"
                msg.append(line)

            msg = "\n".join(msg)
            embed = Embed(
                title="💀💀💀   SKULLS OF THE WEEK   💀💀💀",
                colour=LIGHT_GREY,
                description=msg,
            )

            await interaction.response.send_message(
                embed=embed, allowed_mentions=AllowedMentions().none(), ephemeral=True
            )

        except Exception as e:
            logging.exception("Week")
            await interaction.response.send_message(
                f"An error occurred: {str(e)}", ephemeral=True
            )

    @app_commands.command(name="stats", description="Get skullboard stats")
    @app_commands.choices(
        timeframe=[
            app_commands.Choice(name="week", value="w"),
            app_commands.Choice(name="month", value="m"),
            app_commands.Choice(name="year", value="y"),
            app_commands.Choice(name="alltime", value="a"),
        ]
    )
    async def stats(
        self, interaction: Interaction, timeframe: app_commands.Choice[str]
    ):
        try:
            data = []
            title = ""
            if timeframe.value == "w":
                title += "This Week's "
                data = await self.db.get_7_day_histogram()
            elif timeframe.value == "m":
                title += "This Month's "
                data = await self.db.get_30_day_histogram()
            elif timeframe.value == "y":
                title += "This Year's "
                data = await self.db.get_365_day_histogram()
            elif timeframe.value == "a":
                title += "All-Time "
                data = await self.db.get_alltime_histogram()
            else:
                raise Exception("Invalid option")

            data = [
                (count, frequency)
                for count, frequency in data
                if count > 0 and frequency > 0
            ]  # only including post/counts for more than 0 reactions and 0 posts

            if not data:
                await interaction.response.send_message(
                    "Database error or no posts saved - check the logs.",
                    ephemeral=True,
                )
                return
            title += "Post Distribution"

            # Collecting stats
            count = sum([y for x, y in data])  # number of posts in total
            above_threshold = sum(
                [y for x, y in data if x >= self.db.threshold]
            )  # number of posts meeting or exceeding threshold
            percentile = round(
                100 * above_threshold / count, 1
            )  # percentile of posts meeting or exceeding threshold

            msg = [
                f"### {title}:",
                f"Count: **{count}**",
                f"Over threshold: {above_threshold}/{count} = **{percentile}%**",
            ]
            msg = "\n".join(msg)

            embed = Embed(
                title="💀💀💀   SKULL STATS   💀💀💀",
                colour=LIGHT_GREY,
                description=msg,
            )

            # generate a histogram of skull reaction counts for posts in the time period
            curr_time = time.get_timestamp_str()
            img_name = (title + " " + curr_time + ".png").replace(" ", "_")
            img_buf = get_histogram_image(data)
            img = File(img_buf, filename=img_name, description=title)
            embed.set_image(url="attachment://" + img_name)

            await interaction.response.send_message(
                file=img,
                embed=embed,
                allowed_mentions=AllowedMentions().none(),
                ephemeral=True,
            )

        except Exception as e:
            logging.exception("Stats")
            await interaction.response.send_message(
                f"An error occurred: {str(e)}", ephemeral=True
            )

    @app_commands.command(name="user", description="Get user stats")
    async def user(self, interaction: Interaction, user: Member):
        try:
            user_id = user.id
            user_name = user.name

            data = await self.db.get_user_rankings(999999)  # get all
            data = [(id, freq) for id, freq in data if freq > 0]

            if not data:
                await interaction.response.send_message(
                    "Database error or no posts saved - check the logs.",
                    ephemeral=True,
                )
                return

            user = [(id, freq) for id, freq in data if id == user_id]
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
                f"Skull Posts: **{user_skull_count}**",
                f"Percentile: {above_count}/{count} = **Top {percentile}% of Users**",
            ]
            msg = "\n".join(msg)

            embed = Embed(
                title="💀💀💀   SKULLER STATS   💀💀💀",
                colour=LIGHT_GREY,
                description=msg,
            )

            # generate a histogram of skull post counts of each user
            frequency = list(Counter(values).items())
            img_buf = get_histogram_image(frequency, user_skull_count)
            curr_time = time.get_timestamp_str()
            img_name = (title + " " + curr_time + ".png").replace(" ", "_")
            img = File(img_buf, filename=img_name, description=title)
            embed.set_image(url="attachment://" + img_name)

            await interaction.response.send_message(
                file=img,
                embed=embed,
                allowed_mentions=AllowedMentions().none(),
                ephemeral=True,
            )

        except Exception as e:
            logging.exception("User")
            await interaction.response.send_message(
                f"An error occurred: {str(e)}", ephemeral=True
            )


skullboard_group = SkullGroup()
