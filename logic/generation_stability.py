import os
import requests
from PIL import Image
from io import BytesIO
from typing import Tuple

STABILITY_ASPECT_RATIO_MAP = {
    (1920, 1080): "16:9", (1024, 1024): "1:1", (1080, 1920): "9:16",
    (3000, 660): "21:9", (1500, 1000): "3:2",
}

def get_best_stability_aspect_ratio(target_w: int, target_h: int) -> str:
    target_ratio = target_w / target_h if target_h > 0 else 1.0
    closest_match = min(STABILITY_ASPECT_RATIO_MAP.keys(), key=lambda size: abs((size[0] / size[1]) - target_ratio))
    return STABILITY_ASPECT_RATIO_MAP[closest_match]

def generate_image_with_stability_ai(prompt: str, aspect_ratio: str) -> Image.Image:
    api_key = os.environ.get("STABILITY_API_KEY")
    if not api_key: raise ValueError("Stability AI API Key nicht in .env gefunden (STABILITY_API_KEY).")
    host = "https://api.stability.ai/v2beta/stable-image/generate/ultra"
    headers = {"authorization": f"Bearer {api_key}", "accept": "image/*"}
    data = {"prompt": prompt, "aspect_ratio": aspect_ratio, "output_format": "jpeg"}
    response = requests.post(host, headers=headers, files={"none": ''}, data=data)
    if response.status_code == 200:
        return Image.open(BytesIO(response.content)).convert("RGB")
    else:
        raise Exception(f"Stability AI API Fehler (HTTP {response.status_code}): {response.text}")