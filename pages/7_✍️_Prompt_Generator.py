import streamlit as st
from PIL import Image, ImageOps
import os
import requests
from io import BytesIO
import sys
import pandas as pd

# --------------------------------------------------------------------
# Pfade und Imports
# --------------------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

from utils import load_css, load_sku_data, SKU_CSV_FILENAME
from logic.prompt_engine_concept import CATEGORIZED_ART_STYLES, build_concept_prompt
from logic.generation_v1 import generate_banner_prompt_gpt4
from logic.prompt_engine_origin import build_origin_prompt

# --------------------------------------------------------------------
# Streamlit Page Konfiguration
# --------------------------------------------------------------------
st.set_page_config(page_title="Prompt Generator", page_icon="✍️", layout="wide")
load_css()

# --------------------------------------------------------------------
# API-Key Initialisierung
# --------------------------------------------------------------------
from dotenv import load_dotenv
load_dotenv(os.path.join(project_root, ".env"))
import openai
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    st.error("OPENAI_API_KEY nicht in .env gefunden.")
    st.stop()

# --------------------------------------------------------------------
# Konstanten
# --------------------------------------------------------------------
PREVIEW_IMAGE_WIDTH = 220

# --------------------------------------------------------------------
# Session-State
# --------------------------------------------------------------------
PREFIX = "prompt_gen_"
def key(k: str) -> str: return f"{PREFIX}{k}"

def initialize_session_state():
    defaults = {
        # Modus 1: Konzept
        "concept_subject": "Ein Weinberg in der Toskana bei Sonnenaufgang",
        "concept_style_category": "Malerische & Künstlerische Stile",
        "concept_style": "Watercolor",
        # Modus 2: SKU
        "sku_input": "",
        "sku_image": None,
        # Modus 3: Herkunft
        "origin_wine_type": "Lagrein",
        "origin_region": "Südtirol, Italien",
        "origin_mood": "Realistisch & Elegant",
        # Allgemein
        "generated_prompt": "",
        "is_generating": False,
    }
    for k, v in defaults.items(): st.session_state.setdefault(key(k), v)

# --------------------------------------------------------------------
# Hilfsfunktionen
# --------------------------------------------------------------------
def _render_hero():
    st.markdown( """<div class="hero-section" style="padding:1.5em 1em;margin-bottom:1.5em"> <h1 style="font-size:2em">✍️ Prompt Generator</h1> <p class="subtitle" style="font-size:1em">Erstelle hochwertige Prompts für KI-Bildgeneratoren auf verschiedene Weisen.</p> </div> """, unsafe_allow_html=True)

def _display_generated_prompt():
    """Zeigt das Textfeld für den generierten Prompt an."""
    if st.session_state[key("generated_prompt")]:
        st.markdown("---")
        st.markdown("#### Ihr generierter Prompt:")
        st.code(
            st.session_state[key("generated_prompt")],
            language='text',
            line_numbers=False, # Parameter in st.code heisst `line_numbers` nicht `show_line_numbers`
        )
        st.info("Klicken Sie auf das Kopieren-Symbol oben rechts im Prompt-Feld und verwenden Sie den Prompt im Model Testbed oder einem anderen Tool.")

# --------------------------------------------------------------------
# UI und Logik für jeden Tab
# --------------------------------------------------------------------
def tab_from_concept():
    st.markdown("#### 1. Beschreiben Sie Ihr gewünschtes Motiv")
    st.text_area("Motiv / Thema:", key=key("concept_subject"), height=100)
    
    st.markdown("#### 2. Wählen Sie einen künstlerischen Stil")
    col_cat, col_style = st.columns(2)
    with col_cat:
        st.selectbox("Stil-Kategorie:", list(CATEGORIZED_ART_STYLES.keys()), key=key("concept_style_category"))
    with col_style:
        selected_category = st.session_state[key("concept_style_category")]
        available_styles = CATEGORIZED_ART_STYLES[selected_category]
        # Setze den Stil auf den ersten in der neuen Kategorie, wenn die Kategorie sich ändert
        if st.session_state[key("concept_style")] not in available_styles:
            st.session_state[key("concept_style")] = available_styles[0]
        st.selectbox("Künstlerischer Stil:", available_styles, key=key("concept_style"))

    st.markdown("---")
    if st.button("Konzept-Prompt generieren", type="primary", use_container_width=True, disabled=st.session_state[key("is_generating")]):
        subject = st.session_state[key("concept_subject")]
        style = st.session_state[key("concept_style")]
        if not subject.strip():
            st.warning("Bitte geben Sie ein Motiv / Thema ein."); return
        
        st.session_state[key("is_generating")] = True
        with st.spinner("KI erweitert Ihre Idee zu einem detaillierten Prompt..."):
            try:
                prompt = build_concept_prompt(subject, style)
                st.session_state[key("generated_prompt")] = prompt
            except Exception as e:
                st.error(f"Fehler bei der Prompt-Erstellung: {e}")
            finally:
                st.session_state[key("is_generating")] = False

def tab_from_sku(df_skus):
    st.markdown("#### 1. Geben Sie die Produkt-SKU an")
    st.text_input("SKU:", key=key("sku_input"))
    
    if st.session_state[key("sku_image")]:
        st.image(st.session_state[key("sku_image")], caption="Analysiertes Bild", width=PREVIEW_IMAGE_WIDTH)

    st.markdown("---")
    if st.button("Bild analysieren & Prompt generieren", type="primary", use_container_width=True, disabled=st.session_state[key("is_generating")]):
        sku = st.session_state[key("sku_input")].strip()
        if not sku:
            st.warning("Bitte eine SKU eingeben."); return
            
        st.session_state[key("is_generating")] = True
        with st.spinner(f"Lade & analysiere Bild für SKU {sku}..."):
            try:
                # Bild laden
                match = df_skus[df_skus["sku"].astype(str).str.lower() == sku.lower()]
                if match.empty or pd.isna(match.iloc[0]["image_url"]):
                    st.error(f"Für SKU '{sku}' wurde kein gültiges Bild gefunden.")
                    st.session_state[key("is_generating")] = False
                    return
                
                resp = requests.get(match.iloc[0]["image_url"], timeout=15); resp.raise_for_status()
                img = Image.open(BytesIO(resp.content)); img = ImageOps.exif_transpose(img).convert("RGB")
                st.session_state[key("sku_image")] = img
                
                # Dummy-System-Prompt; der eigentliche wird in der v1-Logik verwendet
                # NOTE: Die Funktion `generate_banner_prompt_gpt4` aus logic.generation_v1 erwartet einen system_prompt.
                # In der Implementierung des Classic Banner Generators wird `build_autonomous_prompt` aus `prompt_engine_v1` verwendet.
                # Hier wurde ein leerer String übergeben, was zu Fehlern führen kann. Wir verwenden den korrekten autonomen Prompt.
                from logic.prompt_engine_v1 import build_autonomous_prompt
                system_prompt = build_autonomous_prompt()

                prompt = generate_banner_prompt_gpt4(img, system_prompt)
                st.session_state[key("generated_prompt")] = prompt

            except Exception as e:
                st.error(f"Fehler bei der SKU-Verarbeitung: {e}")
            finally:
                st.session_state[key("is_generating")] = False

def tab_from_origin():
    st.markdown("#### 1. Beschreiben Sie den Wein")
    col1, col2 = st.columns(2)
    with col1:
        st.text_input("Rebsorte / Weintyp", key=key("origin_wine_type"), help="z.B. Lagrein, Chardonnay, Rotwein-Cuvée")
    with col2:
        st.text_input("Herkunft / Region", key=key("origin_region"), help="z.B. Südtirol, Italien")
        
    st.markdown("#### 2. Wählen Sie die gewünschte Stimmung")
    st.radio("Stimmung:", ["Realistisch & Elegant", "Künstlerisch & Malerisch", "Modern & Abstrakt"], key=key("origin_mood"), horizontal=True)

    st.markdown("---")
    if st.button("Herkunfts-Prompt generieren", type="primary", use_container_width=True, disabled=st.session_state[key("is_generating")]):
        wine_type = st.session_state[key("origin_wine_type")]
        origin = st.session_state[key("origin_region")]
        mood = st.session_state[key("origin_mood")]
        if not wine_type.strip() or not origin.strip():
            st.warning("Bitte geben Sie Weintyp und Herkunft an."); return
            
        st.session_state[key("is_generating")] = True
        with st.spinner("KI erstellt einen atmosphärischen Prompt basierend auf der Herkunft..."):
            try:
                prompt = build_origin_prompt(wine_type, origin, mood)
                st.session_state[key("generated_prompt")] = prompt
            except Exception as e:
                st.error(f"Fehler bei der Prompt-Erstellung: {e}")
            finally:
                st.session_state[key("is_generating")] = False

# --------------------------------------------------------------------
# Haupt-Page
# --------------------------------------------------------------------
def prompt_generator_page():
    initialize_session_state()
    df_skus = load_sku_data(SKU_CSV_FILENAME)
    _render_hero()

    tab1, tab2, tab3 = st.tabs(["Aus Konzept", "Aus Bild (SKU)", "Aus Herkunft"])

    with tab1:
        tab_from_concept()

    with tab2:
        # Sicherstellen, dass die SKU-Daten geladen wurden, bevor der Tab verwendet wird
        if df_skus.empty:
            st.error("SKU-Daten konnten nicht geladen werden. Bitte prüfen Sie die `banner_bilder_v1.csv`.")
        else:
            tab_from_sku(df_skus)
    
    with tab3:
        tab_from_origin()
        
    # Ergebnis-Anzeige ist außerhalb der Tabs, damit sie immer sichtbar ist, wenn ein Prompt generiert wurde
    _display_generated_prompt()

if __name__ == "__main__":
    prompt_generator_page()