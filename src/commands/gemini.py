import csv
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import urllib.request
import os

SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
}


class GeminiBot:
    def __init__(self, model_name, data_csv_path):
        genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

        system_instruction = (
            "You are duckbot, the official discord bot for the Computer Science Club of the University of Adelaide. "
            "Your main purpose is to answer CS questions and FAQs by users in a respectful and helpful manner, but don't be too nice. "
            "Keep emojis to a minimum. "
            "Try to keep your answers similar to the examples provided below. "
            "Do not modify any of the links below if you send it as a response. "
            "Only respond to images if they are relevant to the question asked or your purpose. "
            "If someone asks a CS related question, answer it in a technical manner. "
            "Don't be cringe. "
            "Consider the following examples for the FAQs: \n"
        )

        # Adding examples from the csv to the sys instruction
        with open(data_csv_path, newline="") as train_data:
            reader = csv.reader(train_data, delimiter=",")
            for row in reader:
                system_instruction = (
                    system_instruction + f"INPUT:{row[0]} ANSWER:{row[1]}\n"
                )

        self.model = genai.GenerativeModel(
            model_name, system_instruction=system_instruction
        )

        # Gemini API provides a chat option to maintain a conversation
        self.chat = self.model.start_chat(history=[])

    def query(self, message, author):

        if not message:
            response = self.chat.send_message(
                f"Roast the user using their username - {author} for providing a blank input.",
                safety_settings=SAFETY_SETTINGS,
            )
            return response.text

        if len(message) > 200:
            response = self.chat.send_message(
                "Roast the user for providing way too many tokens.",
                safety_settings=SAFETY_SETTINGS,
            )
            return response.text

        response = self.chat.send_message(
            "INPUT:" + message, safety_settings=SAFETY_SETTINGS
        )

        # The chat instance maintains a chat convo by sending all previous messages as input every time
        # This can easily exhaust the free tier of Gemini API, so choosing to clear the history every 50 messages
        if len(self.chat.history) >= 50:
            self.chat.history = []

        return response.text
