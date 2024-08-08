import os
import random
from typing import Optional

import aiohttp
from dotenv import load_dotenv

load_dotenv()

TENOR_API_KEY = os.getenv("TENOR_API_KEY")
TENOR_API_URL = "https://g.tenor.com/v2/search"


async def get_tenor_gif(search_term: str) -> Optional[str]:
    """Fetch a random GIF from Tenor API."""
    async with aiohttp.ClientSession() as session:
        params = {
            "q": search_term,
            "key": TENOR_API_KEY,
            "limit": 30,
            "contentfilter": "high",
            "media_filter": "minimal",
            "ar_range": "standard",
        }
        try:
            async with session.get(TENOR_API_URL, params=params) as response:
                if response.status != 200:
                    print(f"Error fetching GIF: {response.status}")
                    return None
                data = await response.json()
                results = data.get("results", [])
                if not results:
                    return None
                result = random.choice(results)
                return result.get("media_formats", {}).get("gif", {}).get("url")
        except Exception as e:
            print(f"Error fetching GIF: {str(e)}")
            return None
