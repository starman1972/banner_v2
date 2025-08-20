import os
import requests
from PIL import Image
from io import BytesIO
import base64
import fal_client

from utils import get_secret

# --- Stability AI Upscaler ---

def _get_stability_api_key():
    """Holt den Stability-Key sicher."""
    key = get_secret("STABILITY_API_KEY")
    if not key:
        raise ValueError("STABILITY_API_KEY wurde weder in st.secrets noch in der .env-Datei gefunden.")
    return key

def upscale_with_stability(image_bytes: bytes, model: str) -> Image.Image:
    """
    Skaliert ein Bild mit der Stability AI API hoch.
    :param image_bytes: Die Roh-Bytes des Bildes.
    :param model: Entweder 'fast' oder 'conservative'.
    """
    api_key = _get_stability_api_key()
    
    if model == 'fast':
        url = "https://api.stability.ai/v2beta/stable-image/upscale/fast"
        data = {"output_format": "png"}
    elif model == 'conservative':
        url = "https://api.stability.ai/v2beta/stable-image/upscale/conservative"
        # Generischer, aber effektiver Prompt, um die Qualität zu verbessern, ohne den Inhalt zu verändern.
        prompt = "professional high-quality photo, sharp focus, high definition, enhanced detail, clear image"
        data = {"prompt": prompt, "output_format": "png"}
    else:
        raise ValueError("Ungültiges Stability-Modell. Wähle 'fast' oder 'conservative'.")

    try:
        response = requests.post(
            url,
            headers={
                "authorization": f"Bearer {api_key}",
                "accept": "image/*"
            },
            files={"image": image_bytes},
            data=data
        )
        response.raise_for_status()  # Löst einen Fehler bei HTTP-Statuscodes 4xx/5xx aus
        return Image.open(BytesIO(response.content)).convert("RGB")
    except requests.exceptions.HTTPError as e:
        # Versucht, eine detailliertere Fehlermeldung aus dem JSON-Body zu extrahieren
        try:
            error_details = e.response.json()
            raise Exception(f"Stability AI API Fehler (HTTP {e.response.status_code}): {error_details}")
        except:
            raise Exception(f"Stability AI API Fehler (HTTP {e.response.status_code}): {e.response.text}")
    except Exception as e:
        raise Exception(f"Ein unerwarteter Fehler bei der Kommunikation mit Stability AI ist aufgetreten: {e}")


# --- Fal.ai Upscaler ---

def _image_bytes_to_data_url(image_bytes: bytes, mime_type: str = "image/png") -> str:
    """Konvertiert Bild-Bytes in einen Base64-Data-URL."""
    base64_encoded_data = base64.b64encode(image_bytes).decode('utf-8')
    return f"data:{mime_type};base64,{base64_encoded_data}"

def upscale_with_fal(image_bytes: bytes) -> Image.Image:
    """
    Skaliert ein Bild mit der Fal.ai Recraft Crisp Upscaler API hoch.
    """
    # Sicherstellen, dass der FAL_KEY in der Umgebung gesetzt ist
    if not get_secret("FAL_KEY"):
         raise ValueError("FAL_KEY wurde weder in st.secrets noch in der .env-Datei gefunden.")

    try:
        data_url = _image_bytes_to_data_url(image_bytes)
        
        # Die `fal-client`-Bibliothek vereinfacht den Aufruf
        result = fal_client.run(
            "fal-ai/recraft/upscale/crisp",
            arguments={"image_url": data_url}
        )
        
        if not result or "image" not in result or not result["image"]["url"]:
            raise ValueError("Fal.ai API hat keine gültige Bild-URL zurückgegeben.")
            
        upscaled_image_url = result["image"]["url"]
        
        # Herunterladen des hochskalierten Bildes
        response = requests.get(upscaled_image_url, timeout=60)
        response.raise_for_status()
        
        return Image.open(BytesIO(response.content)).convert("RGB")
    except Exception as e:
        raise Exception(f"Ein Fehler bei der Kommunikation mit Fal.ai ist aufgetreten: {e}")