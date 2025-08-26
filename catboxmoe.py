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


class CatboxUploader:
    """
    Minimal wrapper for https://catbox.moe/user/api.php

    - Anonymous uploads require no credentials.
    - If you have a Catbox account, you can pass `userhash` (or set CATBOX_USERHASH env var)
      to associate uploads with your account.
    - Returns the direct URL on success, or None on failure.
    """

    def __init__(self, userhash: Optional[str] = None, endpoint: str = "https://catbox.moe/user/api.php"):
        self.userhash = userhash or os.getenv("CATBOX_USERHASH")
        self.endpoint = endpoint

        # Catbox allows large files (≈200MB). Keep a conservative ceiling for optional recompression.
        self.max_bytes = 195 * 1024 * 1024
        self.jpeg_quality = 85
        self.max_retries = 2

    def _maybe_convert_image(self, bytes_in: bytes, content_type: Optional[str]) -> Tuple[bytes, str, str]:
        """
        Optionally convert WEBP/huge images to JPEG to stay under a size ceiling.
        Catbox accepts many formats; this is just a safety valve mirroring your original behavior.
        """
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

        # Otherwise, just send as-is (Catbox is fine with PNG/WEBP/etc.)
        # If you want to preserve the original extension/mimetype, you can enhance this.
        return bytes_in, ext, mimetype

    def upload(self, raw: bytes, display_name: str, content_type: Optional[str]) -> Optional[str]:
        """
        Upload raw bytes to Catbox. Returns the direct link on success, else None.
        """
        raw2, ext, mimetype = self._maybe_convert_image(raw, content_type)
        filename = f"{self._safe_name(display_name)}{ext}"

        data = {"reqtype": "fileupload"}
        if self.userhash:
            data["userhash"] = self.userhash

        files = {"fileToUpload": (filename, raw2, mimetype)}

        r = None
        for attempt in range(self.max_retries + 1):
            try:
                r = requests.post(self.endpoint, data=data, files=files, timeout=30)
            except Exception:
                time.sleep(1.0)
                continue

            # Retry on transient errors / rate limit
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(1.2)
                continue
            break

        text = (r.text if r is not None and r.text is not None else "").strip()
        # Success is a plain URL in the body; errors are "ERROR: ..."
        if r is not None and r.ok and text.startswith("http"):
            return text
        return None

    def upload_url(self, source_url: str) -> Optional[str]:
        """
        Ask Catbox to fetch a remote URL directly (server-side).
        """
        data = {"reqtype": "urlupload", "url": source_url}
        if self.userhash:
            data["userhash"] = self.userhash

        r = None
        for attempt in range(self.max_retries + 1):
            try:
                r = requests.post(self.endpoint, data=data, timeout=30)
            except Exception:
                time.sleep(1.0)
                continue

            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(1.2)
                continue
            break

        text = (r.text if r is not None and r.text is not None else "").strip()
        if r is not None and r.ok and text.startswith("http"):
            return text
        return None

    def _safe_name(self, s: str) -> str:
        import re
        return re.sub(r"[^A-Za-z0-9._-]+", "_", str(s)).strip("_") or "file"
