import re
import requests
from typing import Optional
from base import ImageSearchService

# === Hardcoded Settings ===
BING_IMAGE_API_URL = "https://www.bing.com/images/async"

BING_TIMEOUT = 20
BING_USER_AGENT = "Mozilla/5.0"
BING_ACCEPT_LANGUAGE = "en-US,en;q=0.9"

BING_QUERY_PARAMS = {
    "first": "0",
    "count": "1",  # only need the first
    "adlt": "safe",
    "qft": "+filterui:photo-photo",  # bias towards real photos
}

BING_IMAGE_REGEX = r"murl&quot;:&quot;(.*?)&quot;"


class BingService(ImageSearchService):
    def __init__(self):
        self.timeout = BING_TIMEOUT
        self.ua = BING_USER_AGENT
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.ua,
            "Accept-Language": BING_ACCEPT_LANGUAGE,
        })

    def name(self) -> str:
        return "Bing"

    def first_image_url(self, product_query: str) -> Optional[str]:
        """
        Returns the first image result from Bing Image Search (unofficial endpoint).
        No filtering, no heuristics.
        """
        try:
            params = {"q": product_query, **BING_QUERY_PARAMS}
            r = self.session.get(BING_IMAGE_API_URL, params=params, timeout=self.timeout)
            r.raise_for_status()
            html = r.text

            m = re.search(BING_IMAGE_REGEX, html)
            if not m:
                return None
            return m.group(1)
        except Exception:
            return None
