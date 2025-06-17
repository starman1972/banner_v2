import streamlit as st
import os
import sys
from dotenv import load_dotenv

# .env-Datei laden (wichtig für die lokale Entwicklung)
load_dotenv()

# Pfad zum Projekt-Root hinzufügen, damit 'utils' gefunden wird
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from utils import load_css

# --- Seitenkonfiguration ---
st.set_page_config(
    page_title="Image Tools Hub",
    page_icon="🛠️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS laden ---
load_css("style.css")

# --- Hauptseite ---
st.title("🛠️ Willkommen im Image Tools Hub")

st.markdown(
    """
    Dies ist die zentrale Anlaufstelle für eine Sammlung von KI-gestützten Bildbearbeitungs- und Generierungswerkzeugen.

    **Bitte wählen Sie ein Werkzeug aus der Seitenleiste links, um zu beginnen.**

    Verfügbare Tools umfassen unter anderem:
    - **🚀 Banner Generator (Direct)**: Erzeugt Banner direkt aus einem Produktbild mit `gpt-image-1`.
    - **🎨 Banner Generator (Classic)**: Nutzt einen 2-Stufen-Prozess (GPT-4o Vision → DALL·E 3).
    - **✏️ Background Remover**: Entfernt automatisch den Hintergrund von Bildern.
    - **✂️ Image Optimizer**: Interaktives Zuschneiden und Optimieren von Bildern.
    - **💡 Concept Generator**: Erzeugt Bilder aus textuellen Ideen und Stilen.
    - **🔬 Model Testbed**: Vergleicht die Ergebnisse verschiedener Bildmodelle.
    - **✍️ Prompt Generator**: Erstellt hochwertige Prompts für Bild-KIs.
    """
)

st.info(
    "Jede Seite ist ein eigenständiges Tool. API-Schlüssel und Konfigurationen werden aus der `.env`-Datei im Projektverzeichnis geladen.",
    icon="ℹ️"
)