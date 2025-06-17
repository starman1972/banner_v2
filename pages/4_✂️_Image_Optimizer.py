import streamlit as st
from PIL import Image, ImageOps
from io import BytesIO
import requests

# Importe aus utils.py
import sys
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

from utils import load_css

# Cropper Import (bleibt spezifisch hier)
try:
    from streamlit_cropper import st_cropper
    CROPPER_AVAILABLE_OPTIMIZER = True
except ImportError:
    CROPPER_AVAILABLE_OPTIMIZER = False
    st.error("`streamlit-cropper` ist nicht installiert. Bitte installiere es: `pip install streamlit-cropper`")


# --- Seitenkonfiguration ---
st.set_page_config(
    page_title="Image Optimizer",
    page_icon="✂️",
    layout="wide",
    initial_sidebar_state="expanded"
)
load_css() # Lädt style.css

# --- Konstanten für diese Seite ---
ASPECT_RATIOS_CONFIG_OPTIMIZER = {
    "Banner (4.54:1)": (3000, 660), "Quadratisch (1:1)": (1200, 1200),
    "Breitbild (16:9)": (1920, 1080), "Hochformat (9:16)": (1080, 1920),
    "Klassisch (3:2)": (1500, 1000), "Hochformat (2:3)": (1000, 1500),
    "Flexibel (Freie Auswahl)": None, "Benutzerdefiniert (Seitenverhältnis)": "custom_ratio",
    "Benutzerdefiniert (Feste Größe)": "custom_size"
}
FORMAT_OPTIONS_ORDER_OPTIMIZER = list(ASPECT_RATIOS_CONFIG_OPTIMIZER.keys())
DEFAULT_CUSTOM_WIDTH_OPTIMIZER = 1200
DEFAULT_CUSTOM_HEIGHT_OPTIMIZER = 800
DEFAULT_JPEG_QUALITY_OPTIMIZER = 80 # Höhere Standardqualität
DEFAULT_INITIAL_BOX_WIDTH_SCALE_FACTOR_OPTIMIZER = 0.3 # Größerer Startwert
MIN_BOX_SCALE_FACTOR_OPTIMIZER = 0.05
MAX_BOX_SCALE_FACTOR_OPTIMIZER = 0.95 # Kann bis fast Vollbild gehen
BOX_SCALE_ADJUSTMENT_FACTOR_SMALLER_OPTIMIZER = 0.6 # Feinere Anpassung
BOX_SCALE_ADJUSTMENT_FACTOR_LARGER_OPTIMIZER = 1.4 # Feinere Anpassung

# --- Session State Initialisierung für diese Seite ---
def init_optimizer_session_state(full_reset=False):
    # Prefix für Session State Keys dieser Seite
    prefix = "optimizer_"
    defaults = {
        'cropped_img': None, 'original_img_details': None, 'image_url': "",
        'error_message': None, 'uploader_key': 0, 'output_format': "JPEG",
        'jpeg_quality': DEFAULT_JPEG_QUALITY_OPTIMIZER,
        'custom_ar_w': 16, 'custom_ar_h': 9,
        'custom_w': DEFAULT_CUSTOM_WIDTH_OPTIMIZER, 'custom_h': DEFAULT_CUSTOM_HEIGHT_OPTIMIZER,
        'format_selector': FORMAT_OPTIONS_ORDER_OPTIMIZER[0], # Default zum ersten in der Liste
        'current_box_scale_factor': DEFAULT_INITIAL_BOX_WIDTH_SCALE_FACTOR_OPTIMIZER
    }
    # Reset-Logik, um Keys neu zu initialisieren
    # Hilfreich, wenn man zwischen den Seiten wechselt und einen sauberen Start will
    # oder der Nutzer explizit resettet.
    if full_reset or not st.session_state.get(prefix + 'initialized_flag', False):
        for key, value in defaults.items():
            st.session_state[prefix + key] = value
        st.session_state[prefix + 'uploader_key'] = st.session_state.get(prefix + 'uploader_key',0) + (1 if full_reset else 0)
        st.session_state[prefix + 'initialized_flag'] = True # Markieren, dass initialisiert wurde
    else: # Nur initialisieren, wenn Keys noch nicht existieren (Standardverhalten von Streamlit)
        for key, value in defaults.items():
            if prefix + key not in st.session_state:
                st.session_state[prefix + key] = value
        if prefix + 'uploader_key' not in st.session_state :
             st.session_state[prefix + 'uploader_key'] = 0

# --- Helper Funktionen für diese Seite (mit Prefix für Session State) ---
opt_prefix = "optimizer_" # Für leichteren Zugriff auf prefixed keys

def get_format_details_optimizer():
    selected_format_key = st.session_state[opt_prefix + 'format_selector']
    config_value = ASPECT_RATIOS_CONFIG_OPTIMIZER[selected_format_key]
    aspect_ratio_defining_tuple = None
    final_target_output_size = None

    if config_value is None: # Flexibel
        st.sidebar.info("Freie Auswahl: Endgröße nach Zuschnitt.")
    elif config_value == "custom_ratio":
        st.sidebar.markdown("##### Benutzerdefiniertes Seitenverhältnis")
        st.session_state[opt_prefix + 'custom_ar_w'] = st.sidebar.number_input(
            "Verhältnis Breite", min_value=1, value=st.session_state[opt_prefix + 'custom_ar_w'], step=1,
            key=opt_prefix + "cs_ar_w"
        )
        st.session_state[opt_prefix + 'custom_ar_h'] = st.sidebar.number_input(
            "Verhältnis Höhe", min_value=1, value=st.session_state[opt_prefix + 'custom_ar_h'], step=1,
            key=opt_prefix + "cs_ar_h"
        )
        custom_ar_w = st.session_state[opt_prefix + 'custom_ar_w']
        custom_ar_h = st.session_state[opt_prefix + 'custom_ar_h']
        if custom_ar_w > 0 and custom_ar_h > 0:
            aspect_ratio_defining_tuple = (custom_ar_w, custom_ar_h)
        st.sidebar.info(f"Seitenverhältnis {custom_ar_w}:{custom_ar_h}. Endgröße nach Zuschnitt.")
    elif config_value == "custom_size":
        st.sidebar.markdown("##### Benutzerdefinierte Ausgabegröße")
        st.session_state[opt_prefix + 'custom_w'] = st.sidebar.number_input(
            "Ziel-Breite (px)", min_value=50, value=st.session_state[opt_prefix + 'custom_w'], step=10,
            key=opt_prefix + "cs_w"
        )
        st.session_state[opt_prefix + 'custom_h'] = st.sidebar.number_input(
            "Ziel-Höhe (px)", min_value=50, value=st.session_state[opt_prefix + 'custom_h'], step=10,
            key=opt_prefix + "cs_h"
        )
        custom_w = st.session_state[opt_prefix + 'custom_w']
        custom_h = st.session_state[opt_prefix + 'custom_h']
        if custom_w > 0 and custom_h > 0:
            aspect_ratio_defining_tuple = (custom_w, custom_h) # Definiert Form für Cropper
            final_target_output_size = (custom_w, custom_h)    # Definiert Endgröße
        st.sidebar.metric("Zielgröße", f"{custom_w}x{custom_h}px")
    else: # Feste Ratio aus Config
        aspect_ratio_defining_tuple = config_value
        final_target_output_size = config_value
        st.sidebar.metric("Zielgröße", f"{config_value[0]}x{config_value[1]}px")

    return aspect_ratio_defining_tuple, final_target_output_size

def calculate_cropper_aspect_parameter_optimizer(img_width, img_height, aspect_ratio_defining_tuple, width_scale_factor):
    if aspect_ratio_defining_tuple is None: return None # Freie Auswahl
    ar_def_w, ar_def_h = aspect_ratio_defining_tuple
    if ar_def_w <= 0 or ar_def_h <= 0: # Sollte nicht passieren bei custom, aber als Fallback
        return (int(img_width * width_scale_factor), int(img_width * width_scale_factor * 0.75)) # Default zu 4:3 artig

    aspect_ratio_value = ar_def_w / ar_def_h
    # Berechne initiale Box basierend auf Skalierungsfaktor und Bilddimensionen
    initial_w = int(img_width * width_scale_factor)
    initial_h = int(initial_w / aspect_ratio_value)

    # Sicherstellen, dass die Box nicht größer als das Bild ist (mit kleinem Puffer)
    if initial_h > img_height * 0.98:
        initial_h = int(img_height * 0.98)
        initial_w = int(initial_h * aspect_ratio_value)
    if initial_w > img_width * 0.98:
        initial_w = int(img_width * 0.98)
        initial_h = int(initial_w / aspect_ratio_value)

    return (max(10, initial_w), max(10, initial_h)) # Mindestgröße für die Box

def load_image_from_url_optimizer(url):
    try:
        response = requests.get(url, stream=True, timeout=10)
        response.raise_for_status()
        img = Image.open(BytesIO(response.content))
        img = ImageOps.exif_transpose(img) # Wichtig für korrekte Orientierung
        return img.convert("RGB"), None # Konvertiere zu RGB für Konsistenz
    except Exception as e:
        return None, f"Fehler beim Laden von URL: {e}"

# --- Hauptanwendung für diese Seite ---
def image_optimizer_page():
    init_optimizer_session_state() # Initialisiert mit Prefix

    with st.sidebar:
        st.title("✂️ Image Optimizer")
        st.markdown("Bild laden, zuschneiden und optimieren.")

        uploaded_file = st.file_uploader(
            "1a. Bild hochladen", type=["png", "jpg", "jpeg"],
            key=opt_prefix + f"uploader_{st.session_state[opt_prefix + 'uploader_key']}",
            accept_multiple_files=False
        )
        st.markdown("---")
        st.markdown("1b. Oder Bild von URL laden")
        current_url = st.session_state[opt_prefix + 'image_url']
        new_url = st.text_input("Bild-URL:", value=current_url, key=opt_prefix + "img_url_in")
        if new_url != current_url:
            st.session_state[opt_prefix + 'image_url'] = new_url

        if st.button("Von URL laden", key=opt_prefix + "load_url_btn"):
            if st.session_state[opt_prefix + 'image_url']:
                with st.spinner("Lade Bild von URL..."):
                    img, err_msg = load_image_from_url_optimizer(st.session_state[opt_prefix + 'image_url'])
                    if img:
                        st.session_state[opt_prefix + 'original_img_details'] = {
                            'image': img, 'name': st.session_state[opt_prefix + 'image_url'].split('/')[-1] or "url_image.jpg",
                            'type': img.format or "IMAGE", 'width': img.width, 'height': img.height, 'source': 'url'
                        }
                        st.session_state[opt_prefix + 'cropped_img'] = None
                        st.session_state[opt_prefix + 'error_message'] = None
                        st.session_state[opt_prefix + 'current_box_scale_factor'] = DEFAULT_INITIAL_BOX_WIDTH_SCALE_FACTOR_OPTIMIZER
                        st.session_state[opt_prefix + 'uploader_key'] += 1
                        st.rerun()
                    else:
                        st.session_state[opt_prefix + 'error_message'] = err_msg
                        st.session_state[opt_prefix + 'original_img_details'] = None
            else:
                st.session_state[opt_prefix + 'error_message'] = "Bitte eine gültige Bild-URL eingeben."

        if st.session_state[opt_prefix + 'error_message']:
            st.error(st.session_state[opt_prefix + 'error_message'])

        if uploaded_file:
            # Logik, um Bild zu laden, wenn neu oder anders als vorheriges
            current_og_details = st.session_state.get(opt_prefix + 'original_img_details')
            if not current_og_details or \
               current_og_details.get('source') != 'file' or \
               current_og_details.get('name') != uploaded_file.name:
                try:
                    img = Image.open(uploaded_file)
                    img = ImageOps.exif_transpose(img) # EXIF Korrektur
                    img_rgb = img.convert("RGB") # Zu RGB für Konsistenz
                    st.session_state[opt_prefix + 'original_img_details'] = {
                        'image': img_rgb, 'name': uploaded_file.name, 'type': uploaded_file.type,
                        'width': img_rgb.width, 'height': img_rgb.height, 'source': 'file'
                    }
                    st.session_state[opt_prefix + 'cropped_img'] = None
                    st.session_state[opt_prefix + 'error_message'] = None
                    st.session_state[opt_prefix + 'current_box_scale_factor'] = DEFAULT_INITIAL_BOX_WIDTH_SCALE_FACTOR_OPTIMIZER
                    if st.session_state[opt_prefix + 'image_url']: # URL löschen, wenn Datei geladen wird
                         st.session_state[opt_prefix + 'image_url'] = ""
                         # st.rerun() # Kann zu Endlosschleife führen, besser vermeiden
                except Exception as e:
                    st.error(f"Fehler beim Laden der Datei: {e}")
                    st.session_state[opt_prefix + 'original_img_details'] = None
                    return # Frühzeitiger Ausstieg bei Fehler

        st.markdown("---")
        if st.button("🔄 Optimizer zurücksetzen", key=opt_prefix + "reset_app_btn"):
            init_optimizer_session_state(full_reset=True)
            st.rerun()

        if st.session_state[opt_prefix + 'original_img_details']:
            st.markdown("---")
            st.subheader("2. Zuschneide-Optionen")
            st.session_state[opt_prefix + 'format_selector'] = st.selectbox(
                "Format/Seitenverhältnis:", options=FORMAT_OPTIONS_ORDER_OPTIMIZER,
                index=FORMAT_OPTIONS_ORDER_OPTIMIZER.index(st.session_state[opt_prefix + 'format_selector']),
                key=opt_prefix + "fmt_sel_wdg"
            )
            _, _ = get_format_details_optimizer() # Aktualisiert Sidebar basierend auf Auswahl

            st.markdown("---")
            st.subheader("3. Export-Optionen")
            st.session_state[opt_prefix + 'output_format'] = st.selectbox(
                "Ausgabeformat:", ["JPEG", "PNG", "WEBP"],
                index=["JPEG", "PNG", "WEBP"].index(st.session_state[opt_prefix + 'output_format']),
                key=opt_prefix + f"out_fmt_sb_{st.session_state[opt_prefix + 'uploader_key']}"
            )
            if st.session_state[opt_prefix + 'output_format'] == "JPEG":
                st.session_state[opt_prefix + 'jpeg_quality'] = st.slider(
                    "JPEG Qualität:", 10, 100, st.session_state[opt_prefix + 'jpeg_quality'], 5,
                    key=opt_prefix + f"jpeg_ql_sl_{st.session_state[opt_prefix + 'uploader_key']}"
                )
            elif st.session_state[opt_prefix + 'output_format'] == "WEBP":
                 # Hier könnte man noch Optionen für WebP hinzufügen (lossy quality, lossless)
                 st.caption("WebP wird mit Standardeinstellungen gespeichert (lossy, Qualität ~80).")


    # --- Hauptbereich Logik ---
    if not st.session_state[opt_prefix + 'original_img_details']:
        st.info("✨ Willkommen beim Image Optimizer! Bitte lade ein Bild über die Sidebar, um zu starten.")
        return

    if not CROPPER_AVAILABLE_OPTIMIZER:
        st.error("Das streamlit-cropper Modul konnte nicht geladen werden. Bitte stelle sicher, dass es installiert ist.")
        return

    og_data = st.session_state[opt_prefix + 'original_img_details']
    og_pil_img = og_data['image']

    col_cropper, col_box_controls = st.columns([0.85, 0.15])

    with col_cropper:
        st.subheader(f"Interaktiver Zuschnitt für: {og_data['name']}")
        st.caption(f"Original: {og_data['width']}x{og_data['height']}px. Gewähltes Format: {st.session_state[opt_prefix + 'format_selector']}")

        aspect_ratio_defining_tuple, final_target_output_size = get_format_details_optimizer()
        cropper_aspect_param = calculate_cropper_aspect_parameter_optimizer(
            og_data['width'], og_data['height'],
            aspect_ratio_defining_tuple, st.session_state[opt_prefix + 'current_box_scale_factor']
        )

        # Dynamischer Key für den Cropper, um ihn bei Änderungen neu zu initialisieren
        cropper_key_parts = [opt_prefix + "cropper", og_data['name'], str(st.session_state[opt_prefix + 'format_selector']),
                             f"{st.session_state[opt_prefix + 'current_box_scale_factor']:.3f}"]
        if st.session_state[opt_prefix + 'format_selector'] == "Benutzerdefiniert (Seitenverhältnis)":
            cropper_key_parts.append(f"{st.session_state[opt_prefix+'custom_ar_w']}x{st.session_state[opt_prefix+'custom_ar_h']}")
        elif st.session_state[opt_prefix + 'format_selector'] == "Benutzerdefiniert (Feste Größe)":
            cropper_key_parts.append(f"{st.session_state[opt_prefix+'custom_w']}x{st.session_state[opt_prefix+'custom_h']}")
        cropper_key = "_".join(cropper_key_parts)

        cropped_pil_image = st_cropper(og_pil_img, realtime_update=True, box_color="#FF4B4B",
                                       aspect_ratio=cropper_aspect_param, key=cropper_key)
        st.session_state[opt_prefix + 'cropped_img'] = cropped_pil_image
        st.caption(f"Aktueller Ausschnitt (vor Skalierung): {cropped_pil_image.width}x{cropped_pil_image.height}px")

    with col_box_controls:
        st.write("") # Abstandshalter
        st.write("")
        st.write("")
        st.caption("Box-Größe:")
        if st.button("➖", key=opt_prefix + "btn_box_smaller", help="Initiale Auswahlbox verkleinern", use_container_width=True):
            new_factor = st.session_state[opt_prefix + 'current_box_scale_factor'] * BOX_SCALE_ADJUSTMENT_FACTOR_SMALLER_OPTIMIZER
            st.session_state[opt_prefix + 'current_box_scale_factor'] = max(MIN_BOX_SCALE_FACTOR_OPTIMIZER, new_factor)
            st.rerun()
        if st.button("➕", key=opt_prefix + "btn_box_larger", help="Initiale Auswahlbox vergrößern", use_container_width=True):
            new_factor = st.session_state[opt_prefix + 'current_box_scale_factor'] * BOX_SCALE_ADJUSTMENT_FACTOR_LARGER_OPTIMIZER
            st.session_state[opt_prefix + 'current_box_scale_factor'] = min(MAX_BOX_SCALE_FACTOR_OPTIMIZER, new_factor)
            st.rerun()
        if st.button("Reset", key=opt_prefix + "btn_box_reset", help="Box-Größe auf Standard zurücksetzen", use_container_width=True):
            st.session_state[opt_prefix + 'current_box_scale_factor'] = DEFAULT_INITIAL_BOX_WIDTH_SCALE_FACTOR_OPTIMIZER
            st.rerun()

    if st.session_state[opt_prefix + 'cropped_img']:
        st.markdown("---")
        st.subheader("Vorschau des optimierten Bildes")

        final_img_to_display = st.session_state[opt_prefix + 'cropped_img']
        caption_text = f"Zuschnitt: {final_img_to_display.width}x{final_img_to_display.height}px"
        current_output_dimensions = final_img_to_display.size

        # Wenn eine feste Zielgröße definiert ist, skaliere das zugeschnittene Bild
        if final_target_output_size:
            final_img_to_display = st.session_state[opt_prefix + 'cropped_img'].resize(final_target_output_size, Image.Resampling.LANCZOS)
            caption_text = f"Final skaliert auf: {final_target_output_size[0]}x{final_target_output_size[1]}px"
            current_output_dimensions = final_target_output_size

        st.image(final_img_to_display, caption=caption_text, use_container_width=True) # use_container_width für responsive Anzeige

        # Bild für den Download vorbereiten
        buffer = BytesIO()
        save_args = {}
        output_format_selected = st.session_state[opt_prefix + 'output_format']
        file_extension = output_format_selected.lower()
        mime_type = f"image/{file_extension}"

        img_to_save = final_img_to_display # Das ist das bereits skalierte Bild (falls Skalierung aktiv war)

        if output_format_selected == "JPEG":
            save_args['quality'] = st.session_state[opt_prefix + 'jpeg_quality']
            if img_to_save.mode == 'RGBA' or img_to_save.mode == 'P': # PNGs können RGBA oder P (Palette) sein
                img_to_save = img_to_save.convert('RGB') # Konvertiere zu RGB vor JPEG Speicherung
        elif output_format_selected == "WEBP":
            # Beispielhafte WebP-Speicheroptionen (können erweitert werden)
            save_args['quality'] = 80 # Standard für verlustbehaftetes WebP
            # save_args['lossless'] = True # Für verlustfreies WebP
            if img_to_save.mode == 'P' and 'transparency' in img_to_save.info : # WebP unterstützt Alpha, aber P-Mode nicht direkt
                 img_to_save = img_to_save.convert('RGBA')


        img_to_save.save(buffer, format=output_format_selected.upper(), **save_args) # Format muss UPPERCASE sein

        download_filename = f"optimized_image_{current_output_dimensions[0]}x{current_output_dimensions[1]}.{file_extension}"
        st.download_button(
            label=f"📥 Download als {output_format_selected}",
            data=buffer.getvalue(),
            file_name=download_filename,
            mime=mime_type,
            key=opt_prefix + "dl_btn",
            use_container_width=True,
            type="primary"
        )

if __name__ == "__main__":
    image_optimizer_page()