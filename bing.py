import requests
from typing import Optional
from base import ImageSearchService


class BingService(ImageSearchService):
    def __init__(self, timeout: int = 20, user_agent: str = "Mozilla/5.0"):
        self.timeout = timeout
        self.ua = user_agent
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.ua,
            "Accept-Language": "en-US,en;q=0.9",
        })

    def name(self) -> str:
        return "Bing"

    def first_image_url(self, product_query: str) -> Optional[str]:
        """
        Returns the first image result from Bing Image Search (unofficial endpoint).
        No filtering, no heuristics.
        """
        try:
            url = "https://www.bing.com/images/async"
            params = {
                "q": product_query,
                "first": "0",
                "count": "1",  # only need the first
                "adlt": "safe",
                "qft": "+filterui:photo-photo",  # bias towards real photos
            }
            r = self.session.get(url, params=params, timeout=self.timeout)
            r.raise_for_status()
            html = r.text

            # Extract murl="https://..." (original image url) — Bing's async payload contains this
            import re
            m = re.search(r"murl&quot;:&quot;(.*?)&quot;", html)
            if not m:
                return None
            return m.group(1)
        except Exception:
            return None
