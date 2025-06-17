import streamlit as st
from PIL import Image, ImageOps
import pandas as pd
import io
import os
import requests
from rembg import remove
import base64 # Für die Base64-Kodierung der Bilder für HTML
from typing import Tuple, Optional, List, Any
from streamlit.runtime.uploaded_file_manager import UploadedFile # type: ignore

# Importe aus utils.py
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

from utils import load_css, load_sku_data, SKU_CSV_FILENAME

# --- Seitenkonfiguration ---
st.set_page_config(
    page_title="Background Remover",
    page_icon="✏️",
    layout="centered"
)
load_css()

# --- Konstanten für diese Seite ---
TARGET_PREVIEW_HEIGHT: int = 300
SUPPORTED_IMAGE_TYPES_BG_REMOVER: List[str] = ["png", "jpg", "jpeg", "webp"]
REQUESTS_TIMEOUT_BG_REMOVER: int = 15

# --- Session State Initialisierung für diese Seite ---
def initialize_bg_remover_session_state() -> None:
    prefix = "bg_remover_"
    session_defaults: dict[str, Any] = {
        prefix + "original_image_pil": None,
        prefix + "freigestelltes_image_pil": None,
        prefix + "current_sku": None,
        prefix + "image_source_name": None,
        prefix + "sku_input_text": "",
        prefix + "last_uploaded_file_id": None,
        prefix + "processing_error": None,
    }
    for key, value in session_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

def reset_bg_remover_images() -> None:
    prefix = "bg_remover_"
    st.session_state[prefix + "original_image_pil"] = None
    st.session_state[prefix + "freigestelltes_image_pil"] = None
    st.session_state[prefix + "current_sku"] = None
    st.session_state[prefix + "image_source_name"] = None
    st.session_state[prefix + "processing_error"] = None

# --- Helper Funktionen für diese Seite ---
def process_and_store_image(image_bytes: bytes, source_name: str, sku: Optional[str] = None) -> None:
    prefix = "bg_remover_"
    reset_bg_remover_images()
    st.session_state[prefix + "image_source_name"] = source_name
    st.session_state[prefix + "current_sku"] = sku
    original_pil_temp = None

    try:
        with st.spinner("Lade Originalbild..."):
            img_opened = Image.open(io.BytesIO(image_bytes))
            img_exif_corrected = ImageOps.exif_transpose(img_opened)
            original_pil_temp = img_exif_corrected.convert("RGBA") # Immer RGBA für konsistente Behandlung
            st.session_state[prefix + "original_image_pil"] = original_pil_temp

        if original_pil_temp:
            with st.spinner("Entferne Hintergrund... Dies kann einen Moment dauern."):
                buffer = io.BytesIO()
                original_pil_temp.save(buffer, format="PNG")
                original_png_bytes_for_rembg = buffer.getvalue()

                removed_bg_bytes: bytes = remove(original_png_bytes_for_rembg)
                freigestelltes_pil = Image.open(io.BytesIO(removed_bg_bytes)).convert("RGBA")
                st.session_state[prefix + "freigestelltes_image_pil"] = freigestelltes_pil
                st.success("Hintergrund erfolgreich entfernt!")
        else:
            st.session_state[prefix + "processing_error"] = "Originalbild konnte nicht geladen werden."
            st.error(st.session_state[prefix + "processing_error"])

    except Exception as e:
        error_msg = f"Fehler bei der Bildverarbeitung ({source_name}): {e}"
        st.error(error_msg)
        st.session_state[prefix + "processing_error"] = error_msg
        if prefix + "original_image_pil" not in st.session_state or st.session_state[prefix + "original_image_pil"] is None:
             if original_pil_temp:
                 st.session_state[prefix + "original_image_pil"] = original_pil_temp
             elif image_bytes:
                try:
                    fallback_original_pil = Image.open(io.BytesIO(image_bytes))
                    fallback_original_pil = ImageOps.exif_transpose(fallback_original_pil)
                    st.session_state[prefix + "original_image_pil"] = fallback_original_pil.convert("RGBA")
                except Exception as final_e:
                    st.warning(f"Konnte Originalbild auch im Fallback nicht laden: {final_e}")

# --- Hauptanwendung für diese Seite ---
def background_remover_page() -> None:
    st.title("🪄 Automatischer Background Remover")
    st.caption("Lade ein Bild hoch oder gib eine SKU ein. Der Hintergrund wird automatisch entfernt (Ausgabe als PNG).")
    initialize_bg_remover_session_state()
    prefix = "bg_remover_"

    sku_df: pd.DataFrame = load_sku_data(SKU_CSV_FILENAME)

    with st.container(border=True):
        st.subheader("1. Bild-Input")
        # ... (Input-Logik bleibt unverändert von der vorherigen Version) ...
        input_col1, input_col2 = st.columns(2)
        with input_col1:
            st.markdown("##### Bild hochladen")
            uploaded_file: Optional[UploadedFile] = st.file_uploader(
                "Flaschenbild auswählen",
                type=SUPPORTED_IMAGE_TYPES_BG_REMOVER,
                key=prefix + "uploader_final_bg",
                label_visibility="collapsed",
                on_change=reset_bg_remover_images
            )
            if uploaded_file:
                if st.session_state[prefix + "original_image_pil"] is None or \
                   st.session_state[prefix + "image_source_name"] != uploaded_file.name:
                    if uploaded_file.file_id != st.session_state.get(prefix + "last_uploaded_file_id"):
                        st.session_state[prefix + "last_uploaded_file_id"] = uploaded_file.file_id
                        image_bytes_content: bytes = uploaded_file.read()
                        process_and_store_image(image_bytes_content, uploaded_file.name)
                        st.rerun()

        with input_col2:
            st.markdown("##### Bild via SKU laden")
            current_sku_text = st.session_state.get(prefix + "sku_input_text", "")
            new_sku_text = st.text_input(
                "Produkt SKU:", value=current_sku_text, key=prefix + "sku_input_widget_final_bg",
                label_visibility="collapsed",
                on_change=reset_bg_remover_images
            )
            if new_sku_text != current_sku_text:
                 st.session_state[prefix + "sku_input_text"] = new_sku_text

            if st.button("🔎 SKU laden & Freistellen", key=prefix + "load_sku_btn_final_bg", use_container_width=True, type="primary"):
                sku_to_load: str = st.session_state[prefix + "sku_input_text"].strip()
                if sku_to_load:
                    reset_bg_remover_images()
                    if sku_df.empty: st.error("SKU-Daten nicht geladen.")
                    else:
                        match = sku_df[sku_df["sku"] == sku_to_load]
                        if match.empty: st.error(f"SKU '{sku_to_load}' nicht gefunden.")
                        else:
                            image_url = str(match["image_url"].values[0]).strip()
                            if not image_url or not image_url.startswith("http"):
                                st.error(f"Keine gültige Bild-URL für SKU '{sku_to_load}'.")
                            else:
                                try:
                                    response = requests.get(image_url, timeout=REQUESTS_TIMEOUT_BG_REMOVER)
                                    response.raise_for_status()
                                    process_and_store_image(response.content, f"SKU_{sku_to_load}", sku_to_load)
                                except Exception as e:
                                    st.error(f"Fehler bei SKU '{sku_to_load}': {e}")
                                    st.session_state[prefix + "processing_error"] = str(e)
                    st.rerun()
                else:
                    st.warning("Bitte SKU eingeben.")


    original_image_to_display: Optional[Image.Image] = st.session_state.get(prefix + "original_image_pil")
    freigestelltes_image_to_display: Optional[Image.Image] = st.session_state.get(prefix + "freigestelltes_image_pil")
    image_source_name: Optional[str] = st.session_state.get(prefix + "image_source_name")

    if original_image_to_display:
        st.markdown("---")
        st.subheader("2. Ergebnisse")
        col_orig, col_frei = st.columns(2)

        with col_orig:
            st.markdown("##### Originalbild")
            # Konvertiere Original für HTML-Einbettung (PNG Format für Vorschau, um Alpha zu erhalten, falls vorhanden)
            buffered_orig = io.BytesIO()
            original_image_to_display.save(buffered_orig, format="PNG")
            img_str_base64_orig = base64.b64encode(buffered_orig.getvalue()).decode()

            st.markdown(
                f"""
                <div class="original-preview-container" style="max-width: 100%; text-align: center; line-height: {TARGET_PREVIEW_HEIGHT}px;">
                    <img src="data:image/png;base64,{img_str_base64_orig}" alt="Originalbild"
                         style="max-width:100%; max-height:{TARGET_PREVIEW_HEIGHT}px; object-fit:contain; vertical-align: middle;">
                </div>
                """,
                unsafe_allow_html=True
            )
            st.caption(f"Original: {image_source_name or 'Bild'}")

        if freigestelltes_image_to_display:
            with col_frei:
                st.markdown("##### Freigestelltes Bild (PNG)")
                buffered_frei = io.BytesIO()
                freigestelltes_image_to_display.save(buffered_frei, format="PNG")
                img_str_base64_frei = base64.b64encode(buffered_frei.getvalue()).decode()

                st.markdown(
                    f"""
                    <div class="transparent-preview-bg" style="max-width: 100%; text-align: center; line-height: {TARGET_PREVIEW_HEIGHT}px;">
                        <img src="data:image/png;base64,{img_str_base64_frei}" alt="Freigestelltes Bild"
                             style="max-width:100%; max-height:{TARGET_PREVIEW_HEIGHT}px; object-fit:contain; vertical-align: middle;">
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                st.caption(f"Freigestellt: {image_source_name or 'Bild'}")

                download_bytes = buffered_frei.getvalue()
                download_filename = f"freigestellt_{image_source_name or 'bild'}.png"
                st.markdown("")
                st.download_button(
                    label=f"📥 '{download_filename}' herunterladen",
                    data=download_bytes,
                    file_name=download_filename,
                    mime="image/png",
                    key=prefix + "download_freigestellt_btn_consistency",
                    use_container_width=True,
                    type="primary"
                )
        elif st.session_state.get(prefix + "processing_error"):
            with col_frei:
                st.error("Fehler bei der Freistellung.")
        elif not st.session_state.get(prefix + "processing_error"):
             with col_frei:
                st.info("Bild wird verarbeitet...")
    elif not uploaded_file and not st.session_state.get(prefix + "sku_input_text"):
        st.info("Bitte Bild hochladen oder eine SKU eingeben, um zu starten.")

if __name__ == "__main__":
    background_remover_page()