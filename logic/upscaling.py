import os
import requests
from PIL import Image
from io import BytesIO
import base64
import fal_client
from math import sqrt

from utils import get_secret

# --- Konstante: Fal.ai erlaubt max. 4'194'304 Pixel (≈ 4.19 MP) ---
MAX_PIXELS = 4_194_304


def _image_bytes_to_data_url(image_bytes: bytes, mime_type: str = "image/png") -> str:
    """Konvertiert Bild-Bytes in einen Base64-Data-URL."""
    base64_encoded_data = base64.b64encode(image_bytes).decode('utf-8')
    return f"data:{mime_type};base64,{base64_encoded_data}"


def _downscale_to_max_pixels(image: Image.Image, max_pixels: int = MAX_PIXELS) -> Image.Image:
    """
    Skaliert ein Pillow-Image proportional herunter, falls width*height > max_pixels.
    Bewahrt Seitenverhältnis und nutzt LANCZOS für beste Qualität.
    """
    w, h = image.size
    if w * h <= max_pixels:
        return image

    scale = sqrt(max_pixels / (w * h))
    new_w = max(1, int(w * scale))
    new_h = max(1, int(h * scale))
    return image.resize((new_w, new_h), Image.LANCZOS)


def upscale_with_fal(image_bytes: bytes) -> Image.Image:
    """
    Skaliert ein Bild mit der Fal.ai Recraft Crisp Upscaler API hoch.
    Führt automatisch Downscaling auf <= 4.19 MP durch, falls nötig.
    """
    if not get_secret("FAL_KEY"):
        raise ValueError("FAL_KEY wurde weder in st.secrets noch in der .env-Datei gefunden.")

    try:
        # Bild aus Bytes laden
        image = Image.open(BytesIO(image_bytes))
        w, h = image.size

        # Automatische Reduktion bei zu hoher Auflösung
        if w * h > MAX_PIXELS:
            original_size = (w, h)
            image = _downscale_to_max_pixels(image, MAX_PIXELS)
            print(
                f"[INFO] Eingabebild automatisch herunterskaliert: "
                f"{original_size[0]}x{original_size[1]} → {image.width}x{image.height} px "
                f"(Fal.ai-Limit: ≤ {MAX_PIXELS:,} Pixel)"
            )

        # In PNG-Bytes umwandeln (verlustfrei, universell kompatibel)
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        safe_bytes = buffer.getvalue()

        # In Base64-Data-URL konvertieren
        data_url = _image_bytes_to_data_url(safe_bytes)

        # Fal.ai-Aufruf
        result = fal_client.run(
            "fal-ai/recraft/upscale/crisp",
            arguments={"image_url": data_url}
        )

        if not result or "image" not in result or not result["image"]["url"]:
            raise ValueError("Fal.ai API hat keine gültige Bild-URL zurückgegeben.")

        upscaled_image_url = result["image"]["url"]

        # Hochskaliertes Bild abrufen
        response = requests.get(upscaled_image_url, timeout=60)
        response.raise_for_status()

        return Image.open(BytesIO(response.content)).convert("RGB")

    except Exception as e:
        raise Exception(f"Ein Fehler bei der Kommunikation mit Fal.ai ist aufgetreten: {e}")
