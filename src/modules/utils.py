"""
Utilities
"""

import time

from discord.ext import commands

import util


class Utilities(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def uptime(self, ctx):
        days, hours, mins, secs = util.extract_time_from_secs(
            int(time.time()) - self.bot.startup_time
        )
        await ctx.send(f"Uptime: {days}d, {hours}h, {mins}m, {secs}s")


async def setup(bot: commands.Bot):
    await bot.add_cog(Utilities(bot))
