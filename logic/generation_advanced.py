import openai
import base64
from io import BytesIO
from PIL import Image
from typing import Tuple

def get_best_gpt_image_1_size(target_aspect_ratio: float) -> str:
    """
    Wählt die am besten passende gpt-image-1 Ausgabegröße.
    Unterstützt: "1024x1024", "1536x1024" (landscape), "1024x1536" (portrait).
    """
    gpt_image_1_sizes = {
        "square": (1.0, "1024x1024"),
        "landscape": (1536 / 1024, "1536x1024"), # 1.5
        "portrait": (1024 / 1536, "1024x1536")  # ~0.667
    }
    closest_size_key = min(
        gpt_image_1_sizes.keys(),
        key=lambda k: abs(gpt_image_1_sizes[k][0] - target_aspect_ratio)
    )
    return gpt_image_1_sizes[closest_size_key][1]

def generate_image_with_gpt_image_1_from_text(prompt: str, size: str, quality: str = "auto") -> Image.Image:
    """
    Generiert ein Bild mit gpt-image-1 aus einem Text-Prompt.
    Gibt ein PIL Image Objekt zurück.
    """
    try:
        response = openai.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            n=1,
            size=size, # type: ignore
            quality=quality
        )
        if response.data and response.data[0].b64_json:
            b64_data = response.data[0].b64_json
            image_data_bytes = base64.b64decode(b64_data)
            generated_image_pil = Image.open(BytesIO(image_data_bytes))
            return generated_image_pil.convert("RGB")
        else:
            raise ValueError("gpt-image-1 API hat keine Bilddaten zurückgegeben.")
    except openai.BadRequestError as e:
        detail_msg = str(e)
        if e.body and isinstance(e.body, dict) and 'error' in e.body and 'message' in e.body['error']:
            detail_msg = e.body['error']['message']
        if "content_policy_violation" in detail_msg:
            raise ValueError(f"Der Prompt wurde aufgrund von Content-Richtlinien abgelehnt. Prompt: '{prompt[:100]}...'") from e
        raise ValueError(f"API Bad Request: {detail_msg}") from e
    except Exception as e:
        print(f"Fehler bei der gpt-image-1 Bildgenerierung: {e}")
        raise