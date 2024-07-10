import os
import requests
import re
from discord import Embed, Client, Color
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

REQUIRED_REACTIONS = int(os.getenv("REQUIRED_REACTIONS"))


class SkullboardManager:
    def __init__(self, client: Client):
        self.client = client
        self.required_reactions = REQUIRED_REACTIONS

    # Function to handle reactions and update/delete skullboard messages
    async def handle_skullboard(self, message, skullboard_channel_id):
        skullboard_channel = self.client.get_channel(skullboard_channel_id)
        if not skullboard_channel:
            return

        emoji = "💀"
        current_count = next(
            (
                reaction.count
                for reaction in message.reactions
                if reaction.emoji == emoji
            ),
            0,
        )

        await self.update_or_send_skullboard_message(
            skullboard_channel, message, current_count, emoji
        )

    # Function to update or send skullboard message
    async def update_or_send_skullboard_message(
        self, channel, message, current_count, emoji
    ):
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
        # Get the page content
        page_content = requests.get(view_url).text

        # Regex to find the URL on the media.tenor.com domain that ends with .gif
        regex = r"(?i)\b((https?://media1[.]tenor[.]com/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))[.]gif)"

        # Find and return the first match
        match = re.findall(regex, page_content)

        return match[0][0] if match else None

    # Function to edit or send skullboard message
    async def edit_or_send_skullboard_message(
        self,
        channel,
        message,
        current_count,
        emoji,
        send=False,
        skullboard_message_id=None,
    ):
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
            colour=Color.from_rgb(204, 214, 221),
        )

        if message.content.startswith("https://tenor.com/view/"):
            # Constructing the embed
            embed = Embed(
                timestamp=message.created_at,
                colour=Color.from_rgb(204, 214, 221),
            )

            # Find the URL of the gif
            gif_url = await self.get_gif_url(message.content)

            if gif_url:
                embed.set_image(url=gif_url)
            
        # Set user nickname and thumbnail
        embed.set_author(name=user_nickname, icon_url=user_avatar_url)

        # Add images, stickers, and attachments
        if message.stickers:
            print(message.stickers[0].id)
            print(message.stickers[0].format)

            # Replace the pattern with just the format type
            format_type = str(message.stickers[0].format).split('.', maxsplit=1)[-1]

            sticker_id = message.stickers[0].id
            sticker_url = f"https://media.discordapp.net/stickers/{
                sticker_id}.{format_type}"
            print(sticker_url)
            embed.set_image(url=sticker_url)

        if message.attachments:
            embed.set_image(url=message.attachments[0].url)

        # Determine if sending or editing the message
        if send:
            await channel.send(message_content, embed=embed)
        else:
            skullboard_message = await channel.fetch_message(skullboard_message_id)
            await skullboard_message.edit(content=message_content, embed=embed)
