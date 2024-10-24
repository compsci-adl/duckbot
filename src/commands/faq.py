import datetime as dt
import pytz
from math import floor, ceil
from discord import app_commands, Interaction, File


class FAQGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="faq", description="Answers to common questions")
        self.add_command(FNGGroup())

    @app_commands.command(name="rsp", description="Learn about RSP")
    async def rsp(self, interaction: Interaction):
        rsp_info = (
            "Participating in RSP (Ravi's Study Program) could possibly be the single most beneficial thing you can do while you're at University to land a job as a Software Engineer at a great company.\n\n"
            "The program is run by current and former students and tutors from The University of Adelaide, and provides students with the exact steps they need to take to prepare themselves to pass interviews at big tech/FAANG companies. There are very impressive numbers of people that land internships at these companies after successfully completing the program.\n\n"
            "RSP is an intensive programming bootcamp run each summer break. If you wish to get involved, keep an eye out for flyers on campus towards the end of Semester 2, as well as advertisements that are posted in various computer science related discord servers.\n"
        )
        await interaction.response.send_message(rsp_info)

    @app_commands.command(name="cpc", description="Learn about CPC")
    async def cpc(self, interaction: Interaction):
        cpc_info = (
            "The Competitive Programming Club (CPC) is the University of Adelaide's home for competitive programming. Whether you're just getting started, or looking to flex those programming muscles, the CPC offers a wide range of events and opportunities for those interested.\n\n"
            "There's no cost for registration and you can find out more here:\n"
            "https://acpc.io/\n"
        )
        await interaction.response.send_message(cpc_info)

    @app_commands.command(name="drive", description="Access CS Club Drive")
    async def drive(self, interaction: Interaction):
        drive_info = "Access the CS Club Drive through your CS Club account here:\n"
        drive_image = File("assets/drive.png")
        await interaction.response.send_message(drive_info, file=drive_image)


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
            "Friday Night Games (FNG) is a regular Computer Science Club event where the Duck Lounge (Located in EM110) hosts a weekly games night from 5PM where members commonly play amongst a Nintendo Switch and board games.\n"
            "Moreover, on the final Friday of each month within semester, we have free food for all members! Type ``/faq fng food`` to find out when the next FNG with food will be.\n\n"
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
            tz.localize(dt.datetime(2024, 10, 25, 17)),
            tz.localize(dt.datetime(2024, 8, 30, 17)),
            tz.localize(dt.datetime(2024, 7, 26, 17)),
            tz.localize(dt.datetime(2024, 5, 31, 17)),
            tz.localize(dt.datetime(2024, 4, 26, 17)),
            tz.localize(dt.datetime(2024, 3, 29, 17)),
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


faq_group = FAQGroup()
