import os
import datetime
import pytz
from discord import Embed

# Dictionary to map original message IDs to Skullboard message IDs and current skull counts
message_map = {}

async def handle_skullboard(client, reaction, SKULLBOARD_CHANNEL_ID, type):
    skullboard_channel = client.get_channel(SKULLBOARD_CHANNEL_ID)
    if skullboard_channel:
        message = reaction.message
        emoji = "💀"

        # Check if the reaction is a skull emoji
        if str(reaction.emoji) == emoji:
            # Skip reposting messages sent by the bot
            if message.author == client.user:
                return  

            # Check if the message ID is in the map
            if message.id in message_map:
                skullboard_message_id, current_count = message_map[message.id]
            else:
                skullboard_message_id = None
                current_count = 0

            # Update the current count based on the reaction event
            if type == "ADD":
                current_count += 1
            elif type == "REMOVE":
                current_count -= 1

            # Store the updated count in the message map
            message_map[message.id] = (skullboard_message_id, current_count)

            # Determine action based on current count
            if current_count > 0:
                await update_or_send_skullboard_message(skullboard_channel, message, current_count, emoji)
            else:
                await delete_skullboard_message(skullboard_channel, message)
        else:
            print("Reaction is not a skull emoji. Skipping Skullboard handling.")
    else:
        print(f"Skullboard channel not found with ID {SKULLBOARD_CHANNEL_ID}. Message could not be sent.")

async def update_or_send_skullboard_message(channel, message, current_count, emoji):
    if message.id in message_map:
        skullboard_message_id, _ = message_map[message.id]
        if skullboard_message_id:
            await update_skullboard_message(channel, message, current_count, emoji, skullboard_message_id)
        else:
            await send_skullboard_message(channel, message, current_count, emoji)
    else:
        await send_skullboard_message(channel, message, current_count, emoji)

async def send_skullboard_message(channel, message, current_count, emoji):
    # Format the reposted message with the number of skulls, channel name, timestamp, and mention
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

    # Send the reposted message as an embed in the selected channel
    skullboard_message = await channel.send(embed=embed)
    message_map[message.id] = (skullboard_message.id, current_count)

async def update_skullboard_message(channel, message, current_count, emoji, skullboard_message_id):
    # Format the updated embed with the current count
    channel_name = message.channel.name
    adelaide_time = get_adelaide_time()
    mention = message.author.mention
    message_content = message.content
    message_link = message.jump_url  # URL to jump to the message

    # Constructing the updated embed
    embed = Embed(
        title=f"{current_count} {emoji} | #{channel_name}",
        description=f"{mention}\n\n{message_content}\n\n[Click to go to message!]({message_link})",
        timestamp=adelaide_time
    )

    # Fetch the existing Skullboard message and update it
    skullboard_message = await channel.fetch_message(skullboard_message_id)
    await skullboard_message.edit(embed=embed)
    message_map[message.id] = (skullboard_message.id, current_count)

async def delete_skullboard_message(channel, message):
    # Delete the Skullboard message
    if message.id in message_map:
        skullboard_message_id, _ = message_map[message.id]
        if skullboard_message_id:
            skullboard_message = await channel.fetch_message(skullboard_message_id)
            await skullboard_message.delete()
            del message_map[message.id]

def get_adelaide_time():
    # Convert UTC timestamp to Adelaide time
    adelaide_tz = pytz.timezone('Australia/Adelaide')
    utc_now = datetime.datetime.utcnow()
    adelaide_time = utc_now.replace(tzinfo=pytz.utc).astimezone(adelaide_tz)
    return adelaide_time
