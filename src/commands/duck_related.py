import random
from typing import Optional

import aiohttp
from discord import Embed, Interaction, app_commands

from constants.duck_data import DUCK_FACTS, DUCK_JOKES
from utils.tenor import get_tenor_gif

DUCK_PIC_API_URL = (
    "https://random-d.uk/api/v2/random?type=jpg"  # Duck picture API by random-d.uk
)


class DuckCommands(app_commands.Group):
    def __init__(self):
        super().__init__(name="duck", description="Fun duck-related commands")

    async def get_duck_image(self) -> Optional[str]:
        """Fetch a random duck image from the random-d.uk API."""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(DUCK_PIC_API_URL) as response:
                    if response.status != 200:
                        print(f"Error fetching image: {response.status}")
                        return None
                    data = await response.json()
                    # Extract and return the URL of the image
                    return data.get("url")
            except Exception as e:
                print(f"Error fetching image: {str(e)}")
                return None

    @app_commands.command(name="gif", description="Sends a random duck gif")
    async def duck_gif(self, interaction: Interaction):
        """Send a random duck GIF."""
        await interaction.response.defer()
        search_term = "duck"
        gif_url = await get_tenor_gif(search_term)
        if gif_url:
            # Create an embed with the GIF
            embed = Embed(title="Here's a random duck gif!")
            embed.set_image(url=gif_url)
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(
                "Sorry, I couldn't fetch a duck GIF right now."
            )

    @app_commands.command(name="pic", description="Sends a random duck picture")
    async def duck_pic(self, interaction: Interaction):
        """Send a random duck picture."""
        pic_url = await self.get_duck_image()
        if pic_url:
            # Create an embed with the picture
            embed = Embed(title="Here's a random duck picture!")
            embed.set_image(url=pic_url)
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(
                "Sorry, I couldn't fetch a duck picture right now."
            )

    @app_commands.command(name="fact", description="Sends a random duck fact")
    async def duck_fact(self, interaction: Interaction):
        """Send a random duck fact from the predefined list."""
        fact = random.choice(DUCK_FACTS)
        await interaction.response.send_message(f"{fact}")

    @app_commands.command(name="joke", description="Tells a duck-related joke")
    async def duck_joke(self, interaction: Interaction):
        """Tell a random duck-related joke from the predefined list."""
        joke = random.choice(DUCK_JOKES)
        await interaction.response.send_message(f"{joke}")


duck_commands = DuckCommands()
