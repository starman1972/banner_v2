from __future__ import annotations
import os
import json
from io import BytesIO
from typing import Tuple
from PIL import Image

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

    value_json = get_secret("GOOGLE_CREDENTIALS_JSON")
    value_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    credentials = None
    if value_json and value_json.strip() != "":
        creds_info = json.loads(value_json)
        credentials = service_account.Credentials.from_service_account_info(
            creds_info, scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
    elif value_path and value_path.strip() != "":
        if os.path.exists(value_path):
            credentials = service_account.Credentials.from_service_account_file(
                value_path, scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
        else:
            raise ValueError(
                f"GOOGLE_APPLICATION_CREDENTIALS zeigt auf keine existierende Datei: {value_path}"
            )
    else:
        raise ValueError(
            "Google Credentials konnten nicht geladen werden. Setze GOOGLE_CREDENTIALS_JSON (Service-Account JSON als String) "
            "oder GOOGLE_APPLICATION_CREDENTIALS (Pfad zur JSON-Datei)."
        )

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
