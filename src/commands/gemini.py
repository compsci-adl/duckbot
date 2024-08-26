import csv
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import urllib.request
import re
import os
import glob
import os.path

SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
}


class GeminiBot:
    def __init__(self, model_name, data_csv_path, bot):
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

        # Might be a hacky way to pass the client object
        # It's only required to swap mentions with usernames
        self.bot = bot

        # Gemini API provides a chat option to maintain a conversation
        self.chat = self.model.start_chat(history=[])

    async def query(self, author, message=None, attachment=None):

        # No message or file
        if not message and not attachment:
            response = self.chat.send_message(
                f"Roast the user using their username - {author} for providing a blank input.",
                safety_settings=SAFETY_SETTINGS,
            )
            return response.text
            
        # Message too long
        if len(message) > 200:
            response = self.chat.send_message(
                "Roast the user for providing way too many tokens.",
                safety_settings=SAFETY_SETTINGS,
            )
            return response.text
        
        message = swap_mention_with_username(message, self.bot)

        # If a file is provided and is valid
        if attachment is not None and is_valid_ext(attachment):
            file_ref = await upload_or_return_file_ref(attachment)

            if file_ref:
                print("Received ref")
                # Prompt Gemini using the file and prompt provided
                response = self.chat.send_message(
                    ["INPUT:" + message, file_ref], safety_settings=SAFETY_SETTINGS
                )
                return response.text

        # If just text is provided or attachment provided but fails to upload
        response = self.chat.send_message(
            "INPUT:" + message, safety_settings=SAFETY_SETTINGS
        )

        # The chat instance maintains a chat convo by sending all previous messages as input every time
        # This can easily exhaust the free tier of Gemini API, so choosing to clear the history every 50 messages
        if len(self.chat.history) >= 50:
            self.chat.history = []
            delete_files()

        return response.text

    
async def upload_or_return_file_ref(attachment):
    """Uploads the image to the Google Gemini Project
    Stored for 48 hours by default"""

    try:
        # If image already exists
        print("Checking if file exists")
        if os.path.isfile(f"../src/temp/{attachment.filename}"):
            print("File does exist")
            file_ref = genai.get_file(name=attachment.filename)
            print("Fetching from google api")
        # Upload image and get ref
        else:
            print("Downloading to temp")
            print(attachment.url, attachment.filename)
            await attachment.save(f"temp/{attachment.filename}")
            print("Uploading to genai")
            file_ref = genai.upload_file(path=f"temp/{attachment.filename}", display_name=attachment.filename)
    except Exception:
        return None
    return  file_ref

def delete_files():
    """Delete all attachment files"""

    files = glob.glob('../temp/*')
    for file in files:
        os.remove(file)

        
        
def is_valid_ext(file):
    """Helper function to check if the file passed as input is valid
    Currently only supporting images"""

    valid_content_types = ['image/png', 'image/jpg', 'image/webp', 'image/heic', 'image/heif']
    if file.content_type in valid_content_types:
        return True
    return False

def swap_mention_with_username(message, bot):
    """Helper function to swap mentions in bot messages with their username"""

    if message is None:
        return
    
    mentions = re.findall(r'<@\d+>', message)
    for i in mentions:
        try:
            username = bot.get_user(i).name
        except Exception:
            username = "Unknown user"

        message.replace(f"<@{i}", f"@{username}")
    
    return message