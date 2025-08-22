import os
import re
from typing import Optional, Tuple

import requests


__all__ = [
    "safe_name",
    "ensure_dir",
    "guess_ext_and_type",
    "download_image",
    "save_one_local",
]


def safe_name(s: str) -> str:
    """
    Sanitize a string into a safe filename component.
    """
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(s)).strip("_") or "image"


def ensure_dir(path: str) -> None:
    """
    Ensure a directory exists.
    """
    os.makedirs(path, exist_ok=True)


def guess_ext_and_type(url: str, content_type: Optional[str]) -> Tuple[str, str]:
    """
    Guess file extension and MIME type from a URL and/or Content-Type header.
    """
    ct = (content_type or "").lower()
    url_l = (url or "").lower()
    if "jpeg" in ct or url_l.endswith((".jpg", ".jpeg")):
        return ".jpg", "image/jpeg"
    if "png" in ct or url_l.endswith(".png"):
        return ".png", "image/png"
    if "gif" in ct or url_l.endswith(".gif"):
        return ".gif", "image/gif"
    if "webp" in ct or url_l.endswith(".webp"):
        return ".webp", "image/webp"
    return ".jpg", "image/jpeg"


def download_image(url: str, *, ua: str, timeout: int) -> Tuple[Optional[bytes], Optional[str]]:
    """
    Download image bytes and return (content, content_type_header).
    Returns (None, None) on failure.
    """
    try:
        resp = requests.get(url, headers={"User-Agent": ua}, timeout=timeout, stream=True)
        resp.raise_for_status()
        return resp.content, resp.headers.get("Content-Type")
    except Exception:
        return None, None


def save_one_local(
    product: str,
    url: str,
    raw: bytes,
    content_type: Optional[str],
    *,
    service_key: str,
    save_root: str,
) -> str:
    """
    Save one image locally under {save_root}/{service_key}/{safe_product}.{ext}
    Returns the absolute file path.
    """
    # Target folder per service (keeps files tidy and avoids name collisions)
    target_dir = os.path.join(save_root, service_key)
    ensure_dir(target_dir)

    ext, _mime = guess_ext_and_type(url, content_type)
    filename = f"{safe_name(product)}{ext}"
    path = os.path.join(target_dir, filename)

    with open(path, "wb") as f:
        f.write(raw)

    return path
