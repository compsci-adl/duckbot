import csv
import urllib.request
import re
import os
from pathlib import Path
import glob
import os.path
from enum import IntEnum
import tempfile
import logging

from constants.colours import LIGHT_YELLOW
from discord import Embed
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold, File

SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
}


# Error codes are implemented just to give the user an accurate error message
class Errors(IntEnum):
    FILE_UPLOAD_ERR = 0
    FILE_SIZE_ERR = 1
    FILE_TYPE_ERR = 2
    GEMINI_ERR = 3
    GEMINI_RESPONSE_TOO_LONG_ERR = 4
    GEMINI_PERMISSION_DENIED = 403
    GEMINI_NOT_FOUND = 404
    GEMINI_RESOURCE_EXHAUSTED = 429
    GEMINI_INTERNAL = 500
    GEMINI_UNAVAILABLE = 503
    GEMINI_DEADLINE_EXCEEDED = 504


ERROR_MESSAGES = {
    Errors.FILE_UPLOAD_ERR: "There was an error uploading the file.",
    Errors.FILE_SIZE_ERR: "Unsupported file: File over 50MB.",
    Errors.FILE_TYPE_ERR: "Unsupported file: Duckbot only supports images and audio files at the moment.",
    Errors.GEMINI_ERR: "Gemini couldn't process the request.",
    Errors.GEMINI_RESPONSE_TOO_LONG_ERR: "The response was too long!",
    Errors.GEMINI_PERMISSION_DENIED: "The Gemini API key does not have the required permissions to perform this action!",
    Errors.GEMINI_NOT_FOUND: "There was a problem fetching the requested resource (media file) from Gemini API.",
    Errors.GEMINI_RESOURCE_EXHAUSTED: "Gemini's free tier rate limit has been exceeded. Take a break!",
    Errors.GEMINI_INTERNAL: "Gemini ran into an error processing your query! Try shortening your query.",
    Errors.GEMINI_UNAVAILABLE: "Gemini is temporarily unavailable. Please try again in a while.",
    Errors.GEMINI_DEADLINE_EXCEEDED: "Gemini was unable to process a response as the query was too large. Please shorten your query and try again.",
}


class GeminiBot:
    def __init__(self, model_name, data_csv_path, bot, api_key):
        genai.configure(api_key=api_key)

        system_instruction = (
            "You are DuckBot, the official discord bot for the Computer Science Club of the University of Adelaide. "
            "Your main purpose is to answer CS questions and FAQs by users. "
            "However, you're allowed to roast other users. "
            "Keep emojis to a minimum. "
            "Keep your answers less than 1024 characters and similar to the examples provided below. "
            "Do not modify any of the links below if you send it as a response. "
            "If someone asks a CS related question, answer it in a technical manner. "
            "Don't be cringe. "
            "Do not hallucinate. "
            "If you do not know the answer to something, inform the user that the answer you provide might not be correct. "
            "Consider the following examples for the FAQs: \n"
        )

        # Adding examples from the csv to the sys instruction
        with open(data_csv_path, newline="") as train_data:
            reader = csv.reader(train_data, delimiter=",")
            for row in reader:
                system_instruction = (
                    system_instruction + f"INPUT:{row[0]} ANSWER:{row[1]}\n"
                )

        try:
            self.model = genai.GenerativeModel(
                model_name, system_instruction=system_instruction
            )
        except Exception as e:
            logging.exception(
                f"GEMINI: Error encountered initiating Gemini: {e}. Initiating gemini-1.5-flash as the default model instead. "
            )
            self.model = genai.GenerativeModel(
                "models/gemini-1.5-flash", system_instruction=system_instruction
            )

        # Might be a hacky way to pass the client object
        # It's only required to swap mentions with usernames
        self.bot = bot

        # Gemini API provides a chat option to maintain a conversation
        self.chat = self.model.start_chat(history=[])

    async def prompt_gemini(
        self, author, input_msg=None, attachment=None, show_input=True
    ) -> (Embed, Errors):
        try:
            payload = []

            # Form the payload to Gemini API according to the inputs provided
            if input_msg:
                payload.append(f"INPUT:{input_msg} ANSWER:")
            if attachment:
                payload.append(attachment)

            response = await self.chat.send_message_async(
                payload,
                safety_settings=SAFETY_SETTINGS,
            )

            if len(response.text) > 1024:
                logging.error(
                    f"GEMINI: {author} encountered an error processing the response: {ERROR_MESSAGES[Errors.GEMINI_RESPONSE_TOO_LONG_ERR]}"
                )
                return None, Errors.GEMINI_RESPONSE_TOO_LONG_ERR
        except Exception as e:
            logging.exception(
                f"GEMINI: {author} encountered an error prompting Gemini: {e}"
            )

            # Google Core API Errors have the code attribute that denotes the HTTP code
            if hasattr(e, "code") and e.code in Errors:
                return None, Errors(e.code)

            # If unrecognised error
            return None, Errors.GEMINI_ERR

        response_embed = Embed(title="Ask Gemini", color=LIGHT_YELLOW)

        if show_input:

            response_embed.add_field(
                name="Input",
                value=input_msg if input_msg is not None else "Attachment",
                inline=False,
            )
        response_embed.add_field(
            name="Answer",
            value=response.text,
            inline=False,
        )
        return response_embed, None

    async def query(self, author, message=None, attachment=None) -> list[Embed]:

        response_embeds = []
        response_image_url = None
        errors = []

        # No message or file
        if not message and not attachment:
            logging.error(f"GEMINI: {author} provided blank input to Gemini!")
            response_embed, err = await self.prompt_gemini(
                author=author,
                input_msg=f"Roast the user using their username - {author} for providing no input.",
                show_input=False,
            )
            if err is not None:
                return [get_error_embed([err])]
            return [response_embed]

        # Message too long
        if message is not None and len(message) > 200:
            logging.error(
                f"GEMINI: {author} provided {len(message)} tokens to Gemini, which exceeds the limit."
            )
            response_embed, err = await self.prompt_gemini(
                author=author,
                input_msg=f"Roast the user using their username - {author} for providing way too many tokens.",
                show_input=False,
            )
            if err is not None:
                return [get_error_embed([err])]
            return [response_embed]

        message = swap_mention_with_username(message, self.bot)
        attachment_ref = None

        # If a file is provided and is valid
        if attachment is not None:

            err = is_valid_ext_size(author, attachment)
            if err:
                errors.append(err)
            if err is None:
                file_ref, err = await upload_or_return_file_ref(attachment)
                if file_ref:
                    attachment_ref = file_ref
                    response_image_url = attachment.url
                if err:
                    logging.error(
                        f"GEMINI: {author} encountered an error uploading an attachment to Gemini: {ERROR_MESSAGES[err]}"
                    )
                    errors.append(err)

        # If only attachment was provided but did not upload successfully
        if message is None and len(errors) != 0:
            logging.error(
                f"GEMINI: {author} passed an empty query and uploaded an invalid attachment to Gemini."
            )
            return [
                Embed(
                    title="Ask Gemini",
                    description="The attachment is invalid and no text input is provided.",
                    color=LIGHT_YELLOW,
                )
            ]

        response_embed, err = await self.prompt_gemini(
            author=author, input_msg=message, attachment=attachment_ref
        )

        # If response is none, it means something went wrong, so directly go to the error embed
        if response_embed is not None:

            # Only set the response_embed image if image is provided and
            if response_image_url is not None:
                response_embed.set_image(url=response_image_url)

            response_embeds.append(response_embed)

        # The last encountered error is used for the embed
        if err is not None:
            errors.append(err)

        if len(errors) != 0:
            err_embed = get_error_embed(errors)
            response_embeds.append(err_embed)

        # The chat instance maintains a chat convo by sending all previous messages as input every time
        # This can easily exhaust the free tier of Gemini API, so choosing to clear the history every 50 messages
        if len(self.chat.history) >= 50:
            self.chat.history([])
            delete_files()

        return response_embeds


async def upload_or_return_file_ref(attachment) -> (File, Errors):
    """Uploads the image to the Google Gemini Project
    Stored for 48 hours by default"""

    file_name = os.path.splitext(attachment.filename)[0]

    try:
        # If image is already uploaded to
        file_ref = return_genai_file_ref(file_name)

        if file_ref:
            return file_ref, None

        # If new image
        else:
            with tempfile.TemporaryDirectory() as temp:

                await attachment.save(f"{temp}/{attachment.filename}")

                file_ref = genai.upload_file(
                    path=f"{temp}/{attachment.filename}", display_name=file_name
                )

            return file_ref, None

    except Exception as e:
        if hasattr(e, "code") and e.code in Errors:
            return None, Errors(e.code)
        return None, Errors.FILE_UPLOAD_ERR


def return_genai_file_ref(file_name):
    """
    Returns a File object from the Gemini API if the user provided file has been uploaded before.
    Returns None otherwise.
    """
    files_list = genai.list_files()

    for file in files_list:

        if file.display_name == file_name:
            return file

    return None


def delete_files():
    """Delete all attachment files"""

    for file in genai.list_files():

        genai.delete_file(file.name)


def is_valid_ext_size(author, file) -> Errors:
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
        logging.error(
            f"GEMINI: {author} uploaded an attachment that was too large for Gemini."
        )
        return Errors.FILE_SIZE_ERR

    if file.content_type not in valid_content_types:
        logging.error(
            f"GEMINI: {author} uploaded an attachment with an invalid content type: {file.content_type}"
        )
        return Errors.FILE_TYPE_ERR

    return None


def swap_mention_with_username(message, bot):
    """Helper function to swap mentions in bot messages with their username"""

    if message is None:
        return
    mentions = re.findall(r"<@\d+>", message)
    for i in mentions:
        user_id = int(i[2:-1])
        try:
            username = bot.get_user(user_id).name
        except Exception:
            username = "Unknown user"

        message = message.replace(i, f"@{username}")

    return message


def get_error_embed(errors):
    """
    Takes a list of Errors as input and creates an Embed containing error names and messages as subfields.
    """

    err_embed = Embed(
        title="NOTE",
        description="There were a bunch of errors!",
        color=LIGHT_YELLOW,
    )

    # Subfield for all errors faced
    for err in errors:
        err_embed.add_field(name=ERROR_MESSAGES[err], value="", inline=False)

    return err_embed
