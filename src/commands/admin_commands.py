import logging

from discord import Color, Embed, Interaction, app_commands
from dotenv import load_dotenv

from models.databases.admin_settings_db import AdminSettingsDB

load_dotenv()


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
        """Check if the user who called the admin command is an admin"""

        user_name = interaction.user.name
        logging.info(f"Checking admin status for user: {user_name}")
        # Consider users with roles 'Exec Committee' or 'Mods' as admins
        member = interaction.user
        if interaction.guild and hasattr(member, "roles"):
            role_names = {r.name for r in member.roles}
            if "Exec Committee" in role_names or "Mods" in role_names:
                logging.info(f"User {user_name} is authorised by role.")
                return True

        await interaction.response.send_message(
            "You don't have permission to execute that command.", ephemeral=True
        )
        logging.warning(f"User {user_name} is not authorised.")
        return False

    @app_commands.command(
        name="help", description="Display name and description of admin commands"
    )
    async def admin_help(self, interaction: Interaction):
        """Help command containing all admin commands and details"""
        if not await self.check_admin(interaction):
            return

        embed = Embed(
            title=self.name,
            description=self.description,
            color=Color.yellow(),
        )
        for subcommand in self.walk_commands():
            if isinstance(subcommand, app_commands.Group):
                for subsubcommand in subcommand.commands:
                    embed.add_field(
                        name=f"/{self.name} {subcommand.name} {subsubcommand.name}",
                        value=subsubcommand.description,
                        inline=True,
                    )
            else:
                embed.add_field(
                    name=f"/{self.name} {subcommand.name}",
                    value=subcommand.description,
                    inline=False,
                )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="log-variables", description="Display all current environment variables."
    )
    async def log_info(self, interaction: Interaction):
        """Command to log and display all relevant environment variables."""
        if not await self.check_admin(interaction):
            return
        # Show per-guild settings if possible
        guild_id = interaction.guild.id if interaction.guild else None
        if guild_id:
            channel_id, required = self.settings_db.get_server_settings(str(guild_id))
            channel_id = channel_id or "Not Set"
            required = required if required is not None else "Not Set"
        else:
            channel_id = (
                self.settings_db.get_setting("SKULLBOARD_CHANNEL_ID") or "Not Set"
            )
            required = self.settings_db.get_setting("REQUIRED_REACTIONS") or "Not Set"

        # Also include ticketing-related names
        def _get_key(k):
            return (
                self.settings_db.get_setting(k, guild_id=str(guild_id))
                if guild_id
                else self.settings_db.get_setting(k)
            )

        committee_role = _get_key("COMMITTEE_ROLE_NAME") or "Not Set"
        anon_ticket_channel = _get_key("ANON_TICKET_CHANNEL_NAME") or "Not Set"
        ticket_category = _get_key("TICKET_CATEGORY_NAME") or "Not Set"
        archive_category = _get_key("ARCHIVE_CATEGORY_NAME") or "Not Set"
        log_channel = (
            _get_key("LOG_CHANNEL_NAME")
            or self.settings_db.get_setting("LOG_CHANNEL_ID")
            or "Not Set"
        )

        embed = Embed(title="Current Settings", color=0x00FF00)
        embed.add_field(name="Guild ID", value=f"`{guild_id}`", inline=False)
        embed.add_field(
            name="Skullboard Channel ID", value=f"`{channel_id}`", inline=False
        )
        embed.add_field(name="Required Reactions", value=f"`{required}`", inline=False)
        embed.add_field(
            name="Log Channel / Name", value=f"`{log_channel}`", inline=False
        )
        embed.add_field(
            name="Committee Role Name", value=f"`{committee_role}`", inline=False
        )
        embed.add_field(
            name="Anonymous Ticket Channel Name",
            value=f"`{anon_ticket_channel}`",
            inline=False,
        )
        embed.add_field(
            name="Ticket Category Name", value=f"`{ticket_category}`", inline=False
        )
        embed.add_field(
            name="Archive Category Name", value=f"`{archive_category}`", inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


class SetSubGroup(app_commands.Group):
    def __init__(self, check_admin, settings_db):
        super().__init__(
            name="set", description="Set configuration values for DuckBot."
        )
        self.check_admin = check_admin
        self.settings_db = settings_db

    @app_commands.command(
        name="skullboard-channel-id", description="Set the Skullboard channel ID."
    )
    async def set_skullboard_channel_id(
        self, interaction: Interaction, channel_id: str
    ):
        if not await self.check_admin(interaction):
            return
        guild_id = interaction.guild.id if interaction.guild else None
        if not guild_id:
            await interaction.response.send_message(
                "Guild context required.", ephemeral=True
            )
            return
        # Preserve existing required reactions for this guild
        _, required = self.settings_db.get_server_settings(str(guild_id))
        self.settings_db.set_server_settings(str(guild_id), channel_id, required)
        await interaction.response.send_message(
            f"Skullboard channel ID set to {channel_id} for this server.",
            ephemeral=True,
        )

    @app_commands.command(
        name="required-reactions", description="Set required reactions for Skullboard."
    )
    async def set_required_reactions(self, interaction: Interaction, reactions: int):
        if not await self.check_admin(interaction):
            return
        guild_id = interaction.guild.id if interaction.guild else None
        if not guild_id:
            await interaction.response.send_message(
                "Guild context required.", ephemeral=True
            )
            return
        # Preserve existing channel id for this guild
        channel_id, _ = self.settings_db.get_server_settings(str(guild_id))
        self.settings_db.set_server_settings(str(guild_id), channel_id, reactions)
        await interaction.response.send_message(
            f"Required reactions set to {reactions} for this server.", ephemeral=True
        )

    @app_commands.command(
        name="committee-role-name",
        description="Set the committee role name used for ticketing.",
    )
    async def set_committee_role_name(self, interaction: Interaction, name: str):
        if not await self.check_admin(interaction):
            return
        guild_id = interaction.guild.id if interaction.guild else None
        if not guild_id:
            await interaction.response.send_message(
                "Guild context required.", ephemeral=True
            )
            return
        self.settings_db.set_setting(
            "COMMITTEE_ROLE_NAME", name, guild_id=str(guild_id)
        )
        await interaction.response.send_message(
            f"Committee role name set to {name} for this server.", ephemeral=True
        )

    @app_commands.command(
        name="anon-ticket-channel-name",
        description="Set the anonymous ticket channel name.",
    )
    async def set_anon_ticket_channel_name(self, interaction: Interaction, name: str):
        if not await self.check_admin(interaction):
            return
        guild_id = interaction.guild.id if interaction.guild else None
        if not guild_id:
            await interaction.response.send_message(
                "Guild context required.", ephemeral=True
            )
            return
        self.settings_db.set_setting(
            "ANON_TICKET_CHANNEL_NAME", name, guild_id=str(guild_id)
        )
        await interaction.response.send_message(
            f"Anon ticket channel name set to {name} for this server.", ephemeral=True
        )

    @app_commands.command(
        name="ticket-category-name",
        description="Set the ticket category name.",
    )
    async def set_ticket_category_name(self, interaction: Interaction, name: str):
        if not await self.check_admin(interaction):
            return
        guild_id = interaction.guild.id if interaction.guild else None
        if not guild_id:
            await interaction.response.send_message(
                "Guild context required.", ephemeral=True
            )
            return
        self.settings_db.set_setting(
            "TICKET_CATEGORY_NAME", name, guild_id=str(guild_id)
        )
        await interaction.response.send_message(
            f"Ticket category name set to {name} for this server.", ephemeral=True
        )

    @app_commands.command(
        name="archive-category-name",
        description="Set the archive category name.",
    )
    async def set_archive_category_name(self, interaction: Interaction, name: str):
        if not await self.check_admin(interaction):
            return
        guild_id = interaction.guild.id if interaction.guild else None
        if not guild_id:
            await interaction.response.send_message(
                "Guild context required.", ephemeral=True
            )
            return
        self.settings_db.set_setting(
            "ARCHIVE_CATEGORY_NAME", name, guild_id=str(guild_id)
        )
        await interaction.response.send_message(
            f"Archive category name set to {name} for this server.", ephemeral=True
        )

    @app_commands.command(
        name="log-channel-name",
        description="Set the log channel name used by ticketing.",
    )
    async def set_log_channel_name(self, interaction: Interaction, name: str):
        if not await self.check_admin(interaction):
            return
        guild_id = interaction.guild.id if interaction.guild else None
        if not guild_id:
            await interaction.response.send_message(
                "Guild context required.", ephemeral=True
            )
            return
        self.settings_db.set_setting("LOG_CHANNEL_NAME", name, guild_id=str(guild_id))
        await interaction.response.send_message(
            f"Log channel name set to {name} for this server.", ephemeral=True
        )

    @app_commands.command(
        name="log-channel-id", description="Set the global log channel ID for DuckBot."
    )
    async def set_log_channel_id(self, interaction: Interaction, channel_id: str):
        if not await self.check_admin(interaction):
            return
        # This is a global setting stored in the settings table
        self.settings_db.set_setting("LOG_CHANNEL_ID", channel_id)
        await interaction.response.send_message(
            f"Log channel ID set to {channel_id}.", ephemeral=True
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
