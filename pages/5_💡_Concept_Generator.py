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
from utils import load_css
from logic.prompt_engine_concept import CATEGORIZED_ART_STYLES, build_concept_prompt
from logic.generation_v1 import generate_dalle_image, get_best_dalle_size
from logic.generation_advanced import generate_image_with_gpt_image_1_from_text, get_best_gpt_image_1_size

# ---------------------------------------------------------------- Streamlit
st.set_page_config(page_title="Concept Generator", page_icon="💡", layout="wide")
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
DEFAULT_MODEL = "DALL·E 3"

RATIO_OPTIONS_MAP = {
    "Wide Banner (4.54:1)": (3000, 660), "Showcase (3:2)": (1500, 1000),
    "Square (1:1)": (1024, 1024), "Video Thumbnail (16:9)": (1920, 1080), "Custom": None
}
DEFAULT_RATIO_KEY = "Wide Banner (4.54:1)"
CUSTOM_DEFAULT_WIDTH = 3840
CUSTOM_DEFAULT_HEIGHT = 2160
CROPPER_ASPECT_DEFINITION_MAX_WIDTH = 700

DALLE3_PRICING_CHF = {
    "standard": {"1024x1024": 0.04, "1792x1024": 0.08, "1024x1792": 0.08},
    "hd": {"1024x1024": 0.08, "1792x1024": 0.12, "1024x1792": 0.12}
}
GPT_IMAGE_1_PRICING_CHF = {"low": 0.01, "medium": 0.015, "high": 0.03, "auto": 0.015}
PROMPT_ENHANCEMENT_COST_CHF = 0.01

# ------------------------------------------------------- Session-State & Callbacks
PREFIX = "concept_bg_"

def key(k: str) -> str:
    return f"{PREFIX}{k}"

def initialize_session_state() -> None:
    defaults = {
        "subject": "A lush vineyard in tuscany at sunrise", 
        "style_category_choice": "Malerische & Künstlerische Stile", # Default Kategorie
        "style_choice": "Watercolor", # Default Stil
        "direct_prompt_mode": False, "model_choice": DEFAULT_MODEL,
        "ratio_choice": DEFAULT_RATIO_KEY, "custom_width": CUSTOM_DEFAULT_WIDTH, "custom_height": CUSTOM_DEFAULT_HEIGHT,
        "dalle_quality_choice": "standard", "gpt_quality_choice": "medium",
        "generated_dalle_prompt": None, "ai_banner_img": None, "status_message": "", "is_generating": False
    }
    for k, v in defaults.items(): st.session_state.setdefault(key(k), v)
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

def _on_parameter_change():
    _update_target_size_from_state()
    _reset_ai_states()

def _on_category_change():
    """Wird aufgerufen, wenn die Kategorie sich ändert, um den Stil-State zurückzusetzen."""
    selected_category = st.session_state[key("style_category_choice")]
    # Setze den Stil auf den ersten in der neuen Kategorie
    st.session_state[key("style_choice")] = CATEGORIZED_ART_STYLES[selected_category][0]
    _on_parameter_change() # Führe auch den allgemeinen Reset aus

# -------------------------------------------------------------- UI-Funktionen
def _render_hero() -> None:
    st.markdown( """<div class="hero-section" style="padding:1.5em 1em;margin-bottom:1.5em"> <h1 style="font-size:2em">💡 Concept Generator</h1> <p class="subtitle" style="font-size:1em">Erstelle Banner aus Stichwörtern, einem Stil und dem KI-Modell deiner Wahl.</p> </div> """, unsafe_allow_html=True)

def _render_step_header(step: int, title: str) -> None:
    st.markdown(f"<h2>{step}️⃣ Schritt {step}: {title}</h2>", unsafe_allow_html=True)

def _get_total_cost() -> str:
    try:
        model = st.session_state[key("model_choice")]
        w, h = st.session_state[key("target_size")]
        ratio = w / h if h > 0 else 1
        
        if model == "DALL·E 3":
            quality = st.session_state[key("dalle_quality_choice")]
            native_size = get_best_dalle_size(ratio)
            gen_cost = DALLE3_PRICING_CHF.get(quality, {}).get(native_size, 0)
        else: # GPT-Image-1
            quality = st.session_state[key("gpt_quality_choice")]
            gen_cost = GPT_IMAGE_1_PRICING_CHF.get(quality, 0)

        total_cost = gen_cost
        if not st.session_state[key("direct_prompt_mode")]:
            total_cost += PROMPT_ENHANCEMENT_COST_CHF
        return f"~{total_cost:.2f} CHF"
    except Exception: return "N/A"

def _select_options() -> None:
    # --- Modus & Eingabe ---
    st.checkbox("Eigenen Prompt direkt verwenden (Expertenmodus)", key=key("direct_prompt_mode"), on_change=_on_parameter_change)
    direct_mode = st.session_state[key("direct_prompt_mode")]
    subject_label = "Eigener Prompt:" if direct_mode else "Motiv / Thema:"
    st.text_area(subject_label, key=key("subject"), height=100, on_change=_on_parameter_change)
    
    # --- Kategorisierte Stilauswahl ---
    col_cat, col_style = st.columns(2)
    with col_cat:
        st.selectbox("Stil-Kategorie:", list(CATEGORIZED_ART_STYLES.keys()), 
                     key=key("style_category_choice"), 
                     on_change=_on_category_change, 
                     disabled=direct_mode)
    with col_style:
        selected_category = st.session_state[key("style_category_choice")]
        available_styles = CATEGORIZED_ART_STYLES[selected_category]
        st.selectbox("Künstlerischer Stil:", available_styles, 
                     key=key("style_choice"), 
                     on_change=_on_parameter_change, 
                     disabled=direct_mode)
    
    st.markdown("---")
    
    # --- Modell, Qualität & Format ---
    col_model, col_quality = st.columns(2)
    with col_model:
        st.markdown("##### KI-Modell")
        st.radio("Modell wählen:", ["DALL·E 3", "GPT-Image-1"], key=key("model_choice"), on_change=_on_parameter_change, horizontal=True)
    with col_quality:
        st.markdown("##### KI-Qualität")
        if st.session_state[key("model_choice")] == "DALL·E 3":
            st.radio("Qualität:", ["standard", "hd"], key=key("dalle_quality_choice"), on_change=_on_parameter_change, horizontal=True)
        else:
            st.radio("Qualität:", ["auto", "low", "medium", "high"], key=key("gpt_quality_choice"), on_change=_on_parameter_change, horizontal=True)
    
    st.markdown("##### Format")
    st.radio("Seitenverhältnis:", list(RATIO_OPTIONS_MAP.keys()), key=key("ratio_choice"), on_change=_on_parameter_change)
    if st.session_state[key("ratio_choice")] == "Custom":
        c1, c2 = st.columns(2)
        c1.number_input("Breite (px)", min_value=1, key=key("custom_width"), value=st.session_state[key("custom_width")], on_change=_on_parameter_change)
        c2.number_input("Höhe (px)", min_value=1, key=key("custom_height"), value=st.session_state[key("custom_height")], on_change=_on_parameter_change)

def _perform_generation() -> None: # Unverändert
    prompt_input = st.session_state[key("subject")].strip()
    if not prompt_input: st.warning("Bitte geben Sie ein Motiv oder einen Prompt ein."); return
    
    st.session_state[key("is_generating")] = True; _reset_ai_states(); st.session_state[key("is_generating")] = True
    
    model_choice = st.session_state[key("model_choice")]
    status_message = f"🖼️ {model_choice} generiert Banner..."
    with st.spinner(status_message):
        try:
            _update_target_size_from_state()
            prompt = prompt_input if st.session_state[key("direct_prompt_mode")] else build_concept_prompt(prompt_input, st.session_state[key("style_choice")])
            st.session_state[key("generated_dalle_prompt")] = prompt
            
            w, h = st.session_state[key("target_size")]
            ratio = w / h if h > 0 else 1

            if model_choice == "DALL·E 3":
                quality = st.session_state[key("dalle_quality_choice")]
                native_size = get_best_dalle_size(ratio)
                img_url = generate_dalle_image(prompt, native_size, quality)
                resp = requests.get(img_url, timeout=45); resp.raise_for_status()
                img = Image.open(BytesIO(resp.content))
            else:
                quality = st.session_state[key("gpt_quality_choice")]
                native_size = get_best_gpt_image_1_size(ratio)
                img = generate_image_with_gpt_image_1_from_text(prompt, native_size, quality)

            st.session_state[key("ai_banner_img")] = img.convert("RGB")
            st.session_state[key("status_message")] = "✅ Banner erfolgreich generiert!"
        except Exception as e: st.session_state[key("status_message")] = f"Fehler bei Banner-Generierung: {e}"
        finally: st.session_state[key("is_generating")] = False

def _crop_and_download() -> None: # Unverändert
    img_to_crop = st.session_state[key("ai_banner_img")]
    if not img_to_crop: return 
    target_w, target_h = st.session_state[key("target_size")]
    if CROPPER_AVAILABLE:
        aspect_def_w, aspect_def_h = target_w, target_h
        if aspect_def_w > CROPPER_ASPECT_DEFINITION_MAX_WIDTH:
            scale = CROPPER_ASPECT_DEFINITION_MAX_WIDTH / aspect_def_w
            aspect_def_w, aspect_def_h = int(aspect_def_w * scale), int(aspect_def_h * scale)
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
    st.download_button(f"📥 Banner herunterladen ({target_w}×{target_h}px)", data=img_byte_buffer.getvalue(), file_name=f"concept_banner_{target_w}x{target_h}.{OUTPUT_IMAGE_EXTENSION}", mime=OUTPUT_IMAGE_MIME, type="primary", use_container_width=True)

# ---------------------------------------------------- Haupt-Page
def concept_generator_page() -> None:
    initialize_session_state()
    _render_hero()
    
    _render_step_header(1, "Konzept definieren")
    _select_options()
    
    _update_target_size_from_state()
    tw, th = st.session_state[key("target_size")]
    cost = _get_total_cost()
    st.caption(f"📐 Zielgröße: {tw}x{th}px | 🤖 Modell: {st.session_state[key('model_choice')]} | 💰 Geschätzte Gesamtkosten: {cost}")
    cost_explanation = "*Gesamtkosten = Prompt-Anreicherung + Bildgenerierung.*" if not st.session_state[key("direct_prompt_mode")] else "*Gesamtkosten = Nur Bildgenerierung.*"
    st.caption(f"<small><i>{cost_explanation}</i></small>", unsafe_allow_html=True)

    _render_step_header(2, "KI-Banner generieren")
    if st.button("🚀 KI-Banner generieren", type="primary", use_container_width=True, disabled=st.session_state[key("is_generating")]):
        _perform_generation(); st.rerun()

    if not st.session_state[key("is_generating")]:
        prompt_expander_label = "💡 Generierter Prompt (KI-erweitert)" if not st.session_state[key("direct_prompt_mode")] else "📝 Eigener Prompt"
        if st.session_state[key("generated_dalle_prompt")]:
            with st.expander(prompt_expander_label, expanded=True):
                st.code(st.session_state[key("generated_dalle_prompt")], language='text')
        status = st.session_state[key("status_message")]
        if "✅" in status: st.success(status)
        elif "Fehler" in status: st.error(status)
    
    if st.session_state[key("ai_banner_img")]:
        _render_step_header(3, "Ergebnis ansehen & herunterladen")
        _crop_and_download()
    elif not st.session_state[key("is_generating")]:
        st.info("Klicke auf '🚀 KI-Banner generieren', um dein Konzept zu visualisieren.")

# -------------------------------------------------------------------- Main
if __name__ == "__main__":
    concept_generator_page()