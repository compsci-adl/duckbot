import os
import logging
from discord import app_commands, Interaction

# Retrieve the list of admin usernames from the .env file
ADMIN_USERS = os.getenv("ADMIN_USERS", "").split(",")


class AdminCommands(app_commands.Group):
    def __init__(self, gemini_bot):
        super().__init__(name="admin", description="Admin commands for DuckBot setup.")

        # Add subgroups to the main admin group
        self.set = SetSubGroup(self.check_admin)
        self.reset = ResetSubGroup(self.check_admin, gemini_bot)

        # Register subgroups
        self.add_command(self.set)
        self.add_command(self.reset)

    async def check_admin(self, interaction: Interaction) -> bool:
        user_name = interaction.user.name
        logging.info(f"Checking admin status for user: {user_name}")

        if user_name in ADMIN_USERS:
            logging.info(f"User {user_name} is authorized.")
            return True
        else:
            logging.warning(f"User {user_name} is not authorized.")
            return False

    async def interaction_check(self, interaction: Interaction) -> bool:
        """Restrict all admin commands visibility to authorized users only."""
        is_admin = await self.check_admin(interaction)
        if is_admin:
            return True
        await interaction.response.send_message("Unauthorized", ephemeral=True)
        return False

    @app_commands.command(
        name="log-info", description="Display all current environment variables."
    )
    async def log_info(self, interaction: Interaction):
        """Command to log and display all relevant environment variables."""
        if not await self.check_admin(interaction):
            await interaction.response.send_message("Unauthorized", ephemeral=True)
            return

        # Collect environment variable values
        guild_id = os.getenv("GUILD_ID", "Not Set")
        skullboard_channel_id = os.getenv("SKULLBOARD_CHANNEL_ID", "Not Set")
        required_reactions = os.getenv("REQUIRED_REACTIONS", "Not Set")
        tenor_api_key = os.getenv("TENOR_API_KEY", "Not Set")
        gemini_api_key = os.getenv("GEMINI_API_KEY", "Not Set")

        # Construct a formatted message for environment variables
        config_message = (
            "**Current Environment Variables:**\n"
            f"Guild ID: `{guild_id}`\n"
            f"Skullboard Channel ID: `{skullboard_channel_id}`\n"
            f"Required Reactions: `{required_reactions}`\n"
        )

        await interaction.response.send_message(config_message, ephemeral=True)


class SetSubGroup(app_commands.Group):
    def __init__(self, check_admin):
        super().__init__(
            name="set", description="Set configuration values for DuckBot."
        )
        self.check_admin = check_admin

    @app_commands.command(name="guild-id", description="Set the guild ID for DuckBot.")
    async def set_guild_id(self, interaction: Interaction, guild_id: str):
        if not await self.check_admin(interaction):
            await interaction.response.send_message("Unauthorized", ephemeral=True)
            return
        os.environ["GUILD_ID"] = guild_id
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
            await interaction.response.send_message("Unauthorized", ephemeral=True)
            return
        os.environ["SKULLBOARD_CHANNEL_ID"] = channel_id
        await interaction.response.send_message(
            f"Skullboard channel ID set to {channel_id}.", ephemeral=True
        )

    @app_commands.command(
        name="required-reactions", description="Set required reactions for Skullboard."
    )
    async def set_required_reactions(self, interaction: Interaction, reactions: int):
        if not await self.check_admin(interaction):
            await interaction.response.send_message("Unauthorized", ephemeral=True)
            return
        os.environ["REQUIRED_REACTIONS"] = str(reactions)
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
            await interaction.response.send_message("Unauthorized", ephemeral=True)
            return

        # Call the method to reset Gemini chat history
        self.gemini_bot.clear_chat_history()

        await interaction.response.send_message(
            "Gemini chat history has been reset.", ephemeral=True
        )
