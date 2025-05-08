from datetime import datetime, timezone

import discord
from discord import Interaction, TextStyle, app_commands
from discord.ext import commands
from discord.ui import Button, Modal, TextInput, View

COMMITTEE_ROLE_NAME = "Committee"
ANON_TICKET_CHANNEL_NAME = "anonymous-tickets"
TICKET_CATEGORY_NAME = "Tickets"


class TicketForm(Modal, title="Create a Ticket"):
    def __init__(self, anonymous: bool):
        super().__init__(timeout=None)
        self.anonymous = anonymous

        # Only add these fields if it's a non-anonymous ticket
        if not self.anonymous:
            self.add_item(TextInput(label="Name (optional)", required=False))
            self.add_item(TextInput(label="Email (optional)", required=False))
            self.add_item(TextInput(label="Year (optional)", required=False))

        # Add the details field for both anonymous and non-anonymous tickets
        self.add_item(
            TextInput(
                label="Details of your issue",
                style=TextStyle.paragraph,
                required=True,
            )
        )

    async def on_submit(self, interaction: Interaction):
        guild = interaction.guild
        committee_role = discord.utils.get(guild.roles, name=COMMITTEE_ROLE_NAME)
        category = discord.utils.get(guild.categories, name=TICKET_CATEGORY_NAME)

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
                    name=field.label, value=field.value or "Not Provided", inline=False
                )
            await anon_channel.send(embed=embed)
            await interaction.response.send_message(
                "Your anonymous ticket has been submitted.", ephemeral=True
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

            embed = discord.Embed(
                title="New Ticket",
                color=discord.Color.green(),
                timestamp=datetime.now(timezone.utc),
            )
            for field in self.children:
                embed.add_field(
                    name=field.label, value=field.value or "Not Provided", inline=False
                )
            await ticket_channel.send(embed=embed)
            await interaction.response.send_message(
                f"Ticket created: {ticket_channel.mention}", ephemeral=True
            )


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
async def ticket_panel(interaction: Interaction):
    embed = discord.Embed(
        title="Support",
        description="Need help? Click a button below to create a ticket.",
        color=discord.Color.blue(),
    )
    await interaction.channel.send(embed=embed, view=TicketPanel())
    await interaction.response.send_message("Ticket panel posted.", ephemeral=True)


async def setup(bot: commands.Bot):
    bot.tree.add_command(ticket_group)
