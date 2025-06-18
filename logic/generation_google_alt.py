from __future__ import annotations
import os
from io import BytesIO
import json
from typing import Tuple
from PIL import Image

# Importiere die korrekten, aktuellen und stabilen Klassen für Vertex AI
import vertexai
from vertexai.vision_models import ImageGenerationModel
from google.oauth2 import service_account

# WICHTIG: Importiere unsere robuste Hilfsfunktion
from utils import get_secret


def _best_imagen_aspect_ratio(target_w: int, target_h: int) -> str:
    """Liefert das zu Imagen passende aspect_ratio-Label."""
    target_ratio = (target_w / target_h) if target_h else 1.0
    aspect_map: dict[str, float] = {
        "1:1": 1.0, "16:9": 16 / 9, "9:16": 9 / 16,
        "4:3": 4 / 3, "3:4": 3 / 4,
    }
    return min(aspect_map.items(), key=lambda kv: abs(kv[1] - target_ratio))[0]

def get_closest_imagen_dimensions(target_w: int, target_h: int) -> str:
    """Alias – hält den alten Funktionsnamen am Leben."""
    return _best_imagen_aspect_ratio(target_w, target_h)

def generate_image_with_google_imagen(prompt: str, target_w: int, target_h: int) -> Image.Image:
    """Generiert ein Bild mit Google Vertex AI Imagen über das stabile und umgebungsbewusste SDK."""
    # --- START DER FINALEN KORREKTUR ---
    
    # Schritt 1: Lade Projekt-ID und Credentials sicher mit unserer Hilfsfunktion
    project_id = get_secret("GOOGLE_CLOUD_PROJECT")
    creds_json_str = get_secret("GOOGLE_CREDENTIALS_JSON") # Für Streamlit Cloud
    cred_path = get_secret("GOOGLE_APPLICATION_CREDENTIALS") # Für lokale .env

    if not project_id:
        raise ValueError("GOOGLE_CLOUD_PROJECT wurde weder in st.secrets noch in der .env-Datei gefunden.")

    # Schritt 2: Erstelle das Credentials-Objekt basierend auf der Umgebung
    credentials = None
    if creds_json_str:
        # Fall 1: Wir sind in der Streamlit Cloud und laden aus dem JSON-String
        creds_info = json.loads(creds_json_str)
        credentials = service_account.Credentials.from_service_account_info(
            creds_info, scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
    elif cred_path:
        # Fall 2: Wir sind lokal und laden aus dem Dateipfad, der in .env steht
        credentials = service_account.Credentials.from_service_account_file(
            cred_path, scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )

    if not credentials:
        raise ValueError("Google Credentials konnten nicht geladen werden. Stellen Sie sicher, dass entweder GOOGLE_CREDENTIALS_JSON in st.secrets oder GOOGLE_APPLICATION_CREDENTIALS in .env gesetzt ist.")

    # --- ENDE DER FINALEN KORREKTUR ---

    try:
        # Initialisiere Vertex AI mit dem sicher geladenen Credentials-Objekt
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