import asyncio
import logging
import os
from collections import Counter
from functools import wraps
from inspect import signature
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
    Object,
    app_commands,
)
from discord.errors import NotFound
from discord.utils import MISSING
from dotenv import load_dotenv

from constants.colours import LIGHT_GREY
from models.databases.admin_settings_db import AdminSettingsDB
from models.databases.skullboard_database import SkullboardDB
from utils import time
from utils.plotting import get_histogram_image

load_dotenv()
KLIPY_API_KEY = os.getenv("KLIPY_API_KEY")


def _get_guild_id(interaction: Interaction):
    """Return the guild id from an interaction (or None)."""
    return interaction.guild.id if interaction.guild else None


def _format_post_link(guild_id, channel_id, post_id, user_id, frequency):
    """Format a skullboard post link line for lists (keeps previous behaviour when guild_id is None)."""
    return f"💀 {frequency} : https://discord.com/channels/{guild_id}/{channel_id}/{post_id} from <@{user_id}>"


class SkullboardManager:
    """Manages discord activities related to the skullboard"""

    def __init__(self, client: Client):
        """Initialise SkullboardManager"""
        self.client = client
        self.db = SkullboardDB()
        self.admin_db = AdminSettingsDB()
        self.backfill_completed = False

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

    async def handle_skullboard(
        self, message, skullboard_channel_id, guild_id, threshold
    ):
        """Handle reactions and update/delete skullboard messages for a guild"""
        skullboard_channel = None
        if skullboard_channel_id:
            skullboard_channel = self.client.get_channel(int(skullboard_channel_id))
            if not skullboard_channel:
                try:
                    skullboard_channel = await self.client.fetch_channel(
                        int(skullboard_channel_id)
                    )
                except Exception as e:
                    logging.error(
                        f"Failed to fetch skullboard channel {skullboard_channel_id}: {e}"
                    )
                    return
        if not skullboard_channel:
            return

        # Guild Mismatch Guard: Prevent posting to wrong server
        if message.guild and skullboard_channel.guild.id != message.guild.id:
            logging.warning(
                f"Guild mismatch: skullboard channel {skullboard_channel.id} "
                f"belongs to guild {skullboard_channel.guild.id}, but message "
                f"belongs to guild {message.guild.id}. Aborting."
            )
            return

        emoji = "💀"
        current_count = await self.get_reaction_count(message, emoji)

        await self.update_or_send_skullboard_message(
            skullboard_channel, message, current_count, emoji, guild_id, threshold
        )

    async def update_or_send_skullboard_message(
        self, channel, message, current_count, emoji, guild_id, threshold
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
                message_id, author_id, channel_id, message_time, current_count, guild_id
            )
        except Exception as e:
            print("Could not update skull post for ", message_id)
            print("Error:", e)

        async for skullboard_message in channel.history(limit=100):
            if message_jump_url in skullboard_message.content:
                skullboard_message_id = skullboard_message.id
                break

        if current_count >= (threshold or 0):
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
        """Extract Klipy GIF ID from URL"""
        url = SkullboardManager._simplify(url.casefold())
        for prefix in ("klipy.com/gif/", "klipy.com/gifs/"):
            if url.startswith(prefix):
                print(url.replace(prefix, "").split("/")[0])
                return url.replace(prefix, "").split("/")[0]
        return None

    @staticmethod
    async def get_gif_url(view_url):
        """Get URL of GIF from a Klipy view URL"""
        gifid = SkullboardManager.get_gif_id(view_url)
        if not gifid:
            logging.warning(f"Invalid Klipy URL: {view_url}")
            return None
        async with aiohttp.ClientSession() as session:
            url = f"https://api.klipy.com/api/v1/{KLIPY_API_KEY}/gifs/items"
            async with session.get(url, params={"slugs": gifid}) as r:
                if r.status == 200:
                    data = await r.json()
                    results = data.get("data", {}).get("data", [])
                    if not results:
                        return None
                    return results[0]["file"]["hd"]["gif"]["url"]
                else:
                    logging.error(f"Klipy API error for ID {gifid}: status {r.status}")
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
        user_nickname = message.author.display_name
        user_avatar_url = (
            message.author.display_avatar.url
            if hasattr(message.author, "display_avatar")
            else (message.author.avatar.url if message.author.avatar else "")
        )

        guild = self.client.get_guild(message.guild.id)
        if guild:
            member = guild.get_member(message.author.id)
            if not member:
                try:
                    member = await guild.fetch_member(message.author.id)
                except Exception:
                    pass
            if member:
                user_nickname = member.nick if member.nick else member.name
                user_avatar_url = (
                    member.display_avatar.url
                    if hasattr(member, "display_avatar")
                    else (member.avatar.url if member.avatar else "")
                )

        # Constructing the message content
        message_jump_url = message.jump_url
        message_content = f"{emoji} {current_count} | {message_jump_url}"

        # Constructing the embed
        embed = Embed(
            description=f"{message.content}\n\n",
            timestamp=message.created_at,
            colour=LIGHT_GREY,
        )

        if message.content.startswith("https://klipy.com/"):
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
                    f"Failed to retrieve GIF URL for Klipy link: {message.content}"
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

    async def rebuild_reactor_totals(
        self, messages_per_page: int = 100, page_delay: float = 1.0
    ):
        """Scan text channels for historical 💀 reactions and populate `reactor_posts`.

        This method pages through each accessible text channel in each guild, finds
        messages that have 💀 reactions, records each reactor in the DB and updates
        per-channel progress so the scan can resume after restarts without reprocessing.
        """
        logging.info("Starting reactor totals rebuild scan")

        for guild in self.client.guilds:
            guild_id_str = str(guild.id)

            # Iterate text channels sequentially to avoid rate limits
            for channel in getattr(guild, "text_channels", []):
                try:
                    # Minimal permission check; if missing, skip the channel
                    perms = channel.permissions_for(guild.me) if guild.me else None
                    if perms and not (
                        perms.view_channel and perms.read_message_history
                    ):
                        logging.info(
                            f"Skipping channel {channel.id} due to missing permissions"
                        )
                        continue
                except Exception:
                    # If permissions cannot be determined, attempt to proceed and rely on exceptions
                    pass

                # Get progress for this channel
                progress = await self.db.get_reactor_progress(
                    guild_id_str, str(channel.id)
                )
                last_marker = None
                completed = False
                if progress:
                    last_marker, completed = progress[0], bool(progress[1])

                if completed:
                    logging.info(f"Skip channel {channel.id} (already scanned)")
                    continue

                before_id = (
                    int(last_marker) if last_marker and int(last_marker) > 0 else None
                )

                while True:
                    try:
                        # Page messages newest -> oldest using `before` marker
                        if before_id:
                            msgs = [
                                m
                                async for m in channel.history(
                                    limit=messages_per_page, before=Object(id=before_id)
                                )
                            ]
                        else:
                            msgs = [
                                m
                                async for m in channel.history(limit=messages_per_page)
                            ]
                    except Exception as e:
                        logging.exception(
                            f"Failed to fetch history for channel {channel.id}: {e}"
                        )
                        break

                    if not msgs:
                        # Nothing left to scan; mark completed
                        await self.db.set_reactor_progress(
                            guild_id_str, str(channel.id), before_id or 0, 1
                        )
                        logging.info(f"Completed scanning channel {channel.id}")
                        break

                    # msgs come newest-first; we'll process them in the order returned
                    # and use the oldest message in the page as the next `before` marker
                    for message in msgs:
                        # Only look for skull reactions on messages
                        if not getattr(message, "reactions", None):
                            continue

                        for reaction in message.reactions:
                            try:
                                # Only process skull emoji
                                if reaction.emoji == "💀":
                                    async for user in reaction.users():
                                        # Skip bot's own reactions
                                        if user.id == self.client.user.id:
                                            continue
                                        try:
                                            # If the message is within the 7-day tracking window, keep
                                            # the reactor in the temporary `reactor_posts` table so
                                            # live updates and expiry logic continue to work.
                                            # For older messages, increment the long-term
                                            # `reactors` aggregate directly so `reactor_posts` stays
                                            # temporary-only.
                                            message_day = time.get_day_from_timestamp(
                                                message.created_at
                                            )
                                            if time.get_current_day() - 7 < message_day:
                                                await self.db.add_reactor_post(
                                                    message.id, user.id, guild_id_str
                                                )
                                            else:
                                                await self.db.add_reactor_count(
                                                    user.id, guild_id_str, 1
                                                )
                                        except Exception:
                                            logging.exception(
                                                "Failed to record reactor for message %s user %s",
                                                message.id,
                                                user.id,
                                            )
                            except Exception:
                                # Reaction/users fetch may fail for permissions/rate limit; skip
                                logging.exception(
                                    "Failed to iterate users for reaction on message %s",
                                    getattr(message, "id", None),
                                )

                    # Update progress marker to the oldest message id we processed in this page
                    oldest_msg_id = msgs[-1].id
                    await self.db.set_reactor_progress(
                        guild_id_str, str(channel.id), oldest_msg_id, 0
                    )

                    # If we received less than a full page, we've reached the start of history
                    if len(msgs) < messages_per_page:
                        await self.db.set_reactor_progress(
                            guild_id_str, str(channel.id), oldest_msg_id, 1
                        )
                        logging.info(
                            f"Completed scanning channel {channel.id} (final page)"
                        )
                        break

                    # Prepare next page marker and sleep a bit to avoid hitting rate limits
                    before_id = oldest_msg_id
                    await asyncio.sleep(page_delay)

        logging.info("Reactor totals rebuild scan finished")

        # Once the historical scan has completed for all guilds, aggregate any
        # remaining temporary reactor_posts into the long-term `reactors` table,
        # clear the temporary table, and mark progress as finished so subsequent
        # reaction events update the aggregated table in real-time.
        try:
            await self.db.aggregate_and_clear_reactor_posts()
            await self.db.mark_all_reactor_progress_completed()
            self.backfill_completed = True
            logging.info(
                "Backfill complete: reactor_posts migrated and progress marked finished"
            )
        except Exception:
            logging.exception("Failed to finalize reactor backfill")


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
        self.admin_db = AdminSettingsDB()

    def interaction_handler(func: Callable[[], Awaitable[Response]]):
        """Wrapper to handle skullboard command interactions and errors"""

        @wraps(func)
        async def wrapper(self, interaction: Interaction, *args, **kwargs):
            try:
                public_flag = False
                try:
                    sig = signature(func)
                    bound = sig.bind_partial(self, interaction, *args, **kwargs)
                    public_flag = bool(bound.arguments.get("public", False))
                except Exception:
                    public_flag = bool(kwargs.get("public", False))

                ephemeral_flag = not bool(public_flag)

                await interaction.response.defer(ephemeral=ephemeral_flag)

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
                    ephemeral=ephemeral_flag,
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
    async def about(self, interaction: Interaction, public: bool = False) -> Response:
        guild_id = _get_guild_id(interaction)
        channel_id, required = self.admin_db.get_server_settings(str(guild_id))
        channel_mention = f"<#{channel_id}>" if channel_id else "(not configured)"
        skullboard_info = (
            "## 💀 WELCOME TO THE SKULLZONE 💀\n\n"
            "The **Skullboard** is a fun way to track popular posts and active users in the CS Club! 💀\n"
            f"When a post receives a certain number of 💀 reactions, it gets added to {channel_mention}. 💀\n"
            "Users earn a 💀 for their popular posts, and these 💀 contribute to their overall ranking. 💀\n"
        )
        cmds = [
            "`/skull rank` to view the top skullboard users of all-time",
            "`/skull hof` to view the top posts of all-time",
            "`/skull week` to view the top posts of the week",
            "`/skull stats` to view the distribution of skullboard posts from the past week, month, year, or all-time",
            "`/skull user` to show the total number of skullboard posts a user has, compared to other users",
            "`/skull reactors` to view the top users who add skull reactions (all-time)",
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
    async def rank(self, interaction: Interaction, public: bool = False):
        guild_id = _get_guild_id(interaction)
        rankings = await self.db.get_user_rankings(10, str(guild_id))
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

    @app_commands.command(
        name="reactors", description="Get top Skull reactors (all-time)"
    )
    @interaction_handler
    async def reactors(
        self, interaction: Interaction, public: bool = False
    ) -> Response:
        guild = interaction.guild
        guild_id = _get_guild_id(interaction)
        # Request more rows than we will display so we can filter out users who left
        rankings = await self.db.get_reactor_rankings(100, str(guild_id))
        if rankings is None:
            raise Exception("Database Error")

        # If we're in a guild context, exclude reactors who are no longer members.
        filtered = []
        if guild:
            for reactor_id, frequency in rankings:
                try:
                    member = guild.get_member(int(reactor_id))
                except Exception:
                    member = None
                if member:
                    filtered.append((reactor_id, frequency))
                if len(filtered) >= 10:
                    break
        else:
            filtered = rankings[:10]

        msg = ["### Top Reactors of All-Time:\n"]

        for reactor_id, frequency in filtered[:10]:
            line = f"💀 {frequency} : <@{reactor_id}>"
            msg.append(line)
        msg = "\n".join(msg)

        # Compute backfill progress for this guild (percentage of eligible channels scanned)
        backfill_text = None
        if guild:
            try:
                guild_id_str = str(guild.id)
                eligible_channels = []
                for ch in getattr(guild, "text_channels", []):
                    try:
                        perms = ch.permissions_for(guild.me) if guild.me else None
                        if perms and perms.view_channel and perms.read_message_history:
                            eligible_channels.append(ch)
                    except Exception:
                        # If permission check failed, skip the channel
                        continue

                total = len(eligible_channels)
                completed_cnt = 0
                overall_percent = 0.0
                if total > 0:
                    per_channel_percents = []
                    for ch in eligible_channels:
                        progress = await self.db.get_reactor_progress(
                            guild_id_str, str(ch.id)
                        )
                        # Fully scanned channel
                        if progress and int(progress[1]) == 1:
                            completed_cnt += 1
                            per_channel_percents.append(100.0)
                            continue

                        # Partial or not-started channel: estimate progress using timestamps
                        last_marker = None
                        if progress:
                            last_marker = progress[0]

                        if not last_marker or int(last_marker) == 0:
                            per_channel_percents.append(0.0)
                            continue

                        try:
                            # newest message
                            newest_msgs = [m async for m in ch.history(limit=1)]
                            newest = newest_msgs[0] if newest_msgs else None
                            # oldest message
                            oldest_msgs = [
                                m async for m in ch.history(limit=1, oldest_first=True)
                            ]
                            oldest = oldest_msgs[0] if oldest_msgs else None
                            # message corresponding to the last processed marker
                            processed_msg = await ch.fetch_message(int(last_marker))

                            if not (newest and oldest and processed_msg):
                                per_channel_percents.append(0.0)
                                continue

                            new_ts = newest.created_at.timestamp()
                            old_ts = oldest.created_at.timestamp()
                            proc_ts = processed_msg.created_at.timestamp()

                            denom = new_ts - old_ts
                            if denom <= 0:
                                pct = 100.0 if proc_ts <= new_ts else 0.0
                            else:
                                pct = max(
                                    0.0, min(100.0, 100.0 * (new_ts - proc_ts) / denom)
                                )

                            per_channel_percents.append(pct)
                        except Exception:
                            logging.exception(
                                "Failed to compute progress for channel %s", ch.id
                            )
                            per_channel_percents.append(0.0)

                    overall_percent = round(sum(per_channel_percents) / total, 1)
                    if overall_percent < 100:
                        backfill_text = (
                            f"INCOMPLETE NUMBERS: Backfill progress: {overall_percent}% "
                            f"({completed_cnt}/{total} channels scanned). Please check again later for updated numbers."
                        )
            except Exception:
                logging.exception("Failed to compute reactor backfill progress")

        embed = Embed(
            title="💀   TOP REACTORS   💀",
            colour=LIGHT_GREY,
            description=msg,
        )

        if backfill_text:
            embed.set_footer(text=backfill_text)
        response = Response(embed=embed)
        return response

    @app_commands.command(name="hof", description="Get top Skullboard posts (all-time)")
    @interaction_handler
    async def hof(self, interaction: Interaction, public: bool = False) -> Response:
        guild_id = _get_guild_id(interaction)
        hof_entries = await self.db.get_HOF(10, str(guild_id))
        if not hof_entries:
            raise Exception("Database Error")
        # Warning: description in embed cannot be longer than 2048 characters
        msg = ["### Top Posts of All-Time:"]

        # The post date is unused, may use in future if needed.
        for post_id, user_id, channel_id, day, frequency in hof_entries[:10]:
            # Format the HoF entries into a readable message
            line = _format_post_link(guild_id, channel_id, post_id, user_id, frequency)
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
    async def week(self, interaction: Interaction, public: bool = False) -> Response:
        guild_id = _get_guild_id(interaction)
        hof_entries = await self.db.get_7_day_post(5, str(guild_id))
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
            line = _format_post_link(guild_id, channel_id, post_id, user_id, frequency)
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
        self,
        interaction: Interaction,
        timeframe: app_commands.Choice[str],
        public: bool = False,
    ) -> Response:
        data = []
        title = ""
        option = ""
        guild_id = interaction.guild.id if interaction.guild else None
        if timeframe.value == "w":
            option = "This Week's"
            data = await self.db.get_7_day_histogram(str(guild_id))
        elif timeframe.value == "m":
            option = "This Month's"
            data = await self.db.get_30_day_histogram(str(guild_id))
        elif timeframe.value == "y":
            option = "This Year's"
            data = await self.db.get_365_day_histogram(str(guild_id))
        elif timeframe.value == "a":
            option = "All-Time"
            data = await self.db.get_alltime_histogram(str(guild_id))
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
        _, threshold = self.admin_db.get_server_settings(str(guild_id))
        above_threshold = sum([y for x, y in data if x >= threshold])
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
    async def user(
        self, interaction: Interaction, member: Member, public: bool = False
    ) -> Response:
        user_id = member.id
        user_name = member.name
        guild_id = _get_guild_id(interaction)

        data = await self.db.get_user_rankings(999999, str(guild_id))  # get all
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
