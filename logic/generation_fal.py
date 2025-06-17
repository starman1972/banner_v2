import os
import requests
from PIL import Image
from io import BytesIO
import fal_client

def _generate_fal_image(model_id: str, prompt: str, aspect_ratio: str) -> Image.Image:
    """Eine generische Hilfsfunktion, um ein Bild von einem Fal AI Modell zu generieren."""
    if not os.environ.get("FAL_KEY"):
        raise ValueError("Fal AI Key nicht in .env gefunden (FAL_KEY).")
        
    try:
        result = fal_client.subscribe(
            model_id,
            arguments={
                "prompt": prompt,
                "aspect_ratio": aspect_ratio,
            }
        )
        if not result or "images" not in result or not result["images"]:
            raise ValueError("Fal AI API hat keine Bilder zurückgegeben.")
        
        image_url = result["images"][0]["url"]
        
        response = requests.get(image_url, timeout=45)
        response.raise_for_status()
        
        img = Image.open(BytesIO(response.content))
        return img.convert("RGB")
    except Exception as e:
        raise Exception(f"Fehler bei der Fal AI Bildgenerierung ({model_id}): {e}")

def generate_image_with_fal_flux_pro(prompt: str, aspect_ratio: str) -> Image.Image:
    """Generiert ein Bild mit dem Fal AI FLUX.1 Pro Modell."""
    return _generate_fal_image("fal-ai/flux-pro/kontext/text-to-image", prompt, aspect_ratio)

def generate_image_with_fal_flux_ultra(prompt: str, aspect_ratio: str) -> Image.Image:
    """Generiert ein Bild mit dem Fal AI FLUX.1 Ultra Modell."""
    return _generate_fal_image("fal-ai/flux-pro/v1.1-ultra", prompt, aspect_ratio)

def generate_image_with_ideogram_v3(prompt: str, aspect_ratio: str) -> Image.Image:
    """Generiert ein Bild mit dem Ideogram v3 Modell via Fal AI."""
    return _generate_fal_image("fal-ai/ideogram/v3", prompt, aspect_ratio)