import os
import requests
import re
from discord import Embed, Client
from dotenv import load_dotenv
from constants.colours import LIGHT_GREY


class SkullboardManager:
    def __init__(self, client: Client):
        """Initialise SkullboardManager"""
        load_dotenv()  # Load environment variables from .env file
        self.client = client
        self.required_reactions = int(os.getenv("REQUIRED_REACTIONS"))

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

        async for skullboard_message in channel.history(limit=100):
            if message_jump_url in skullboard_message.content:
                skullboard_message_id = skullboard_message.id
                break

        if current_count >= self.required_reactions:
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
        user_avatar_url = message.author.avatar.url

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
            sticker_url = f"https://media.discordapp.net/stickers/{
                sticker_id}.{format_type}"
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
