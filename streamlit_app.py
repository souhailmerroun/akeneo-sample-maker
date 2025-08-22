#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import streamlit as st
import os
import time
import random
import requests
import pandas as pd
from typing import Optional, Tuple, Dict
import tempfile
from pathlib import Path
from PIL import Image
import io

# Import all three services
from bing import BingService
from openverse import OpenverseService
from duckduckgo import DuckDuckGoService
from imgbb import ImgbbUploader

# =========================
# 🔧 SETTINGS
# =========================
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/123 Safari/537.36"
TIMEOUT = 20
SLEEP_BETWEEN_UPLOADS = (0.6, 1.2)
SAVE_ROOT = "./product_images"  # Hardcoded local save path

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

def display_image_preview(image_bytes: bytes, caption: str, width: int = 120):
    """Display image preview with caption in a compact format"""
    try:
        image = Image.open(io.BytesIO(image_bytes))
        # Resize image to fit within the specified width while maintaining aspect ratio
        aspect_ratio = image.height / image.width
        height = int(width * aspect_ratio)
        image = image.resize((width, height), Image.Resampling.LANCZOS)
        st.image(image, caption=caption, width=width, use_column_width=False)
    except Exception as e:
        st.error(f"Error displaying image: {e}")

def create_service_card(service_name: str, status: str = "waiting", **kwargs):
    """Create a service card with different states"""
    card_style = """
        border: 2px solid #e0e0e0;
        border-radius: 8px;
        padding: 15px;
        margin: 5px;
        background-color: #ffffff;
        min-height: 180px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-align: center;
    """
    if status == "waiting":
        card_style += "border-color: #cccccc; background-color: #f8f9fa;"
        content = f"""
        <div style="{card_style}">
            <h4 style="margin: 0 0 10px 0; color: #666;">{service_name}</h4>
            <p style="margin: 0; color: #999;">⏳ Waiting...</p>
        </div>
        """
    elif status == "searching":
        card_style += "border-color: #ffc107; background-color: #fff3cd;"
        content = f"""
        <div style="{card_style}">
            <h4 style="margin: 0 0 10px 0; color: #856404;">{service_name}</h4>
            <p style="margin: 0; color: #856404;">🔍 Searching...</p>
        </div>
        """
    elif status == "downloading":
        card_style += "border-color: #17a2b8; background-color: #d1ecf1;"
        content = f"""
        <div style="{card_style}">
            <h4 style="margin: 0 0 10px 0; color: #0c5460;">{service_name}</h4>
            <p style="margin: 0; color: #0c5460;">📥 Downloading...</p>
        </div>
        """
    elif status == "saving":
        card_style += "border-color: #28a745; background-color: #d4edda;"
        content = f"""
        <div style="{card_style}">
            <h4 style="margin: 0 0 10px 0; color: #155724;">{service_name}</h4>
            <p style="margin: 0; color: #155724;">💾 Saving...</p>
        </div>
        """
    elif status == "uploading":
        card_style += "border-color: #6f42c1; background-color: #e2d9f3;"
        content = f"""
        <div style="{card_style}">
            <h4 style="margin: 0 0 10px 0; color: #4a148c;">{service_name}</h4>
            <p style="margin: 0; color: #4a148c;">☁️ Uploading...</p>
        </div>
        """
    elif status == "success":
        card_style += "border-color: #28a745; background-color: #d4edda;"
        content = f"""
        <div style="{card_style}">
            <h4 style="margin: 0 0 10px 0; color: #155724;">{service_name}</h4>
            <p style="margin: 0; color: #155724;">✅ Success!</p>
        </div>
        """
    elif status == "skip":
        card_style += "border-color: #6c757d; background-color: #e2e3e5;"
        content = f"""
        <div style="{card_style}">
            <h4 style="margin: 0 0 10px 0; color: #383d41;">{service_name}</h4>
            <p style="margin: 0; color: #383d41;">⏭️ Skip</p>
        </div>
        """
    elif status == "error":
        card_style += "border-color: #dc3545; background-color: #f8d7da;"
        content = f"""
        <div style="{card_style}">
            <h4 style="margin: 0 0 10px 0; color: #721c24;">{service_name}</h4>
            <p style="margin: 0; color: #721c24;">❌ Error</p>
            <p style="margin: 5px 0 0 0; color: #721c24; font-size: 0.8em;">{kwargs.get('error', 'Unknown error')}</p>
        </div>
        """
    elif status == "no_image":
        card_style += "border-color: #ffc107; background-color: #fff3cd;"
        content = f"""
        <div style="{card_style}">
            <h4 style="margin: 0 0 10px 0; color: #856404;">{service_name}</h4>
            <p style="margin: 0; color: #856404;">⚠️ No image</p>
        </div>
        """

    return content

def create_product_card(product_name: str, row_num: int, total_rows: int, services_results: Dict = None):
    """Create a product card with service cards that update in real-time"""
    # Card header
    st.markdown(f"""
    <div style="
        border: 2px solid #e0e0e0;
        border-radius: 10px;
        padding: 20px;
        margin: 15px 0;
        background-color: #f8f9fa;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    ">
        <h3 style="margin: 0 0 10px 0; color: #1f77b4;"> {product_name}</h3>
        <p style="margin: 0 0 20px 0; color: #666; font-size: 0.9em;">Row {row_num}/{total_rows}</p>
    """, unsafe_allow_html=True)

    # Create three columns for services
    col1, col2, col3 = st.columns(3)

    # Service names and their display columns
    services = [
        ("bing", "Bing", col1),
        ("openverse", "Openverse", col2),
        ("duckduckgo", "DuckDuckGo", col3)
    ]

    # Display service cards
    for service_key, service_name, display_col in services:
        with display_col:
            if services_results and service_key in services_results:
                result = services_results[service_key]
                if result["status"] == "success":
                    display_image_preview(
                        result["image_bytes"],
                        f"{service_name} - {product_name}",
                        width=120
                    )
                    st.success("✅ Success!")
                    st.caption(f"URL: {result['url'][:40]}...")
                    if result.get("imgbb_url"):
                        st.caption(f"ImgBB: {result['imgbb_url'][:40]}...")
                elif result["status"] == "skip":
                    st.markdown(create_service_card(service_name, "skip"), unsafe_allow_html=True)
                elif result["status"] == "no_image":
                    st.markdown(create_service_card(service_name, "no_image"), unsafe_allow_html=True)
                elif result["status"] == "error":
                    st.markdown(create_service_card(service_name, "error", error=result.get("error", "Unknown error")), unsafe_allow_html=True)
            else:
                # Show waiting state
                st.markdown(create_service_card(service_name, "waiting"), unsafe_allow_html=True)

    # Close the card
    st.markdown("</div>", unsafe_allow_html=True)

# =========================
# Streamlit App
# =========================
def main():
    st.set_page_config(
        page_title="Image Search & Upload Tool",
        page_icon="🖼️",
        layout="wide"
    )

    st.title("🖼️ Image Search & Upload Tool")
    st.markdown("Search for product images using multiple services and upload them to ImgBB")

    # Sidebar configuration
    st.sidebar.header("⚙️ Configuration")

    # File upload
    uploaded_file = st.sidebar.file_uploader(
        "Upload Excel file",
        type=['xlsx', 'xls'],
        help="Upload an Excel file with product names"
    )

    # Column selection
    product_col = st.sidebar.text_input(
        "Product Name Column",
        value="Product Name",
        help="Name of the column containing product names"
    )

    image_col = st.sidebar.text_input(
        "Image URL Column (read-only)",
        value="Image URL",
        help="Name of the column containing existing image URLs (will not be overwritten)"
    )

    # New column names
    col_bing = st.sidebar.text_input("Bing Column", value="image_bing")
    col_openverse = st.sidebar.text_input("Openverse Column", value="image_openverse")
    col_ddg = st.sidebar.text_input("DuckDuckGo Column", value="image_duckduckgo")

    # Options
    force_overwrite = st.sidebar.checkbox("Force Overwrite", value=True)

    # Local save info (hardcoded)
    st.sidebar.info(f"📁 Images will be saved locally to: `{os.path.abspath(SAVE_ROOT)}`")

    # Main content area
    if uploaded_file is not None:
        try:
            df = pd.read_excel(uploaded_file)
            st.success(f"✅ Successfully loaded Excel file with {len(df)} rows")

            # Display preview
            st.subheader("📊 Data Preview")
            st.dataframe(df.head(), use_container_width=True)

            # Check if required columns exist
            if product_col not in df.columns:
                st.error(f"❌ Column '{product_col}' not found in the Excel file")
                st.write("Available columns:", list(df.columns))
                return

            # Ensure new columns exist
            for col in [col_bing, col_openverse, col_ddg]:
                if col not in df.columns:
                    df[col] = ""

            # Display current status
            st.subheader("📈 Current Status")
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("Total Rows", len(df))
            with col2:
                st.metric("Bing Images", df[col_bing].notna().sum())
            with col3:
                st.metric("Openverse Images", df[col_openverse].notna().sum())
            with col4:
                st.metric("DuckDuckGo Images", df[col_ddg].notna().sum())

            # Process button
            if st.button(" Start Processing", type="primary"):
                # Initialize services
                services: Dict[str, object] = {
                    "bing": BingService(user_agent=UA, timeout=TIMEOUT),
                    "openverse": OpenverseService(user_agent=UA, timeout=TIMEOUT),
                    "duckduckgo": DuckDuckGoService(user_agent=UA, timeout=TIMEOUT),
                }

                service_to_column = {
                    "bing": col_bing,
                    "openverse": col_openverse,
                    "duckduckgo": col_ddg,
                }

                uploader = ImgbbUploader()

                # Progress tracking
                progress_bar = st.progress(0)
                status_text = st.empty()

                # Create detailed progress container that keeps history
                progress_container = st.container()
                with progress_container:
                    st.subheader("🔄 Processing Progress")

                total = len(df)
                updates = {col_bing: 0, col_openverse: 0, col_ddg: 0}

                # Create results container
                results_container = st.container()

                for i in range(total):
                    idx = df.index[i]
                    product_val = df.at[idx, product_col]
                    product = str(product_val).strip() if pd.notna(product_val) else ""
                    if not product:
                        product = f"Product_{i+1}"  # default name if blank

                    # Update progress
                    progress = (i + 1) / total
                    progress_bar.progress(progress)
                    status_text.text(f"Processing {i+1}/{total}: {product}")

                    # --- ONE PLACEHOLDER PER PRODUCT (prevents duplicate rows) ---
                    with progress_container:
                        if i > 0:
                            st.markdown("---")  # visual separator between products
                        product_placeholder = st.empty()
                        # Initial waiting card inside the placeholder
                        with product_placeholder.container():
                            create_product_card(product, i+1, total)

                    # Process each service
                    product_results: Dict[str, Dict] = {}

                    for key, service in services.items():
                        col = service_to_column[key]
                        existing_val = df.at[idx, col]
                        existing = str(existing_val).strip() if pd.notna(existing_val) else ""

                        if existing and not force_overwrite:
                            product_results[key] = {"status": "skip"}
                            continue

                        try:
                            url = service.first_image_url(product)
                        except Exception as e:
                            product_results[key] = {"status": "error", "error": str(e)}
                            continue

                        if not url:
                            product_results[key] = {"status": "no_image"}
                            continue

                        # Download image
                        raw, ct = _download_image(url)
                        if not raw:
                            product_results[key] = {"status": "error", "error": "Download failed"}
                            continue

                        # Save locally (always)
                        local_path = _save_one_local(product, url, raw, ct, key)

                        # Upload to ImgBB
                        up = uploader.upload(raw, display_name=f"{product} ({key})", content_type=ct)
                        if up:
                            df.at[idx, col] = up
                            updates[col] += 1
                            product_results[key] = {
                                "status": "success",
                                "image_bytes": raw,
                                "url": url,
                                "imgbb_url": up,
                                "local_path": local_path
                            }
                        else:
                            product_results[key] = {
                                "status": "success",
                                "image_bytes": raw,
                                "url": url,
                                "local_path": local_path
                            }

                        time.sleep(random.uniform(*SLEEP_BETWEEN_UPLOADS))

                    # Update the SAME placeholder with final results
                    product_placeholder.empty()
                    with product_placeholder.container():
                        create_product_card(product, i+1, total, product_results)

                # Final results
                progress_bar.progress(1.0)
                status_text.text("✅ Processing complete!")
                st.success("🎉 Processing completed successfully!")

                # Display results
                with results_container:
                    st.subheader(" Results Summary")
                    col1, col2, col3, col4 = st.columns(4)

                    with col1:
                        st.metric("Total Rows", total)
                    with col2:
                        st.metric("Bing Images", updates[col_bing])
                    with col3:
                        st.metric("Openverse Images", updates[col_openverse])
                    with col4:
                        st.metric("DuckDuckGo Images", updates[col_ddg])

                # Download updated Excel
                st.subheader("💾 Download Results")

                # Create temporary file
                with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
                    df.to_excel(tmp_file.name, index=False)
                    tmp_file_path = tmp_file.name

                # Read the file for download
                with open(tmp_file_path, 'rb') as f:
                    excel_data = f.read()

                # Clean up
                os.unlink(tmp_file_path)

                st.download_button(
                    label="📥 Download Updated Excel File",
                    data=excel_data,
                    file_name=f"updated_products_{time.strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

                # Display updated data
                st.subheader("📊 Updated Data Preview")
                st.dataframe(df.head(), use_container_width=True)

        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
            st.exception(e)

    else:
        st.info("📁 Please upload an Excel file to get started")

        # Show sample format
        st.subheader("📋 Expected Excel Format")
        sample_data = {
            "Product Name": ["Sample Product 1", "Sample Product 2", "Sample Product 3"],
            "Image URL": ["", "", ""],
            "image_bing": ["", "", ""],
            "image_openverse": ["", "", ""],
            "image_duckduckgo": ["", "", ""]
        }
        sample_df = pd.DataFrame(sample_data)
        st.dataframe(sample_df, use_container_width=True)

        st.markdown("""
        **Instructions:**
        1. Upload an Excel file with a column containing product names
        2. Configure the column names and options in the sidebar
        3. Click "Start Processing" to search for images
        4. Download the updated Excel file with image URLs

        **Features:**
        - Always processes ALL rows in the Excel file
        - Always saves images locally to `./product_images/`
        - Uses a placeholder so each product renders **one** row that updates in place
        - Keeps complete history of all processed products (separated by horizontal rules)
        """)

if __name__ == "__main__":
    main()
