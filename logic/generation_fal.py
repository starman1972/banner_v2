import os
from dataclasses import dataclass
from io import BytesIO
from typing import Optional

import fal_client
import requests
from PIL import Image
import base64


def _ratio_to_dimensions(aspect_ratio: str, base_width: int = 2048) -> tuple[int, int]:
    """Parse 'width:height' string into absolute ints, scaled to base_width."""
    try:
        w_str, h_str = aspect_ratio.split(":")
        ratio_w = int(w_str.strip())
        ratio_h = int(h_str.strip())
        if ratio_w <= 0 or ratio_h <= 0:
            raise ValueError
    except Exception as exc:  # pragma: no cover - defensive parsing
        raise ValueError(f"Ungültiges Aspect Ratio: '{aspect_ratio}'") from exc

    target_height = max(64, int(round(base_width * ratio_h / ratio_w)))
    return base_width, target_height


def _blank_data_uri(width: int, height: int, color: tuple[int, int, int] = (255, 255, 255)) -> str:
    """Create a simple JPEG data URI placeholder."""
    image = Image.new("RGB", (width, height), color=color)
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    base64_payload = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{base64_payload}"


@dataclass(frozen=True)
class FalFluxBannerResult:
    image: Image.Image
    requested_width: Optional[int]
    requested_height: Optional[int]
    returned_width: Optional[int]
    returned_height: Optional[int]
    seed: Optional[int] = None
    requested_aspect_ratio: Optional[str] = None
    used_placeholder_image: bool = False

    @property
    def size_matches_request(self) -> bool:
        if self.requested_width is None or self.requested_height is None:
            return False
        if self.returned_width is None or self.returned_height is None:
            return False
        return (
            int(self.returned_width) == int(self.requested_width)
            and int(self.returned_height) == int(self.requested_height)
        )


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
            },
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


def generate_flux_banner_with_explicit_size(
    prompt: str,
    width: int,
    height: int,
    *,
    num_inference_steps: int = 28,
    guidance_scale: float = 7.0,
    seed: Optional[int] = None,
) -> FalFluxBannerResult:
    """
    Nutzt den Fal `fal-ai/flux/dev` Endpunkt, um ein Banner in einer expliziten Zielgröße
    (Breite/Höhe) zu erzeugen. Ferner erlaubt optional die Angabe eines Seeds.
    """
    fal_key = os.environ.get("FAL_KEY")
    if not fal_key:
        raise ValueError("Fal AI Key nicht in .env gefunden (FAL_KEY).")

    if width <= 0 or height <= 0:
        raise ValueError("Width und Height müssen größer als 0 sein.")

    arguments = {
        "prompt": prompt,
        "image_size": {
            "width": int(width),
            "height": int(height),
        },
        "num_inference_steps": num_inference_steps,
        "guidance_scale": guidance_scale,
    }
    if seed is not None:
        arguments["seed"] = seed

    try:
        result = fal_client.run("fal-ai/flux/dev", arguments=arguments)
    except Exception as e:
        raise RuntimeError(f"Fal/Flux Anfrage fehlgeschlagen: {e}") from e

    if not result:
        raise RuntimeError("Fal/Flux hat keine Antwort zurückgegeben.")

    image_url = None
    returned_width = None
    returned_height = None

    if isinstance(result.get("image"), dict):
        image_payload = result["image"]
        image_url = image_payload.get("url")
        returned_width = image_payload.get("width")
        returned_height = image_payload.get("height")
    elif isinstance(result.get("images"), list) and result["images"]:
        image_payload = result["images"][0]
        image_url = image_payload.get("url")
        returned_width = image_payload.get("width")
        returned_height = image_payload.get("height")

    if not image_url:
        raise RuntimeError(f"Fal/Flux hat keine gültige Bild-URL geliefert: {result}")

    try:
        response = requests.get(image_url, timeout=60)
        response.raise_for_status()
    except Exception as e:
        raise RuntimeError(f"Bilddownload fehlgeschlagen: {e}") from e

    try:
        image = Image.open(BytesIO(response.content)).convert("RGB")
    except Exception as e:
        raise RuntimeError(f"Bild konnte nicht geöffnet werden: {e}") from e

    actual_width = image.width
    actual_height = image.height

    returned_width = int(returned_width or actual_width)
    returned_height = int(returned_height or actual_height)

    return FalFluxBannerResult(
        image=image,
        requested_width=int(width),
        requested_height=int(height),
        returned_width=returned_width,
        returned_height=returned_height,
        seed=result.get("seed"),
        requested_aspect_ratio=None,
        used_placeholder_image=False,
    )


def generate_flux_ultra_redux_banner(
    prompt: str,
    *,
    aspect_ratio: str = "4:1",
    image_url: Optional[str] = None,
    image_prompt_strength: float = 0.0,
    num_inference_steps: int = 28,
    guidance_scale: float = 3.5,
    num_images: int = 1,
    enable_safety_checker: bool = True,
    safety_tolerance: str = "2",
    output_format: str = "jpeg",
    enhance_prompt: bool = True,
    sync_mode: bool = False,
    seed: Optional[int] = None,
) -> FalFluxBannerResult:
    """
    Wrapper für den `fal-ai/flux-pro/v1.1-ultra/redux` Endpunkt.
    Unterstützt sowohl Text-zu-Bild (nur Prompt) als auch Bild-zu-Bild per `image_url`.
    """
    if not os.environ.get("FAL_KEY"):
        raise ValueError("Fal AI Key nicht in .env gefunden (FAL_KEY).")

    if num_images < 1:
        raise ValueError("num_images muss >= 1 sein.")

    if image_url and not image_url.startswith(("http://", "https://")):
        raise ValueError("image_url muss eine absolute HTTP/HTTPS-URL sein.")

    arguments = {
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "num_images": num_images,
        "enable_safety_checker": enable_safety_checker,
        "output_format": output_format,
        "safety_tolerance": safety_tolerance,
        "num_inference_steps": num_inference_steps,
        "guidance_scale": guidance_scale,
        "enhance_prompt": enhance_prompt,
    }

    if sync_mode:
        arguments["sync_mode"] = True

    if seed is not None:
        arguments["seed"] = int(seed)

    placeholder_used = False

    if image_url:
        arguments["image_url"] = image_url
        arguments["image_prompt_strength"] = float(image_prompt_strength)
    else:
        placeholder_used = True
        placeholder_width, placeholder_height = _ratio_to_dimensions(aspect_ratio, base_width=1024)
        arguments["image_url"] = _blank_data_uri(placeholder_width, placeholder_height)
        arguments["image_prompt_strength"] = 0.0

    try:
        result = fal_client.run("fal-ai/flux-pro/v1.1-ultra/redux", arguments=arguments)
    except Exception as exc:
        raise RuntimeError(f"Fal/Flux Ultra Redux Anfrage fehlgeschlagen: {exc}") from exc

    if not result:
        raise RuntimeError("Fal/Flux Ultra Redux hat keine Antwort zurückgegeben.")

    image_payload = None
    image_url_result = None
    returned_width = None
    returned_height = None

    # Schema laut Doku: `images` Liste mit URL + optional width/height
    if isinstance(result.get("images"), list) and result["images"]:
        image_payload = result["images"][0]
    elif isinstance(result.get("image"), dict):
        image_payload = result["image"]

    if image_payload:
        image_url_result = image_payload.get("url")
        returned_width = image_payload.get("width")
        returned_height = image_payload.get("height")

        # sync_mode True kann Base64 liefern (data URI)
        if not image_url_result and image_payload.get("content"):
            image_url_result = image_payload["content"]

    if not image_url_result:
        raise RuntimeError(f"Fal/Flux Ultra Redux hat keine Bild-URL geliefert: {result}")

    image_content: Optional[bytes] = None

    if image_url_result.startswith("data:"):
        # Data URI -> herauslösen
        header, _, data_part = image_url_result.partition(",")
        if not data_part:
            raise RuntimeError("Data-URI ohne Inhalt erhalten.")
        import base64

        try:
            image_content = base64.b64decode(data_part)
        except Exception as exc:
            raise RuntimeError(f"Data-URI konnte nicht dekodiert werden: {exc}") from exc
    else:
        try:
            response = requests.get(image_url_result, timeout=60)
            response.raise_for_status()
        except Exception as exc:
            raise RuntimeError(f"Bilddownload fehlgeschlagen: {exc}") from exc
        image_content = response.content

    try:
        image = Image.open(BytesIO(image_content)).convert("RGB")
    except Exception as exc:
        raise RuntimeError(f"Bild konnte nicht geöffnet werden: {exc}") from exc

    actual_width = image.width
    actual_height = image.height

    returned_width = int(returned_width or actual_width)
    returned_height = int(returned_height or actual_height)

    result_seed = result.get("seed")
    # seed might be nested for redux responses
    if not result_seed and isinstance(result.get("seeds"), list):
        maybe_seed = result["seeds"][0]
        result_seed = maybe_seed

    return FalFluxBannerResult(
        image=image,
        requested_width=None,
        requested_height=None,
        returned_width=returned_width,
        returned_height=returned_height,
        seed=result_seed,
        requested_aspect_ratio=aspect_ratio,
        used_placeholder_image=placeholder_used,
    )
