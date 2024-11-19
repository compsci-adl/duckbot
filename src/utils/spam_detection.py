import datetime
import discord
import os
from dotenv import load_dotenv
import Levenshtein

# Load environment variables from .env file
load_dotenv()
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))

# List of known spam messages
spam_messages = [
    "Hi! Everyone, please I’m trying to sell my Zach Bryan tickets because I can’t attend the show anymore due to change of plans. Anyone interested should text me on WhatsApp +1 (214) 632‑6846",
    "I want to give out my MacBook Air 2020 & Charger** for free, it's in perfect health and good as new, alongside a charger so it's perfect, I want to give it out because I just got a new model and I thought of giving out the old one to someone who can't afford one and is in need of it... Strictly First come first serve ! PM IF YOU ARE INTERESTED OR YOU CAN DM ME FOR MORE INFO",
    "Top University Ghost Tutor Contact Email: ivy.researcher1@gmail.com Instagram: Ivyreseacher1 Telegram:t.me/Ivyresearchers WhatsApp :+44 7878519184 :+12067366194 Courses Engineering (Aerospace, Material, Mechanical, Industrial) Business (Analytics, Statistics, Accounting) Economics (Microeconomics) Management (Supply Chain, MBA) IT & Project Management PolicyTech & Various Engineering Fields Science, Math, Psychology, Philosophy Medical courses Academic Support 24/7 Services include: ✏️ Quizzes & Assignments 🖊️ Reports & Thesis 📝 Essay Writing & More 💻 Online Sessions WhatsApp group: https://chat.whatsapp.com/H5TnqaEp2uy8bHms4ibkDr Message John on WhatsApp. https://wa.me/message/F3QWRUV4EGWVK1 Group 2 https://chat.whatsapp.com/JEJ5TCd7UPSH2LtYMHkrZt",
    "Hey everyone! I’m looking to pass my Sabrina carpenter tickets for footprint center in Phoenix, AZ. Wed,Nov 13. HMU if you’re interested +1 480-719-4319",
    "Hi! Everyone, please I’m trying to sell my Sabrina Carpenter tickets because I can’t attend the show anymore due to change of plans. Anyone interested should DM",
    "I want to give out my MacBook 2020 & Charger** for free, it's in perfect health and good as new, alongside a charger so it's perfect, I want to give it out because I just got a new model and I thought of giving out the old one to someone who can't afford one and is in need of it... Strictly First come first serve ! DM IF YOU ARE INTERESTED or on my iMessage…..jaynicky626@gmail.com",
    "Hi! Everyone, please I’m trying to sell my Billie Eilish tickets because I can’t attend the show anymore due to change of plans. Anyone interested should Text me on (360)-572-6816",
]


# Function to calculate normalised Levenshtein distance and detect spam
def is_spam(input_message, spam_messages, threshold=0.2):
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
            print(f"User {member} has been timed out for 1 day.")
        except Exception as e:
            print(f"An error occurred: {e}")

        # Log the spam message
        try:
            log_channel = message.guild.get_channel(LOG_CHANNEL_ID)

            # Create an embed to log the spam message
            embed = discord.Embed(
                description=f"**Message sent by {member.mention} in {message.channel.mention} was flagged as spam, deleted, and the user has been timed out for 1 day. Review the message and ban the member if confirmed as spam.**",
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
