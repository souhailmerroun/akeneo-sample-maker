import re
import time
import requests
from typing import Optional
from base import ImageSearchService

class DuckDuckGoService(ImageSearchService):
    def __init__(self, timeout: int = 20, user_agent: str = "Mozilla/5.0"):
        self.timeout = timeout
        self.ua = user_agent
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.ua,
            "Accept-Language": "en-US,en;q=0.9",
        })

    def name(self) -> str:
        return "DuckDuckGo"

    def _get_vqd(self, query: str) -> Optional[str]:
        r = self.session.get(
            "https://duckduckgo.com/",
            params={"q": query},
            timeout=self.timeout,
            headers={"User-Agent": self.ua, "Referer": "https://duckduckgo.com/"},
        )
        m = (re.search(r"vqd='([\w-]+)'", r.text)
             or re.search(r'vqd=([\w-]+)\&', r.text)
             or re.search(r'"vqd":"([\w-]+)"', r.text))
        return m.group(1) if m else None

    def _first_batch_first_url(self, query: str, vqd: str) -> Optional[str]:
        params = {
            "q": query,
            "vqd": vqd,
            "o": "json",
            "p": "1",
            "l": "us-en",
            "s": "0",
            "ia": "images",
            "iax": "images",
        }
        r = self.session.get(
            "https://duckduckgo.com/i.js",
            params=params,
            timeout=self.timeout,
            headers={
                "User-Agent": self.ua,
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Referer": "https://duckduckgo.com/",
            },
        )
        if r.status_code in (429, 500, 502, 503, 504, 403):
            time.sleep(1.0)
            r = self.session.get("https://duckduckgo.com/i.js", params=params, timeout=self.timeout,
                                 headers={"User-Agent": self.ua, "Referer": "https://duckduckgo.com/"})
        r.raise_for_status()
        data = r.json()
        results = data.get("results") or []
        if not results:
            return None
        # just the first image field that exists
        first = results[0]
        return first.get("image") or first.get("thumbnail")

    def first_image_url(self, product_query: str) -> Optional[str]:
        # No heuristics, no re-query — literally the first result from offset 0
        try:
            vqd = self._get_vqd(product_query)
            if not vqd:
                return None
            return self._first_batch_first_url(product_query, vqd)
        except Exception:
            return None
