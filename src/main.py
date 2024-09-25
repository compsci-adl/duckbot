import os
import importlib
import pkgutil
import asyncio
import logging

from discord import (
    Intents,
    app_commands,
    Object,
    Interaction,
    Embed,
    Color,
    Message,
    RawReactionActionEvent,
    Attachment,
)
from discord.errors import NotFound
from discord.ext import commands
from dotenv import load_dotenv

from constants.colours import LIGHT_YELLOW
from commands import gemini, skullboard
from utils import time

# Load environment variables from .env file
load_dotenv()

# Retrieve guild ID and bot token from environment variables
GUILD_ID = int(os.environ["GUILD_ID"])
BOT_TOKEN = os.environ["BOT_TOKEN"]
SKULLBOARD_CHANNEL_ID = int(os.environ["SKULLBOARD_CHANNEL_ID"])
TENOR_API_KEY = os.environ["TENOR_API_KEY"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

# Load the permissions the bot has been granted in the previous configuration
intents = Intents.default()
intents.guilds = True
intents.messages = True
intents.message_content = True
intents.reactions = True
intents.members = True


class DuckBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="", intents=intents)
        self.synced = False  # Make sure that the command tree will be synced only once
        self.skullboard_manager = skullboard.SkullboardManager(
            self
        )  # Initialise SkullboardManager
        self.prev_day = None
        self.expiry_loop = None

        # logging
        logging.basicConfig(
            filename="DuckBot.log",  # Log file name
            format="%(asctime)s %(levelname)-8s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            level=logging.INFO,  # Minimum log level to capture
        )
        logging.info(f"Started Bot")

        # Initialise gemini model
        self.gemini_model = gemini.GeminiBot(
            model_name="models/gemini-1.5-flash",
            data_csv_path="src/data/duckbot_train_data.csv",
            bot=self,
            api_key=GEMINI_API_KEY,
        )

    async def setup_hook(self):
        # Dynamically load all command groups from the commands directory
        for _, module_name, _ in pkgutil.iter_modules(["src/commands"]):
            module = importlib.import_module(f"commands.{module_name}")
            for attribute_name in dir(module):
                attribute = getattr(module, attribute_name)
                if isinstance(attribute, app_commands.Group):
                    self.tree.add_command(attribute, guild=Object(GUILD_ID))
        if not self.synced:  # Check if slash commands have been synced
            await self.tree.sync(guild=Object(GUILD_ID))
            self.synced = True
        self.loop.create_task(self.run_expiry_loop())

    async def on_ready(self):
        print(f"Say hi to {self.user}!")

    # Override on_message method with correct parameters
    async def on_message(self, message):
        pass

    # Register the reaction handling
    async def on_raw_reaction_add(self, payload: RawReactionActionEvent):
        if payload.emoji.name == "💀":
            channel = self.get_channel(payload.channel_id)
            message = await channel.fetch_message(payload.message_id)
            # Ignore reactions to own messages
            if message.author.id != self.user.id:
                await self.skullboard_manager.handle_skullboard(
                    message, SKULLBOARD_CHANNEL_ID
                )

    async def on_raw_reaction_remove(self, payload: RawReactionActionEvent):
        if payload.emoji.name == "💀":
            channel = self.get_channel(payload.channel_id)
            message = await channel.fetch_message(payload.message_id)
            # Ignore reactions to own messages
            if message.author.id != self.user.id:
                await self.skullboard_manager.handle_skullboard(
                    message, SKULLBOARD_CHANNEL_ID
                )

    async def run_expiry_loop(self):
        """runs every minute checking for expiration"""
        while True:
            curr = time.get_current_day()
            if self.prev_day != curr:
                await self.skullboard_manager.db.expire()
                logging.info(f"Expired old data {curr}")
                self.prev_day = curr
            await asyncio.sleep(60)  # Wait 1 minute


client = DuckBot()


@client.tree.command(description="Pong!", guild=Object(GUILD_ID))
async def ping(interaction: Interaction):
    await interaction.response.send_message("Pong!", ephemeral=True)


@client.tree.command(description="Ask Gemini anything!", guild=Object(GUILD_ID))
async def chat(interaction: Interaction, query: str | None, file: Attachment | None):

    try:
        await interaction.response.defer()
        query = "" if query == None else query
        bot_response = await client.gemini_model.query(
            message=query, attachment=file, author=interaction.user.display_name
        )
        await interaction.followup.send(embeds=bot_response)

    except NotFound as e:
        """
        As implemented in skullboard by Josh
        Note that for the commands which use interaction.response.defer() method, sporadic 404 errors will be occassionally raised.
        This is a known bug with the discord API/client https://github.com/discord/discord-api-docs/issues/5558
        The exception clauses suppresses this particular error message from being sent to the client or logged, since it does not affect the final message sent.
        """
        IGNORE_404_API_BUG_ERROR_CODE = 10062
        if e.code != IGNORE_404_API_BUG_ERROR_CODE:  # Supress API bug error
            raise  # Re-raise other NotFound errors

    except Exception as e:
        await interaction.followup.send(
            embed=Embed(
                title="Error",
                description="There was an error processing your request.",
                color=LIGHT_YELLOW,
            )
        )
        logging.exception(
            f"GEMINI: User {interaction.user.display_name} triggered the following error while calling Gemini: {e}"
        )


@client.tree.command(
    description="View useful information about using the bot.",
    guild=Object(GUILD_ID),
)
async def help(interaction: Interaction):
    commands = list(client.tree.get_commands(guild=Object(GUILD_ID)))
    embed = Embed(
        title="DuckBot",
        description="DuckBot is the CS Club's Discord bot, created by the CS Club Open Source Team.",
        color=Color.yellow(),
    )
    for command in commands:
        if isinstance(command, app_commands.Group):
            # Add the group name
            embed.add_field(
                name=f"/{command.name}", value=f"{command.description}", inline=False
            )
            # Add each subcommand in the group
            for subcommand in command.commands:
                embed.add_field(
                    name=f"/{command.name} {subcommand.name}",
                    value=subcommand.description,
                    inline=True,
                )
        else:
            embed.add_field(
                name=f"/{command.name}", value=command.description, inline=False
            )
    await interaction.response.send_message(embed=embed)


# Ignore non-slash commands
@client.event
async def on_message(message: Message):
    if (
        client.user.mentioned_in(message) or "d.chat" in message.clean_content
    ) and message.author != client.user:
        attachment = message.attachments[0] if message.attachments else None

        bot_response = await client.gemini_model.query(
            author_id=message.author.id,
            author=message.author.display_name,
            message=message.clean_content.replace("d.chat", ""),
            attachment=attachment,
        )
        await message.reply(embeds=bot_response, mention_author=False)


# Add the token of bot
client.run(BOT_TOKEN)
