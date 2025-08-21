import time
import requests
from typing import Optional
from base import ImageSearchService

class OpenverseService(ImageSearchService):
    def __init__(self, timeout: int = 20, user_agent: str = "Mozilla/5.0"):
        self.timeout = timeout
        self.ua = user_agent

    def name(self) -> str:
        return "Openverse"

    def first_image_url(self, product_query: str) -> Optional[str]:
        try:
            params = {"q": product_query, "license_type": "commercial", "page_size": 1}
            r = requests.get(
                "https://api.openverse.engineering/v1/images/",
                params=params, timeout=self.timeout, headers={"User-Agent": self.ua}
            )
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(1.0)
                r = requests.get(
                    "https://api.openverse.engineering/v1/images/",
                    params=params, timeout=self.timeout, headers={"User-Agent": self.ua}
                )
            r.raise_for_status()
            data = r.json()
            results = data.get("results") or []
            if not results:
                return None
            first = results[0]
            return first.get("url") or first.get("thumbnail")
        except Exception:
            return None
