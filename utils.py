import streamlit as st
import pandas as pd
import os
from io import BytesIO # Nur wenn Download-Helfer hier wären

# --- Gemeinsame Konstanten ---
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
SKU_CSV_FILENAME = os.path.join(PROJECT_ROOT, "banner_bilder_v1.csv")
ASSETS_DIR = os.path.join(PROJECT_ROOT, "assets")

# --- NEUE, ROBUSTE FUNKTION ZUM LADEN VON SECRETS ---
def get_secret(key: str) -> str | None:
    """
    Ruft einen Secret-Wert sicher ab.
    Versucht zuerst, aus st.secrets zu lesen (für Streamlit Cloud).
    Wenn das fehlschlägt (lokale Ausführung), wird auf os.getenv() zurückgegriffen.
    """
    try:
        # Dieser Block wird in der Streamlit Cloud ausgeführt
        if key in st.secrets:
            return st.secrets[key]
        else:
            return None
    except st.errors.StreamlitAPIException:
        # Dieser Block wird bei lokaler Ausführung ausgeführt, da st.secrets nicht verfügbar ist
        return os.getenv(key)

# --- Bestehende Funktionen (unverändert) ---

def load_css(css_filename: str = "style.css"):
    """Lädt eine CSS-Datei aus dem assets-Ordner."""
    css_file_path = os.path.join(ASSETS_DIR, css_filename)
    try:
        with open(css_file_path) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.warning(f"CSS-Datei nicht gefunden: {css_file_path}. Stelle sicher, dass sie im '{ASSETS_DIR}' Ordner liegt.")

@st.cache_data
def load_sku_data(path: str = SKU_CSV_FILENAME) -> pd.DataFrame:
    """
    Lädt SKU-Daten aus einer CSV-Datei.
    Bereinigt Spaltennamen und behandelt potenzielle Fehler.
    """
    try:
        df = pd.read_csv(path, sep=";", encoding="utf-8-sig", dtype={"sku": str})
        df.columns = [str(col).strip().lower() for col in df.columns]

        if "sku" not in df.columns:
            st.error(f"FEHLER: Die CSV-Datei unter '{path}' muss eine Spalte 'sku' enthalten.")
            return pd.DataFrame(columns=["sku", "image_url", "background_image_url_opt"])

        df["sku"] = df["sku"].astype(str).str.strip()

        if "image_url" not in df.columns and "bild" in df.columns:
            df.rename(columns={"bild": "image_url"}, inplace=True)
        elif "image_url" not in df.columns and "bild" not in df.columns:
            df["image_url"] = None

        if "background_image_url_opt" not in df.columns and "hintergrundbild" in df.columns:
            df.rename(columns={"hintergrundbild": "background_image_url_opt"}, inplace=True)
        elif "background_image_url_opt" not in df.columns and "hintergrundbild" not in df.columns:
            df["background_image_url_opt"] = None

        final_expected_cols = ["sku", "image_url", "background_image_url_opt"]
        for col in final_expected_cols:
            if col not in df.columns:
                df[col] = None

        return df[final_expected_cols]

    except FileNotFoundError:
        st.error(f"FEHLER: Die SKU-Datendatei '{path}' wurde nicht gefunden.")
        return pd.DataFrame(columns=["sku", "image_url", "background_image_url_opt"])
    except Exception as e:
        st.error(f"Ein Fehler ist beim Laden der SKU-Daten von '{path}' aufgetreten: {e}.")
        return pd.DataFrame(columns=["sku", "image_url", "background_image_url_opt"])

def set_global_setting(key, value):
    st.session_state[key] = value

def get_global_setting(key, default=None):
    return st.session_state.get(key, default)