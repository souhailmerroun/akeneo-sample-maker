#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import random
import requests
import pandas as pd
from typing import Optional, Tuple, Dict

# Import all three services
from bing import BingService
from openverse import OpenverseService
from duckduckgo import DuckDuckGoService

from imgbb import ImgbbUploader

# =========================
# 🔧 SETTINGS
# =========================
EXCEL_PATH  = r"/Users/souhail.merroun@akeneo.com/Downloads/medical_products.xlsx"
PRODUCT_COL = "Product Name"
IMAGE_COL   = "Image URL"  # will NOT be overwritten

# New columns (created if missing)
COL_BING       = "image_bing"
COL_OPENVERSE  = "image_openverse"
COL_DDG        = "image_duckduckgo"

FORCE_OVERWRITE = True          # applies to the three new columns
LIMIT_ROWS      = None
SKIP_IF_PRODUCT_BLANK = True

SAVE_ROOT = r"./product_images"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/123 Safari/537.36"
TIMEOUT = 20
SLEEP_BETWEEN_UPLOADS = (0.6, 1.2)

# =========================
# Helpers
# =========================
def _safe_name(s: str) -> str:
    import re
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(s)).strip("_") or "image"

def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def _guess_ext_and_type(url: str, content_type: Optional[str]) -> Tuple[str, str]:
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

def _download_image(url: str) -> Tuple[Optional[bytes], Optional[str]]:
    try:
        resp = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT, stream=True)
        resp.raise_for_status()
        return resp.content, resp.headers.get("Content-Type")
    except Exception:
        return None, None

def _save_one_local(product: str, url: str, raw: bytes, content_type: Optional[str], service_key: str) -> str:
    # Target folder per service (keeps files tidy and avoids name collisions)
    target_dir = os.path.join(SAVE_ROOT, service_key)
    _ensure_dir(target_dir)

    ext, _mime = _guess_ext_and_type(url, content_type)
    filename = f"{_safe_name(product)}{ext}"
    path = os.path.join(target_dir, filename)

    with open(path, "wb") as f:
        f.write(raw)

    return path

# =========================
# Main
# =========================
def main():
    # Initialize the three services
    services: Dict[str, object] = {
        "bing":       BingService(user_agent=UA, timeout=TIMEOUT),
        "openverse":  OpenverseService(user_agent=UA, timeout=TIMEOUT),
        "duckduckgo": DuckDuckGoService(user_agent=UA, timeout=TIMEOUT),
    }
    service_to_column = {
        "bing": COL_BING,
        "openverse": COL_OPENVERSE,
        "duckduckgo": COL_DDG,
    }

    uploader = ImgbbUploader()

    try:
        df = pd.read_excel(EXCEL_PATH)
    except Exception as e:
        raise SystemExit(f"Failed to read Excel: {e}")

    if PRODUCT_COL not in df.columns:
        raise SystemExit(f"Column not found: {PRODUCT_COL}")

    # Ensure new columns exist (do NOT touch IMAGE_COL)
    for col in [COL_BING, COL_OPENVERSE, COL_DDG]:
        if col not in df.columns:
            df[col] = ""

    total = len(df) if LIMIT_ROWS is None else min(LIMIT_ROWS, len(df))
    print("Services:", ", ".join([type(s).__name__ for s in services.values()]))
    print(f"Processing {total} rows from '{EXCEL_PATH}'")

    updates = {COL_BING: 0, COL_OPENVERSE: 0, COL_DDG: 0}

    for i in range(total):
        idx = df.index[i]
        product_val = df.at[idx, PRODUCT_COL]
        product = str(product_val).strip() if pd.notna(product_val) else ""

        if SKIP_IF_PRODUCT_BLANK and not product:
            print(f"[skip {i+1}] empty product name")
            continue

        print(f"\n[{i+1}/{total}] {product!r}")

        for key, service in services.items():
            col = service_to_column[key]
            existing_val = df.at[idx, col]
            existing = str(existing_val).strip() if pd.notna(existing_val) else ""

            if existing and not FORCE_OVERWRITE:
                print(f"   [{key}] skip: column already set")
                continue

            # Ask service for first image URL
            try:
                url = service.first_image_url(product)
            except Exception as e:
                print(f"   [{key}] ⚠️ service error: {e}")
                continue

            if not url:
                print(f"   [{key}] ⚠️ No image URL from service.")
                continue

            raw, ct = _download_image(url)
            if not raw:
                print(f"   [{key}] ⚠️ Download failed.")
                continue

            local_path = _save_one_local(product, url, raw, ct, key)
            print(f"   [{key}] saved -> {local_path}")

            up = uploader.upload(raw, display_name=f"{product} ({key})", content_type=ct)
            if up:
                df.at[idx, col] = up
                updates[col] += 1
                print(f"   [{key}] ✅ uploaded -> {up}")
            else:
                print(f"   [{key}] ⚠️ Upload failed (local saved).")

            time.sleep(random.uniform(*SLEEP_BETWEEN_UPLOADS))

    df.to_excel(EXCEL_PATH, index=False)
    print("\nDone.")
    for col, n in updates.items():
        print(f"Updated {col}: {n}")
    print(f"Saved Excel: {EXCEL_PATH}")
    print(f"Local images under: {os.path.abspath(SAVE_ROOT)}")

if __name__ == "__main__":
    main()
