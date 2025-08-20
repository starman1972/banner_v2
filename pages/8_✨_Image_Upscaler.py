import streamlit as st
from PIL import Image
from io import BytesIO
import os
import sys

# --- Pfade und Imports ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

from utils import load_css
from logic.upscaling import upscale_with_fal

# --- Seitenkonfiguration ---
st.set_page_config(page_title="Image Upscaler", page_icon="✨", layout="wide")
load_css()

# --- Session State Initialisierung ---
def init_session_state():
    defaults = {
        "upscaler_original_img": None,
        "upscaler_original_img_bytes": None,
        "upscaler_upscaled_img": None,
        "upscaler_last_file_id": None,
        "upscaler_output_format": "JPEG",
        "upscaler_jpeg_quality": 90,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# --- UI & Logik ---
st.markdown("""<div class="hero-section" style="padding:1.5em 1em;margin-bottom:1.5em"> <h1 style="font-size:2em">✨ Image Upscaler</h1> <p class="subtitle" style="font-size:1em">Verbessere die Auflösung und Qualität deiner Bilder mit KI.</p> </div>""", unsafe_allow_html=True)

# 1. Sidebar für Optionen
with st.sidebar:
    st.header("⚙️ Optionen")

    uploaded_file = st.file_uploader(
        "1. Bild hochladen",
        type=["png", "jpg", "jpeg", "webp"],
        key="upscaler_uploader_static"
    )

    start_button = st.button(
        "🚀 Upscaling starten",
        type="primary",
        use_container_width=True,
        disabled=not uploaded_file
    )
    
    st.markdown("---")
    st.subheader("Export-Optionen")
    
    st.selectbox(
        "Ausgabeformat",
        options=["JPEG", "PNG"],
        key="upscaler_output_format",
        help="JPEG ist ideal für Webseiten (kleinere Dateien). PNG ist verlustfrei (größere Dateien)."
    )
    
    if st.session_state.upscaler_output_format == "JPEG":
        st.slider(
            "JPEG Qualität",
            min_value=10,
            max_value=100,
            key="upscaler_jpeg_quality",
            help="Höhere Werte bedeuten bessere Qualität und größere Dateien."
        )

# Robuste Logik zur Verarbeitung einer NEUEN Datei
if uploaded_file is not None:
    if uploaded_file.file_id != st.session_state.upscaler_last_file_id:
        st.session_state.upscaler_original_img = None
        st.session_state.upscaler_original_img_bytes = None
        st.session_state.upscaler_upscaled_img = None
        st.session_state.upscaler_last_file_id = uploaded_file.file_id
        
        try:
            image_bytes = uploaded_file.getvalue()
            st.session_state.upscaler_original_img_bytes = image_bytes
            st.session_state.upscaler_original_img = Image.open(BytesIO(image_bytes))
            st.rerun()
        except Exception as e:
            st.error(f"Fehler beim Laden des Bildes: {e}")
            st.stop()

# Starten des Upscaling-Prozesses bei Knopfdruck
if start_button and st.session_state.get("upscaler_original_img_bytes"):
    with st.spinner("Bild wird hochskaliert... Dies kann einen Moment dauern."):
        try:
            original_bytes = st.session_state.upscaler_original_img_bytes
            upscaled_image = upscale_with_fal(original_bytes)
            st.session_state.upscaler_upscaled_img = upscaled_image
            st.success("Upscaling erfolgreich abgeschlossen!")
        except Exception as e:
            st.error(f"Ein Fehler ist aufgetreten: {e}")
            st.session_state.upscaler_upscaled_img = None

# 3. Ergebnisse anzeigen
if st.session_state.get("upscaler_original_img"):
    st.markdown("---")
    st.header("Ergebnis")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Original")
        orig_img = st.session_state.upscaler_original_img
        st.image(orig_img, use_container_width=True)
        st.caption(f"Auflösung: {orig_img.width} x {orig_img.height} px")
        
    with col2:
        st.subheader("Hochskaliert")
        upscaled_img = st.session_state.get("upscaler_upscaled_img")
        if upscaled_img:
            st.image(upscaled_img, use_container_width=True)
            st.caption(f"Auflösung: {upscaled_img.width} x {upscaled_img.height} px")
            
            # Download-Logik
            output_format = st.session_state.upscaler_output_format
            buf = BytesIO()
            save_kwargs = {}
            if output_format == 'JPEG':
                save_kwargs['quality'] = st.session_state.upscaler_jpeg_quality
                file_extension = "jpg"
                mime_type = "image/jpeg"
            else: # PNG
                file_extension = "png"
                mime_type = "image/png"

            img_to_save = upscaled_img.convert("RGB") if output_format == 'JPEG' else upscaled_img
            img_to_save.save(buf, format=output_format, **save_kwargs)
            
            if uploaded_file:
                download_filename = f"upscaled_{os.path.splitext(uploaded_file.name)[0]}.{file_extension}"
            else:
                download_filename = f"upscaled_image.{file_extension}"

            st.download_button(
                label=f"📥 Bild als {output_format} herunterladen",
                data=buf.getvalue(),
                file_name=download_filename,
                mime=mime_type,
                use_container_width=True
            )
        else:
            st.info("Das hochskalierte Bild wird hier angezeigt, nachdem der Prozess gestartet wurde.")
else:
    st.info("Bitte laden Sie ein Bild hoch und klicken Sie in der Sidebar auf 'Upscaling starten'.")