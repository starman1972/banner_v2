import os
import sys
from hashlib import sha256
from io import BytesIO
from time import perf_counter

import pandas as pd
import requests
import streamlit as st
from PIL import Image, ImageOps

# -------------------------------------------------------------------- Paths
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

# -------------------------------------------------------------------- Imports
from logic.generation_v2 import (
    DEFAULT_GENERATION_QUALITY,
    DEFAULT_OUTPUT_COMPRESSION,
    DEFAULT_OUTPUT_FORMAT,
    GenerationSizePlan,
    IMAGE_MODEL_LABEL,
    generate_banner_with_gpt_image_2,
    get_generation_size_for_target,
)
from logic.prompt_engine_v2 import (
    PROMPT_MODE_DESCRIPTIONS,
    PROMPT_MODE_LABELS,
    build_banner_prompt,
)
from utils import SKU_CSV_FILENAME, get_secret, load_css, load_sku_data

# ---------------------------------------------------------------- Streamlit
st.set_page_config(page_title="Banner Generator", page_icon="🚀", layout="wide")
load_css()

# ---------------------------------------------------------------- OpenAI-Key
OPENAI_API_KEY = get_secret("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    st.error("OpenAI API-Key fehlt. Bitte OPENAI_API_KEY in der Umgebung oder den Streamlit-Secrets setzen.")
    st.stop()

# -------------------------------------------------------- Optional dependency
try:
    from streamlit_cropper import st_cropper

    CROPPER_AVAILABLE = True
except ImportError:
    CROPPER_AVAILABLE = False

# ---------------------------------------------------------------- Constants
RATIO_OPTIONS_MAP = {
    "Wide Banner (4.54:1)": (3000, 660),
    "Showcase (3:2)": (1500, 1000),
    "Square (1:1)": (1024, 1024),
    "Video Thumbnail (16:9)": (1920, 1080),
    "Custom": None,
}
DEFAULT_RATIO_KEY = "Wide Banner (4.54:1)"
CUSTOM_DEFAULT_WIDTH = 3840
CUSTOM_DEFAULT_HEIGHT = 2160
PREVIEW_IMAGE_WIDTH = 220


def _get_output_metadata(output_format: str) -> tuple[str, str, str]:
    extension = "jpg" if output_format == "jpeg" else output_format
    mime = "image/jpeg" if output_format == "jpeg" else f"image/{output_format}"
    pil_format = output_format.upper() if output_format != "jpeg" else "JPEG"
    return extension, mime, pil_format


def _get_download_save_kwargs(output_format: str, compression: int) -> dict:
    if output_format in {"jpeg", "webp"}:
        quality = max(1, min(100, 100 - compression))
        return {"quality": quality}
    return {}


# ------------------------------------------------------- Session state
def initialize_session_state() -> None:
    defaults = {
        "banner_gen_image_input": None,
        "banner_gen_image_input_name": None,
        "banner_gen_image_input_digest": None,
        "banner_gen_img_from": None,
        "uploader_instance_key": 0,
        "banner_gen_ratio_choice": DEFAULT_RATIO_KEY,
        "banner_gen_custom_width": CUSTOM_DEFAULT_WIDTH,
        "banner_gen_custom_height": CUSTOM_DEFAULT_HEIGHT,
        "banner_gen_quality_choice": DEFAULT_GENERATION_QUALITY,
        "banner_gen_prompt_mode": "classic",
        "banner_gen_output_format_choice": DEFAULT_OUTPUT_FORMAT,
        "banner_gen_output_compression": DEFAULT_OUTPUT_COMPRESSION,
        "banner_gen_include_text": False,
        "banner_gen_user_text": "",
        "banner_gen_text_position": "zentral",
        "banner_gen_instruction_prompt_for_gpt_image_1": None,
        "banner_gen_ai_banner_img": None,
        "banner_gen_status_message": "",
        "banner_gen_is_generating": False,
        "banner_gen_cropper_version": 0,
        "temp_sku_input": "",
        "banner_gen_current_sku_data": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)

    _update_target_size_from_state()


def _update_target_size_from_state() -> None:
    if st.session_state.banner_gen_ratio_choice == "Custom":
        st.session_state.banner_gen_target_size = (
            int(st.session_state.banner_gen_custom_width),
            int(st.session_state.banner_gen_custom_height),
        )
    else:
        st.session_state.banner_gen_target_size = RATIO_OPTIONS_MAP.get(
            st.session_state.banner_gen_ratio_choice,
            RATIO_OPTIONS_MAP[DEFAULT_RATIO_KEY],
        )


def _get_current_generation_plan() -> GenerationSizePlan:
    width, height = st.session_state.banner_gen_target_size
    return get_generation_size_for_target(int(width), int(height))


def _reset_ai_states() -> None:
    st.session_state.banner_gen_ai_banner_img = None
    st.session_state.banner_gen_instruction_prompt_for_gpt_image_1 = None
    st.session_state.banner_gen_status_message = ""
    st.session_state.banner_gen_cropper_version += 1


def _on_parameter_change() -> None:
    _update_target_size_from_state()
    _reset_ai_states()


# -------------------------------------------------------------- UI helpers
def _render_hero() -> None:
    st.markdown(
        f"""
        <div class="hero-section" style="padding:1.5em 1em;margin-bottom:1.5em">
          <h1 style="font-size:2em">🚀 Banner Generator ({IMAGE_MODEL_LABEL})</h1>
          <p class="subtitle" style="font-size:1em">
            Generate AI banners from your product image with {IMAGE_MODEL_LABEL} and flexible sizing.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_step_header(step: int, title: str) -> None:
    st.markdown(f"<h2>{step}️⃣ Schritt {step}: {title}</h2>", unsafe_allow_html=True)


def _handle_upload() -> None:
    uploader_key = f"banner_gen_uploader_{st.session_state.uploader_instance_key}"
    uploaded_file = st.file_uploader(
        "Bild auswaehlen (PNG/JPG/WEBP)",
        type=["png", "jpg", "jpeg", "webp"],
        key=uploader_key,
    )
    if not uploaded_file:
        return

    image_bytes = uploaded_file.getvalue()
    image_digest = sha256(image_bytes).hexdigest()
    if (
        st.session_state.get("banner_gen_image_input_name") == uploaded_file.name
        and st.session_state.get("banner_gen_image_input_digest") == image_digest
        and st.session_state.get("banner_gen_img_from") == "upload"
    ):
        return

    try:
        image = Image.open(BytesIO(image_bytes))
        image = ImageOps.exif_transpose(image).convert("RGB")
        st.session_state.banner_gen_image_input = image
        st.session_state.banner_gen_image_input_name = uploaded_file.name
        st.session_state.banner_gen_image_input_digest = image_digest
        st.session_state.banner_gen_img_from = "upload"
        st.session_state.banner_gen_current_sku_data = None
        st.session_state.temp_sku_input = ""
        st.session_state.uploader_instance_key += 1
        _reset_ai_states()
        st.rerun()
    except Exception as exc:
        st.error(f"Bild konnte nicht geladen werden: {exc}")


def _handle_sku_lookup(df_skus: pd.DataFrame) -> None:
    st.text_input("SKU eingeben:", key="temp_sku_input")
    if not st.button("🔍 Bild via SKU suchen"):
        return

    sku_value = st.session_state.temp_sku_input.strip()
    if not sku_value:
        st.warning("Bitte eine SKU eingeben.")
        return

    if (
        st.session_state.get("banner_gen_image_input_name") == f"SKU:{sku_value}"
        and st.session_state.get("banner_gen_img_from") == "sku"
    ):
        return

    match = df_skus[df_skus["sku"].astype(str).str.lower() == sku_value.lower()]
    if match.empty or pd.isna(match.iloc[0]["image_url"]):
        st.error(f"Fuer SKU '{sku_value}' wurde kein gueltiges Bild gefunden.")
        return

    try:
        response = requests.get(match.iloc[0]["image_url"], timeout=15)
        response.raise_for_status()
        image = Image.open(BytesIO(response.content))
        image = ImageOps.exif_transpose(image).convert("RGB")
        st.session_state.banner_gen_image_input = image
        st.session_state.banner_gen_image_input_name = f"SKU:{sku_value}"
        st.session_state.banner_gen_image_input_digest = None
        st.session_state.banner_gen_img_from = "sku"
        st.session_state.banner_gen_current_sku_data = match.iloc[0].to_dict()
        st.session_state.uploader_instance_key += 1
        _reset_ai_states()
        st.rerun()
    except Exception as exc:
        st.error(f"SKU-Bild konnte nicht geladen werden: {exc}")


def _render_size_plan(plan: GenerationSizePlan) -> None:
    st.caption(
        f"Finale Zielgroesse: {plan.requested_size_str} px | "
        f"Angefragte Generationsgroesse: {plan.generation_size_str} px"
    )

    if plan.requires_crop:
        crop_message = (
            "Die OpenAI-Ausgabe wird fuer dieses Seitenverhaeltnis lokal auf das Endformat "
            "zugeschnitten und/oder skaliert."
        )
        if st.session_state.banner_gen_ratio_choice == "Custom":
            st.warning(crop_message)
        else:
            st.info(crop_message)


def _select_options() -> None:
    st.radio(
        "Prompt-Stil:",
        list(PROMPT_MODE_LABELS),
        format_func=PROMPT_MODE_LABELS.__getitem__,
        key="banner_gen_prompt_mode",
        on_change=_on_parameter_change,
        horizontal=True,
    )
    st.caption(PROMPT_MODE_DESCRIPTIONS[st.session_state.banner_gen_prompt_mode])

    ratio_option_keys = list(RATIO_OPTIONS_MAP.keys())
    st.radio(
        "Seitenverhaeltnis:",
        ratio_option_keys,
        key="banner_gen_ratio_choice",
        on_change=_on_parameter_change,
    )

    if st.session_state.banner_gen_ratio_choice == "Custom":
        col_width, col_height = st.columns(2)
        with col_width:
            st.number_input(
                "Breite (px)",
                min_value=1,
                key="banner_gen_custom_width",
                on_change=_on_parameter_change,
            )
        with col_height:
            st.number_input(
                "Hoehe (px)",
                min_value=1,
                key="banner_gen_custom_height",
                on_change=_on_parameter_change,
            )

    plan = _get_current_generation_plan()
    _render_size_plan(plan)

    st.radio(
        "KI-Qualitaet:",
        ["auto", "low", "medium", "high"],
        key="banner_gen_quality_choice",
        on_change=_on_parameter_change,
        horizontal=True,
        help="Die Qualitaet steuert direkt die Renderkosten und die Bildtreue.",
    )

    config_col_1, config_col_2 = st.columns(2)
    with config_col_1:
        st.caption(
            "Die Qualitaetsstufe bleibt ein echter API-Parameter, weil sie Kosten und Renderdauer beeinflusst. "
            "Hintergrund und Moderation werden in diesem Direct-Flow derzeit nicht separat angeboten."
        )
    with config_col_2:
        st.radio(
            "Downloadformat:",
            ["png", "jpeg", "webp"],
            key="banner_gen_output_format_choice",
            on_change=_on_parameter_change,
            horizontal=True,
        )
        if st.session_state.banner_gen_output_format_choice in {"jpeg", "webp"}:
            st.slider(
                "Kompression (0-100)",
                min_value=0,
                max_value=100,
                key="banner_gen_output_compression",
                on_change=_on_parameter_change,
                help="Hoeherer Wert bedeutet kleinere Datei und staerkere Kompression.",
            )
        else:
            st.caption("PNG nutzt keine einstellbare Kompression in diesem Flow.")

    st.checkbox(
        "Text in Banner integrieren?",
        key="banner_gen_include_text",
        on_change=_on_parameter_change,
    )
    if st.session_state.banner_gen_include_text:
        st.text_area(
            "Zu integrierender Text:",
            key="banner_gen_user_text",
            placeholder="Dein Banner-Text ...",
            on_change=_on_parameter_change,
        )
        st.radio(
            "Textposition (KI-Vorschlag):",
            ["zentral", "oben", "unten", "links", "rechts"],
            key="banner_gen_text_position",
            on_change=_on_parameter_change,
            horizontal=True,
        )
        if not st.session_state.banner_gen_user_text.strip():
            st.warning("Bitte Banner-Text eingeben oder die Textoption deaktivieren.")


def _perform_banner_generation() -> None:
    if not st.session_state.banner_gen_image_input:
        return

    st.session_state.banner_gen_is_generating = True
    _reset_ai_states()
    try:
        _update_target_size_from_state()
        size_plan = _get_current_generation_plan()
        user_text = (
            st.session_state.banner_gen_user_text.strip()
            if st.session_state.banner_gen_include_text
            else ""
        )
        if st.session_state.banner_gen_include_text and not user_text:
            raise ValueError("Bitte Banner-Text eingeben oder die Textoption deaktivieren.")
        prompt = build_banner_prompt(
            mode=st.session_state.banner_gen_prompt_mode,
            target_size=st.session_state.banner_gen_target_size,
            generation_size=(size_plan.generation_width, size_plan.generation_height),
            user_text=user_text,
            text_position=st.session_state.banner_gen_text_position,
        )
        st.session_state.banner_gen_instruction_prompt_for_gpt_image_1 = prompt
        output_format = st.session_state.banner_gen_output_format_choice
        compression = (
            st.session_state.banner_gen_output_compression
            if output_format in {"jpeg", "webp"}
            else None
        )
        mode_label = PROMPT_MODE_LABELS[st.session_state.banner_gen_prompt_mode]
        st.session_state.banner_gen_status_message = (
            f"🎨 {IMAGE_MODEL_LABEL} generiert Banner ({mode_label}, {size_plan.generation_size_str}, "
            f"Qualitaet: {st.session_state.banner_gen_quality_choice}) ..."
        )
        with st.spinner(st.session_state.banner_gen_status_message):
            started_at = perf_counter()
            image_result = generate_banner_with_gpt_image_2(
                original_image_pil=st.session_state.banner_gen_image_input,
                instruction_prompt=prompt,
                size_plan=size_plan,
                quality=st.session_state.banner_gen_quality_choice,
                output_format=output_format,
                output_compression=compression,
            )
            st.session_state.banner_gen_ai_banner_img = image_result
            elapsed_seconds = perf_counter() - started_at
            st.session_state.banner_gen_status_message = (
                f"✅ Banner erfolgreich generiert! {IMAGE_MODEL_LABEL} | "
                f"Generierungsdauer: {elapsed_seconds:.1f} s"
            )
    except Exception as exc:
        st.session_state.banner_gen_status_message = f"Fehler bei Bannergenerierung: {exc}"
    finally:
        st.session_state.banner_gen_is_generating = False


def _initial_crop_box(img: Image.Image, aspect_ratio: tuple[int, int]) -> dict:
    # The cropper calls this on its preview; keep the exact ratio and maximum area.
    width = min(img.width, img.height * aspect_ratio[0] / aspect_ratio[1])
    height = width * aspect_ratio[1] / aspect_ratio[0]
    return {
        "left": (img.width - width) / 2,
        "top": (img.height - height) / 2,
        "width": width,
        "height": height,
    }


def _build_download_image(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    if CROPPER_AVAILABLE:
        cropped = st_cropper(
            img,
            realtime_update=True,
            box_color="#8c133a",
            aspect_ratio=(target_w, target_h),
            box_algorithm=_initial_crop_box,
            key=f"banner_gen_cropper_{st.session_state.banner_gen_cropper_version}",
        )
        if cropped.width == 0 or cropped.height == 0:
            st.warning("Der gewählte Ausschnitt ist zu klein. Bitte vergrößern.")
            st.stop()
        return ImageOps.fit(cropped, (target_w, target_h), method=Image.Resampling.LANCZOS)

    st.warning("`streamlit-cropper` ist nicht installiert. Verwende automatischen Zuschnitt.")
    return ImageOps.fit(img, (target_w, target_h), method=Image.Resampling.LANCZOS)


def _crop_and_download() -> None:
    image_to_crop = st.session_state.banner_gen_ai_banner_img
    if not image_to_crop:
        return

    target_w, target_h = st.session_state.banner_gen_target_size
    st.caption(f"Tatsächlich erzeugte Bildgröße: {image_to_crop.width}x{image_to_crop.height} px")
    final_image = _build_download_image(image_to_crop, target_w, target_h)
    output_format = st.session_state.banner_gen_output_format_choice
    compression = st.session_state.banner_gen_output_compression
    extension, mime_type, pil_format = _get_output_metadata(output_format)
    save_kwargs = _get_download_save_kwargs(output_format, compression)

    st.image(
        final_image,
        caption=f"Vorschau Banner ({target_w}x{target_h}px)",
        width=400,
    )

    download_image = final_image
    if pil_format == "JPEG" and download_image.mode in {"RGBA", "P"}:
        download_image = download_image.convert("RGB")

    image_buffer = BytesIO()
    download_image.save(image_buffer, format=pil_format, **save_kwargs)

    st.download_button(
        f"📥 Banner herunterladen ({target_w}x{target_h}px - .{extension})",
        data=image_buffer.getvalue(),
        file_name=f"wine_banner_{target_w}x{target_h}.{extension}",
        mime=mime_type,
        type="primary",
        use_container_width=True,
    )


# ---------------------------------------------------- Main page
def banner_generator_page() -> None:
    initialize_session_state()
    df_skus = load_sku_data(SKU_CSV_FILENAME)
    _render_hero()

    _render_step_header(1, "Bildquelle waehlen")
    upload_col, sku_col = st.columns([0.6, 0.4])
    with upload_col:
        _handle_upload()
    with sku_col:
        _handle_sku_lookup(df_skus)

    if not st.session_state.banner_gen_image_input:
        st.info("Bitte zuerst ein Bild hochladen oder per SKU laden.")
        st.stop()

    st.image(
        st.session_state.banner_gen_image_input,
        caption=f"Inspiration: {st.session_state.banner_gen_image_input_name}",
        width=PREVIEW_IMAGE_WIDTH,
    )
    st.markdown("---")

    _render_step_header(2, "Prompt-Stil, Format & Textoptionen")
    _select_options()

    target_w, target_h = st.session_state.banner_gen_target_size
    generation_plan = _get_current_generation_plan()
    st.caption(
        f"Finales Banner: {target_w}x{target_h}px | "
        f"Angefragt: {generation_plan.generation_size_str}px | "
        f"Prompt: {PROMPT_MODE_LABELS[st.session_state.banner_gen_prompt_mode]} | "
        f"Qualitaet: {st.session_state.banner_gen_quality_choice} | "
        f"Downloadformat: {st.session_state.banner_gen_output_format_choice}"
    )

    st.markdown("---")
    _render_step_header(3, "KI-Banner generieren")

    if st.button(
        f"🚀 KI-Banner generieren ({IMAGE_MODEL_LABEL})",
        type="primary",
        use_container_width=True,
        disabled=st.session_state.banner_gen_is_generating or (
            st.session_state.banner_gen_include_text
            and not st.session_state.banner_gen_user_text.strip()
        ),
    ):
        _perform_banner_generation()
        st.rerun()

    if not st.session_state.banner_gen_is_generating:
        if st.session_state.banner_gen_instruction_prompt_for_gpt_image_1:
            with st.expander("📜 Verwendeter KI-Prompt", expanded=False):
                st.code(
                    st.session_state.banner_gen_instruction_prompt_for_gpt_image_1,
                    language="text",
                )

        current_status = st.session_state.banner_gen_status_message
        if "✅ Banner erfolgreich generiert!" in current_status:
            st.success(current_status)
        elif "Fehler" in current_status or "API-Fehler" in current_status:
            st.error(current_status)

    if st.session_state.banner_gen_ai_banner_img and not st.session_state.banner_gen_is_generating:
        st.markdown("---")
        _render_step_header(4, "Ergebnis ansehen & herunterladen")
        _crop_and_download()
    elif not st.session_state.banner_gen_is_generating:
        st.markdown("---")
        st.info("Klicke auf '🚀 KI-Banner generieren', um das Banner zu erstellen.")


if __name__ == "__main__":
    banner_generator_page()
