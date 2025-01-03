import os

from discord import (
    ButtonStyle,
    Color,
    Embed,
    Interaction,
    Object,
    SelectOption,
    app_commands,
    ui,
)

GUILD_ID = int(os.environ["GUILD_ID"])


class HelpMenu(ui.View):
    currentpage: int = 0
    commands = []
    maxpages: int

    def __init__(self, client):
        super().__init__()
        self.value = None
        self.commands = list(
            client.tree.get_commands(guild=Object(GUILD_ID))
        )  # Gets commands on class creation

        # Separate group commands and misc commands
        self.group_commands = []
        self.misc_commands = []
        self.maxpages = 1
        self.organise_commands()

    def organise_commands(self):
        """Organise commands into groups and misc categories."""
        for command in self.commands:
            if isinstance(command, app_commands.Group):
                if command.name == "admin":  # TODO make a variable for ignore
                    continue
                self.group_commands.append(command)
                self.maxpages += 1
            else:
                self.misc_commands.append(command)

    def create_help_embed(self, page: int):
        """Create and return new embed for given page"""

        # Adjust current page index based on boundaries
        if page < 0:
            self.currentpage = 0
        elif page > self.maxpages:
            self.currentpage = self.maxpages - 1
        else:
            self.currentpage = page

        # Disable buttons in invalid states (using or does not work)
        for item in self.children:
            if isinstance(item, ui.Button):
                if item.label == "Next":
                    item.disabled = self.currentpage >= self.maxpages
                if item.label == "End":
                    item.disabled = self.currentpage >= self.maxpages
                if item.label == "Back":
                    item.disabled = self.currentpage == 0
                if item.label == "Start":
                    item.disabled = self.currentpage == 0

        # Define embed
        embed = Embed(
            title="Invalid embed",
            description="Something went wrong!",
            color=Color.yellow(),
        )

        if (
            self.currentpage == 0
        ):  # Main help menu for displaying different groups with limited detail
            embed = Embed(
                title="__DuckBot__",
                description="DuckBot is the CS Club's Discord bot, created by the CS Club Open Source Team.",
                color=Color.yellow(),
            )
            # Adding group names
            for command in self.group_commands:
                embed.add_field(
                    name=f"{self.capfirst(command.name)}",
                    value=f"{command.description}",
                    inline=False,
                )
            # Misc command
            embed.add_field(
                name="__**Misc**__", value="Miscellaneous commands", inline=False
            )
            for command in self.misc_commands:
                embed.add_field(
                    name=f"{self.capfirst(command.name)}",
                    value=f"{command.description}",
                    inline=False,
                )

        elif (
            self.currentpage > 0 and self.currentpage < self.maxpages
        ):  # Menu for different groups
            command = self.group_commands[self.currentpage - 1]
            # Adding fields for groups
            embed = Embed(
                title=f"{self.capfirst(command.name)} Commands",
                description=f"{command.description}",
                color=Color.yellow(),
            )
            for subcommand in command.commands:
                if isinstance(subcommand, app_commands.Group):
                    for subsubcommand in subcommand.commands:
                        embed.add_field(
                            name=f"/{command.name} {subcommand.name} {subsubcommand.name}",
                            value=subsubcommand.description,
                            inline=True,
                        )
                else:
                    embed.add_field(
                        name=f"/{command.name} {subcommand.name}",
                        value=subcommand.description,
                        inline=True,
                    )
        elif self.currentpage == self.maxpages:
            embed = Embed(
                title="Miscellaneous Commands",
                description="These are commands that are not part of any group.",
                color=Color.yellow(),
            )
            for command in self.misc_commands:
                embed.add_field(
                    name=f"/{command.name}",
                    value=f"{command.description}",
                    inline=False,
                )
        return embed

    def total_pages(self):
        """Calculate total pages: 1 for grouped commands, 1 for misc commands, and 1 for each group."""
        return 2 + len(self.group_commands)

    def update_select_options(self):
        """Update options in the select menu"""
        options = []
        options.append(
            SelectOption(
                label="DuckBot",
                value=0,
                description="DuckBot is the CS Club's Discord bot, created by the CS Club Open Source Team.",
            )
        )
        for i, command in enumerate(self.group_commands):
            label = f"{command.name}"
            options.append(
                SelectOption(
                    label=label, value=str(i + 1), description=command.description
                )
            )
        options.append(
            SelectOption(
                label="Miscellaneous Commands",
                value=self.maxpages,
                description="These are commands that are not part of any group.",
            )
        )
        for item in self.children:
            if isinstance(item, ui.Select):
                item.options = options

    def capfirst(self, string):
        """Capitalize the first letter of string argument"""
        newstring = string[0].upper() + string[1:].lower()
        return newstring

    # Buttons change currentpage to corresponding value

    @ui.button(label="Start", style=ButtonStyle.primary)
    async def menu_start(self, interaction: Interaction, button: ui.Button):
        """Start menu button"""
        self.currentpage = 0
        embed = self.create_help_embed(self.currentpage)
        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="Back", style=ButtonStyle.primary)
    async def menu_back(self, interaction: Interaction, button: ui.Button):
        """Back button"""
        self.currentpage -= 1
        embed = self.create_help_embed(self.currentpage)
        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="Next", style=ButtonStyle.primary)
    async def menu_next(self, interaction: Interaction, button: ui.Button):
        """Next button"""
        self.currentpage += 1
        embed = self.create_help_embed(self.currentpage)
        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="End", style=ButtonStyle.primary)
    async def menu_end(self, interaction: Interaction, button: ui.Button):
        """End menu button"""
        self.currentpage = self.maxpages
        embed = self.create_help_embed(self.currentpage)
        await interaction.response.edit_message(embed=embed, view=self)

    # Select menu changes menu to selected
    @ui.select(
        placeholder="Select a command or group...",
        min_values=1,
        max_values=1,
        options=[],
    )
    async def help_select_callback(self, interaction: Interaction, select: ui.Select):
        """Get the selected index and update the current page"""
        selected_index = int(select.values[0])
        self.currentpage = selected_index

        embed = self.create_help_embed(selected_index)
        await interaction.response.edit_message(embed=embed, view=self)
