import os
import time
import requests
from io import BytesIO
from typing import Optional, Tuple

try:
    from PIL import Image
    PIL_OK = True
except Exception:
    PIL_OK = False


class ImgbbUploader:
    def __init__(self, api_key: Optional[str] = None, endpoint: str = "https://api.imgbb.com/1/upload"):
        self.api_key = api_key or "1f901252510a5e0602004e8f2bfcd8d5"
        self.endpoint = endpoint
        if not self.api_key:
            raise SystemExit("Please set IMGBB_API_KEY in env or pass to ImgbbUploader")

        self.max_bytes = 15 * 1024 * 1024  # 15 MB
        self.jpeg_quality = 85
        self.max_retries = 2

    def _maybe_convert_image(self, bytes_in: bytes, content_type: Optional[str]) -> Tuple[bytes, str, str]:
        ext = ".jpg"
        mimetype = "image/jpeg"
        too_big = len(bytes_in) > self.max_bytes
        needs_convert = True if (content_type and "webp" in content_type.lower()) else False

        if (too_big or needs_convert) and PIL_OK:
            try:
                im = Image.open(BytesIO(bytes_in))
                if im.mode not in ("RGB", "L"):
                    im = im.convert("RGB")
                buf = BytesIO()
                im.save(buf, format="JPEG", quality=self.jpeg_quality, optimize=True)
                return buf.getvalue(), ".jpg", "image/jpeg"
            except Exception:
                pass
        return bytes_in, ext, mimetype

    def upload(self, raw: bytes, display_name: str, content_type: Optional[str]) -> Optional[str]:
        raw2, ext, mimetype = self._maybe_convert_image(raw, content_type)
        filename = f"{self._safe_name(display_name)}{ext}"

        params = {"key": self.api_key}
        files = {"image": (filename, raw2, mimetype)}
        data = {"name": self._safe_name(display_name)}

        r = None
        for attempt in range(self.max_retries + 1):
            try:
                r = requests.post(self.endpoint, params=params, data=data, files=files, timeout=20)
            except Exception:
                time.sleep(1.0)
                continue

            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(1.2)
                continue
            break

        try:
            payload = r.json() if r is not None else {}
        except Exception:
            payload = {}

        if r is not None and r.ok and payload.get("success"):
            return payload["data"]["display_url"]
        return None

    def _safe_name(self, s: str) -> str:
        import re
        return re.sub(r"[^A-Za-z0-9._-]+", "_", str(s)).strip("_") or "image"
