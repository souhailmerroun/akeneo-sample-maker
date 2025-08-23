import time
import requests
from typing import Optional, List
from base import ImageSearchService

# === Hardcoded Settings ===
OPENVERSE_API_URL = "https://api.openverse.engineering/v1/images/"
OPENVERSE_TIMEOUT = 20
OPENVERSE_USER_AGENT = "Mozilla/5.0"
OPENVERSE_LICENSE_TYPE = "commercial"
OPENVERSE_RETRY_STATUS_CODES = (429, 500, 502, 503, 504)
OPENVERSE_RETRY_DELAY = 1.0

class OpenverseService(ImageSearchService):
    def __init__(self, user_agent: Optional[str] = None, timeout: Optional[int] = None):
        self.timeout = timeout or OPENVERSE_TIMEOUT
        self.ua = user_agent or OPENVERSE_USER_AGENT

    def name(self) -> str:
        return "Openverse"

    def image_urls(self, product_query: str, limit: int = 5) -> List[str]:
        try:
            params = {
                "q": product_query,
                "license_type": OPENVERSE_LICENSE_TYPE,
                "page_size": limit,
            }
            r = requests.get(
                OPENVERSE_API_URL,
                params=params, timeout=self.timeout,
                headers={"User-Agent": self.ua}
            )
            if r.status_code in OPENVERSE_RETRY_STATUS_CODES:
                time.sleep(OPENVERSE_RETRY_DELAY)
                r = requests.get(
                    OPENVERSE_API_URL,
                    params=params, timeout=self.timeout,
                    headers={"User-Agent": self.ua}
                )
            r.raise_for_status()
            data = r.json()
            results = data.get("results") or []
            out = []
            for item in results[:limit]:
                # prefer original url, fallback to thumbnail
                u = item.get("url") or item.get("thumbnail")
                if u:
                    out.append(u)
            return out
        except Exception:
            return []

    # backward-compat
    def first_image_url(self, product_query: str) -> Optional[str]:
        urls = self.image_urls(product_query, limit=1)
        return urls[0] if urls else None
