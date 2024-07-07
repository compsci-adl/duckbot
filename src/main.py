import os
from dotenv import load_dotenv
import importlib
import pkgutil
from discord import (
    Intents,
    app_commands,
    Object,
    Interaction,
    Embed,
    Color,
    RawReactionActionEvent,
)
from discord.ext import commands
from commands import skullboard

# Load environment variables from .env file
load_dotenv()

# Retrieve environment variables
GUILD_ID = int(os.environ["GUILD_ID"])
BOT_TOKEN = os.environ["BOT_TOKEN"]
SKULLBOARD_CHANNEL_ID = int(os.environ["SKULLBOARD_CHANNEL_ID"])

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

    async def setup_hook(self):
        # Dynamically load all command groups from the commands directory
        for _, module_name, _ in pkgutil.iter_modules(["commands"]):
            module = importlib.import_module(f"commands.{module_name}")
            for attribute_name in dir(module):
                attribute = getattr(module, attribute_name)
                if isinstance(attribute, app_commands.Group):
                    self.tree.add_command(attribute, guild=Object(GUILD_ID))

        if not self.synced:  # Check if slash commands have been synced
            await self.tree.sync(guild=Object(GUILD_ID))
            self.synced = True

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
                    message, SKULLBOARD_CHANNEL_ID, "ADD"
                )

    async def on_raw_reaction_remove(self, payload: RawReactionActionEvent):
        if payload.emoji.name == "💀":
            channel = self.get_channel(payload.channel_id)
            message = await channel.fetch_message(payload.message_id)
            # Ignore reactions to own messages
            if message.author.id != self.user.id:
                await self.skullboard_manager.handle_skullboard(
                    message, SKULLBOARD_CHANNEL_ID, "REMOVE"
                )


client = DuckBot()


@client.tree.command(description="Pong!", guild=Object(GUILD_ID))
async def ping(interaction: Interaction):
    await interaction.response.send_message("Pong!")


@client.tree.command(
    description="View useful information about using the bot.",
    guild=Object(GUILD_ID),
)
async def help(interaction: Interaction):
    commands_list = list(client.tree.get_commands(guild=Object(GUILD_ID)))
    embed = Embed(
        title="DuckBot",
        description="DuckBot is the CS Club's Discord bot, created by the CS Club Open Source Team.",
        color=Color.yellow(),
    )
    for command in commands_list:
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


# Add the token of bot
client.run(BOT_TOKEN)
