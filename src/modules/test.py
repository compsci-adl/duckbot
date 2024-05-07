"""
Testing purposes only
"""

from discord import app_commands
from discord.ext import commands


class Test(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def hello(self, ctx):
        await ctx.send("Hello world!")

class TestSlash(app_commands.Group):

    test = app_commands.Group(name="test", description="For testing purposes")

    @test.command(name="hello")
    async def hello_slash(self, interaction):
        await interaction.response.send_message("Hello world!")

async def setup(bot: commands.Bot):
    await bot.add_cog(Test(bot))
    bot.tree.add_command(TestSlash())
