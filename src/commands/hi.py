import discord

hi_group = discord.app_commands.Group(
    name="hi",
    description="Commands to greet users.",
)


@hi_group.command(name="there", description="Say hi.")
async def there(interaction: discord.Interaction):
    await interaction.response.send_message("Hi there!")


@hi_group.command(name="me", description="Say hi to you.")
async def say_hi(interaction: discord.Interaction):
    user = interaction.user
    await interaction.response.send_message(f"Hi {user.mention}!")
