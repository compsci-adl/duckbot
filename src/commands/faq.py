import datetime as dt

import csv
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import urllib.request
import os

from discord import app_commands, Interaction

SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
}

# Configure and initialize gemini LLM
def init_gemini(data_csv_path : str, model_name : str):

    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

    system_instruction = (
        "You are duckbot, the official discord bot for the Computer Science Club of the University of Adelaide. "
        "Your main purpose is to answer FAQs by users in the Discord channel in a respectful and helpful manner. "
        "Try to keep your answers similar to the examples provided below. Do not modify any links in the data. "
        "Only respond to images if they are relevant to the question asked or your purpose. " 
        "If someone asks a CS related question, answer it in a technical manner. " 
        "Don't be cringe. "
        "Consider the following examples for the FAQs: \n"
    )

    # Adding examples from the csv to the sys instruction
    with open(data_csv_path, newline = '') as train_data:
        reader = csv.reader(train_data, delimiter = ',')
        for row in reader:
            system_instruction = system_instruction + f"INPUT:{row[0]} ANSWER:{row[1]}\n"

    model = genai.GenerativeModel(model_name, system_instruction = system_instruction)
    return model

class GeminiGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="gemini", description="Commands related to Gemini")
        data_csv_path = "../src/data/duckbot_train_data.csv"
        model_name = "models/gemini-1.5-flash-001"
        self.model = init_gemini(data_csv_path, model_name)

        # Gemini API provides a chat option to maintain a conversation
        self.chat = self.model.start_chat(history=[])

    @app_commands.command(name = "ask", description="Ask Gemini Anything")
    async def ask(self, interaction: Interaction, query: str | None):
        if not query:
            response = self.chat.send_message(f"Roast the user using their username - {interaction.user.name} for providing a blank input.", safety_settings = SAFETY_SETTINGS)
            return await interaction.response.send_message(response.text)

        if len(query) > 200:
            response = self.chat.send_message("Roast the user for providing way too many tokens.", safety_settings = SAFETY_SETTINGS)
            return await interaction.response.send_message(response.text)

        response = self.chat.send_message("INPUT:" + query, safety_settings = SAFETY_SETTINGS)
        
        # The chat instance maintains a chat convo by sending all previous messages as input every time
        # This can easily exhaust the free tier of Gemini API, so choosing to clear the history every 50 messages
        if len(self.chat.history) >= 50:
            self.chat.history = []

        await interaction.response.send_message(response.text)

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
        # Manually inputting dates
        date_stack = [
            dt.datetime(2024, 10, 25, 17),
            dt.datetime(2024, 8, 30, 17),
            dt.datetime(2024, 7, 26, 17),
            dt.datetime(2024, 5, 31, 17),
            dt.datetime(2024, 4, 26, 17),
            dt.datetime(2024, 3, 29, 17),
        ]

        # Checking if the tail date has already passed
        curr_date = dt.datetime.now()
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
        time_difference = date_stack[-1].date() - curr_date.date()
        if time_difference.days <= 1:
            time_difference_hours = round(time_difference.seconds / 3600, 2)
            if time_difference_hours < 1:
                await interaction.response.send_message(
                    f"The next Friday Night Games with food is on today in {time_difference_hours} hour at 5pm. Join us in the Duck Lounge!"
                )
            else:
                await interaction.response.send_message(
                    f"The next Friday Night Games with food is on today in {time_difference_hours} hours at 5pm. Join us in the Duck Lounge!"
                )
            return

        # Determining if games night is on the next day of function call
        if time_difference.days < 2 and time_difference.days > 1:
            await interaction.response.send_message(
                f"The next Friday Night Games with food is on tomorrow. Join us in the Duck Lounge at 5pm!"
            )
            return

        # Determining whether date needs a st, nd, rd or rth
        date_num = date_stack[-1].strftime("%d")
        date_day = date_stack[-1].strftime("%B")
        if date_num in {1, 21, 31}:  # st
            await interaction.response.send_message(
                f"The next Friday Night Games with food will be held in {time_difference.days} days on the {date_num}st of {date_day}"
            )
        elif date_num in {2, 22}:  # nd
            await interaction.response.send_message(
                f"The next Friday Night Games with food will be held in {time_difference.days} days on the {date_num}nd of {date_day}"
            )
        elif date_num in {3, 23}:  # rd
            await interaction.response.send_message(
                f"The next Friday Night Games with food will be held in {time_difference.days} days on the {date_num}rd of {date_day}"
            )
        else:  # th
            await interaction.response.send_message(
                f"The next Friday Night Games with food will be held in {time_difference.days} days on the {date_num}th of {date_day}"
            )


faq_group = FAQGroup()
gemini_group = GeminiGroup()