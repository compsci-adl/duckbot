import logging
import os

from discord import Embed, Interaction, app_commands
from dotenv import load_dotenv

from models.databases.admin_settings_db import AdminSettingsDB

load_dotenv()

# Retrieve the list of admin usernames from the .env file
ADMIN_USERS = os.getenv("ADMIN_USERS", "").split(",")


class AdminCommands(app_commands.Group):
    def __init__(self, gemini_bot):
        super().__init__(name="admin", description="Admin commands for DuckBot setup.")

        # Initialise the database
        self.settings_db = AdminSettingsDB()

        # Add subgroups to the main admin group
        self.set = SetSubGroup(self.check_admin, self.settings_db)
        self.reset = ResetSubGroup(self.check_admin, gemini_bot)

        # Register subgroups
        self.add_command(self.set)
        self.add_command(self.reset)

    async def check_admin(self, interaction: Interaction) -> bool:
        user_name = interaction.user.name
        logging.info(f"Checking admin status for user: {user_name}")

        if user_name in ADMIN_USERS:
            logging.info(f"User {user_name} is authorised.")
            return True
        else:
            await interaction.response.send_message(
                "You don't have permission to execute that command.", ephemeral=True
            )
            logging.warning(f"User {user_name} is not authorised.")
            return False

    @app_commands.command(
        name="log-variables", description="Display all current environment variables."
    )
    async def log_info(self, interaction: Interaction):
        """Command to log and display all relevant environment variables."""
        if not await self.check_admin(interaction):
            return

        # Get values from database instead of env
        guild_id = self.settings_db.get_setting("GUILD_ID") or "Not Set"
        skullboard_channel_id = (
            self.settings_db.get_setting("SKULLBOARD_CHANNEL_ID") or "Not Set"
        )
        required_reactions = (
            self.settings_db.get_setting("REQUIRED_REACTIONS") or "Not Set"
        )

        embed = Embed(title="Current Settings", color=0x00FF00)
        embed.add_field(name="Guild ID", value=f"`{guild_id}`", inline=False)
        embed.add_field(
            name="Skullboard Channel ID",
            value=f"`{skullboard_channel_id}`",
            inline=False,
        )
        embed.add_field(
            name="Required Reactions", value=f"`{required_reactions}`", inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


class SetSubGroup(app_commands.Group):
    def __init__(self, check_admin, settings_db):
        super().__init__(
            name="set", description="Set configuration values for DuckBot."
        )
        self.check_admin = check_admin
        self.settings_db = settings_db

    @app_commands.command(name="guild-id", description="Set the guild ID for DuckBot.")
    async def set_guild_id(self, interaction: Interaction, guild_id: str):
        if not await self.check_admin(interaction):
            return
        self.settings_db.set_setting("GUILD_ID", guild_id)
        await interaction.response.send_message(
            f"Guild ID set to {guild_id}.", ephemeral=True
        )

    @app_commands.command(
        name="skullboard-channel-id", description="Set the Skullboard channel ID."
    )
    async def set_skullboard_channel_id(
        self, interaction: Interaction, channel_id: str
    ):
        if not await self.check_admin(interaction):
            return
        self.settings_db.set_setting("SKULLBOARD_CHANNEL_ID", channel_id)
        await interaction.response.send_message(
            f"Skullboard channel ID set to {channel_id}.", ephemeral=True
        )

    @app_commands.command(
        name="required-reactions", description="Set required reactions for Skullboard."
    )
    async def set_required_reactions(self, interaction: Interaction, reactions: int):
        if not await self.check_admin(interaction):
            return
        self.settings_db.set_setting("REQUIRED_REACTIONS", str(reactions))
        await interaction.response.send_message(
            f"Required reactions set to {reactions}.", ephemeral=True
        )


class ResetSubGroup(app_commands.Group):
    def __init__(self, check_admin, gemini_bot):
        super().__init__(name="reset", description="Reset specific DuckBot settings.")
        self.check_admin = check_admin
        self.gemini_bot = gemini_bot

    @app_commands.command(name="chat-history", description="Reset Gemini chat history.")
    async def reset_chat_history(self, interaction: Interaction):
        if not await self.check_admin(interaction):
            return

        # Call the method to reset Gemini chat history
        self.gemini_bot.clear_chat_history()

        await interaction.response.send_message(
            "Gemini chat history has been reset.", ephemeral=True
        )
