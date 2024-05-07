"""
Commands related to sending information about the club and its projects
"""

from discord.ext import commands


class Info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


async def setup(bot: commands.Bot):
    await bot.add_cog(Info(bot))
