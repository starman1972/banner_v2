import streamlit as st
from PIL import Image, ImageOps
from io import BytesIO
import os
import pandas as pd
import requests
from dotenv import load_dotenv
import sys

# -------------------------------------------------------------------- Pfade
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

# -------------------------------------------------------------------- Imports
from utils import load_css, load_sku_data, SKU_CSV_FILENAME
from logic.prompt_engine_v2 import (
    build_gpt_image_1_banner_prompt,
    build_gpt_image_1_banner_with_text_prompt,
)
from logic.generation_v2 import generate_banner_with_gpt_image_1, get_best_dalle_size

# ---------------------------------------------------------------- Streamlit
st.set_page_config(page_title="Banner Generator", page_icon="🚀", layout="wide")
load_css()

# ---------------------------------------------------------------- OpenAI-Key
load_dotenv(os.path.join(project_root, ".env"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    st.error("OpenAI API-Key fehlt. Bitte in `.env` setzen.")
    st.stop()
import openai
openai.api_key = OPENAI_API_KEY

# -------------------------------------------------------- optionale Abhängigkeit
try:
    from streamlit_cropper import st_cropper
    CROPPER_AVAILABLE = True
except ImportError:
    CROPPER_AVAILABLE = False

# ---------------------------------------------------------------- Konstanten
OUTPUT_IMAGE_FORMAT = "JPEG"
OUTPUT_IMAGE_QUALITY_DOWNLOAD = 95
OUTPUT_IMAGE_EXTENSION = OUTPUT_IMAGE_FORMAT.lower()
OUTPUT_IMAGE_MIME = f"image/{OUTPUT_IMAGE_EXTENSION}"
GPT_IMAGE_1_GENERATION_QUALITY_DEFAULT = "medium"

RATIO_OPTIONS_MAP = {
    "Wide Banner (4.54:1)": (3000, 660),
    "Showcase (3:2)": (1500, 1000),
    "Square (1:1)": (1024, 1024),
    "Video Thumbnail (16:9)": (1920, 1080),
    "Custom": None
}
DEFAULT_RATIO_KEY = "Wide Banner (4.54:1)"
CUSTOM_DEFAULT_WIDTH = 3840
CUSTOM_DEFAULT_HEIGHT = 2160
PREVIEW_IMAGE_WIDTH = 220
CROPPER_ASPECT_DEFINITION_MAX_WIDTH = 700

# ------------------------------------------------------- Session-State & Callbacks
def initialize_session_state() -> None:
    defaults = {
        "banner_gen_image_input": None, "banner_gen_image_input_name": None, "banner_gen_img_from": None,
        "uploader_instance_key": 0,
        "banner_gen_ratio_choice": DEFAULT_RATIO_KEY,
        "banner_gen_custom_width": CUSTOM_DEFAULT_WIDTH, "banner_gen_custom_height": CUSTOM_DEFAULT_HEIGHT,
        "banner_gen_quality_choice": GPT_IMAGE_1_GENERATION_QUALITY_DEFAULT,
        "banner_gen_include_text": False, "banner_gen_user_text": "", "banner_gen_text_position": "zentral",
        "banner_gen_instruction_prompt_for_gpt_image_1": None, "banner_gen_ai_banner_img": None,
        "banner_gen_status_message": "", "banner_gen_is_generating": False,
        "temp_sku_input": "", "banner_gen_current_sku_data": None
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)
    
    _update_target_size_from_state()

def _update_target_size_from_state() -> None:
    if st.session_state.banner_gen_ratio_choice == "Custom":
        st.session_state.banner_gen_target_size = (
            st.session_state.banner_gen_custom_width,
            st.session_state.banner_gen_custom_height,
        )
    else:
        st.session_state.banner_gen_target_size = RATIO_OPTIONS_MAP.get(
            st.session_state.banner_gen_ratio_choice, RATIO_OPTIONS_MAP[DEFAULT_RATIO_KEY]
        )

def _reset_ai_states() -> None:
    st.session_state.banner_gen_ai_banner_img = None
    st.session_state.banner_gen_instruction_prompt_for_gpt_image_1 = None
    st.session_state.banner_gen_status_message = ""

def _on_parameter_change():
    """Einziger Callback für alle Format/Qualität/Text-Widgets. Aktualisiert abhängige States."""
    _update_target_size_from_state()
    _reset_ai_states()

# -------------------------------------------------------------- UI-Funktionen
def _render_hero() -> None:
    st.markdown( """<div class="hero-section" style="padding:1.5em 1em;margin-bottom:1.5em"> <h1 style="font-size:2em">🚀 Banner Generator (GPT-Image-1)</h1> <p class="subtitle" style="font-size:1em">Erzeuge KI-Banner auf Basis deines Produktbildes.</p> </div> """, unsafe_allow_html=True, )

def _render_step_header(step: int, title: str) -> None:
    st.markdown(f"<h2>{step}️⃣ Schritt {step}: {title}</h2>", unsafe_allow_html=True)

def _handle_upload() -> None:
    uploader_key = f"banner_gen_uploader_{st.session_state.uploader_instance_key}"
    up_file = st.file_uploader( "Bild auswählen (PNG/JPG/WEBP)", type=["png", "jpg", "jpeg", "webp"], key=uploader_key)
    if up_file:
        if st.session_state.get("banner_gen_image_input_name") != up_file.name or st.session_state.get("banner_gen_img_from") != "upload":
            try:
                img = Image.open(up_file); img = ImageOps.exif_transpose(img).convert("RGB")
                st.session_state.banner_gen_image_input = img
                st.session_state.banner_gen_image_input_name = up_file.name
                st.session_state.banner_gen_img_from = "upload"
                st.session_state.banner_gen_current_sku_data = None
                st.session_state.temp_sku_input = ""
                st.session_state.uploader_instance_key += 1
                _reset_ai_states()
                st.rerun()
            except Exception as e: st.error(f"Bild konnte nicht geladen werden: {e}")

def _handle_sku_lookup(df_skus: pd.DataFrame) -> None:
    st.text_input("SKU eingeben:", key="temp_sku_input")
    if st.button("🔍 Bild via SKU suchen"):
        sku_value = st.session_state.temp_sku_input.strip()
        if not sku_value: st.warning("Bitte eine SKU eingeben."); return

        if st.session_state.get("banner_gen_image_input_name") != f"SKU:{sku_value}" or st.session_state.get("banner_gen_img_from") != "sku":
            match = df_skus[df_skus["sku"].astype(str).str.lower() == sku_value.lower()]
            if match.empty or pd.isna(match.iloc[0]["image_url"]):
                st.error(f"Für SKU '{sku_value}' wurde kein gültiges Bild gefunden."); return
            try:
                resp = requests.get(match.iloc[0]["image_url"], timeout=15); resp.raise_for_status()
                img = Image.open(BytesIO(resp.content)); img = ImageOps.exif_transpose(img).convert("RGB")
                st.session_state.banner_gen_image_input = img
                st.session_state.banner_gen_image_input_name = f"SKU:{sku_value}"
                st.session_state.banner_gen_img_from = "sku"
                st.session_state.banner_gen_current_sku_data = match.iloc[0].to_dict()
                st.session_state.uploader_instance_key += 1
                _reset_ai_states()
                st.rerun()
            except Exception as e: st.error(f"SKU-Bild konnte nicht geladen werden: {e}")

def _select_options() -> None:
    # --- Format
    ratio_opts_keys = list(RATIO_OPTIONS_MAP.keys())
    st.radio( "Seitenverhältnis:", ratio_opts_keys, key="banner_gen_ratio_choice", on_change=_on_parameter_change )
    
    if st.session_state.banner_gen_ratio_choice == "Custom":
        col_w, col_h = st.columns(2)
        with col_w:
            st.number_input(
                "Breite (px)",
                min_value=1,
                key="banner_gen_custom_width",
                value=st.session_state.banner_gen_custom_width, # KORREKTUR: Explizit den Wert setzen
                on_change=_on_parameter_change
            )
        with col_h:
            st.number_input(
                "Höhe (px)",
                min_value=1,
                key="banner_gen_custom_height",
                value=st.session_state.banner_gen_custom_height, # KORREKTUR: Explizit den Wert setzen
                on_change=_on_parameter_change
            )
    
    # --- Qualität
    qual_opts = ["auto", "low", "medium", "high"]
    st.radio( "KI-Qualität:", qual_opts, key="banner_gen_quality_choice", on_change=_on_parameter_change, horizontal=True )
    
    # --- Text
    st.checkbox("Text in Banner integrieren?", key="banner_gen_include_text", on_change=_on_parameter_change)
    if st.session_state.banner_gen_include_text:
        st.text_area( "Zu integrierender Text:", key="banner_gen_user_text", placeholder="Dein Banner-Text …", on_change=_on_parameter_change )
        st.radio( "Textposition (KI-Vorschlag):", ["zentral", "oben", "unten", "links", "rechts"], key="banner_gen_text_position", on_change=_on_parameter_change, horizontal=True )

def _perform_banner_generation() -> None:
    if not st.session_state.banner_gen_image_input: return
    st.session_state.banner_gen_is_generating = True
    _reset_ai_states()
    st.session_state.banner_gen_is_generating = True
    
    st.session_state.banner_gen_status_message = f"🎨 GPT-Image-1 generiert Banner (Qualität: {st.session_state.banner_gen_quality_choice}) …"
    with st.spinner(st.session_state.banner_gen_status_message):
        try:
            _update_target_size_from_state()
            user_text_final = st.session_state.banner_gen_user_text.strip()
            use_text_prompt = st.session_state.banner_gen_include_text and user_text_final
            prompt = build_gpt_image_1_banner_with_text_prompt(user_text_final, st.session_state.banner_gen_text_position) \
                if use_text_prompt else build_gpt_image_1_banner_prompt()
            st.session_state.banner_gen_instruction_prompt_for_gpt_image_1 = prompt
            
            w, h = st.session_state.banner_gen_target_size
            dalle_size_str = get_best_dalle_size(w / h if h > 0 else 1)
            img_result = generate_banner_with_gpt_image_1(
                st.session_state.banner_gen_image_input, prompt, dalle_size_str, st.session_state.banner_gen_quality_choice
            )
            st.session_state.banner_gen_ai_banner_img = img_result
            st.session_state.banner_gen_status_message = "✅ Banner erfolgreich generiert!"
        except Exception as e: st.session_state.banner_gen_status_message = f"Fehler bei Bannergenerierung: {e}"
        finally: st.session_state.banner_gen_is_generating = False

def _crop_and_download() -> None: # Unverändert
    img_to_crop = st.session_state.banner_gen_ai_banner_img
    if not img_to_crop: return 
    target_w, target_h = st.session_state.banner_gen_target_size
    if CROPPER_AVAILABLE:
        aspect_def_w, aspect_def_h = target_w, target_h
        if aspect_def_w > CROPPER_ASPECT_DEFINITION_MAX_WIDTH:
            scale = CROPPER_ASPECT_DEFINITION_MAX_WIDTH / aspect_def_w
            aspect_def_w = int(aspect_def_w * scale); aspect_def_h = int(aspect_def_h * scale)
        if aspect_def_h <= 0: aspect_def_h = 1
        aspect_tuple_for_cropper = (aspect_def_w, aspect_def_h)
        cropped_pil_img = st_cropper( img_to_crop, realtime_update=True, box_color="#8c133a", aspect_ratio=aspect_tuple_for_cropper, key="banner_gen_cropper_widget", )
        final_image_to_display = cropped_pil_img.resize((target_w, target_h), Image.Resampling.LANCZOS)
    else: st.warning("`streamlit-cropper` nicht installiert."); final_image_to_display = img_to_crop
    st.image(final_image_to_display, caption=f"Vorschau Banner ({target_w}×{target_h}px)", width=400)
    img_byte_buffer = BytesIO(); save_kwargs_dl = {}
    download_image = final_image_to_display
    if OUTPUT_IMAGE_FORMAT == "JPEG":
        save_kwargs_dl["quality"] = OUTPUT_IMAGE_QUALITY_DOWNLOAD
        if download_image.mode in ("RGBA", "P"): download_image = download_image.convert("RGB")
    download_image.save(img_byte_buffer, format=OUTPUT_IMAGE_FORMAT, **save_kwargs_dl)
    st.download_button( f"📥 Banner herunterladen ({target_w}×{target_h}px - .{OUTPUT_IMAGE_EXTENSION})", data=img_byte_buffer.getvalue(), file_name=f"wine_banner_{target_w}x{target_h}.{OUTPUT_IMAGE_EXTENSION}", mime=OUTPUT_IMAGE_MIME, type="primary", use_container_width=True, )

# ---------------------------------------------------- Haupt-Page
def banner_generator_page() -> None:
    initialize_session_state()
    df_skus = load_sku_data(SKU_CSV_FILENAME)
    _render_hero()
    
    # --- Schritt 1: Bildquelle ---
    _render_step_header(1, "Bildquelle wählen")
    up_col, sku_col = st.columns([0.6, 0.4])
    with up_col: _handle_upload()
    with sku_col: _handle_sku_lookup(df_skus)

    if not st.session_state.banner_gen_image_input:
        st.info("Bitte zuerst ein Bild hochladen oder per SKU laden."); st.stop()

    st.image( st.session_state.banner_gen_image_input, caption=f"Inspiration: {st.session_state.banner_gen_image_input_name}", width=PREVIEW_IMAGE_WIDTH, )
    st.markdown("---")
    
    # --- Schritt 2: Optionen ---
    _render_step_header(2, "Format, Qualität & Textoptionen")
    _select_options()
    
    # --- Anzeige der aktuellen Einstellungen ---
    # `_on_parameter_change` hat `_update_target_size_from_state` bereits aufgerufen
    tw_display, th_display = st.session_state.banner_gen_target_size
    st.caption(f"📐 Zielgröße für Zuschnitt: {tw_display}x{th_display}px | "
               f"🎨 Gewählte KI-Qualität: {st.session_state.banner_gen_quality_choice}")

    # --- Schritt 3: Generierung ---
    st.markdown("---")
    _render_step_header(3, "KI-Banner generieren")

    if st.button("🚀 KI-Banner generieren (GPT-Image-1)", type="primary", use_container_width=True, disabled=st.session_state.banner_gen_is_generating):
        _perform_banner_generation()
        st.rerun()

    if not st.session_state.banner_gen_is_generating:
        if st.session_state.banner_gen_instruction_prompt_for_gpt_image_1 :
            with st.expander("📜 Verwendeter KI-Prompt", expanded=False):
                st.code(st.session_state.banner_gen_instruction_prompt_for_gpt_image_1, language='text')
        
        current_status = st.session_state.banner_gen_status_message
        if "✅ Banner erfolgreich generiert!" in current_status:
            st.success(current_status)
        elif "Fehler" in current_status or "API-Fehler" in current_status:
            st.error(current_status)

    # --- Schritt 4: Ergebnis & Download ---
    if st.session_state.banner_gen_ai_banner_img and not st.session_state.banner_gen_is_generating:
        st.markdown("---")
        _render_step_header(4, "Ergebnis ansehen & herunterladen")
        _crop_and_download()
    elif not st.session_state.banner_gen_is_generating:
        st.markdown("---")
        st.info("Klicke auf '🚀 KI-Banner generieren', um das Banner zu erstellen.")

# -------------------------------------------------------------------- Main
if __name__ == "__main__":
    banner_generator_page()