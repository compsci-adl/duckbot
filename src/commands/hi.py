from discord import Interaction, app_commands


class HiGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="hi", description="Commands to greet users")

    @app_commands.command(name="me", description="Say hi to you.")
    async def me(self, interaction: Interaction):
        user = interaction.user
        await interaction.response.send_message(f"Hi {user.mention}!")

    @app_commands.command(name="there", description="Say hi.")
    async def there(self, interaction: Interaction):
        await interaction.response.send_message("Hi there!")


hi_group = HiGroup()
