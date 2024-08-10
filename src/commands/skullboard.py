import os
import requests
import re

from discord import Client, Interaction, AllowedMentions, Embed, app_commands

from models.databases.skullboard_database import SkullboardDB
from utils import time
from constants.colours import LIGHT_GREY


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
            skullboard_info, embed=embed, allowed_mentions=AllowedMentions().none()
        )

    @app_commands.command(name="rank", description="Get top users")
    async def rank(self, interaction: Interaction):
        try:
            rankings = await self.db.get_user_rankings()
            if not rankings:
                await interaction.response.send_message(
                    "Database error fetching user rankings - check the logs."
                )
                return

            # Warning: description in embed cannot be longer than 2048 characters
            msg = ["### Top Users of All-Time:\n"]

            for user_id, frequency in rankings[:10]:
                # Format the rankings into a readable message
                line = f"💀 {frequency} : <@!{user_id}>"
                msg.append(line)
            msg = "\n".join(msg)

            embed = Embed(
                title="💀💀💀   TOP SKULLERS   💀💀💀",
                colour=LIGHT_GREY,
                description=msg,
            )

            await interaction.response.send_message(
                embed=embed, allowed_mentions=AllowedMentions().none()
            )

        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {str(e)}")

    @app_commands.command(name="hof", description="Get top posts")
    async def hof(self, interaction: Interaction):
        try:
            hof_entries = await self.db.get_HOF()
            if not hof_entries:
                await interaction.response.send_message(
                    "Database error fetching Hall of Fame - check the logs."
                )
                return

            # Warning: description in embed cannot be longer than 2048 characters
            msg = ["### Top Posts of All-Time:"]

            # The post date is unused, may use in future if needed.
            for post_id, user_id, channel_id, day, frequency in hof_entries[:10]:
                # Format the HoF entries into a readable message
                line = f"💀 {frequency} : https://discord.com/channels/{self.db.guild_id}/{channel_id}/{post_id} from <@!{user_id}>"
                msg.append(line)

            msg = "\n".join(msg)
            embed = Embed(
                title="💀💀💀   HALL OF FAME   💀💀💀",
                colour=LIGHT_GREY,
                description=msg,
            )

            await interaction.response.send_message(
                embed=embed, allowed_mentions=AllowedMentions().none()
            )

        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {str(e)}")


skullboard_group = SkullGroup()
