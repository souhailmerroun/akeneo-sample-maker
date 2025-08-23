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
NUM_COLS = 5          # tiles per row
TILE_IMG_HEIGHT = 200 # px; uniform tile height
TILE_PADDING = 10     # px around each tile

# =========================
# HELPERS
# =========================
def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")

def render_img_tile(image_bytes: bytes):
    """Uniform tile with proportional image (no stretching)."""
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
    """Download & verify image for preview; return bytes or None."""
    raw, ct = download_image(url, ua=UA, timeout=TIMEOUT)
    if not raw:
        return None
    if ct and ("image" not in ct.lower()):
        return None
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
            # clear only selections & checkbox widget states (keep fetched data)
            st.session_state.selections = {}
            for k in list(st.session_state.keys()):
                if str(k).startswith("sel_"):
                    del st.session_state[k]
            st.info("Selections cleared.")

        # --- FETCH PHASE (download & filter invalid images) ---
        if fetch_clicked or st.session_state.fetched:
            if fetch_clicked:
                st.session_state.fetched_items = {}
                st.session_state.selections = {}
                # also clear any previous checkbox keys so defaults work
                for k in list(st.session_state.keys()):
                    if str(k).startswith("sel_"):
                        del st.session_state[k]
                st.session_state.fetched = True

            total = len(df)
            p = st.progress(0.0)
            status = st.empty()

            for i, idx in enumerate(df.index):
                name_val = df.at[idx, product_col]
                product = str(name_val).strip() if pd.notna(name_val) and str(name_val).strip() else f"Product_{i+1}"

                if fetch_clicked:
                    items: List[Dict] = []
                    pairs: List[Tuple[str, str]] = []
                    for key, svc in services.items():
                        try:
                            urls = svc.image_urls(product, limit=max_images)
                        except Exception:
                            urls = []
                        pairs.extend((key, u) for u in urls)

                    # Download each for preview; keep only valid images
                    for svc_key, url in pairs:
                        img_bytes = download_for_preview(url)
                        if img_bytes:
                            items.append({"svc": svc_key, "url": url, "bytes": img_bytes})

                    st.session_state.fetched_items[idx] = items

                p.progress((i + 1) / total)
                status.text(f"Fetched {i+1}/{total}")

            # --- AUTO-SELECT N (set checkbox states + selections; do NOT clear anything) ---
            if auto_select_clicked:
                for idx, items in st.session_state.fetched_items.items():
                    take = min(auto_n, len(items))
                    for j in range(take):
                        svc_key = items[j]["svc"]
                        url = items[j]["url"]
                        # mark as selected in our data model
                        st.session_state.selections.setdefault(idx, {}).setdefault(svc_key, [])
                        if url not in st.session_state.selections[idx][svc_key]:
                            st.session_state.selections[idx][svc_key].append(url)
                        # and set the checkbox widget state (no value= passed later)
                        st.session_state[f"sel_{idx}_{j}"] = True
                st.success(f"Auto-selected up to {auto_n} per product.")

            st.markdown("---")

            # --- RENDER (skip products with zero valid images; DON'T pass value=) ---
            shown = 0
            for i, idx in enumerate(df.index):
                items = st.session_state.fetched_items.get(idx, [])
                if not items:
                    continue  # no empty blocks

                st.markdown(f"#### Row {i+1}/{len(df)}")

                cols = st.columns(NUM_COLS)
                for j, item in enumerate(items):
                    svc_key, url, img_bytes = item["svc"], item["url"], item["bytes"]
                    ck_key = f"sel_{idx}_{j}"
                    with cols[j % NUM_COLS]:
                        # Never pass a default `value=`; rely on st.session_state[ck_key] if set
                        checked = st.checkbox(f"[{service_labels.get(svc_key, svc_key)}] #{j+1}", key=ck_key)
                        render_img_tile(img_bytes)

                        # sync selections based on the live checkbox state
                        sel_list = st.session_state.selections.setdefault(idx, {}).setdefault(svc_key, [])
                        if checked and url not in sel_list:
                            sel_list.append(url)
                        if not checked and url in sel_list:
                            sel_list.remove(url)

                st.markdown("---")
                shown += 1

            if shown == 0:
                st.warning("No valid images were found across all products.")

        # --- EXPORT PHASE ---
        st.subheader("💾 Save selections & export")
        run_export = st.button("☁️ Save locally + Upload to ImgBB + Export Excel")

        if run_export:
            # Ensure per-service columns exist up to max_images
            for svc_key, prefix in service_prefix.items():
                for n in range(1, max_images + 1):
                    colname = f"{prefix}_{n}"
                    if colname not in df.columns:
                        df[colname] = ""

            uploader = ImgbbUploader()
            total = len(df)
            p2 = st.progress(0.0)
            status2 = st.empty()

            # cache preview bytes by url (speeds up uploads)
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

                    # write to columns _1.._N; blanks for the rest
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
