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
from logic.prompt_engine_v1 import build_autonomous_prompt
from logic.generation_v1 import generate_banner_prompt_gpt4, generate_dalle_image, get_best_dalle_size

# ---------------------------------------------------------------- Streamlit
st.set_page_config(page_title="Classic Banner Generator", page_icon="🎨", layout="wide")
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
DALLE3_QUALITY_DEFAULT = "standard"

RATIO_OPTIONS_MAP = {
    "Wide Banner (4.54:1)": (3000, 660), "Showcase (3:2)": (1500, 1000),
    "Square (1:1)": (1024, 1024), "Video Thumbnail (16:9)": (1920, 1080),
    "Custom": None
}
DEFAULT_RATIO_KEY = "Wide Banner (4.54:1)"
CUSTOM_DEFAULT_WIDTH = 3840
CUSTOM_DEFAULT_HEIGHT = 2160
PREVIEW_IMAGE_WIDTH = 220
CROPPER_ASPECT_DEFINITION_MAX_WIDTH = 700

# NEU: Preis-Mapping für DALL-E 3
DALLE3_PRICING_CHF = {
    "standard": {
        "1024x1024": 0.04,
        "1792x1024": 0.08,
        "1024x1792": 0.08,
    },
    "hd": {
        "1024x1024": 0.08,
        "1792x1024": 0.12,
        "1024x1792": 0.12,
    }
}

# ------------------------------------------------------- Session-State & Callbacks
PREFIX = "classic_bg_"

def key(k: str) -> str:
    return f"{PREFIX}{k}"

def initialize_session_state() -> None:
    defaults = {
        "image_input": None, "image_input_name": None, "img_from": None, "uploader_instance_key": 0,
        "ratio_choice": DEFAULT_RATIO_KEY, "custom_width": CUSTOM_DEFAULT_WIDTH, "custom_height": CUSTOM_DEFAULT_HEIGHT,
        "dalle_quality_choice": DALLE3_QUALITY_DEFAULT,
        "generated_dalle_prompt": None, "ai_banner_img": None, "status_message": "",
        "generation_phase": None,
        "temp_sku_input": "", "current_sku_data": None
    }
    for k, v in defaults.items():
        st.session_state.setdefault(key(k), v)
    _update_target_size_from_state()

def _update_target_size_from_state() -> None:
    if st.session_state[key("ratio_choice")] == "Custom":
        st.session_state[key("target_size")] = (st.session_state[key("custom_width")], st.session_state[key("custom_height")])
    else:
        st.session_state[key("target_size")] = RATIO_OPTIONS_MAP.get(st.session_state[key("ratio_choice")])

def _reset_ai_states() -> None:
    st.session_state[key("generated_dalle_prompt")] = None
    st.session_state[key("ai_banner_img")] = None
    st.session_state[key("status_message")] = ""
    st.session_state[key("generation_phase")] = None

def _on_parameter_change():
    _update_target_size_from_state()
    _reset_ai_states()

# -------------------------------------------------------------- UI-Funktionen
def _render_hero() -> None:
    st.markdown( """<div class="hero-section" style="padding:1.5em 1em;margin-bottom:1.5em"> <h1 style="font-size:2em">🎨 Banner Generator (Classic Vision)</h1> <p class="subtitle" style="font-size:1em">KI-Banner basierend auf einer KI-Bildbeschreibung (GPT-4o Vision → DALL·E 3).</p> </div> """, unsafe_allow_html=True)

def _render_step_header(step: int, title: str) -> None:
    st.markdown(f"<h2>{step}️⃣ Schritt {step}: {title}</h2>", unsafe_allow_html=True)

def _handle_upload() -> None:
    uploader_key_full = f"{PREFIX}uploader_{st.session_state[key('uploader_instance_key')]}"
    up_file = st.file_uploader("Bild auswählen (PNG/JPG/WEBP)", type=["png", "jpg", "jpeg", "webp"], key=uploader_key_full)
    if up_file and st.session_state.get(key("image_input_name")) != up_file.name:
        try:
            img = Image.open(up_file); img = ImageOps.exif_transpose(img).convert("RGB")
            st.session_state[key("image_input")] = img
            st.session_state[key("image_input_name")] = up_file.name
            st.session_state[key("img_from")] = "upload"
            st.session_state[key("temp_sku_input")] = ""
            st.session_state[key("uploader_instance_key")] += 1
            _reset_ai_states()
            st.rerun()
        except Exception as e: st.error(f"Bild konnte nicht geladen werden: {e}")

def _handle_sku_lookup(df_skus: pd.DataFrame) -> None:
    st.text_input("SKU eingeben:", key=key("temp_sku_input"))
    if st.button("🔍 Bild via SKU suchen"):
        sku_value = st.session_state[key("temp_sku_input")].strip()
        if not sku_value: st.warning("Bitte eine SKU eingeben."); return
        if st.session_state.get(key("image_input_name")) != f"SKU:{sku_value}":
            match = df_skus[df_skus["sku"].astype(str).str.lower() == sku_value.lower()]
            if match.empty or pd.isna(match.iloc[0]["image_url"]):
                st.error(f"Für SKU '{sku_value}' wurde kein gültiges Bild gefunden."); return
            try:
                resp = requests.get(match.iloc[0]["image_url"], timeout=15); resp.raise_for_status()
                img = Image.open(BytesIO(resp.content)); img = ImageOps.exif_transpose(img).convert("RGB")
                st.session_state[key("image_input")] = img
                st.session_state[key("image_input_name")] = f"SKU:{sku_value}"
                st.session_state[key("img_from")] = "sku"
                st.session_state[key("uploader_instance_key")] += 1
                _reset_ai_states()
                st.rerun()
            except Exception as e: st.error(f"SKU-Bild konnte nicht geladen werden: {e}")

def _get_dalle3_cost() -> str:
    """Ermittelt die Kosten für die DALL-E 3 Generierung basierend auf der aktuellen Auswahl."""
    try:
        quality = st.session_state[key("dalle_quality_choice")]
        w, h = st.session_state[key("target_size")]
        native_size = get_best_dalle_size(w / h if h > 0 else 1)
        
        cost = DALLE3_PRICING_CHF.get(quality, {}).get(native_size)
        if cost is not None:
            return f"~{cost:.2f} CHF"
        return "N/A"
    except Exception:
        return "N/A"

def _select_format_and_quality() -> None:
    col_format, col_quality = st.columns(2)
    with col_format:
        st.markdown("##### Format")
        ratio_opts_keys = list(RATIO_OPTIONS_MAP.keys())
        st.radio("Seitenverhältnis:", ratio_opts_keys, key=key("ratio_choice"), on_change=_on_parameter_change)
        if st.session_state[key("ratio_choice")] == "Custom":
            c1, c2 = st.columns(2)
            c1.number_input("Breite (px)", min_value=1, key=key("custom_width"), value=st.session_state[key("custom_width")], on_change=_on_parameter_change)
            c2.number_input("Höhe (px)", min_value=1, key=key("custom_height"), value=st.session_state[key("custom_height")], on_change=_on_parameter_change)

    with col_quality:
        st.markdown("##### KI-Qualität (DALL·E 3)")
        st.radio("Qualität:", ["standard", "hd"], key=key("dalle_quality_choice"), on_change=_on_parameter_change, horizontal=True)


def _perform_generation_flow() -> None:
    if st.session_state[key("generation_phase")] == "prompting":
        st.session_state[key("status_message")] = "🧠 GPT-4o analysiert Bild und erstellt Prompt..."
        with st.spinner(st.session_state[key("status_message")]):
            try:
                prompt_template = build_autonomous_prompt()
                generated_prompt = generate_banner_prompt_gpt4(st.session_state[key("image_input")], prompt_template)
                st.session_state[key("generated_dalle_prompt")] = generated_prompt
                st.session_state[key("generation_phase")] = "imaging"
                st.rerun()
            except Exception as e:
                st.error(f"Fehler bei Prompt-Generierung: {e}")
                st.session_state[key("generation_phase")] = None

    if st.session_state[key("generation_phase")] == "imaging":
        quality = st.session_state[key("dalle_quality_choice")]
        st.session_state[key("status_message")] = f"🖼️ DALL·E 3 generiert Banner (Qualität: {quality})..."
        with st.spinner(st.session_state[key("status_message")]):
            try:
                _update_target_size_from_state() # Sicherstellen, dass target_size aktuell ist
                w, h = st.session_state[key("target_size")]
                dalle_size_str = get_best_dalle_size(w / h if h > 0 else 1)
                img_url = generate_dalle_image(st.session_state[key("generated_dalle_prompt")], dalle_size_str, quality=quality)
                resp = requests.get(img_url, timeout=45); resp.raise_for_status()
                img = Image.open(BytesIO(resp.content))
                st.session_state[key("ai_banner_img")] = img.convert("RGB")
                st.session_state[key("status_message")] = "✅ Banner erfolgreich generiert!"
            except Exception as e:
                st.error(f"Fehler bei Banner-Generierung: {e}")
            finally:
                st.session_state[key("generation_phase")] = None

def _crop_and_download() -> None:
    img_to_crop = st.session_state[key("ai_banner_img")]
    if not img_to_crop: return 
    target_w, target_h = st.session_state[key("target_size")]
    if CROPPER_AVAILABLE:
        aspect_def_w, aspect_def_h = target_w, target_h
        if aspect_def_w > CROPPER_ASPECT_DEFINITION_MAX_WIDTH:
            scale = CROPPER_ASPECT_DEFINITION_MAX_WIDTH / aspect_def_w
            aspect_def_w = int(aspect_def_w * scale); aspect_def_h = int(aspect_def_h * scale)
        if aspect_def_h <= 0: aspect_def_h = 1
        cropped_pil_img = st_cropper(img_to_crop, realtime_update=True, box_color="#8c133a", aspect_ratio=(aspect_def_w, aspect_def_h), key=key("cropper"))
        final_image = cropped_pil_img.resize((target_w, target_h), Image.Resampling.LANCZOS)
    else: st.warning("`streamlit-cropper` nicht installiert."); final_image = img_to_crop
    st.image(final_image, caption=f"Vorschau Banner ({target_w}×{target_h}px)", width=400)
    img_byte_buffer = BytesIO(); save_kwargs_dl = {}
    if OUTPUT_IMAGE_FORMAT == "JPEG":
        save_kwargs_dl["quality"] = OUTPUT_IMAGE_QUALITY_DOWNLOAD
        if final_image.mode in ("RGBA", "P"): final_image = final_image.convert("RGB")
    final_image.save(img_byte_buffer, format=OUTPUT_IMAGE_FORMAT, **save_kwargs_dl)
    st.download_button(f"📥 Banner herunterladen ({target_w}×{target_h}px)", data=img_byte_buffer.getvalue(), file_name=f"classic_banner_{target_w}x{target_h}.{OUTPUT_IMAGE_EXTENSION}", mime=OUTPUT_IMAGE_MIME, type="primary", use_container_width=True)

# ---------------------------------------------------- Haupt-Page
def banner_generator_classic_page() -> None:
    initialize_session_state()
    df_skus = load_sku_data(SKU_CSV_FILENAME)
    _render_hero()
    
    _render_step_header(1, "Bildquelle & Format")
    up_col, sku_col = st.columns([0.6, 0.4])
    with up_col: _handle_upload()
    with sku_col: _handle_sku_lookup(df_skus)

    if not st.session_state[key("image_input")]:
        st.info("Bitte zuerst ein Bild hochladen oder per SKU laden."); st.stop()

    st.image(st.session_state[key("image_input")], caption=f"Inspiration: {st.session_state[key('image_input_name')]}", width=PREVIEW_IMAGE_WIDTH)
    st.markdown("---")
    _select_format_and_quality()
    
    # Sicherstellen, dass target_size aktuell ist, bevor die Caption gerendert wird
    _update_target_size_from_state() 
    tw, th = st.session_state[key("target_size")]
    
    # Kosten berechnen und anzeigen
    cost_estimate = _get_dalle3_cost()
    quality_display = st.session_state[key('dalle_quality_choice')].upper()
    
    st.caption(f"📐 Zielgröße für Zuschnitt: {tw}x{th}px | 🎨 DALL·E 3 Qualität: {quality_display} | 💰 Geschätzte Kosten: {cost_estimate}")
    st.caption("<small><i>*Die Kosten für die Bildanalyse durch GPT-4o Vision sind hier nicht eingerechnet (typ. < 0.01 CHF).</i></small>", unsafe_allow_html=True)


    _render_step_header(2, "KI-Banner generieren")
    if st.button("🚀 KI-Banner generieren", type="primary", use_container_width=True, disabled=st.session_state[key("generation_phase")] is not None):
        st.session_state[key("generation_phase")] = "prompting"
        st.rerun()
    
    _perform_generation_flow()

    if st.session_state[key("generated_dalle_prompt")]:
        with st.expander("💡 Generierter DALL·E Prompt", expanded=False):
            st.code(st.session_state[key("generated_dalle_prompt")], language='text')

    if st.session_state[key("ai_banner_img")]:
        _render_step_header(3, "Ergebnis ansehen & herunterladen")
        _crop_and_download()
    
    if st.session_state[key("generation_phase")] is None and st.session_state[key("status_message")]:
        if "✅" in st.session_state[key("status_message")]:
            st.success(st.session_state[key("status_message")])
        else:
            st.error(st.session_state[key("status_message")])
        st.session_state[key("status_message")] = ""

if __name__ == "__main__":
    banner_generator_classic_page()