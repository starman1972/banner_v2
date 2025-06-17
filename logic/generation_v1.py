import openai
import base64
from io import BytesIO
from PIL import Image
from typing import Tuple

# === V1: Bildanalyse und DALL-E Prompt Generierung (GPT-4o) ===
def encode_image_to_base64(img: Image.Image) -> str:
    """Konvertiert ein PIL Image in einen Base64-kodierten String."""
    buffered = BytesIO()
    img.save(buffered, format="JPEG") # JPEG ist für Vision-Modelle oft ausreichend
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def generate_banner_prompt_gpt4(img: Image.Image, system_prompt: str) -> str:
    """Sendet ein Bild an GPT-4o und generiert basierend darauf einen DALL-E Prompt."""
    base64_image = encode_image_to_base64(img)
    
    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                { "role": "system", "content": system_prompt },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Please analyze this image and generate the DALL·E 3 prompt based on your instructions."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                    ],
                }
            ],
            max_tokens=300
        )
        if response.choices[0].message.content:
            return response.choices[0].message.content.strip()
        else:
            raise ValueError("GPT-4o hat einen leeren Prompt zurückgegeben.")
    except Exception as e:
        print(f"Fehler bei der Kommunikation mit GPT-4o: {e}")
        raise

# === V1: DALL-E 3 Bildgenerierung ===
def get_best_dalle_size(target_aspect_ratio: float) -> str:
    """Wählt die am besten passende DALL·E 3 Ausgabegröße."""
    dalle_sizes = {
        "square": (1.0, "1024x1024"),
        "wide": (1792 / 1024, "1792x1024"),
        "tall": (1024 / 1792, "1024x1792")
    }
    closest_size_key = min(dalle_sizes.keys(), key=lambda k: abs(dalle_sizes[k][0] - target_aspect_ratio))
    return dalle_sizes[closest_size_key][1]

def generate_dalle_image(prompt: str, size: str = "1792x1024", quality: str = "standard") -> str:
    """Generiert ein Bild mit DALL·E 3 und gibt die URL zurück."""
    try:
        response = openai.images.generate(
            model="dall-e-3",
            prompt=prompt,
            n=1,
            size=size, # type: ignore
            quality=quality,
            response_format="url"
        )
        if response.data[0].url:
            return response.data[0].url
        else:
            raise ValueError("DALL-E API hat keine Bild-URL zurückgegeben.")
    except openai.BadRequestError as e:
        if e.body and "content_policy_violation" in str(e.body):
            raise ValueError(f"DALL·E hat den Prompt aufgrund von Content-Richtlinien abgelehnt. Prompt: '{prompt[:100]}...'") from e
        raise
    except Exception as e:
        print(f"Fehler bei der DALL-E Bildgenerierung: {e}")
        raise