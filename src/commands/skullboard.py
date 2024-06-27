from discord import Embed
from .utils.time import get_adelaide_time

# Dictionary to map original message IDs to Skullboard message IDs and current skull counts
message_map = {}

async def handle_skullboard(client, reaction, SKULLBOARD_CHANNEL_ID, type):
    skullboard_channel = client.get_channel(SKULLBOARD_CHANNEL_ID)
    if not skullboard_channel:
        print(f"Skullboard channel not found with ID {SKULLBOARD_CHANNEL_ID}. Message could not be sent.")
        return

    message = reaction.message
    emoji = "💀"

    # Check if the reaction is a skull emoji
    if str(reaction.emoji) != emoji or message.author == client.user:
        return

    # Update or delete Skullboard message based on reaction type
    if message.id in message_map:
        skullboard_message_id, current_count = message_map[message.id]
    else:
        skullboard_message_id = None
        current_count = 0

    if type == "ADD":
        current_count += 1
    elif type == "REMOVE":
        current_count = max(0, current_count - 1)

    message_map[message.id] = (skullboard_message_id, current_count)

    if current_count > 0:
        await update_or_send_skullboard_message(skullboard_channel, message, current_count, emoji)
    else:
        await delete_skullboard_message(skullboard_channel, message)

async def update_or_send_skullboard_message(channel, message, current_count, emoji):
    skullboard_message_id, _ = message_map.get(message.id, (None, 0))

    if skullboard_message_id:
        await update_skullboard_message(channel, message, current_count, emoji, skullboard_message_id)
    else:
        await send_skullboard_message(channel, message, current_count, emoji)

async def send_skullboard_message(channel, message, current_count, emoji):
    await edit_or_send_skullboard_message(channel, message, current_count, emoji, send=True)

async def update_skullboard_message(channel, message, current_count, emoji, skullboard_message_id):
    await edit_or_send_skullboard_message(channel, message, current_count, emoji, send=False, skullboard_message_id=skullboard_message_id)

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
        message_map[message.id] = (skullboard_message.id, current_count)
    else:
        skullboard_message = await channel.fetch_message(skullboard_message_id)
        await skullboard_message.edit(embed=embed)

async def delete_skullboard_message(channel, message):
    # Delete the Skullboard message
    if message.id in message_map:
        skullboard_message_id, _ = message_map[message.id]
        if skullboard_message_id:
            skullboard_message = await channel.fetch_message(skullboard_message_id)
            await skullboard_message.delete()
            del message_map[message.id]
