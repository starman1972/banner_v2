import os
import requests
from PIL import Image
from io import BytesIO
import base64
import fal_client

from utils import get_secret

# --- Fal.ai Upscaler ---

def _image_bytes_to_data_url(image_bytes: bytes, mime_type: str = "image/png") -> str:
    """Konvertiert Bild-Bytes in einen Base64-Data-URL."""
    base64_encoded_data = base64.b64encode(image_bytes).decode('utf-8')
    return f"data:{mime_type};base64,{base64_encoded_data}"

def upscale_with_fal(image_bytes: bytes) -> Image.Image:
    """
    Skaliert ein Bild mit der Fal.ai Recraft Crisp Upscaler API hoch.
    """
    if not get_secret("FAL_KEY"):
         raise ValueError("FAL_KEY wurde weder in st.secrets noch in der .env-Datei gefunden.")

    try:
        data_url = _image_bytes_to_data_url(image_bytes)
        
        result = fal_client.run(
            "fal-ai/recraft/upscale/crisp",
            arguments={"image_url": data_url}
        )
        
        if not result or "image" not in result or not result["image"]["url"]:
            raise ValueError("Fal.ai API hat keine gültige Bild-URL zurückgegeben.")
            
        upscaled_image_url = result["image"]["url"]
        
        response = requests.get(upscaled_image_url, timeout=60)
        response.raise_for_status()
        
        return Image.open(BytesIO(response.content)).convert("RGB")
    except Exception as e:
        raise Exception(f"Ein Fehler bei der Kommunikation mit Fal.ai ist aufgetreten: {e}")