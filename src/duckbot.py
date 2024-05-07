"""
DuckBot
"""

# TODO: Set up proper logging

import json
import os
import time
from pathlib import Path

import discord
from discord.ext import commands
from dotenv import load_dotenv


class DuckBot(commands.AutoShardedBot):
    def __init__(self, config, intents):
        super().__init__(command_prefix="d.", intents=intents)

        self.config = config
        self.env_path = config["env-path"]
        self.developers = config["developers"]

    def run_process(self):
        """Run the bot"""

        self.startup_time = time.time()

        load_dotenv(dotenv_path=self.env_path, verbose=True)
        token = os.getenv("BOT_TOKEN")

        super().run(token, reconnect=True)

    async def load_all_modules(self):
        """Load all modules at bot startup"""
        loaded_modules = 0
        modules = [
            x.stem for x in Path("modules").glob("*.py") if "__init__" not in x.stem
        ]

        for mod in modules:
            try:
                await self.load_extension(f"modules.{mod}")
                # logger.info("Loaded: %s", mod)
                loaded_modules += 1
            except Exception as e:
                error = f"modules.{mod}\n{type(e).__name__}: {e}"
                # logger.error("Failed to load %s", error)

        # logger.info("STATUS: %s of %s modules have been loaded", loaded_modules, len(modules))

    async def reload(self, ctx: commands.Context, module: str):
        await self.reload_extension(f"modules.{module}")
        await self.tree.sync()
        await ctx.send(f"Successfully reloaded {module}")

    async def load(self, ctx: commands.Context, module: str):
        await self.load_extension(f"modules.{module}")
        await self.tree.sync()
        await ctx.send(f"Successfully loaded {module}")

    async def unload(self, ctx: commands.Context, module: str):
        await self.unload_extension(f"modules.{module}")
        await ctx.send(f"Successfully unloaded {module}")

    async def on_ready(self):
        await self.load_all_modules()
        await self.change_presence(status=discord.Status.online)
        await self.tree.sync()


def run():
    with open("./config.json") as f:
        config = json.load(f)

    bot = DuckBot(config, discord.Intents.all())

    @bot.command()
    async def reload(ctx, module):
        await bot.reload(ctx, module)

    @bot.command()
    async def load(ctx, module):
        await bot.load(ctx, module)

    @bot.command()
    async def unload(ctx, module):
        await bot.unload(ctx, module)

    bot.run_process()
