import datetime
import os
import re

import aiohttp
import discord
import Levenshtein
from dotenv import load_dotenv

from models.databases.admin_settings_db import AdminSettingsDB

# Load environment variables from .env file
load_dotenv()
CMS_URL = os.getenv("CMS_URL")
KNOWN_SPAM_MESSAGES_URL = f"{CMS_URL}/api/known-spam-messages?limit=500"


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
    Advanced spam detection using multiple heuristics including similarity to known spam,
    keyword matching, and pattern detection.

    Args:
    - input_message (str): The message to classify.
    - spam_messages (list): A list of known spam messages.
    - threshold (float): The threshold below which the message is considered spam.

    Returns:
    - bool: Indicates if the message is spam.
    """
    score = 0

    # Levenshtein similarity check
    for spam_message in spam_messages:
        # Calculate the Levenshtein distance between the input and the spam message
        distance = Levenshtein.distance(input_message.lower(), spam_message.lower())
        max_len = max(len(input_message), len(spam_message))
        if max_len > 0:
            normalised_distance = distance / max_len
            # High weight for similarity to known spam
            if normalised_distance < threshold:
                score += 10

    # Common spam keyword check
    spam_keywords = [
        "free",
        "dm",
        "tutors",
        "giving away",
        "first come first serve",
        "hello @everyone",
        "join our discord",
        "email me",
        "text me",
        "pm me",
        "dm me",
        "asap",
        "amazing condition",
        "friend request",
        "@everyone",
        "giving out",
        "for free",
        "perfect health",
        "good as new",
        "perfectly working",
        "just got a new model",
        "can't afford one",
        "in need of it",
        "dm if you are interested",
        "join our discord server",
        "top-tier tutors",
        "ace your assignments",
        "ace your exams",
        "handing out",
        "great condition",
        "practically new",
        "just upgraded",
        "pass this one on",
        "really needs it",
        "give out",
        "give it out",
        "inbox me",
        "trying to sell",
        "can't attend",
        "change of plans",
        "text me on whatsapp",
        "save some money",
        "pm if you are interested",
        "email me via",
        "whatsapp",
    ]

    keyword_count = 0
    lower_message = input_message.lower()
    for kw in spam_keywords:
        if kw.lower() in lower_message:
            keyword_count += 1
    if keyword_count > 0:
        score += keyword_count * 2

    # URL detection
    url_pattern = re.compile(
        r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
    )
    if url_pattern.search(input_message):
        score += 3

    # Email detection
    email_pattern = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
    if email_pattern.search(input_message):
        score += 2

    # Phone number detection (basic US format)
    phone_pattern = re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b")
    if phone_pattern.search(input_message):
        score += 2

    # Excessive emojis
    emoji_pattern = re.compile(
        r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]"
    )
    emoji_count = len(emoji_pattern.findall(input_message))
    if emoji_count > 5:
        score += 1

    # Threshold for spam
    return score > 6


async def check_spam(message, settings_db=None):
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

        # Log the spam message using the configured global `LOG_CHANNEL_ID` stored in DB
        try:
            # Accept a settings_db instance to avoid repeated DB instantiation.
            db = settings_db if settings_db is not None else AdminSettingsDB()
            log_channel_id = db.get_setting("LOG_CHANNEL_ID")
            if not log_channel_id:
                # Nothing configured, skip logging
                return
            try:
                log_channel_obj = message.guild.get_channel(int(log_channel_id))
            except Exception:
                log_channel_obj = None

            if log_channel_obj is None:
                return

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
            await log_channel_obj.send(embed=embed)
        except Exception as e:
            print(f"An error occurred while logging the spam message: {e}")
