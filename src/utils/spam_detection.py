import datetime
import os

import aiohttp
import discord
import Levenshtein
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
CMS_URL = os.getenv("CMS_URL")
KNOWN_SPAM_MESSAGES_URL = f"{CMS_URL}/api/known-spam-messages"


async def fetch_spam_messages():
    """
    Fetches known spam messages from the CMS and caches them.

    Returns:
        list: A list of known spam messages (strings).
    """
    # Check for cached spam messages and their age
    now = datetime.datetime.now(datetime.timezone.utc)
    if hasattr(fetch_spam_messages, "_cached_spam_messages") and hasattr(
        fetch_spam_messages, "_cache_time"
    ):
        cached = fetch_spam_messages._cached_spam_messages
        cache_time = fetch_spam_messages._cache_time
        if cached is not None and cache_time is not None:
            # If cache is less than 1 day old, use it
            if (now - cache_time).total_seconds() < 86400:
                return cached
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(KNOWN_SPAM_MESSAGES_URL) as resp:
                if resp.status == 200:
                    data = await resp.json()

                    # Parse CMS response
                    messages = [
                        doc["message"] for doc in data["docs"] if "message" in doc
                    ]
                    fetch_spam_messages._cached_spam_messages = messages
                    fetch_spam_messages._cache_time = now
                    return messages
    except Exception as e:
        print(f"Failed to fetch spam messages from CMS: {e}")

    # Fallback to empty list if fetch fails
    fetch_spam_messages._cached_spam_messages = []
    fetch_spam_messages._cache_time = now
    return []


def is_spam(input_message, spam_messages, threshold=0.3):
    """
    Detects if the input message is similar to known spam messages based on Levenshtein distance.
    The distance is normalised, so it ranges from 0 (exact match) to 1 (completely different).

    Args:
    - input_message (str): The message to classify.
    - spam_messages (list): A list of known spam messages.
    - threshold (float): The threshold below which the message is considered spam.

    Returns:
    - bool: Indicates if the message is spam.
    """
    for spam_message in spam_messages:
        # Calculate the Levenshtein distance between the input and the spam message
        distance = Levenshtein.distance(input_message.lower(), spam_message.lower())
        max_len = max(len(input_message), len(spam_message))
        normalised_distance = distance / max_len

        # If the Levenshtein distance is below the threshold, classify as spam
        if normalised_distance < threshold:
            return True

    # If no message is close enough to be considered spam, classify as not spam
    return False


async def check_spam(message):
    """
    Checks potential spam messages by deleting them and timing out the user.

    Args:
    - message (discord.Message): The message object to evaluate.
    """
    input_message = message.content
    spam_messages = await fetch_spam_messages()
    is_spam_flag = is_spam(input_message, spam_messages)

    # If the message is spam, take action
    if is_spam_flag:
        try:
            # Try to delete the spam message
            await message.delete()
        except Exception as e:
            print(f"An error occurred: {e}")

        member = message.author

        # Check if the bot can timeout this member
        bot_role = message.guild.me.top_role
        member_top_role = member.top_role

        if member_top_role >= bot_role:
            print(
                f"Cannot timeout {member.display_name}: Their role is higher or equal to the bot's role."
            )
            return

        try:
            # Timeout the user for 1 day
            await member.timeout(
                datetime.timedelta(days=1), reason="Sending spam messages"
            )
            print(
                f"User {member} has been timed out for 1 day for sending spam messages."
            )
        except Exception as e:
            print(f"An error occurred: {e}")

        # Log the spam message
        try:
            log_channel = message.guild.get_channel(LOG_CHANNEL_ID)

            # Create an embed to log the spam message
            embed = discord.Embed(
                description=f"**Message sent by {member.mention} in {message.channel.mention} was flagged as spam, deleted, and the user has been timed out for 1 day. Review the message and take appropriate action if confirmed as spam.**",
                color=discord.Color.red(),
                timestamp=message.created_at,
            )

            embed.add_field(name="", value=input_message, inline=False)

            embed.set_author(
                name="Spam Message Detected",
                icon_url=(
                    member.avatar.url if member.avatar else member.default_avatar.url
                ),
            )

            embed.set_footer(text=f"User ID: {member.id} | Message ID: {message.id}")

            # Send the embed to the log channel
            await log_channel.send(embed=embed)
        except Exception as e:
            print(f"An error occurred while logging the spam message: {e}")
