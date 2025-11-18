import asyncio
import logging
from datetime import datetime, timezone

import discord
from discord import Interaction, TextStyle, app_commands
from discord.ext import commands
from discord.ui import Button, Modal, TextInput, View

from commands.command_helpers import require_admin

# Names are assumed to be the same across guilds; channel IDs differ per guild.
COMMITTEE_ROLE_NAME = "Committee"
ANON_TICKET_CHANNEL_NAME = "anonymous-tickets"
TICKET_CATEGORY_NAME = "Tickets"
ARCHIVE_CATEGORY_NAME = "Archived Tickets"
LOG_CHANNEL_NAME = "bot-log-ticketing"


class TicketForm(Modal, title="Create a Ticket"):
    def __init__(self, anonymous: bool):
        super().__init__(timeout=None)
        self.anonymous = anonymous

        # Set the description based on whether the ticket is anonymous or not
        if self.anonymous:
            self.description = "This ticket will be posted anonymously for committee members to review."
        else:
            self.description = "You will be added to a private channel to discuss your issue further with committee members."

        # Only add these fields if it's a non-anonymous ticket
        if not self.anonymous:
            self.add_item(TextInput(label="Name (optional)", required=False))
            self.add_item(TextInput(label="Uni Year Level (optional)", required=False))

        # Add the details field for both anonymous and non-anonymous tickets
        self.add_item(
            TextInput(
                label="Details of your issue",
                placeholder=self.description,
                style=TextStyle.paragraph,
                required=True,
            )
        )

    async def on_submit(self, interaction: Interaction):
        guild = interaction.guild
        committee_role = discord.utils.get(guild.roles, name=COMMITTEE_ROLE_NAME)
        category = discord.utils.get(guild.categories, name=TICKET_CATEGORY_NAME)
        log_channel = discord.utils.get(guild.text_channels, name=LOG_CHANNEL_NAME)

        if self.anonymous:
            # Send anonymous tickets to a dedicated anonymous channel
            anon_channel = discord.utils.get(
                guild.text_channels, name=ANON_TICKET_CHANNEL_NAME
            )
            embed = discord.Embed(
                title="New Anonymous Ticket",
                color=discord.Color.blue(),
                timestamp=datetime.now(timezone.utc),
            )
            for field in self.children:
                embed.add_field(
                    name=field.label, value=field.value or "N/A", inline=False
                )
            await anon_channel.send(embed=embed)
            await interaction.response.send_message(
                "Your anonymous ticket has been submitted.", ephemeral=True
            )

            # Log the ticket creation in the log channel
            if log_channel:
                await log_channel.send(
                    embed=discord.Embed(
                        title="📨 Anonymous Ticket Submitted",
                        description=f"Ticket submitted in {anon_channel.mention}",
                        color=discord.Color.blue(),
                        timestamp=datetime.now(timezone.utc),
                    )
                )
        else:
            # Create a new ticket channel that only the committee and user can view
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                committee_role: discord.PermissionOverwrite(view_channel=True),
                interaction.user: discord.PermissionOverwrite(view_channel=True),
            }

            ticket_channel = await guild.create_text_channel(
                name=f"ticket-{interaction.user.name}".lower(),
                category=category,
                overwrites=overwrites,
                topic=f"Ticket created by {interaction.user.display_name}",
            )

            # Send a welcome message tagging the user
            await ticket_channel.send(content=f"Welcome {interaction.user.mention}!")

            embed = discord.Embed(
                title="New Ticket",
                color=discord.Color.yellow(),
                timestamp=datetime.now(timezone.utc),
            )
            for field in self.children:
                embed.add_field(
                    name=field.label, value=field.value or "Not Provided", inline=False
                )
            await ticket_channel.send(embed=embed)

            # After sending initial embed in ticket channel
            await ticket_channel.send(
                embed=discord.Embed(
                    title="✅ Ticket Created",
                    description="Thank you for submitting your ticket. A committee member will respond when available. To close this ticket, please click the button below.",
                    color=discord.Color.green(),
                    timestamp=datetime.now(timezone.utc),
                ),
                view=CloseTicketView(channel=ticket_channel),
            )

            await interaction.response.send_message(
                f"Ticket created: {ticket_channel.mention}", ephemeral=True
            )

            # Log the ticket creation in the log channel
            if log_channel:
                await log_channel.send(
                    embed=discord.Embed(
                        title="📨 Ticket Created",
                        description=f"{interaction.user.mention} created {ticket_channel.mention}",
                        color=discord.Color.green(),
                        timestamp=datetime.now(timezone.utc),
                    )
                )


class CloseReasonModal(Modal, title="Close Ticket"):
    def __init__(self, view: "CloseTicketView"):
        super().__init__(timeout=None)
        self.view = view
        self.reason = TextInput(
            label="Reason for closing the ticket",
            style=TextStyle.paragraph,
            required=True,
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: Interaction):
        # Add a small delay to allow the modal to close
        await asyncio.sleep(1)

        # Defer the interaction to avoid 404 error
        await interaction.response.defer(ephemeral=True)

        # Move the channel to Archived Tickets
        guild = interaction.guild
        archive_category = discord.utils.get(
            guild.categories, name=ARCHIVE_CATEGORY_NAME
        )
        log_channel = discord.utils.get(guild.text_channels, name=LOG_CHANNEL_NAME)

        if archive_category:
            # Send the close reason and embed
            embed = discord.Embed(
                title="🔒 Ticket Closed",
                color=discord.Color.red(),
                timestamp=datetime.now(timezone.utc),
            )
            embed.add_field(
                name="Closed by", value=interaction.user.mention, inline=False
            )
            embed.add_field(name="Reason", value=self.reason.value, inline=False)

            await self.view.channel.send(embed=embed)

            # Move the channel to the archived category
            await self.view.channel.edit(category=archive_category)

            # Extract the user ID from the first message in the channel
            first_message = None
            async for message in self.view.channel.history(limit=1, oldest_first=True):
                first_message = message
                break

            if first_message:
                user_id = int(first_message.content.split("@")[1].split(">")[0])
                user = guild.get_member(user_id)
            else:
                user = None

            if user:
                # Disable sending messages for the user who created the ticket, but keep the view permission
                await self.view.channel.set_permissions(
                    user, view_channel=True, send_messages=False
                )

            # Send a confirmation response back to the user using followup
            await interaction.followup.send(
                embed=discord.Embed(
                    title="✅ Ticket Archived",
                    description="This ticket has been successfully closed and moved to Archived Tickets. You can no longer send messages in this ticket.",
                    color=discord.Color.green(),
                    timestamp=datetime.now(timezone.utc),
                ),
                ephemeral=True,
            )

            if log_channel:
                await log_channel.send(
                    embed=discord.Embed(
                        title="🔒 Ticket Closed",
                        description=f"{self.view.channel.mention} closed by {interaction.user.mention}",
                        color=discord.Color.red(),
                        timestamp=datetime.now(timezone.utc),
                    ).add_field(name="Reason", value=self.reason.value, inline=False)
                )
        else:
            await interaction.followup.send(
                "❌ Archive category not found.", ephemeral=True
            )


class CloseTicketView(View):
    def __init__(self, channel: discord.TextChannel):
        super().__init__(timeout=None)
        self.channel = channel

    @discord.ui.button(label="🔒 Close Ticket", style=discord.ButtonStyle.red)
    async def close_ticket(self, interaction: Interaction, button: Button):
        await interaction.response.send_modal(CloseReasonModal(view=self))


class TicketPanel(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="📩 Create Ticket",
        style=discord.ButtonStyle.green,
        custom_id="ticket_panel:create_ticket",
    )
    async def non_anon_ticket(self, interaction: Interaction, button: Button):
        await interaction.response.send_modal(TicketForm(anonymous=False))

    @discord.ui.button(
        label="🕵️ Create Anonymous Ticket",
        style=discord.ButtonStyle.blurple,
        custom_id="ticket_panel:create_anon_ticket",
    )
    async def anon_ticket(self, interaction: Interaction, button: Button):
        await interaction.response.send_modal(TicketForm(anonymous=True))


ticket_group = app_commands.Group(name="ticket", description="Ticketing commands")


@ticket_group.command(name="panel", description="Send a ticket panel with buttons")
@require_admin(require_guild=True)
async def ticket_panel(interaction: Interaction):
    member = interaction.user
    user_name = member.name
    logging.info(f"Posting ticket panel at request of user: {user_name}")

    embed = discord.Embed(
        title="Support",
        description="Need help? Click a button below to create a ticket.",
        color=discord.Color.blue(),
    )
    await interaction.channel.send(embed=embed, view=TicketPanel())
    await interaction.response.send_message("Ticket panel posted.", ephemeral=True)


async def setup(bot: commands.Bot):
    bot.tree.add_command(ticket_group)
