import time
import requests
from typing import Optional
from base import ImageSearchService

# === Hardcoded Settings ===
OPENVERSE_API_URL = "https://api.openverse.engineering/v1/images/"
OPENVERSE_TIMEOUT = 20
OPENVERSE_USER_AGENT = "Mozilla/5.0"
OPENVERSE_LICENSE_TYPE = "commercial"
OPENVERSE_PAGE_SIZE = 1
OPENVERSE_RETRY_STATUS_CODES = (429, 500, 502, 503, 504)
OPENVERSE_RETRY_DELAY = 1.0


class OpenverseService(ImageSearchService):
    def __init__(self):
        self.timeout = OPENVERSE_TIMEOUT
        self.ua = OPENVERSE_USER_AGENT

    def name(self) -> str:
        return "Openverse"

    def first_image_url(self, product_query: str) -> Optional[str]:
        try:
            params = {
                "q": product_query,
                "license_type": OPENVERSE_LICENSE_TYPE,
                "page_size": OPENVERSE_PAGE_SIZE,
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
            if not results:
                return None
            first = results[0]
            return first.get("url") or first.get("thumbnail")
        except Exception:
            return None
