import time
import requests
from typing import Optional, List
from base import ImageSearchService  # Make sure this base class exists

# === Settings ===
OPENVERSE_API_URL = "https://api.openverse.engineering/v1/images/"
DEFAULT_TIMEOUT = 20
DEFAULT_USER_AGENT = "Mozilla/5.0"
LICENSE_TYPE = "commercial"  # Change to None to disable filtering
RETRY_STATUS_CODES = (429, 500, 502, 503, 504)
RETRY_DELAY = 1.0  # seconds
MAX_RETRIES = 2


class OpenverseService(ImageSearchService):
    def __init__(self, user_agent: Optional[str] = None, timeout: Optional[int] = None):
        self.timeout = timeout or DEFAULT_TIMEOUT
        self.user_agent = user_agent or DEFAULT_USER_AGENT

    def name(self) -> str:
        return "Openverse"

    def image_urls(self, product_query: str, limit: int = 5) -> List[str]:
        params = {
            "q": product_query,
            "page_size": limit,
        }

        # Add license_type only if set
        if LICENSE_TYPE:
            params["license_type"] = LICENSE_TYPE

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json"
        }

        for attempt in range(MAX_RETRIES):
            try:
                response = requests.get(
                    OPENVERSE_API_URL,
                    params=params,
                    headers=headers,
                    timeout=self.timeout
                )

                if response.status_code in RETRY_STATUS_CODES and attempt < MAX_RETRIES - 1:
                    print(f"[Retry] Status {response.status_code}, retrying in {RETRY_DELAY}s...")
                    time.sleep(RETRY_DELAY)
                    continue

                response.raise_for_status()
                data = response.json()
                results = data.get("results", [])

                image_list = []
                for item in results[:limit]:
                    url = item.get("url") or item.get("thumbnail")
                    if url:
                        image_list.append(url)

                return image_list

            except requests.RequestException as e:
                print(f"[Error] Openverse API request failed: {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
                else:
                    return []

        return []

    def first_image_url(self, product_query: str) -> Optional[str]:
        urls = self.image_urls(product_query, limit=1)
        return urls[0] if urls else None
