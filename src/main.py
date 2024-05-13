import discord
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Retrieve guild ID and bot token from environment variables
GUILD_ID = os.getenv("GUILD_ID")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Load the permissions the bot has been granted in the previous configuration
intents = discord.Intents.default()
intents.message_content = True


class DuckBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.synced = False  # Make sure that the command tree will be synced only once
        self.added = False

    async def on_ready(self):
        await self.wait_until_ready()
        if not self.synced:  # Check if slash commands have been synced
            await tree.sync(guild=discord.Object(GUILD_ID))
            self.synced = True
        if not self.added:
            self.added = True
        print(f"Say hi to {self.user}!")


client = DuckBot()
tree = discord.app_commands.CommandTree(client)


@tree.command(description="Pong!", guild=discord.Object(GUILD_ID))
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Pong!")


@tree.command(
    description="View useful information about using the bot.",
    guild=discord.Object(GUILD_ID),
)
async def help(interaction: discord.Interaction):
    commands = list(tree.get_commands(guild=discord.Object(GUILD_ID)))
    embed = discord.Embed(
        title="DuckBot",
        description="DuckBot is the CS Club's Discord bot, created by the CS Club Open Source Team.",
        color=discord.Color.yellow(),
    )
    for command in commands:
        embed.add_field(
            name=f"/{command.name}", value=command.description, inline=False
        )
    await interaction.response.send_message(embed=embed)


# Add the token of bot
client.run(BOT_TOKEN)
