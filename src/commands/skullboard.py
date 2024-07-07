import os
import json
from discord import Embed, Client
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

DATA_FILE = os.getenv("DATA_FILE")
REQUIRED_REACTIONS = int(os.getenv("REQUIRED_REACTIONS"))


class SkullboardManager:
    def __init__(self, client: Client):
        self.client = client
        self.data_file = DATA_FILE
        self.required_reactions = REQUIRED_REACTIONS
        self.message_map = {}
        self.load_data()

    # Load existing data from JSON file if available
    def load_data(self):
        if os.path.exists(self.data_file):
            with open(self.data_file, "r", encoding="utf-8") as f:
                self.message_map = json.load(f)

    # Save data to JSON file
    def save_data(self):
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(self.message_map, f)

    # Function to handle reactions and update/delete skullboard messages
    async def handle_skullboard(self, message, skullboard_channel_id, value):
        skullboard_channel = self.client.get_channel(skullboard_channel_id)
        if not skullboard_channel:
            return

        emoji = "💀"
        message_id_str = str(message.id)

        if message_id_str in self.message_map:
            skullboard_message_id, current_count = self.message_map[message_id_str]
        else:
            skullboard_message_id = None
            current_count = 0

        if value == "ADD":
            current_count += 1
        elif value == "REMOVE":
            current_count = max(0, current_count - 1)

        self.message_map[message_id_str] = (skullboard_message_id, current_count)
        await self.update_or_send_skullboard_message(
            skullboard_channel, message, current_count, emoji
        )
        self.save_data()

    # Function to update or send skullboard message
    async def update_or_send_skullboard_message(
        self, channel, message, current_count, emoji
    ):
        skullboard_message_id, _ = self.message_map.get(str(message.id), (None, 0))

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
        # Format the message details
        channel_name = message.channel.name
        message_time = message.created_at
        mention = message.author.mention
        message_content = message.content
        message_link = message.jump_url

        # Constructing the embed
        embed = Embed(
            title=f"{current_count} {emoji} | #{channel_name}",
            description=f"{mention}\n\n{message_content}\n\n[Click to go to message!]({
                message_link})",
            timestamp=message_time,
        )

        # Determine if sending or editing the message
        if send:
            skullboard_message = await channel.send(embed=embed)
            self.message_map[str(message.id)] = (skullboard_message.id, current_count)
        else:
            skullboard_message = await channel.fetch_message(skullboard_message_id)
            await skullboard_message.edit(embed=embed)

        # Save the updated message_map to the JSON file after each modification
        self.save_data()
