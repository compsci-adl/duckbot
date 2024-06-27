import os
import json
from discord import Embed
from dotenv import load_dotenv
from .utils.time import get_adelaide_time

# Load environment variables from .env file
load_dotenv()

# Global variable to store the path to the JSON file
DATA_FILE = os.getenv('DATA_FILE')
REQUIRED_REACTIONS = int(os.getenv('REQUIRED_REACTIONS'))

# Initialise message_map
message_map = {}

# Load existing data from JSON file if available
def load_data():
    global message_map
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            message_map = json.load(f)

# Save data to JSON file
def save_data():
    with open(DATA_FILE, 'w') as f:
        json.dump(message_map, f)

# Function to handle reactions and update/delete skullboard messages
async def handle_skullboard(client, message, SKULLBOARD_CHANNEL_ID, type):
    # Load data at the start
    load_data()

    skullboard_channel = client.get_channel(SKULLBOARD_CHANNEL_ID)
    if not skullboard_channel:
        return
    
    emoji = "💀"

    # Convert message id to string to ensure consistency
    message_id_str = str(message.id)

    # Update or delete Skullboard message based on reaction type
    if message_id_str in message_map:
        skullboard_message_id, current_count = message_map[message_id_str]
    else:
        skullboard_message_id = None
        current_count = 0

    if type == "ADD":
        current_count += 1
    elif type == "REMOVE":
        current_count = max(0, current_count - 1)

    message_map[message_id_str] = (skullboard_message_id, current_count)
    await update_or_send_skullboard_message(skullboard_channel, message, current_count, emoji)

    # Save the updated message_map to the JSON file after each modification
    save_data()

# Function to update or send skullboard message
async def update_or_send_skullboard_message(channel, message, current_count, emoji):
    skullboard_message_id, _ = message_map.get(str(message.id), (None, 0))

    if skullboard_message_id:
        await edit_or_send_skullboard_message(channel, message, current_count, emoji, send=False, skullboard_message_id=skullboard_message_id)
    else:
        await edit_or_send_skullboard_message(channel, message, current_count, emoji, send=True)

# Function to edit or send skullboard message
async def edit_or_send_skullboard_message(channel, message, current_count, emoji, send=False, skullboard_message_id=None):
    # Format the message details
    channel_name = message.channel.name
    adelaide_time = get_adelaide_time()
    mention = message.author.mention
    message_content = message.content
    message_link = message.jump_url

    # Constructing the embed
    embed = Embed(
        title=f"{current_count} {emoji} | #{channel_name}",
        description=f"{mention}\n\n{message_content}\n\n[Click to go to message!]({message_link})",
        timestamp=adelaide_time
    )

    # Determine if sending or editing the message
    if send:
        skullboard_message = await channel.send(embed=embed)
        message_map[str(message.id)] = (skullboard_message.id, current_count)
    else:
        skullboard_message = await channel.fetch_message(skullboard_message_id)
        await skullboard_message.edit(embed=embed)

    # Save the updated message_map to the JSON file after each modification
    save_data()
