import os
from discord import Embed, Client
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
        user_avatar_url = message.author.avatar

        # Constructing the message content
        message_jump_url = message.jump_url
        message_content = f"{emoji} {
            current_count} | {message_jump_url}"

        # Constructing the embed
        embed = Embed(
            description=f"{message.content}\n\n",
            timestamp=message.created_at,
        )
        # Set user nickname and thumbnail
        embed.set_author(name=user_nickname, icon_url=user_avatar_url)

        # Determine if sending or editing the message
        if send:
            await channel.send(message_content, embed=embed)
        else:
            skullboard_message = await channel.fetch_message(skullboard_message_id)
            await skullboard_message.edit(content=message_content, embed=embed)
