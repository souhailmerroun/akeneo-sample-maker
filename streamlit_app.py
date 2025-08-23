#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import base64
import io
import os
import random
import tempfile
import time
from typing import Dict, List, Tuple

import pandas as pd
import streamlit as st
from PIL import Image

from bing import BingService
from duckduckgo import DuckDuckGoService
from helpers import download_image, save_one_local
from imgbb import ImgbbUploader
from openverse import OpenverseService

# =========================
# SETTINGS
# =========================
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/123 Safari/537.36"
TIMEOUT = 20
SLEEP_BETWEEN_UPLOADS = (0.6, 1.2)
SAVE_ROOT = "./product_images"

# Grid look & feel
NUM_COLS = 5                 # how many tiles per row
TILE_IMG_HEIGHT = 200        # px; image box height (uniform)
TILE_PADDING = 10            # px around each tile

# =========================
# HELPERS
# =========================
def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")

def render_img_tile(image_bytes: bytes):
    """
    Render an image in a fixed-size box using raw HTML so we can enforce
    object-fit: contain and consistent tile dimensions.
    """
    b64 = _b64(image_bytes)
    html = f"""
    <div style="
        width: 100%;
        height: {TILE_IMG_HEIGHT}px;
        padding: {TILE_PADDING}px;
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        box-sizing: border-box;
    ">
        <img src="data:image/*;base64,{b64}"
             style="max-width: 100%; max-height: 100%; object-fit: contain; border-radius: 6px;" />
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

def download_for_preview(url: str) -> bytes:
    """
    Try to download an image for preview.
    Returns bytes on success, None on failure.
    """
    raw, ct = download_image(url, ua=UA, timeout=TIMEOUT)
    # basic guard: must have bytes and a likely image content-type
    if not raw:
        return None
    if ct and ("image" not in ct.lower()):
        return None
    # additionally verify we can open it
    try:
        Image.open(io.BytesIO(raw)).verify()
        return raw
    except Exception:
        return None

# =========================
# APP
# =========================
def main():
    st.set_page_config(page_title="Image Search & Upload Tool", page_icon="🖼️", layout="wide")
    st.title("🖼️ Image Search & Upload Tool")
    st.caption("Simple grid selection • Auto-select N per product • Uniform tiles • Broken images hidden")

    # --- session state ---
    if "fetched" not in st.session_state:
        st.session_state.fetched = False
    if "fetched_items" not in st.session_state:
        # fetched_items[row_idx] = List[Dict]: {"svc": str, "url": str, "bytes": bytes}
        st.session_state.fetched_items: Dict[int, List[Dict]] = {}
    if "selections" not in st.session_state:
        # selections[row_idx][service] = [url, ...]
        st.session_state.selections: Dict[int, Dict[str, List[str]]] = {}

    # --- sidebar ---
    st.sidebar.header("⚙️ Configuration")
    uploaded_file = st.sidebar.file_uploader("Upload Excel file", type=["xlsx", "xls"])
    product_col = st.sidebar.text_input("Product Name Column", value="Product Name")

    # column name prefixes (export)
    col_bing_prefix = st.sidebar.text_input("Bing column prefix", value="image_bing")
    col_openverse_prefix = st.sidebar.text_input("Openverse column prefix", value="image_openverse")
    col_ddg_prefix = st.sidebar.text_input("DuckDuckGo column prefix", value="image_duckduckgo")

    max_images = st.sidebar.number_input("Max images per service per product", 1, 10, 5, 1)

    st.sidebar.info(f"📁 Local save folder: `{os.path.abspath(SAVE_ROOT)}`")

    if uploaded_file is None:
        st.info("📁 Upload an Excel file to begin")
        st.dataframe(pd.DataFrame({"Product Name": ["Sample A", "Sample B"]}), use_container_width=True)
        return

    try:
        df = pd.read_excel(uploaded_file)
        if product_col not in df.columns:
            st.error(f"❌ Column '{product_col}' not found. Available: {list(df.columns)}")
            return

        st.success(f"✅ Loaded Excel with {len(df)} rows")
        with st.expander("Preview data", expanded=False):
            st.dataframe(df.head(), use_container_width=True)

        # services
        services: Dict[str, object] = {
            "bing": BingService(user_agent=UA, timeout=TIMEOUT),
            "openverse": OpenverseService(user_agent=UA, timeout=TIMEOUT),
            "duckduckgo": DuckDuckGoService(user_agent=UA, timeout=TIMEOUT),
        }
        service_labels = {"bing": "Bing", "openverse": "Openverse", "duckduckgo": "DuckDuckGo"}
        service_prefix = {"bing": col_bing_prefix, "openverse": col_openverse_prefix, "duckduckgo": col_ddg_prefix}

        # top controls
        c1, c2, c3 = st.columns([1, 1, 2])
        with c1:
            fetch_clicked = st.button("🔍 Fetch images", type="primary")
        with c2:
            clear_clicked = st.button("♻️ Clear selections")
        with c3:
            st.markdown("**Auto-select for all products**")
            auto_n = st.selectbox("How many per product?", options=list(range(1, max_images + 1)),
                                  index=min(2, max_images - 1), label_visibility="collapsed")
            auto_select_clicked = st.button("⚡ Auto Select")

        if clear_clicked:
            st.session_state.fetched = False
            st.session_state.fetched_items = {}
            st.session_state.selections = {}
            # clear any checkbox state
            for k in list(st.session_state.keys()):
                if str(k).startswith("sel_"):
                    del st.session_state[k]
            st.info("Selections cleared.")

        # --- FETCH PHASE (with preview download & filtering) ---
        if fetch_clicked or st.session_state.fetched:
            if fetch_clicked:
                st.session_state.fetched_items = {}
                st.session_state.selections = {}
                st.session_state.fetched = True

            total = len(df)
            p = st.progress(0.0)
            status = st.empty()

            for i, idx in enumerate(df.index):
                name_val = df.at[idx, product_col]
                product = str(name_val).strip() if pd.notna(name_val) and str(name_val).strip() else f"Product_{i+1}"

                if fetch_clicked:
                    items: List[Dict] = []
                    # collect URLs from each service
                    all_pairs: List[Tuple[str, str]] = []
                    for key, svc in services.items():
                        try:
                            urls = svc.image_urls(product, limit=max_images)
                        except Exception:
                            urls = []
                        all_pairs.extend((key, u) for u in urls)

                    # Try downloading each for preview; keep only valid images
                    for svc_key, url in all_pairs:
                        img_bytes = download_for_preview(url)
                        if not img_bytes:
                            continue  # skip broken/blocked/hotlinked images
                        items.append({"svc": svc_key, "url": url, "bytes": img_bytes})

                    st.session_state.fetched_items[idx] = items

                p.progress((i + 1) / total)
                status.text(f"Fetched {i+1}/{total}")

            # --- AUTO-SELECT N (optional) ---
            if auto_select_clicked:
                # reset all checkbox states and selections
                for k in list(st.session_state.keys()):
                    if str(k).startswith("sel_"):
                        del st.session_state[k]
                st.session_state.selections = {}

                for idx, items in st.session_state.fetched_items.items():
                    take = min(auto_n, len(items))
                    for j in range(take):
                        svc_key = items[j]["svc"]
                        url = items[j]["url"]
                        st.session_state.selections.setdefault(idx, {}).setdefault(svc_key, [])
                        if url not in st.session_state.selections[idx][svc_key]:
                            st.session_state.selections[idx][svc_key].append(url)
                        st.session_state[f"sel_{idx}_{j}"] = True
                st.success(f"Auto-selected up to {auto_n} per product.")

            st.markdown("---")

            # --- RENDER PHASE (skip products with zero valid images) ---
            shown = 0
            for i, idx in enumerate(df.index):
                items = st.session_state.fetched_items.get(idx, [])
                if not items:
                    # Nothing to render for this product—no empty cards.
                    continue

                # Product header
                st.markdown(f"#### Row {i+1}/{len(df)}", unsafe_allow_html=True)

                cols = st.columns(NUM_COLS)
                for j, item in enumerate(items):
                    svc_key, url, img_bytes = item["svc"], item["url"], item["bytes"]
                    with cols[j % NUM_COLS]:
                        ck_key = f"sel_{idx}_{j}"
                        already = url in st.session_state.selections.get(idx, {}).get(svc_key, [])
                        checked = st.checkbox(f"[{service_labels.get(svc_key, svc_key)}] #{j+1}",
                                              key=ck_key, value=already)
                        render_img_tile(img_bytes)

                        # keep selection dict in sync
                        if checked and not already:
                            st.session_state.selections.setdefault(idx, {}).setdefault(svc_key, [])
                            st.session_state.selections[idx][svc_key].append(url)
                        if not checked and already:
                            st.session_state.selections[idx][svc_key].remove(url)

                st.markdown("---")
                shown += 1

            if shown == 0:
                st.warning("No valid images were found across all products.")

        # --- EXPORT PHASE ---
        st.subheader("💾 Save selections & export")
        run_export = st.button("☁️ Save locally + Upload to ImgBB + Export Excel")

        if run_export:
            # Create per-service columns up to max_images
            for svc_key, prefix in service_prefix.items():
                for n in range(1, max_images + 1):
                    colname = f"{prefix}_{n}"
                    if colname not in df.columns:
                        df[colname] = ""

            uploader = ImgbbUploader()
            total = len(df)
            p2 = st.progress(0.0)
            status2 = st.empty()

            # index fetched items by url for quick lookup of bytes
            cache_bytes: Dict[str, bytes] = {}
            for items in st.session_state.fetched_items.values():
                for it in items:
                    cache_bytes[it["url"]] = it["bytes"]

            for i, idx in enumerate(df.index):
                name_val = df.at[idx, product_col]
                product = str(name_val).strip() if pd.notna(name_val) and str(name_val).strip() else f"Product_{i+1}"

                row_sel = st.session_state.selections.get(idx, {})
                for svc_key, urls in row_sel.items():
                    chosen = urls[:max_images]
                    out_links: List[str] = []

                    for u in chosen:
                        # reuse preview bytes when possible; else download fresh
                        raw = cache_bytes.get(u)
                        ct = None
                        if raw is None:
                            raw, ct = download_image(u, ua=UA, timeout=TIMEOUT)
                            if not raw:
                                continue
                        _local = save_one_local(product, u, raw, ct, service_key=svc_key, save_root=SAVE_ROOT)
                        up = uploader.upload(raw, display_name=f"{product} ({svc_key})", content_type=ct)
                        out_links.append(up if up else u)
                        time.sleep(random.uniform(*SLEEP_BETWEEN_UPLOADS))

                    # write out to _1.._N (blanks for the rest)
                    prefix = service_prefix[svc_key]
                    for n in range(1, max_images + 1):
                        df.at[idx, f"{prefix}_{n}"] = out_links[n - 1] if n - 1 < len(out_links) else ""

                p2.progress((i + 1) / total)
                status2.text(f"Processed {i+1}/{total}: {product}")

            status2.text("✅ Done.")
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                df.to_excel(tmp.name, index=False)
                path = tmp.name
            with open(path, "rb") as f:
                data = f.read()
            os.unlink(path)

            st.download_button(
                "📥 Download Updated Excel",
                data=data,
                file_name=f"updated_products_{time.strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

            with st.expander("Preview updated data", expanded=False):
                st.dataframe(df.head(), use_container_width=True)

    except Exception as e:
        st.error(f"❌ Error: {e}")
        st.exception(e)

if __name__ == "__main__":
    main()
