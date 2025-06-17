import openai
import base64
from io import BytesIO
from PIL import Image
from typing import Tuple

# === Bildkodierung (für den Upload an OpenAI API) ===
def pil_to_bytes_with_mimetype(img: Image.Image, format: str = "PNG") -> Tuple[bytes, str]:
    """
    Konvertiert ein PIL Image Objekt in Bytes und gibt den Mimetype zurück.
    Format: PNG, JPEG, WEBP
    """
    buffered = BytesIO()
    actual_format = format.upper()
    mimetype = f"image/{actual_format.lower()}"

    if actual_format == "JPEG":
        if img.mode == 'RGBA' or img.mode == 'P':
            img = img.convert('RGB')
        mimetype = "image/jpeg"
    elif actual_format == "WEBP":
        mimetype = "image/webp"
    elif actual_format == "PNG":
        mimetype = "image/png"
    else:
        raise ValueError(f"Unsupported format for pil_to_bytes_with_mimetype: {format}")

    img.save(buffered, format=actual_format)
    return buffered.getvalue(), mimetype

# === GPT-Image-1: Auswahl der besten nativen Ausgabegröße ===
def get_best_dalle_size(target_aspect_ratio: float) -> str:
    """
    Wählt die am besten passende gpt-image-1 Ausgabegröße.
    Unterstützt: "1024x1024", "1536x1024" (landscape), "1024x1536" (portrait).
    """
    gpt_image_1_sizes = {
        "square": (1.0, "1024x1024"),
        "landscape": (1536 / 1024, "1536x1024"),
        "portrait": (1024 / 1536, "1024x1536")
    }
    closest_size_key = min(
        gpt_image_1_sizes.keys(),
        key=lambda k: abs(gpt_image_1_sizes[k][0] - target_aspect_ratio)
    )
    return gpt_image_1_sizes[closest_size_key][1]

# === GPT-Image-1: Generierung des Bildes basierend auf einem Referenzbild ===
def generate_banner_with_gpt_image_1(
    original_image_pil: Image.Image,
    instruction_prompt: str,
    target_size_str: str,
    quality: str = "auto" # 'low', 'medium', 'high', oder 'auto'
) -> Image.Image:
    """
    Generiert ein Banner mit gpt-image-1, inspiriert vom original_image_pil.
    target_size_str: Eine der von gpt-image-1 unterstützten Größen-Strings.
    quality: Die gewünschte Qualität des generierten Bildes für gpt-image-1.
    """
    if not instruction_prompt:
        raise ValueError("Instruction prompt cannot be empty for gpt-image-1.")
    if not original_image_pil:
        raise ValueError("Original image (PIL) must be provided for gpt-image-1.")
    if quality not in ["low", "medium", "high", "auto"]:
        raise ValueError(f"Invalid quality setting: {quality}. Must be one of 'low', 'medium', 'high', 'auto'.")

    try:
        image_bytes, image_mimetype = pil_to_bytes_with_mimetype(original_image_pil, format="PNG")
        dummy_filename = f"input_image.{image_mimetype.split('/')[1]}"

        response = openai.images.edit(
            model="gpt-image-1",
            image=(dummy_filename, image_bytes, image_mimetype),
            prompt=instruction_prompt,
            n=1,
            size=target_size_str, # type: ignore
            quality=quality # Qualitätsparameter hinzugefügt
        )

        if response.data and response.data[0].b64_json:
            b64_data = response.data[0].b64_json
            image_data_bytes = base64.b64decode(b64_data)
            generated_image_pil = Image.open(BytesIO(image_data_bytes))
            return generated_image_pil.convert("RGB")
        else:
            raise ValueError("No image data received from gpt-image-1 API response, or data is empty.")

    except openai.BadRequestError as e:
        error_body = e.body
        error_message = f"gpt-image-1 API Bad Request: {str(e)}."
        detail_msg = ""

        if error_body:
            if isinstance(error_body, dict) and "error" in error_body and isinstance(error_body["error"], dict) and "message" in error_body["error"]:
                 detail_msg = error_body["error"]["message"]
                 error_message = f"gpt-image-1 API Bad Request: {detail_msg}"
            elif "content_policy_violation" in str(error_body).lower():
                 error_message = (f"gpt-image-1 rejected the request due to content policy. "
                                 f"Prompt: '{instruction_prompt[:100]}...'. Please revise.")
            elif "billing" in str(error_body).lower():
                 error_message = "gpt-image-1 image generation failed. Please check your OpenAI account billing status."
            elif "unsupported mimetype" in str(error_body).lower():
                error_message = f"gpt-image-1 API Error: Unsupported image file type. Details: {str(error_body)}"

        print(f"Original BadRequestError: {e}")
        print(f"Parsed error message for UI: {error_message}")

        if "content_policy_violation" in error_message.lower():
            raise ValueError(f"DALL·E rejected the prompt due to content policy: '{instruction_prompt[:100]}...'. Please revise your prompt.") from e
        elif "billing" in error_message.lower():
             raise ValueError("DALL·E image generation failed. Please check your OpenAI account billing status.") from e
        elif "unsupported mimetype" in error_message.lower() or "unsupported file format" in error_message.lower() :
            raise ValueError("The uploaded image format is not supported by the AI. Please use PNG, JPEG, or WEBP.") from e

        raise ValueError(error_message) from e

    except openai.APIError as e:
        error_message = f"OpenAI gpt-image-1 API error: {e}"
        if hasattr(e, 'message') and e.message: # type: ignore
            error_message += f" - Details: {e.message}" # type: ignore
        print(error_message)
        raise
    except Exception as e:
        print(f"An unexpected error occurred during gpt-image-1 image generation: {e}")
        raise