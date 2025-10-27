import os
import sys
from io import BytesIO
from typing import Optional

import streamlit as st
from dotenv import load_dotenv

# --------------------------------------------------------------- Pfad-Setup
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from utils import load_css  # noqa: E402
from logic.generation_fal import (  # noqa: E402
    FalFluxBannerResult,
    generate_flux_banner_with_explicit_size,
    generate_flux_ultra_redux_banner,
)

# --------------------------------------------------------------- Seite setup
st.set_page_config(page_title="Fal Flux Dev-Test", page_icon=":gear:", layout="wide")
load_css()
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

DEFAULT_PROMPT = (
    "Elegant wide panoramic landscape banner, Tuscany hills, soft golden light, "
    "painted style, minimal foreground clutter, clean negative space for text."
)

MODE_ASPECT = "4:1 Banner (Flux Ultra Redux)"
MODE_CUSTOM = "Custom Size (Flux Dev)"
ASPECT_RATIO_CHOICES = ["4:1", "21:9", "16:9", "4:3", "3:2", "1:1", "2:3", "3:4", "9:16", "9:21"]

if "fal_flux_mode" not in st.session_state:
    st.session_state.fal_flux_mode = MODE_ASPECT
if "fal_flux_test_result" not in st.session_state:
    st.session_state.fal_flux_test_result: Optional[FalFluxBannerResult] = None
if "fal_flux_test_error" not in st.session_state:
    st.session_state.fal_flux_test_error = ""
if "fal_flux_last_mode" not in st.session_state:
    st.session_state.fal_flux_last_mode = MODE_ASPECT

# --------------------------------------------------------------- UI
st.title("Fal Flux Dev-Test")
st.caption("Schnelle Experimente mit Flux-Bannern – Text-zu-Bild und Image-to-Image.")

fal_key_available = bool(os.getenv("FAL_KEY"))
if not fal_key_available:
    st.warning("Keine `FAL_KEY` Umgebungsvariable gefunden. Bitte `.env` prüfen.")

mode = st.radio(
    "Generator-Modus",
    options=[MODE_ASPECT, MODE_CUSTOM],
    index=[MODE_ASPECT, MODE_CUSTOM].index(st.session_state.fal_flux_mode),
    horizontal=True,
)
st.session_state.fal_flux_mode = mode

seed_value: Optional[int] = None

submitted = False
prompt = DEFAULT_PROMPT
image_url_input: Optional[str] = None
image_prompt_strength = 0.0
num_steps = 28
guidance_scale = 3.5
aspect_ratio = "4:1"
width = 3000
height = 660

if mode == MODE_ASPECT:
    st.subheader("Flux Ultra 4:1 Banner")
    st.caption(
        "Optional kannst du ein Referenzbild angeben. Ohne Bild erzeugen wir das Banner rein aus dem Prompt."
    )

    prompt = st.text_area("Prompt", DEFAULT_PROMPT, height=140, key="fal_flux_ultra_prompt")
    image_url_input = st.text_input(
        "Referenzbild-URL (optional, für Image-to-Image)",
        value="",
        key="fal_flux_ultra_image_url",
    ).strip() or None

    if image_url_input:
        image_prompt_strength = st.slider(
            "Bild-Prompt-Strength",
            min_value=0.0,
            max_value=1.0,
            value=0.2,
            step=0.05,
            help="Wie stark das Referenzbild den Stil vorgibt.",
            key="fal_flux_ultra_strength",
        )
    else:
        st.info("Kein Referenzbild angegeben – wir verwenden intern ein neutrales Placeholder-Bild.")
        image_prompt_strength = 0.0

    aspect_ratio = st.selectbox(
        "Aspect Ratio",
        options=ASPECT_RATIO_CHOICES,
        index=ASPECT_RATIO_CHOICES.index("4:1"),
        key="fal_flux_ultra_aspect",
    )

    num_steps = st.slider(
        "Inference Steps",
        min_value=10,
        max_value=60,
        value=28,
        step=1,
        key="fal_flux_ultra_steps",
    )
    guidance_scale = st.slider(
        "Guidance Scale",
        min_value=1.5,
        max_value=10.0,
        value=3.5,
        step=0.5,
        key="fal_flux_ultra_guidance",
    )

    seed_str = st.text_input(
        "Optional: Seed (leer lassen für Zufall)",
        value="",
        key="fal_flux_ultra_seed",
    ).strip()
    if seed_str:
        try:
            seed_value = int(seed_str)
        except ValueError:
            st.warning("Seed konnte nicht als Ganzzahl interpretiert werden; wird ignoriert.")
            seed_value = None

    submitted = st.button(
        "Flux Ultra Bannergenerierung starten",
        use_container_width=True,
        disabled=not fal_key_available,
    )

else:
    st.subheader("Flux Dev Custom Size")
    prompt = st.text_area("Prompt", DEFAULT_PROMPT, height=140, key="fal_flux_dev_prompt")

    col1, col2 = st.columns(2)
    with col1:
        width = st.number_input(
            "Breite (px)",
            min_value=64,
            max_value=4096,
            value=3000,
            step=10,
            key="fal_flux_dev_width",
        )
    with col2:
        height = st.number_input(
            "Höhe (px)",
            min_value=64,
            max_value=4096,
            value=660,
            step=10,
            key="fal_flux_dev_height",
        )

    num_steps = st.slider(
        "Inference Steps",
        min_value=10,
        max_value=50,
        value=28,
        step=1,
        key="fal_flux_dev_steps",
    )
    guidance_scale = st.slider(
        "Guidance Scale",
        min_value=1.0,
        max_value=15.0,
        value=7.0,
        step=0.5,
        key="fal_flux_dev_guidance",
    )

    seed_str = st.text_input(
        "Optional: Seed (leer lassen für Zufall)",
        value="",
        key="fal_flux_dev_seed",
    ).strip()
    if seed_str:
        try:
            seed_value = int(seed_str)
        except ValueError:
            st.warning("Seed konnte nicht als Ganzzahl interpretiert werden; wird ignoriert.")
            seed_value = None

    submitted = st.button(
        "Flux Dev Bannergenerierung starten",
        use_container_width=True,
        disabled=not fal_key_available,
    )

# --------------------------------------------------------------- Anfrage ausführen
if submitted:
    st.session_state.fal_flux_test_error = ""
    st.session_state.fal_flux_test_result = None

    try:
        with st.spinner("Fal.ai generiert das Banner ..."):
            if st.session_state.fal_flux_mode == MODE_CUSTOM:
                st.session_state.fal_flux_test_result = generate_flux_banner_with_explicit_size(
                    prompt=prompt,
                    width=int(width),
                    height=int(height),
                    num_inference_steps=int(num_steps),
                    guidance_scale=float(guidance_scale),
                    seed=seed_value,
                )
            else:
                st.session_state.fal_flux_test_result = generate_flux_ultra_redux_banner(
                    prompt=prompt,
                    aspect_ratio=aspect_ratio,
                    image_url=image_url_input,
                    image_prompt_strength=image_prompt_strength,
                    num_inference_steps=int(num_steps),
                    guidance_scale=float(guidance_scale),
                    seed=seed_value,
                    enhance_prompt=True,
                )
            st.session_state.fal_flux_last_mode = st.session_state.fal_flux_mode
    except ValueError as val_err:
        st.session_state.fal_flux_test_error = str(val_err)
    except Exception as err:
        st.session_state.fal_flux_test_error = f"Fehler bei der Generierung: {err}"

# --------------------------------------------------------------- Ausgabe
if st.session_state.fal_flux_test_error:
    st.error(st.session_state.fal_flux_test_error)

result = st.session_state.fal_flux_test_result
if result is not None:
    cols = st.columns([1, 2])
    with cols[0]:
        if result.requested_width and result.requested_height:
            if result.size_matches_request:
                st.success(
                    f"{result.returned_width}×{result.returned_height}px – entspricht der angefragten Größe."
                )
            else:
                st.warning(
                    "Größenabweichung: "
                    f"erhalten {result.returned_width}×{result.returned_height}px "
                    f"(angefragt {result.requested_width}×{result.requested_height}px)."
                )
        else:
            st.info(f"Erhaltenes Format: {result.returned_width}×{result.returned_height}px.")

        meta = []
        if result.seed is not None:
            meta.append(f"Seed {result.seed}")
        meta.append(st.session_state.fal_flux_last_mode)
        if result.requested_aspect_ratio:
            meta.append(f"AR {result.requested_aspect_ratio}")
        if result.used_placeholder_image and not image_url_input:
            meta.append("Placeholder-Startbild")
        if meta:
            st.caption(" | ".join(meta))

        buffer = BytesIO()
        result.image.save(buffer, format="JPEG", quality=92)
        st.download_button(
            f"Banner herunterladen ({result.image.width}x{result.image.height}.jpg)",
            data=buffer.getvalue(),
            file_name=f"fal_flux_banner_{result.image.width}x{result.image.height}.jpg",
            mime="image/jpeg",
            use_container_width=True,
        )

    with cols[1]:
        st.image(result.image, caption="Fal Flux Ergebnis", use_column_width=True)
