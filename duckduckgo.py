import re
import time
import requests
from typing import Optional
from base import ImageSearchService

# === Hardcoded Settings ===
DDG_BASE_URL = "https://duckduckgo.com/"
DDG_IMAGE_API_URL = "https://duckduckgo.com/i.js"

DDG_TIMEOUT = 20
DDG_USER_AGENT = "Mozilla/5.0"
DDG_ACCEPT_LANGUAGE = "en-US,en;q=0.9"

DDG_RETRY_STATUS_CODES = (429, 500, 502, 503, 504, 403)
DDG_RETRY_DELAY = 1.0

DDG_DEFAULT_PARAMS = {
    "o": "json",
    "p": "1",
    "l": "us-en",
    "s": "0",
    "ia": "images",
    "iax": "images",
}


class DuckDuckGoService(ImageSearchService):
    def __init__(self):
        self.timeout = DDG_TIMEOUT
        self.ua = DDG_USER_AGENT
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.ua,
            "Accept-Language": DDG_ACCEPT_LANGUAGE,
        })

    def name(self) -> str:
        return "DuckDuckGo"

    def _get_vqd(self, query: str) -> Optional[str]:
        r = self.session.get(
            DDG_BASE_URL,
            params={"q": query},
            timeout=self.timeout,
            headers={"User-Agent": self.ua, "Referer": DDG_BASE_URL},
        )
        m = (
            re.search(r"vqd='([\w-]+)'", r.text)
            or re.search(r"vqd=([\w-]+)\&", r.text)
            or re.search(r'"vqd":"([\w-]+)"', r.text)
        )
        return m.group(1) if m else None

    def _first_batch_first_url(self, query: str, vqd: str) -> Optional[str]:
        params = {"q": query, "vqd": vqd, **DDG_DEFAULT_PARAMS}
        r = self.session.get(
            DDG_IMAGE_API_URL,
            params=params,
            timeout=self.timeout,
            headers={
                "User-Agent": self.ua,
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Referer": DDG_BASE_URL,
            },
        )
        if r.status_code in DDG_RETRY_STATUS_CODES:
            time.sleep(DDG_RETRY_DELAY)
            r = self.session.get(
                DDG_IMAGE_API_URL,
                params=params,
                timeout=self.timeout,
                headers={"User-Agent": self.ua, "Referer": DDG_BASE_URL},
            )
        r.raise_for_status()
        data = r.json()
        results = data.get("results") or []
        if not results:
            return None
        first = results[0]
        return first.get("image") or first.get("thumbnail")

    def first_image_url(self, product_query: str) -> Optional[str]:
        try:
            vqd = self._get_vqd(product_query)
            if not vqd:
                return None
            return self._first_batch_first_url(product_query, vqd)
        except Exception:
            return None
