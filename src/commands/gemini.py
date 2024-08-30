import csv
import urllib.request
import re
import os
from pathlib import Path
import glob
import os.path
from enum import Enum
import tempfile

from discord import Embed
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold, File

SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
}


# Error codes are implemented just to give the user an accurate error message
class Errors(Enum):
    FILE_UPLOAD_ERR = 0
    FILE_SIZE_ERR = 1
    FILE_TYPE_ERR = 2
    GEMINI_ERR = 3
    GEMINI_RESPONSE_TOO_LONG_ERR = 4


ERROR_MESSAGES = {
    Errors.FILE_UPLOAD_ERR: "There was an error uploading the file.",
    Errors.FILE_SIZE_ERR: "Unsupported file: File over 50MB.",
    Errors.FILE_TYPE_ERR: "Unsupported file: Duckbot only supports images and audio files at the moment.",
    Errors.GEMINI_ERR: "Gemini couldn't process the request.",
    Errors.GEMINI_RESPONSE_TOO_LONG_ERR: "The response was too long!",
}


class GeminiBot:
    def __init__(self, model_name, data_csv_path, bot, api_key):
        genai.configure(api_key=api_key)

        system_instruction = (
            "You are duckbot, the official discord bot for the Computer Science Club of the University of Adelaide. "
            "Your main purpose is to answer CS questions and FAQs by users in a respectful and helpful manner, but don't be too nice. "
            "Keep emojis to a minimum. "
            "Keep your answers less than 1024 characters and similar to the examples provided below. "
            "Do not modify any of the links below if you send it as a response. "
            # "Only respond to images if they are relevant to the question asked or your purpose. "
            "If someone asks a CS related question, answer it in a technical manner. "
            "Don't be cringe. "
            "Do not hallucinate. "
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

    def prompt_gemini(self, input_msg=None, attachment=None) -> (Embed, Errors):
        try:
            payload = []

            # Form the payload to Gemini API according to the inputs provided
            if input_msg:
                payload.append(f"INPUT:{input_msg} ANSWER:")
            if attachment:
                payload.append(attachment)

            response = self.chat.send_message(
                payload,
                safety_settings=SAFETY_SETTINGS,
            )
            if len(response.text) > 1024:
                return None, Errors.GEMINI_RESPONSE_TOO_LONG_ERR
        except Exception:
            return None, Errors.GEMINI_ERR

        response_embed = Embed(title="Ask Gemini", color=0x3333FF)

        response_embed.add_field(
            name="Input",
            value=input_msg if input_msg is not None else "Attachment",
            inline=False,
        )
        response_embed.add_field(name="Answer", value=response.text, inline=False)
        return response_embed, None

    async def query(self, author, message=None, attachment=None) -> list[Embed]:

        response_embeds = []
        response_image_url = None
        main_err = None

        # No message or file
        if not message and not attachment:
            response_embed = self.prompt_gemini(
                f"Roast the user using their username - {author} for providing a blank input."
            )
            return [response_embed]

        # Message too long
        if message is not None and len(message) > 200:
            response_embed = self.prompt_gemini(
                f"Roast the user using their username - {author} for providing way too many tokens."
            )
            return [response_embed]

        message = swap_mention_with_username(message, self.bot)
        attachment_ref = None

        # If a file is provided and is valid
        if attachment is not None:

            err = is_valid_ext_size(attachment)
            if err:
                main_err = err
            if err is None:
                # # Convert extension to lowercase (Gemini File API requires all lowercase characters)
                # attachment = transform_attachment(attachment)

                file_ref, err = await upload_or_return_file_ref(attachment)
                if file_ref:
                    attachment_ref = file_ref
                    response_image_url = attachment.url
                if err:
                    main_err = err

        # If only attachment was provided but did not upload successfully
        if message is None and err is not None:
            return [
                Embed(
                    title="Ask Gemini",
                    description="The attachment is invalid and no text input is provided.",
                    color=0xFF3333,
                )
            ]

        response_embed, err = self.prompt_gemini(
            input_msg=message, attachment=attachment_ref
        )

        # If response is none, it means something went wrong, so directly go to the error embed
        if response_embed is not None:

            # Only set the response_embed image if image is provided and
            if response_image_url is not None:
                response_embed.set_image(url=response_image_url)

            response_embeds.append(response_embed)

        # The last encountered error is used for the embed
        if err is not None:
            main_err = err

        if main_err:
            err_embed = Embed(
                title="NOTE", description=ERROR_MESSAGES[err], color=0xFF3333
            )
            response_embeds.append(err_embed)

        # The chat instance maintains a chat convo by sending all previous messages as input every time
        # This can easily exhaust the free tier of Gemini API, so choosing to clear the history every 50 messages
        if len(self.chat.history) >= 50:
            self.chat.history = []
            delete_files()

        return response_embeds


async def upload_or_return_file_ref(attachment) -> (File, Errors):
    """Uploads the image to the Google Gemini Project
    Stored for 48 hours by default"""

    file_name = os.path.splitext(attachment.filename)[0]

    # Path("src/temp").mkdir(exist_ok=True)

    try:
        # If image is already uploaded to
        file_ref = return_genai_file_ref(file_name)

        if file_ref:
            return file_ref, None

        # # If file exists in the server but not uploaded to Gemini
        # elif os.path.isfile(f"src/temp/{attachment.filename}"):
        #     file_ref = genai.upload_file(
        #         path=f"src/temp/{attachment.filename}", display_name=file_name
        #     )
        #     return file_ref, None

        # If new image
        else:
            with tempfile.TemporaryDirectory() as temp:

                await attachment.save(f"{temp}/{attachment.filename}")

                file_ref = genai.upload_file(
                    path=f"{temp}/{attachment.filename}", display_name=file_name
                )

            return file_ref, None

    except Exception as e:
        return None, Errors.FILE_UPLOAD_ERR


def return_genai_file_ref(file_name):
    files_list = genai.list_files()

    for file in files_list:

        if file.display_name == file_name:
            return file

    return None


def delete_files():
    """Delete all attachment files"""

    for file in genai.list_files():

        genai.delete_file(file.name)


def is_valid_ext_size(file) -> Errors:
    """Helper function to check if the file passed as input has a valid content type and acceptable size
    Currently only supporting images and audio"""

    valid_content_types = [
        "image/png",
        "image/jpeg",
        "image/webp",
        "image/heic",
        "image/heif",
        "audio/wav",
        "audio/mp3",
        "audio/aiff",
        "audio/aac",
        "audio/ogg",
        "audio/flac",
    ]

    # File too large
    if (file.is_voice_message() and file.duration() > 300) or file.size > 3e7:
        return Errors.FILE_SIZE_ERR

    if file.content_type not in valid_content_types:
        return Errors.FILE_TYPE_ERR

    return None


def swap_mention_with_username(message, bot):
    """Helper function to swap mentions in bot messages with their username"""

    if message is None:
        return
    message = message.replace("=duck", "")
    mentions = re.findall(r"<@\d+>", message)
    for i in mentions:
        try:
            username = bot.get_user(i).name
        except Exception:
            username = "Unknown user"

        message.replace(f"<@{i}", f"@{username}")

    return message


# def transform_attachment(attachment):
#     """Converts attachment to lowercase and handles special characters"""

#     attachment.filename = attachment.filename.lower()
#     attachment.filename = re.sub('[^a-z0-9. \n]', '-', attachment.filename)

#     return attachment
