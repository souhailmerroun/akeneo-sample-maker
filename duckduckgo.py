import re
import time
import requests
from typing import Optional, List
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
    def __init__(self, user_agent: Optional[str] = None, timeout: Optional[int] = None):
        self.timeout = timeout or DDG_TIMEOUT
        self.ua = user_agent or DDG_USER_AGENT
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

    def _first_batch_urls(self, query: str, vqd: str, limit: int) -> List[str]:
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
        out = []
        for item in results:
            u = item.get("image") or item.get("thumbnail")
            if u:
                out.append(u)
            if len(out) >= limit:
                break
        return out

    def image_urls(self, product_query: str, limit: int = 5) -> List[str]:
        try:
            vqd = self._get_vqd(product_query)
            if not vqd:
                return []
            return self._first_batch_urls(product_query, vqd, limit)
        except Exception:
            return []

    # backward-compat
    def first_image_url(self, product_query: str) -> Optional[str]:
        urls = self.image_urls(product_query, limit=1)
        return urls[0] if urls else None
