#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import base64
import io
import os
import random
import tempfile
import time
from typing import Dict, List, Tuple

import logging
import pandas as pd
import streamlit as st
from PIL import Image

from bing import BingService
from duckduckgo import DuckDuckGoService
from helpers import download_image, save_one_local
from openverse import OpenverseService

# =========================
# LOGGING
# =========================
logging.basicConfig(
    level=logging.INFO,  # set to logging.DEBUG for more detail
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# =========================
# SETTINGS
# =========================
UA = "Mozilla/5/0 (Windows NT 10.0; Win64; x64) Chrome/123 Safari/537.36".replace("5/0", "5.0")
TIMEOUT = 20
SLEEP_BETWEEN_UPLOADS = (0.6, 1.2)
SAVE_ROOT = "./product_images"

# Upload guard
UPLOAD_TIMEOUT_SECS = 25  # hard timeout per upload (seconds)

# Grid look & feel
NUM_COLS = 5          # tiles per row
TILE_IMG_HEIGHT = 200 # px; uniform tile height
TILE_PADDING = 10     # px around each tile

# =========================
# HELPERS
# =========================
def render_img_tile_from_file(local_path: str, url: str):
    """Render image tile from local file path using Streamlit's native image display."""
    try:
        # Use Streamlit's native image display - it handles file paths efficiently
        # without loading everything into memory
        st.image(
            local_path,
            width=None,  # Let it scale naturally
            use_container_width=True,  # Updated from use_column_width
            caption=f"Source: {url}"  # Display the source URL below the image
        )
    except Exception as e:
        logger.error(f"Failed to render image from {local_path}: {e}")
        # Show placeholder for broken images
        st.error("❌ Image Error")

def download_and_save_for_preview(url: str, product: str, svc_key: str) -> str:
    """Download, verify, and save image locally; return local path or None."""
    logger.debug(f"Downloading and saving for preview: {url}")
    try:
        raw, ct = download_image(url, ua=UA, timeout=TIMEOUT)
    except Exception as e:
        logger.error(f"download_image crashed for {url}: {e}")
        return None

    if not raw:
        logger.warning(f"No data returned for: {url}")
        return None
    if ct and ("image" not in ct.lower()):
        logger.warning(f"Content-Type not image ({ct}) for: {url}")
        return None
    try:
        Image.open(io.BytesIO(raw)).verify()
        logger.debug(f"Verified image ok: {url}")
        
        # Save locally and return the path
        local_path = save_one_local(product, url, raw, ct, service_key=svc_key, save_root=SAVE_ROOT)
        logger.debug(f"Saved image locally: {local_path}")
        return local_path
    except Exception as e:
        logger.error(f"Image verify failed for {url}: {e}")
        return None

# =========================
# APP
# =========================
def main():
    logger.info("App starting...")
    st.set_page_config(page_title="Image Search Tool", page_icon="🖼️", layout="wide")
    st.title("🖼️ Image Search Tool")
    st.caption("Simple grid selection • Uniform tiles • Broken images hidden")

    # --- session state ---
    if "fetched" not in st.session_state:
        st.session_state.fetched = False
        logger.debug("Initialized session_state.fetched=False")
    if "fetched_items" not in st.session_state:
        st.session_state.fetched_items: Dict[int, List[Dict]] = {}
        logger.debug("Initialized session_state.fetched_items={}")
    if "selections" not in st.session_state:
        st.session_state.selections: Dict[int, Dict[str, List[str]]] = {}
        logger.debug("Initialized session_state.selections={} ")

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
        logger.info("Waiting for Excel upload...")
        return

    try:
        logger.info("Reading uploaded Excel...")
        df = pd.read_excel(uploaded_file)
        logger.info(f"Excel loaded with {len(df)} rows and columns: {list(df.columns)}")
        if product_col not in df.columns:
            st.error(f"❌ Column '{product_col}' not found. Available: {list(df.columns)}")
            logger.error(f"Column '{product_col}' not in DataFrame columns.")
            return

        st.success(f"✅ Loaded Excel with {len(df)} rows")
        with st.expander("Preview data", expanded=False):
            st.dataframe(df.head(), use_container_width=True)

        # services
        services: Dict[str, object] = {
            "bing": BingService(user_agent=UA, timeout=TIMEOUT),
            "openverse": OpenverseService(user_agent=UA, timeout=TIMEOUT),
        }
        logger.info("Search services initialized: bing, openverse, duckduckgo")

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
            logger.info("Clear selections clicked.")
            # clear only selections & checkbox widget states (keep fetched data)
            st.session_state.selections = {}
            for k in list(st.session_state.keys()):
                if str(k).startswith("sel_"):
                    del st.session_state[k]
            st.info("Selections cleared.")

        # --- FETCH PHASE (download & save locally, filter invalid images) ---
        if fetch_clicked or st.session_state.fetched:
            if fetch_clicked:
                logger.info("Starting fresh fetch cycle...")
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
            logger.info(f"Beginning fetch across {total} rows...")

            for i, idx in enumerate(df.index):
                name_val = df.at[idx, product_col]
                product = str(name_val).strip() if pd.notna(name_val) and str(name_val).strip() else f"Product_{i+1}"
                logger.info(f"[{i+1}/{total}] Fetching images for: {product}")

                if fetch_clicked:
                    items: List[Dict] = []
                    pairs: List[Tuple[str, str]] = []
                    for key, svc in services.items():
                        try:
                            logger.debug(f"Querying {key} for '{product}' (limit={max_images})")
                            urls = svc.image_urls(product, limit=max_images)
                            logger.info(f"{key} returned {len(urls)} URLs for '{product}'")
                        except Exception as e:
                            logger.error(f"{key} error for '{product}': {e}")
                            urls = []
                        pairs.extend((key, u) for u in urls)

                    # Deduplicate URLs across all services while preserving order
                    seen_urls = set()
                    deduplicated_pairs = []
                    for svc_key, url in pairs:
                        if url not in seen_urls:
                            seen_urls.add(url)
                            deduplicated_pairs.append((svc_key, url))
                        else:
                            logger.debug(f"Skipping duplicate URL: {url}")

                    logger.info(f"After deduplication: {len(deduplicated_pairs)} unique URLs from {len(pairs)} total")

                    # Download each, save locally, and keep only valid images
                    valid_count = 0
                    for svc_key, url in deduplicated_pairs:
                        local_path = download_and_save_for_preview(url, product, svc_key)
                        if local_path:
                            valid_count += 1
                            items.append({"svc": svc_key, "url": url, "local_path": local_path})

                    st.session_state.fetched_items[idx] = items
                    logger.info(f"Valid images kept for '{product}': {valid_count}")

                # Update progress and force UI refresh
                p.progress((i + 1) / total)
                status.text(f"Fetched {i+1}/{total}")
                
                # Small delay to allow UI to update
                time.sleep(0.1)

            # --- AUTO-SELECT N (set checkbox states + selections; do NOT clear anything) ---
            if auto_select_clicked:
                logger.info(f"Auto-select clicked: selecting up to {auto_n} per product.")
                total_selected = 0
                for idx, items in st.session_state.fetched_items.items():
                    take = min(auto_n, len(items))
                    for j in range(take):
                        svc_key = items[j]["svc"]
                        url = items[j]["url"]
                        # mark as selected in our data model
                        st.session_state.selections.setdefault(idx, {}).setdefault(svc_key, [])
                        if url not in st.session_state.selections[idx][svc_key]:
                            st.session_state.selections[idx][svc_key].append(url)
                            total_selected += 1
                        # and set the checkbox widget state (no value= passed later)
                        st.session_state[f"sel_{idx}_{j}"] = True
                logger.info(f"Auto-selected total images: {total_selected}")
                st.success(f"Auto-selected up to {auto_n} per product.")

            st.markdown("---")

            # --- RENDER (skip products with zero valid images; DON'T pass value=) ---
            shown = 0
            for i, idx in enumerate(df.index):
                items = st.session_state.fetched_items.get(idx, [])
                if not items:
                    logger.debug(f"Row {i+1}: no valid images; skipping block render.")
                    continue  # no empty blocks

                st.markdown(f"#### Row {i+1}/{len(df)}")

                cols = st.columns(NUM_COLS)
                for j, item in enumerate(items):
                    svc_key, url, local_path = item["svc"], item["url"], item["local_path"]
                    ck_key = f"sel_{idx}_{j}"
                    with cols[j % NUM_COLS]:
                        checked = st.checkbox(f"[{service_labels.get(svc_key, svc_key)}] #{j+1}", key=ck_key)
                        render_img_tile_from_file(local_path, url)

                        # sync selections based on the live checkbox state
                        sel_list = st.session_state.selections.setdefault(idx, {}).setdefault(svc_key, [])
                        if checked and url not in sel_list:
                            sel_list.append(url)
                            logger.debug(f"Selected [{svc_key}] {url}")
                        if not checked and url in sel_list:
                            sel_list.remove(url)
                            logger.debug(f"Deselected [{svc_key}] {url}")

                st.markdown("---")
                shown += 1

            if shown == 0:
                logger.warning("No valid images found across all products.")
                st.warning("No valid images were found across all products.")
            else:
                logger.info(f"Rendered {shown} product blocks with images.")

        # --- EXPORT PHASE ---
        st.subheader("💾 Save selections & export")
        run_export = st.button("☁️ Export Excel")

        if run_export:
            logger.info("Starting export phase...")
            # Ensure per-service columns exist up to max_images
            for svc_key, prefix in service_prefix.items():
                for n in range(1, max_images + 1):
                    colname = f"{prefix}_{n}"
                    if colname not in df.columns:
                        df[colname] = ""
                        logger.debug(f"Added column to DataFrame: {colname}")

            # Export the Excel file with the original URLs
            total = len(df)
            p2 = st.progress(0.0)
            status2 = st.empty()

            for i, idx in enumerate(df.index):
                name_val = df.at[idx, product_col]
                product = str(name_val).strip() if pd.notna(name_val) and str(name_val).strip() else f"Product_{i+1}"
                logger.info(f"[{i+1}/{total}] Processing export for: {product}")

                row_sel = st.session_state.selections.get(idx, {})
                if not row_sel:
                    logger.info(f"{product}: no selections; skipping.")
                    p2.progress((i + 1) / total)
                    status2.text(f"Processed {i+1}/{total}: {product} (no selections)")
                    continue

                for svc_key, urls in row_sel.items():
                    chosen = urls[:max_images]
                    out_links: List[str] = []
                    logger.info(f"{product}: {svc_key} -> {len(chosen)} images to upload")

                    for k, u in enumerate(chosen, start=1):
                        local_path = st.session_state.fetched_items[idx][0]["local_path"]
                        out_links.append(u)  # keep the original URLs

                    # write to columns _1.._N; blanks for the rest
                    prefix = service_prefix[svc_key]
                    for n in range(1, max_images + 1):
                        df.at[idx, f"{prefix}_{n}"] = out_links[n - 1] if n - 1 < len(out_links) else ""

                p2.progress((i + 1) / total)
                status2.text(f"Processed {i+1}/{total}: {product}")

            logger.info(f"Export phase complete.")
            status2.text("✅ Done.")
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                df.to_excel(tmp.name, index=False)
                path = tmp.name
                logger.debug(f"Temporary Excel saved at: {path}")
            with open(path, "rb") as f:
                data = f.read()
            os.unlink(path)
            logger.debug("Temporary Excel file removed.")

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
        logger.exception(f"Unhandled error: {e}")  # keeps traceback in console
        st.exception(e)

if __name__ == "__main__":
    main()
