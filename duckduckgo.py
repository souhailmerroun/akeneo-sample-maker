import re
import time
import requests
import logging
from typing import Optional, List
from base import ImageSearchService

# === Config ===
DDG_BASE_URL = "https://duckduckgo.com/"
DDG_IMAGE_API_URL = "https://duckduckgo.com/i.js"

DDG_TIMEOUT = 20
DDG_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
DDG_ACCEPT_LANGUAGE = "en-US,en;q=0.9"

DDG_RETRY_STATUS_CODES = (429, 500, 502, 503, 504, 403)
DDG_RETRY_DELAY = 1.0
MAX_RETRIES = 2

DDG_DEFAULT_PARAMS = {
    "o": "json",
    "p": "1",
    "l": "us-en",
    "s": "0",
    "ia": "images",
    "iax": "images",
}

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class DuckDuckGoService(ImageSearchService):
    def __init__(self, user_agent: Optional[str] = None, timeout: Optional[int] = None, max_retries: Optional[int] = MAX_RETRIES):
        self.timeout = timeout or DDG_TIMEOUT
        self.ua = user_agent or DDG_USER_AGENT
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.ua,
            "Accept-Language": DDG_ACCEPT_LANGUAGE,
        })

    def name(self) -> str:
        return "DuckDuckGo"

    def _get_vqd(self, query: str) -> Optional[str]:
        try:
            logger.debug(f"Fetching VQD for query: {query}")
            response = self.session.get(
                DDG_BASE_URL,
                params={"q": query},
                timeout=self.timeout,
                headers={
                    "User-Agent": self.ua, 
                    "Referer": DDG_BASE_URL,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                    "Accept-Encoding": "gzip, deflate",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                },
            )
            response.raise_for_status()
            logger.debug(f"Response status: {response.status_code}, Content length: {len(response.text)}")
            
            # Enhanced regex patterns for VQD token extraction
            patterns = [
                r"vqd='([\w-]+)'",
                r"vqd=([\w-]+)\&",
                r'"vqd":"([\w-]+)"',
                r'vqd["\']?\s*[:=]\s*["\']([\w-]+)["\']',
                r'vqd["\']?\s*=\s*["\']([\w-]+)["\']',
                r'vqd["\']?\s*:\s*["\']([\w-]+)["\']',
                r'vqd["\']?\s*=\s*([\w-]+)',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, response.text)
                if match:
                    vqd = match.group(1)
                    logger.debug(f"VQD found with pattern: {vqd[:10]}...")
                    return vqd
                    
            # Debug: Print a snippet of the response to see what we're getting
            logger.debug(f"VQD search failed. Response snippet: {response.text[:500]}...")
            
        except requests.RequestException as e:
            logger.error(f"Request failed while getting vqd token: {e}")
        except re.error as e:
            logger.error(f"Regex error occurred while extracting vqd: {e}")
        return None

    def _first_batch_urls(self, query: str, vqd: str, limit: int) -> List[str]:
        params = {"q": query, "vqd": vqd, **DDG_DEFAULT_PARAMS}

        for attempt in range(self.max_retries):
            try:
                response = self.session.get(
                    DDG_IMAGE_API_URL,
                    params=params,
                    timeout=self.timeout,
                    headers={
                        "User-Agent": self.ua,
                        "Accept": "application/json, text/javascript, */*; q=0.01",
                        "Referer": DDG_BASE_URL,
                    },
                )

                if response.status_code in DDG_RETRY_STATUS_CODES:
                    logger.warning(f"Attempt {attempt + 1} failed with status {response.status_code}, retrying...")
                    time.sleep(DDG_RETRY_DELAY)
                    continue

                response.raise_for_status()
                data = response.json()
                results = data.get("results", [])

                urls = []
                for item in results:
                    url = item.get("image") or item.get("thumbnail")
                    if url:
                        urls.append(url)
                    if len(urls) >= limit:
                        break
                return urls

            except requests.RequestException as e:
                logger.error(f"DuckDuckGo API error: {e}")
                time.sleep(DDG_RETRY_DELAY)
            except ValueError as e:
                logger.error(f"Failed to parse JSON from DuckDuckGo: {e}")
                time.sleep(DDG_RETRY_DELAY)

        return []

    def image_urls(self, product_query: str, limit: int = 5) -> List[str]:
        try:
            vqd = self._get_vqd(product_query)
            if not vqd:
                logger.error("Could not obtain vqd token, returning empty list.")
                return []
            return self._first_batch_urls(product_query, vqd, limit)
        except Exception as e:
            logger.error(f"Unexpected error during image search: {e}")
            return []

    def first_image_url(self, product_query: str) -> Optional[str]:
        urls = self.image_urls(product_query, limit=1)
        return urls[0] if urls else None
