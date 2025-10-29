import asyncio
import importlib
import logging
import os
import pkgutil

from discord import (
    Attachment,
    Embed,
    Intents,
    Interaction,
    Message,
    Object,
    RawReactionActionEvent,
    app_commands,
)
from discord.errors import NotFound
from discord.ext import commands
from dotenv import load_dotenv

from commands import admin_commands, gemini, help_menu, skullboard, ticketing
from constants.colours import LIGHT_YELLOW
from utils import spam_detection, time
from utils.event_roles import EventRoleManager

# Load environment variables from .env file
load_dotenv()

# Retrieve guild ID and bot token from environment variables
GUILD_ID = int(os.environ["GUILD_ID"])
BOT_TOKEN = os.environ["BOT_TOKEN"]
SKULLBOARD_CHANNEL_ID = int(os.environ["SKULLBOARD_CHANNEL_ID"])
TENOR_API_KEY = os.environ["TENOR_API_KEY"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
SPAM_CHECK_MIN_MSG = 3
MESSAGE_HISTORY_LIMIT = 1000

# Load the permissions the bot has been granted in the previous configuration
intents = Intents.default()
intents.guilds = True
intents.messages = True
intents.message_content = True
intents.reactions = True
intents.members = True


class DuckBot(commands.Bot):
    async def on_scheduled_event_user_add(self, event, user):
        """Delegate to EventRoleManager."""
        await self.event_role_manager.on_scheduled_event_user_add(event, user)

    async def on_scheduled_event_user_remove(self, event, user):
        """Delegate to EventRoleManager."""
        await self.event_role_manager.on_scheduled_event_user_remove(event, user)

    async def on_scheduled_event_update(self, before, after):
        """Delegate to EventRoleManager."""
        await self.event_role_manager.on_scheduled_event_update(before, after)

    def __init__(self):
        super().__init__(command_prefix="", intents=intents)
        self.synced = False  # Make sure that the command tree will be synced only once
        self.skullboard_manager = skullboard.SkullboardManager(
            self
        )  # Initialise SkullboardManager
        self.event_role_manager = EventRoleManager(self)  # Initialise EventRoleManager
        self.prev_day = None
        self.expiry_loop = None

        # logging
        logging.basicConfig(
            filename="DuckBot.log",  # Log file name
            format="%(asctime)s %(levelname)-8s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            level=logging.INFO,  # Minimum log level to capture
        )
        logging.info("Started Bot")

        # Initialise gemini model
        self.gemini_model = gemini.GeminiBot(
            model_name="models/gemini-2.5-flash",
            data_csv_path="src/data/duckbot_train_data.csv",
            bot=self,
            api_key=GEMINI_API_KEY,
        )

        self.admin_commands = admin_commands.AdminCommands(gemini_bot=self.gemini_model)
        self.tree.add_command(self.admin_commands, guild=Object(GUILD_ID))

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
        self.add_view(ticketing.TicketPanel())

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


@client.tree.command(description="Ask DuckBot anything!", guild=Object(GUILD_ID))
async def chat(interaction: Interaction, query: str | None, file: Attachment | None):
    try:
        await interaction.response.defer()
        query = "" if query is None else query
        bot_response = await client.gemini_model.query(
            message=query,
            attachment=file,
            author=interaction.user.display_name,
            author_id=interaction.user.id,
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
async def help(interaction: Interaction):  # noqa: A001
    Help_Menu_View = help_menu.HelpMenu(client)  # Creating the view for buttons
    Help_Menu_View.update_select_options()  # Creating options for select menu
    embed = Help_Menu_View.create_help_embed(0)
    await interaction.response.send_message(
        embed=embed, view=Help_Menu_View, ephemeral=True
    )


# Ignore non-slash commands
@client.event
async def on_message(message: Message):
    # Ignore DMs and bot's own messages
    if message.guild is None or message.author.bot:
        return

    # Count user's messages in channel
    count = 0
    async for msg in message.channel.history(limit=MESSAGE_HISTORY_LIMIT):
        if msg.author.id == message.author.id:
            count += 1
            # Exit early if count exceeds SPAM_CHECK_MIN_MSG
            if count >= SPAM_CHECK_MIN_MSG:
                break

    # If the user has sent less than SPAM_CHECK_MIN_MSG messages in the channel, check for spam
    if count < SPAM_CHECK_MIN_MSG:
        await spam_detection.check_spam(message)

    if (
        (client.user.mentioned_in(message) or "d.chat" in message.clean_content)
        and message.author != client.user
        and not message.mention_everyone
    ):
        attachment = message.attachments[0] if message.attachments else None

        bot_response = await client.gemini_model.query(
            author_id=message.author.id,
            author=message.author.display_name,
            message=message.content.replace("d.chat", "")
            .replace(f"<@{client.user.id}>", "")
            .strip(),
            attachment=attachment,
        )
        await message.reply(embeds=bot_response, mention_author=False)


# Add the token of bot
client.run(BOT_TOKEN)
