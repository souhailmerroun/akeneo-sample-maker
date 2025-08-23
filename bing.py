import re
import requests
from typing import Optional, List
from base import ImageSearchService

# === Hardcoded Settings ===
BING_IMAGE_API_URL = "https://www.bing.com/images/async"

BING_TIMEOUT = 20
BING_USER_AGENT = "Mozilla/5.0"
BING_ACCEPT_LANGUAGE = "en-US,en;q=0.9"

# NOTE: we'll dynamically set "count" based on requested limit
BING_IMAGE_REGEX = r"murl&quot;:&quot;(.*?)&quot;"

class BingService(ImageSearchService):
    def __init__(self, user_agent: Optional[str] = None, timeout: Optional[int] = None):
        self.timeout = timeout or BING_TIMEOUT
        self.ua = user_agent or BING_USER_AGENT
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.ua,
            "Accept-Language": BING_ACCEPT_LANGUAGE,
        })

    def name(self) -> str:
        return "Bing"

    def image_urls(self, product_query: str, limit: int = 5) -> List[str]:
        """Return up to `limit` image URLs from Bing.”
        """
        try:
            params = {
                "q": product_query,
                "first": "0",
                "count": str(limit),
                "adlt": "safe",
                "qft": "+filterui:photo-photo",
            }
            r = self.session.get(BING_IMAGE_API_URL, params=params, timeout=self.timeout)
            r.raise_for_status()
            html = r.text
            urls = re.findall(BING_IMAGE_REGEX, html)[:limit]
            # Deduplicate while preserving order
            seen = set()
            out = []
            for u in urls:
                if u not in seen:
                    out.append(u)
                    seen.add(u)
            return out
        except Exception:
            return []

    # backward-compat
    def first_image_url(self, product_query: str) -> Optional[str]:
        urls = self.image_urls(product_query, limit=1)
        return urls[0] if urls else None
