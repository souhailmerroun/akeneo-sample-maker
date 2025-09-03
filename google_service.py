import re
import requests
from typing import Optional, List
from base import ImageSearchService
import html  # for decoding HTML entities

# === Hardcoded Settings ===
GOOGLE_IMAGE_API_URL = "https://www.googleapis.com/customsearch/v1"
GOOGLE_TIMEOUT = 20
GOOGLE_USER_AGENT = "Mozilla/5.0"
GOOGLE_ACCEPT_LANGUAGE = "en-US,en;q=0.9"
GOOGLE_IMAGE_TYPE = "photo"  # You can set this to "image" for non-photo types
# Placeholder for your Google API key and Custom Search Engine ID (CX)
GOOGLE_API_KEY = "AIzaSyAh3mkmsMkRGgtGDNVmegWEmqlO1IyeJkk"
GOOGLE_CX = "00b56792ad252441c"

class GoogleService(ImageSearchService):
    def __init__(self, user_agent: Optional[str] = None, timeout: Optional[int] = None):
        self.timeout = timeout or GOOGLE_TIMEOUT
        self.ua = user_agent or GOOGLE_USER_AGENT
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.ua,
            "Accept-Language": GOOGLE_ACCEPT_LANGUAGE,
        })

    def name(self) -> str:
        return "Google"

    def image_urls(self, product_query: str, limit: int = 5) -> List[str]:
        """Return up to `limit` image URLs from Google Custom Search."""
        try:
            params = {
                "q": product_query,
                "cx": GOOGLE_CX,  # Custom Search Engine ID
                "key": GOOGLE_API_KEY,  # Your Google API Key
                "searchType": "image",  # Searching for images
                "num": str(limit),  # Number of results (maximum 10)
                "fileType": "jpg",  # File type filter (optional)
                "imgType": GOOGLE_IMAGE_TYPE,  # Image type filter (optional)
                "safe": "high",  # Safe search filter (optional)
            }
            r = self.session.get(GOOGLE_IMAGE_API_URL, params=params, timeout=self.timeout)
            r.raise_for_status()

            response_data = r.json()
            urls = [item["link"] for item in response_data.get("items", [])][:limit]
            
            return urls

        except requests.exceptions.Timeout:
            print(f"Request timed out after {self.timeout} seconds")
            return []
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            return []
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return []
