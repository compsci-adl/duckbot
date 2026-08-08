import os
import random
from typing import Optional

import aiohttp
from dotenv import load_dotenv

load_dotenv()

KLIPY_API_KEY = os.getenv("KLIPY_API_KEY")


async def get_klipy_gif(search_term: str) -> Optional[str]:
    """Fetch a random GIF from Klipy API."""
    url = f"https://api.klipy.com/api/v1/{KLIPY_API_KEY}/gifs/search"
    async with aiohttp.ClientSession() as session:
        params = {
            "q": search_term,
            "per_page": 30,
            "content_filter": "high",
        }
        try:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    print(f"Error fetching GIF: {response.status}")
                    return None
                data = await response.json()
                results = data.get("data", {}).get("data", [])
                if not results:
                    return None
                result = random.choice(results)
                return result.get("file", {}).get("hd", {}).get("gif", {}).get("url")
        except Exception as e:
            print(f"Error fetching GIF: {str(e)}")
            return None
