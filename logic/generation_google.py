from __future__ import annotations
import os
from io import BytesIO
from typing import Tuple
from PIL import Image
import streamlit as st

import vertexai
from vertexai.vision_models import ImageGenerationModel
from google.oauth2 import service_account

from utils import get_secret


def _best_imagen_aspect_ratio(target_w: int, target_h: int) -> str:
    target_ratio = (target_w / target_h) if target_h else 1.0
    aspect_map: dict[str, float] = {
        "1:1": 1.0, "16:9": 16 / 9, "9:16": 9 / 16,
        "4:3": 4 / 3, "3:4": 3 / 4,
    }
    return min(aspect_map.items(), key=lambda kv: abs(kv[1] - target_ratio))[0]

def get_closest_imagen_dimensions(target_w: int, target_h: int) -> str:
    return _best_imagen_aspect_ratio(target_w, target_h)

def generate_image_with_google_imagen(prompt: str, target_w: int, target_h: int) -> Image.Image:
    """Generiert ein Bild mit Google Vertex AI Imagen über das stabile und umgebungsbewusste SDK."""
    project_id = get_secret("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        raise ValueError("GOOGLE_CLOUD_PROJECT wurde weder in st.secrets noch in der .env-Datei gefunden.")

    credentials = None
    try:
        # Fall 1: Wir sind in der Streamlit Cloud und lesen die strukturierte Tabelle
        if "google_credentials" in st.secrets:
            # st.secrets.google_credentials ist bereits ein Dictionary-ähnliches Objekt
            creds_info = st.secrets.google_credentials.to_dict()
            credentials = service_account.Credentials.from_service_account_info(
                creds_info, scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
    except Exception:
        # Fallback für lokale Entwicklung, wenn st.secrets nicht existiert
        pass

    if not credentials:
        # Fall 2: Wir sind lokal und laden aus dem Dateipfad, der in .env steht
        cred_path = get_secret("GOOGLE_APPLICATION_CREDENTIALS")
        if cred_path and os.path.exists(cred_path):
             credentials = service_account.Credentials.from_service_account_file(
                cred_path, scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
        else:
            raise ValueError("Google Credentials konnten nicht geladen werden.")

    try:
        vertexai.init(project=project_id, location="us-central1", credentials=credentials)
    except Exception as e:
        raise ConnectionError(f"Fehler bei der Initialisierung von Vertex AI: {e}")

    model = ImageGenerationModel.from_pretrained("imagegeneration@006")
    aspect_ratio_str = get_closest_imagen_dimensions(target_w, target_h)

    response = model.generate_images(
        prompt=prompt,
        number_of_images=1,
        aspect_ratio=aspect_ratio_str,
    )

    if not response.images:
        raise ValueError("Kein Bild von der Google-Imagen-API erhalten.")

    image_bytes = response.images[0]._image_bytes
    pil_image = Image.open(BytesIO(image_bytes))
    return pil_image.convert("RGB")