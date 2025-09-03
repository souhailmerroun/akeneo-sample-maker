import re
import requests
from typing import Optional, List
from base import ImageSearchService
import html
import requests
import urllib.parse

# === Hardcoded Settings ===
GOOGLE_IMAGE_API_URL = "https://www.googleapis.com/customsearch/v1"
GOOGLE_TIMEOUT = 20
GOOGLE_USER_AGENT = "Mozilla/5.0"
GOOGLE_ACCEPT_LANGUAGE = "en-US,en;q=0.9"

class GoogleService(ImageSearchService):
    def __init__(self, user_agent: Optional[str] = None, timeout: Optional[int] = None, 
                 api_key: str = None, cx: str = None, search_type: str = "photo", site_query: str = None):
        print(f"[DEBUG] GoogleService.__init__ called with:")
        print(f"  - user_agent: {user_agent}")
        print(f"  - timeout: {timeout}")
        print(f"  - api_key: {'***' + api_key[-4:] if api_key and len(api_key) > 4 else 'None'}")
        print(f"  - cx: {cx}")
        print(f"  - search_type: {search_type}")
        print(f"  - site_query: {site_query}")
        
        self.timeout = timeout or GOOGLE_TIMEOUT
        self.ua = user_agent or GOOGLE_USER_AGENT
        self.session = requests.Session()
        self.api_key = api_key
        self.cx = cx
        self.search_type = search_type
        self.site_query = site_query
        
        print(f"[DEBUG] Final configuration:")
        print(f"  - timeout: {self.timeout}")
        print(f"  - user_agent: {self.ua}")
        print(f"  - api_key configured: {bool(self.api_key)}")
        print(f"  - cx configured: {bool(self.cx)}")
        
        self.session.headers.update({
            "User-Agent": self.ua,
            "Accept-Language": GOOGLE_ACCEPT_LANGUAGE,
        })
        
        print(f"[DEBUG] Session headers set: {dict(self.session.headers)}")

    def name(self) -> str:
        return "Google"

    def image_urls(self, product_query: str, limit: int = 5) -> List[str]:
        """Return up to `limit` image URLs from Google Custom Search."""
        print(f"[DEBUG] GoogleService.image_urls called with:")
        print(f"  - product_query: '{product_query}'")
        print(f"  - limit: {limit}")
        
        # Validate required parameters
        if not self.api_key:
            print("[ERROR] Google API key is not configured")
            return []
        if not self.cx:
            print("[ERROR] Google Custom Search Engine ID (cx) is not configured")
            return []
            
        try:
            # URL encode the query to handle special characters
            original_query = product_query
            
            # Add site restriction if specified
            if self.site_query and self.site_query.strip():
                query_with_site = f"{product_query} site:{self.site_query.strip()}"
                print(f"[DEBUG] Adding site restriction: {self.site_query}")
            else:
                query_with_site = product_query
                
            query = urllib.parse.quote(query_with_site)
            print(f"[DEBUG] Query encoding:")
            print(f"  - original: '{original_query}'")
            print(f"  - with site: '{query_with_site}'")
            print(f"  - encoded: '{query}'")
            
            # Construct the params dictionary
            params = {
                "q": query,
                "cx": self.cx,  # Custom Search Engine ID
                "key": self.api_key,  # Your Google API Key
                "searchType": "image",  # Searching for images
                "num": str(limit),  # Number of results (maximum 10)
                "safe": "high",  # Safe search filter (optional)
            }
            
            print(f"[DEBUG] Request parameters:")
            for key, value in params.items():
                if key in ["key", "cx"]:
                    # Mask sensitive data
                    display_value = "***" + str(value)[-4:] if value and len(str(value)) > 4 else "None"
                else:
                    display_value = value
                print(f"  - {key}: {display_value}")
            
            print(f"[DEBUG] Making request to: {GOOGLE_IMAGE_API_URL}")
            print(f"[DEBUG] Request timeout: {self.timeout} seconds")

            # Make the request
            r = self.session.get(GOOGLE_IMAGE_API_URL, params=params, timeout=self.timeout)
            
            print(f"[DEBUG] Response received:")
            print(f"  - Status code: {r.status_code}")
            print(f"  - Response headers: {dict(r.headers)}")
            print(f"  - Response size: {len(r.content)} bytes")
            
            r.raise_for_status()  # Raises HTTPError for bad responses

            # Parse the response JSON
            response_data = r.json()
            print(f"[DEBUG] Response JSON structure:")
            print(f"  - Keys in response: {list(response_data.keys())}")
            print(f"  - Total results: {response_data.get('searchInformation', {}).get('totalResults', 'Unknown')}")
            print(f"  - Items count: {len(response_data.get('items', []))}")
            
            # Extract URLs
            items = response_data.get("items", [])
            urls = [item["link"] for item in items][:limit]
            
            print(f"[DEBUG] Extracted URLs ({len(urls)}):")
            for i, url in enumerate(urls, 1):
                print(f"  {i}. {url}")
            
            return urls

        except requests.exceptions.Timeout:
            print(f"[ERROR] Request timed out after {self.timeout} seconds")
            return []
        except requests.exceptions.HTTPError as e:
            print(f"[ERROR] HTTP error occurred: {e}")
            print(f"[ERROR] Response status code: {e.response.status_code if hasattr(e, 'response') else 'Unknown'}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    print(f"[ERROR] Error response: {error_data}")
                except:
                    print(f"[ERROR] Error response text: {e.response.text[:500]}...")
            return []
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Request failed: {e}")
            print(f"[ERROR] Request exception type: {type(e).__name__}")
            return []
        except KeyError as e:
            print(f"[ERROR] Missing key in response: {e}")
            print(f"[ERROR] Available keys in response: {list(response_data.keys()) if 'response_data' in locals() else 'Response not parsed'}")
            return []
        except Exception as e:
            print(f"[ERROR] An unexpected error occurred: {e}")
            print(f"[ERROR] Exception type: {type(e).__name__}")
            import traceback
            print(f"[ERROR] Traceback: {traceback.format_exc()}")
            return []
