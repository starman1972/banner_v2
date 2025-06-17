import streamlit as st
from PIL import Image
import os
import time
import requests
from io import BytesIO
import sys
import openai

# --- Pfade und Imports ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

# Utils mit der neuen get_secret Funktion importieren
from utils import load_css, get_secret
from logic.generation_v1 import generate_dalle_image
from logic.generation_stability import generate_image_with_stability_ai, get_best_stability_aspect_ratio
from logic.generation_google import generate_image_with_google_imagen
from logic.generation_advanced import generate_image_with_gpt_image_1_from_text, get_best_gpt_image_1_size
from logic.generation_fal import generate_image_with_fal_flux_pro, generate_image_with_fal_flux_ultra, generate_image_with_ideogram_v3

# --- Streamlit Page Konfiguration ---
st.set_page_config(page_title="AI Model Testbed", page_icon="🔬", layout="wide")
load_css()

# --- Konstanten ---
RATIO_OPTIONS_MAP_TESTBED = {"Landscape (16:9)": (1920, 1080), "Square (1:1)": (1024, 1024), "Portrait (9:16)": (1080, 1920)}
# ... (Rest der Konstanten unverändert) ...
DALLE3_SIZE_MAP = {"Landscape (16:9)": "1792x1024", "Square (1:1)": "1024x1024", "Portrait (9:16)": "1024x1792"}
DALLE3_PRICING_CHF = {"hd": {"1024x1024": 0.08, "1792x1024": 0.12, "1024x1792": 0.12}}
GPT_IMAGE_1_PRICING_CHF = {"high": 0.03}
STABILITY_AI_PRICING_CHF = {"Ultra": 0.08}
GOOGLE_IMAGEN_PRICING_CHF = {"Standard": 0.02}
FAL_AI_PRICING_CHF = {"FLUX.1 Pro": "N/A", "FLUX.1.1 Ultra": "N/A", "Ideogram 3.0": "N/A"}

# --- Session-State ---
PREFIX = "testbed_"
def key(k: str) -> str: return f"{PREFIX}{k}"
def initialize_session_state():
    defaults = {
        "prompt": "Hyperrealistic photograph of a single perfect red grape on a rustic wooden table, with a soft, out-of-focus vineyard in the background, golden hour lighting, cinematic.",
        "models_to_run": ["DALL·E 3", "GPT-Image-1"], "ratio_choice": "Landscape (16:9)",
        "results": {}, "is_generating": False,
    }
    for k, v in defaults.items(): st.session_state.setdefault(key(k), v)

# --- UI-Funktionen und Logik (unverändert) ---
def _render_hero():
    st.markdown( """<div class="hero-section" style="padding:1.5em 1em;margin-bottom:1.5em"> <h1 style="font-size:2em">🔬 AI Model Testbed</h1> <p class="subtitle" style="font-size:1em">Vergleiche die Ergebnisse verschiedener KI-Bildgenerierungsmodelle.</p> </div> """, unsafe_allow_html=True)

def _select_options():
    st.text_area("Master Prompt:", key=key("prompt"), height=150, help="Gib hier den Prompt ein, der an alle ausgewählten Modelle gesendet wird.")
    available_models = ["DALL·E 3", "GPT-Image-1", "Google Imagen 2", "Stability AI (Ultra)", "FLUX.1 Pro", "FLUX.1.1 Ultra", "Ideogram 3.0"]
    st.multiselect("Modelle zum Testen auswählen:", options=available_models, key=key("models_to_run"))
    st.radio("Seitenverhältnis:", list(RATIO_OPTIONS_MAP_TESTBED.keys()), key=key("ratio_choice"), horizontal=True)

def _get_cost_estimate_text() -> str:
    #... (Diese Funktion bleibt unverändert)
    models = st.session_state.get(key("models_to_run"), [])
    if not models: return "Bitte Modelle auswählen."
    cost_texts = []
    for model in models:
        cost_str = ""
        if model == "DALL·E 3":
            cost = DALLE3_PRICING_CHF["hd"].get(DALLE3_SIZE_MAP[st.session_state[key("ratio_choice")]], 0)
            cost_str = f"DALL·E 3 (HD): ~{cost:.2f} CHF"
        elif model == "GPT-Image-1":
            cost = GPT_IMAGE_1_PRICING_CHF["high"]
            cost_str = f"GPT-Image-1 (High): ~{cost:.2f} CHF"
        elif model == "Google Imagen 2":
            cost = GOOGLE_IMAGEN_PRICING_CHF["Standard"]
            cost_str = f"Google Imagen 2: ~{cost:.2f} CHF"
        elif model == "Stability AI (Ultra)":
            cost = STABILITY_AI_PRICING_CHF["Ultra"]
            cost_str = f"Stability AI (Ultra): ~{cost:.2f} CHF"
        elif model == "FLUX.1 Pro":
            cost = FAL_AI_PRICING_CHF["FLUX.1 Pro"]
            cost_str = f"FLUX.1 Pro: {cost}"
        elif model == "FLUX.1.1 Ultra":
            cost = FAL_AI_PRICING_CHF["FLUX.1.1 Ultra"]
            cost_str = f"FLUX.1.1 Ultra: {cost}"
        elif model == "Ideogram 3.0":
            cost = FAL_AI_PRICING_CHF["Ideogram 3.0"]
            cost_str = f"Ideogram 3.0: {cost}"
        cost_texts.append(cost_str)
    return " | ".join(cost_texts)

def _perform_generation():
    #... (Diese Funktion bleibt unverändert)
    st.session_state[key("is_generating")] = True
    st.session_state[key("results")] = {}
    prompt = st.session_state[key("prompt")]
    models = st.session_state[key("models_to_run")]
    ratio_key = st.session_state[key("ratio_choice")]
    target_w, target_h = RATIO_OPTIONS_MAP_TESTBED[ratio_key]

    if not prompt.strip(): st.warning("Bitte einen Prompt eingeben."); st.session_state[key("is_generating")] = False; return
    if not models: st.warning("Bitte mindestens ein Modell zum Testen auswählen."); st.session_state[key("is_generating")] = False; return

    progress_bar = st.progress(0, text="Starte Generierung...")
    preferred_order = ["DALL·E 3", "GPT-Image-1", "Google Imagen 2", "Stability AI (Ultra)", "FLUX.1 Pro", "FLUX.1.1 Ultra", "Ideogram 3.0"]
    models_to_run_sorted = sorted(models, key=lambda m: preferred_order.index(m) if m in preferred_order else 99)

    for i, model_name in enumerate(models_to_run_sorted):
        text = f"Generiere mit {model_name}..."; st.info(text)
        progress_bar.progress((i + 1) / len(models_to_run_sorted), text=text)
        try:
            start_time = time.time(); image_result = None
            if model_name == "DALL·E 3":
                dalle_size = DALLE3_SIZE_MAP[ratio_key]
                image_url = generate_dalle_image(prompt, dalle_size, quality="hd")
                response = requests.get(image_url, timeout=45); response.raise_for_status()
                image_result = Image.open(BytesIO(response.content))
            elif model_name == "GPT-Image-1":
                gpt_size = get_best_gpt_image_1_size(target_w / target_h if target_h > 0 else 1)
                image_result = generate_image_with_gpt_image_1_from_text(prompt, gpt_size, quality="high")
            elif model_name == "Google Imagen 2":
                image_result = generate_image_with_google_imagen(prompt, target_w, target_h)
            elif model_name == "Stability AI (Ultra)":
                stability_ratio_str = get_best_stability_aspect_ratio(target_w, target_h)
                image_result = generate_image_with_stability_ai(prompt, stability_ratio_str)
            elif model_name == "FLUX.1 Pro":
                fal_ratio_str = get_best_stability_aspect_ratio(target_w, target_h)
                image_result = generate_image_with_fal_flux_pro(prompt, fal_ratio_str)
            elif model_name == "FLUX.1.1 Ultra":
                fal_ratio_str = get_best_stability_aspect_ratio(target_w, target_h)
                image_result = generate_image_with_fal_flux_ultra(prompt, fal_ratio_str)
            elif model_name == "Ideogram 3.0":
                fal_ratio_str = get_best_stability_aspect_ratio(target_w, target_h)
                image_result = generate_image_with_ideogram_v3(prompt, fal_ratio_str)

            end_time = time.time()
            if image_result:
                st.session_state[key("results")][model_name] = {"image": image_result, "time": end_time - start_time, "error": None}
        except Exception as e:
            st.session_state[key("results")][model_name] = {"image": None, "time": None, "error": str(e)}
    st.session_state[key("is_generating")] = False

# --- Haupt-Page ---
def testbed_page():
    # --- START DER KORREKTUR ---
    # API-Schlüssel sicher laden mit der neuen Hilfsfunktion
    openai.api_key = get_secret("OPENAI_API_KEY")
    
    # Für Bibliotheken, die os.environ nutzen
    stability_key = get_secret("STABILITY_API_KEY")
    if stability_key:
        os.environ["STABILITY_API_KEY"] = stability_key
        
    fal_key = get_secret("FAL_KEY")
    if fal_key:
        os.environ["FAL_KEY"] = fal_key

    # Google Credentials werden von der `generation_google`-Logik selbst geholt.
    # Wir müssen hier nichts tun, außer sicherstellen, dass die .env-Variablen
    # (für lokale Entwicklung) durch load_dotenv() in Image_Tools_Hub.py geladen werden.

    # Optionale Prüfung, ob die Keys vorhanden sind
    if not all([openai.api_key, stability_key, fal_key]):
        st.warning("Ein oder mehrere API-Schlüssel (OpenAI, Stability, Fal) wurden nicht gefunden. Einige Modelle werden nicht funktionieren.")
    # --- ENDE DER KORREKTUR ---

    initialize_session_state()
    _render_hero()
    _select_options()
    st.caption(f"💰 Geschätzte Kosten pro Bild: {_get_cost_estimate_text()}")

    if st.button("🚀 Modelle vergleichen", type="primary", use_container_width=True, disabled=st.session_state[key("is_generating")]):
        _perform_generation(); st.rerun()

    if st.session_state[key("results")]:
        st.markdown("---"); st.markdown("<h2>Ergebnisse</h2>", unsafe_allow_html=True)
        preferred_order = ["DALL·E 3", "GPT-Image-1", "Google Imagen 2", "Stability AI (Ultra)", "FLUX.1 Pro", "FLUX.1.1 Ultra", "Ideogram 3.0"]
        valid_results = {k: v for k, v in st.session_state[key("results")].items() if v}
        sorted_results = {k: valid_results[k] for k in preferred_order if k in valid_results}

        if sorted_results:
            cols = st.columns(len(sorted_results))
            for i, (model_name, result) in enumerate(sorted_results.items()):
                with cols[i]:
                    st.subheader(model_name)
                    if result["error"]: st.error(f"Fehler: {result['error']}")
                    elif result["image"]: st.image(result["image"], caption=f"Generiert in {result['time']:.2f} Sekunden", use_container_width=True)
                    else: st.warning("Kein Bild generiert.")

if __name__ == "__main__":
    testbed_page()