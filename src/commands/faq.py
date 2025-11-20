import datetime as dt
from math import ceil, floor

import pytz
from discord import ButtonStyle, Embed, File, Interaction, app_commands, ui

from constants.colours import LIGHT_YELLOW
from utils import cms, cms_helpers


class FAQGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="faq", description="Answers to common questions")
        self.add_command(FNGGroup())
        self.add_command(EventsGroup())

    @app_commands.command(name="rsp", description="Learn about RSP")
    async def rsp(self, interaction: Interaction):
        rsp_info = (
            "Participating in RSP (Ravi's Study Program) could possibly be the single most beneficial thing you can do while you're at University to land a job as a Software Engineer at a great company.\n\n"
            "The program is run by current and former students and tutors from Adelaide University, and provides students with the exact steps they need to take to prepare themselves to pass interviews at big tech/FAANG companies. There are very impressive numbers of people that land internships at these companies after successfully completing the program.\n\n"
            "RSP is an intensive programming bootcamp run each summer break. If you wish to get involved, keep an eye out for flyers on campus towards the end of Semester 2, as well as advertisements that are posted in various computer science related discord servers.\n"
        )
        await interaction.response.send_message(rsp_info)

    @app_commands.command(name="cpc", description="Learn about CPC")
    async def cpc(self, interaction: Interaction):
        cpc_info = (
            "The Competitive Programming Club (CPC) is Adelaide University's home for competitive programming. Whether you're just getting started, or looking to flex those programming muscles, the CPC offers a wide range of events and opportunities for those interested.\n\n"
            "There's no cost for registration and you can find out more here:\n"
            "https://acpc.io/\n"
        )
        await interaction.response.send_message(cpc_info)

    @app_commands.command(name="drive", description="Access CS Club Drive")
    async def drive(self, interaction: Interaction):
        drive_info = "Access the CS Club Drive through your CS Club account at https://csclub.org.au/\n"
        drive_image = File("assets/drive.png")
        await interaction.response.send_message(drive_info, file=drive_image)

    @app_commands.command(
        name="committee", description="List the CS Club committee members"
    )
    async def committee(self, interaction: Interaction):
        try:
            await interaction.response.defer()
            limit_value = 100  # Get all members
            members = cms.get_committee_members(limit=limit_value)
            if not members:
                await interaction.followup.send("No committee members found.")
                return

            chunk_size = 20
            embeds = []

            for i in range(0, len(members), chunk_size):
                chunk = members[i : i + chunk_size]
                embed_title = "CS Club Committee"
                if len(members) > chunk_size:
                    page_num = (i // chunk_size) + 1
                    total_pages = (len(members) + chunk_size - 1) // chunk_size
                    embed_title += f" (Page {page_num}/{total_pages})"

                embed = Embed(title=embed_title, color=LIGHT_YELLOW)
                for m in chunk:
                    name = m.get("name", "Unknown")
                    role = m.get("role", "")
                    embed.add_field(name=name, value=role, inline=False)
                embeds.append(embed)

            # Send all embeds
            await interaction.followup.send(embeds=embeds)
        except Exception:
            await interaction.followup.send(
                "There was an error fetching committee members."
            )

    @app_commands.command(
        name="projects", description="List current open-source projects"
    )
    async def projects(self, interaction: Interaction):
        try:
            await interaction.response.defer()
            limit_value = 100
            projects = cms.get_projects(limit=limit_value)
            if not projects:
                await interaction.followup.send("No projects found.")
                return
            embed = Embed(title="Open-source Projects", color=LIGHT_YELLOW)
            for p in projects:
                title = p.get("title", "Untitled")
                desc = p.get("description", "").strip()
                embed.add_field(name=title, value=desc, inline=False)
            await interaction.followup.send(embed=embed)
        except Exception:
            await interaction.followup.send("There was an error fetching projects.")

    @app_commands.command(name="sponsors", description="List sponsors")
    async def sponsors(self, interaction: Interaction):
        try:
            await interaction.response.defer()
            limit_value = 100
            sponsors = cms.get_sponsors(limit=limit_value)
            if not sponsors:
                await interaction.followup.send("No sponsors found.")
                return
            embed = Embed(title="CS Club Sponsors", color=LIGHT_YELLOW)
            groups = cms_helpers.group_and_sort_sponsors(sponsors)
            order = ["gold", "silver", "bronze", "other"]
            for tier in order:
                items = groups.get(tier, [])
                if not items:
                    continue
                title = tier.capitalize()
                embed.add_field(name=f"{title}", value="\n".join(items), inline=False)
            await interaction.followup.send(embed=embed)
        except Exception:
            await interaction.followup.send("There was an error fetching sponsors.")


class FNGGroup(app_commands.Group):
    def __init__(self):
        super().__init__(
            name="fng",
            description="Learn about FNG",
        )

    @app_commands.command(
        name="about", description="Provides information about Friday Night Games (FNG)"
    )
    async def about(self, interaction: Interaction):
        fng_info = (
            "Friday Night Games (FNG) is a regular Computer Science Club event where the Duck Lounge (Located in EM110) hosts a weekly games night from 5PM where members commonly play amongst a Nintendo Switch 2 and board games.\n"
            "Moreover, on certain Fridays within the semester, we have free food for all members! Type ``/faq fng food`` to find out when the next FNG with food will be.\n\n"
            "Join us for games and fun!\n"
        )
        await interaction.response.send_message(fng_info)

    @app_commands.command(
        name="food",
        description="Outputs the date of the next Friday Night Games with food",
    )
    async def food(self, interaction: Interaction):
        tz = pytz.timezone("Australia/Adelaide")
        # Manually inputting dates
        date_stack = [
            tz.localize(dt.datetime(2025, 10, 24, 17)),
            tz.localize(dt.datetime(2025, 10, 10, 17)),
            tz.localize(dt.datetime(2025, 9, 19, 17)),
            tz.localize(dt.datetime(2025, 8, 22, 17)),
            tz.localize(dt.datetime(2025, 5, 30, 17)),
            tz.localize(dt.datetime(2025, 3, 28, 17)),
        ]

        # Checking if the tail date has already passed
        curr_date = dt.datetime.now(tz)
        if curr_date > date_stack[-1]:
            while (
                len(date_stack) > 0 and curr_date > date_stack[-1]
            ):  # length check was added to prevent access of first element when list was empty - this would cause a compiler error
                date_stack.pop()

        # Printing next time for Games Night
        if len(date_stack) == 0:
            await interaction.response.send_message(
                "The next Friday Night Games with food will be next year. Thank you for being a valued member!"
            )
            return
        # Determining if games night is on the same day as day of function call
        time_difference = date_stack[-1] - curr_date
        if date_stack[-1].date() == curr_date.date():
            time_difference_hours = floor(time_difference.seconds / 3600)
            time_difference_minutes = ceil((time_difference.seconds % 3600) / 60)
            message = ""
            # Handle hours
            if time_difference_hours == 1:
                message += f"The next Friday Night Games with food is on today in {time_difference_hours} hour "
            else:
                message += f"The next Friday Night Games with food is on today in {time_difference_hours} hours "
            # Handle minutes
            if time_difference_minutes == 1:
                message += f"and {time_difference_minutes} minute at 5pm. Join us in the Duck Lounge!"
            else:
                message += f"and {time_difference_minutes} minutes at 5pm. Join us in the Duck Lounge!"
            await interaction.response.send_message(message)
            return

        # Determining if games night is on the next day of function call
        if date_stack[-1].date() == (curr_date + dt.timedelta(days=1)).date():
            await interaction.response.send_message(
                "The next Friday Night Games with food is on tomorrow. Join us in the Duck Lounge at 5pm!"
            )
            return

        # Determining whether date needs a st, nd, rd or rth
        date_num = date_stack[-1].strftime("%d")
        # Removing zero padding if present
        if date_num[0] == "0":
            date_num = date_num[1:]
        date_day = date_stack[-1].strftime("%B")
        time_difference_days = time_difference.days
        if curr_date.time().hour >= 17:
            time_difference_days += (
                1  # This allows for a more intuitive display of the difference in days
            )
        message = f"The next Friday Night Games with food will be held in {time_difference.days} days on the {date_num}"
        if date_num in {1, 21, 31}:
            message += "st "
        elif date_num in {2, 22}:
            message += "nd "
        elif date_num in {3, 23}:
            message += "rd "
        else:
            message += "th "
        message += f"of {date_day}"
        await interaction.response.send_message(message)
        return


class EventsGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="events", description="Learn about CS Club events")

    @app_commands.command(name="upcoming", description="List upcoming events")
    async def upcoming(self, interaction: Interaction):
        try:
            await interaction.response.defer()
            # Use UI-based pagination (default page size)
            view = EventsListView(kind="upcoming")
            # Pre-fetch initial embed to populate buttons
            try:
                embed, total = await view._fetch_and_build(view.page)
                view.total_pages = total
                await view._update_buttons()
            except Exception:
                embed = Embed(title="Upcoming CS Club Events", color=LIGHT_YELLOW)
            # Use the embed pre-built by the view
            if not hasattr(embed, "fields") or len(embed.fields) == 0:
                await interaction.followup.send("No upcoming events found.")
                return
            await interaction.followup.send(embed=embed, view=view)
        except Exception:
            await interaction.followup.send(
                "There was an error fetching upcoming events."
            )

    @app_commands.command(name="past", description="List past events")
    async def past(self, interaction: Interaction, year: int | None = None):
        try:
            await interaction.response.defer()
            year_value = None if year is None else int(year)
            # Use UI-based pagination view for past events
            view = EventsListView(kind="past", year=year_value)
            try:
                embed, total = await view._fetch_and_build(view.page)
                view.total_pages = total
                await view._update_buttons()
            except Exception:
                embed = Embed(title="Past CS Club Events", color=LIGHT_YELLOW)
            # Use the embed pre-built by the view
            if not hasattr(embed, "fields") or len(embed.fields) == 0:
                await interaction.followup.send("No past events found.")
                return
            # Send embed with interactive pagination view
            await interaction.followup.send(embed=embed, view=view)
        except Exception:
            await interaction.followup.send("There was an error fetching past events.")


class EventsListView(ui.View):
    """View with Previous/Next buttons to paginate events.

    Supports 'upcoming' and 'past' kinds with optional year filtering for past.
    """

    def __init__(
        self,
        kind: str = "upcoming",
        limit: int = 5,
        page: int = 1,
        year: int | None = None,
    ):
        super().__init__(timeout=300)
        self.kind = kind
        self.limit = limit
        self.page = page
        self.year = year
        self.total_pages = 1

    async def _fetch_and_build(self, page: int) -> tuple[Embed, int]:
        if self.kind == "past":
            result = cms.get_past_events(limit=self.limit, page=page, year=self.year)
        else:
            result = cms.get_upcoming_events_page(limit=self.limit, page=page)
        docs = result.get("docs", [])
        page_num = result.get("page", 1)
        total_pages = result.get("totalPages", 1)
        title = (
            "Past CS Club Events" if self.kind == "past" else "Upcoming CS Club Events"
        )
        embed = Embed(title=title, color=LIGHT_YELLOW)
        for ev in docs:
            time_info = ev.get("time") or {}
            start = time_info.get("start") or ev.get("date") or ""
            end = time_info.get("end") or ""
            timestr = (
                cms.fmt_time_range_friendly(start, end, ev.get("date"))
                or "Unknown date"
            )
            title = ev.get("title", "Untitled")
            location = (ev.get("location") or "").strip()
            details = (
                (ev.get("details") or ev.get("description") or "")
                .replace("\n", " ")
                .strip()
            )
            if len(details) > 700:
                details = details[:697] + "..."
            link = ev.get("link") or {}
            link_text = ""
            if isinstance(link, dict):
                link_text = (
                    link.get("displayText") or link.get("Link") or link.get("url") or ""
                )
            elif isinstance(link, str):
                link_text = link
            parts = [timestr]
            if location:
                parts.append(location)
            if details:
                parts.append(details)
            if link_text:
                parts.append(link_text)
            value = "\n\n".join(parts)
            if len(value) > 1000:
                value = value[:997] + "..."
            embed.add_field(name=title, value=value, inline=False)
        embed.set_footer(text=f"Page {page_num} of {total_pages}")
        return embed, total_pages

    async def _update_buttons(self):
        for child in self.children:
            if isinstance(child, ui.Button):
                if child.custom_id == "events_prev":
                    child.disabled = self.page <= 1
                elif child.custom_id == "events_next":
                    child.disabled = self.page >= self.total_pages

    @ui.button(label="Previous", style=ButtonStyle.primary, custom_id="events_prev")
    async def prev(self, interaction: Interaction, button: ui.Button):
        if self.page <= 1:
            return
        self.page -= 1
        embed, total = await self._fetch_and_build(self.page)
        self.total_pages = total
        await self._update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="Next", style=ButtonStyle.primary, custom_id="events_next")
    async def next(self, interaction: Interaction, button: ui.Button):
        if self.page >= self.total_pages:
            return
        self.page += 1
        embed, total = await self._fetch_and_build(self.page)
        self.total_pages = total
        await self._update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)


faq_group = FAQGroup()
events_group = EventsGroup()
