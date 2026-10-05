import base64
from dataclasses import dataclass
from io import BytesIO
from typing import Any, Optional, Tuple

import openai
from PIL import Image

from logic.openai_client import get_openai_client

SUPPORTED_OUTPUT_FORMATS = {"png", "jpeg", "webp"}
VALID_QUALITY_OPTIONS = {"auto", "low", "medium", "high"}
VALID_MODERATION_OPTIONS = {"auto", "low"}
DEFAULT_GENERATION_QUALITY = "medium"
DEFAULT_OUTPUT_FORMAT = "jpeg"
DEFAULT_OUTPUT_COMPRESSION = 50
IMAGE_MODEL_LABEL = "GPT Image 2.5 Flare"

RESPONSES_CONTROLLER_MODEL_CANDIDATES = [
    "gpt-4.1-mini",
    "gpt-4.1",
]
PREFERRED_IMAGE_TOOL_MODEL = "gpt-image-2.5-flare"

MIN_EDGE = 16
MULTIPLE_OF = 16
MAX_EDGE = 3840
MAX_ASPECT_RATIO = 3.0
MIN_PIXELS = 655_360
MAX_PIXELS = 8_294_400

PRESET_GENERATION_SIZES = {
    (3000, 660): (3072, 1024),
    (1500, 1000): (1504, 1008),
    (1024, 1024): (1024, 1024),
    (1920, 1080): (2048, 1152),
}


@dataclass(frozen=True)
class GenerationSizePlan:
    requested_width: int
    requested_height: int
    generation_width: int
    generation_height: int
    warning: Optional[str] = None

    @property
    def requested_size_str(self) -> str:
        return f"{self.requested_width}x{self.requested_height}"

    @property
    def generation_size_str(self) -> str:
        return f"{self.generation_width}x{self.generation_height}"

    @property
    def requires_crop(self) -> bool:
        return (
            self.requested_width != self.generation_width
            or self.requested_height != self.generation_height
        )


def pil_to_bytes_with_mimetype(
    img: Image.Image,
    image_format: str = "PNG",
) -> Tuple[bytes, str]:
    """
    Convert a PIL image into bytes for OpenAI uploads or data URLs.
    """
    buffered = BytesIO()
    actual_format = image_format.upper()
    mimetype = f"image/{actual_format.lower()}"

    if actual_format == "JPEG":
        if img.mode in {"RGBA", "P"}:
            img = img.convert("RGB")
        mimetype = "image/jpeg"
    elif actual_format == "JPG":
        if img.mode in {"RGBA", "P"}:
            img = img.convert("RGB")
        actual_format = "JPEG"
        mimetype = "image/jpeg"
    elif actual_format == "WEBP":
        mimetype = "image/webp"
    elif actual_format == "PNG":
        mimetype = "image/png"
    else:
        raise ValueError(f"Unsupported format for upload: {image_format}")

    img.save(buffered, format=actual_format)
    return buffered.getvalue(), mimetype


def pil_to_data_url(
    img: Image.Image,
    image_format: str = "PNG",
) -> str:
    image_bytes, mimetype = pil_to_bytes_with_mimetype(img, image_format=image_format)
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{mimetype};base64,{encoded}"


def _round_to_multiple(value: float, base: int = MULTIPLE_OF) -> int:
    rounded = int(round(value / base) * base)
    return max(MIN_EDGE, rounded)


def _is_valid_generation_size(width: int, height: int) -> bool:
    if width < MIN_EDGE or height < MIN_EDGE:
        return False
    if width % MULTIPLE_OF != 0 or height % MULTIPLE_OF != 0:
        return False
    if width > MAX_EDGE or height > MAX_EDGE:
        return False
    ratio = max(width / height, height / width)
    if ratio > MAX_ASPECT_RATIO:
        return False
    pixels = width * height
    if pixels < MIN_PIXELS or pixels > MAX_PIXELS:
        return False
    return True


def _build_candidate_for_ratio(long_edge: int, aspect_ratio: float) -> Tuple[int, int]:
    if aspect_ratio >= 1.0:
        width = long_edge
        height = _round_to_multiple(width / aspect_ratio)
    else:
        height = long_edge
        width = _round_to_multiple(height * aspect_ratio)
    return width, height


def _find_best_valid_size_for_ratio(width: int, height: int) -> Tuple[int, int]:
    aspect_ratio = width / height
    best_candidate: Optional[Tuple[int, int]] = None
    best_score: Optional[float] = None

    for long_edge in range(MIN_EDGE, MAX_EDGE + MULTIPLE_OF, MULTIPLE_OF):
        candidate_width, candidate_height = _build_candidate_for_ratio(long_edge, aspect_ratio)
        if not _is_valid_generation_size(candidate_width, candidate_height):
            continue

        size_distance = abs(candidate_width - width) + abs(candidate_height - height)
        pixel_distance = abs((candidate_width * candidate_height) - (width * height)) / 10_000
        score = size_distance + pixel_distance

        if best_score is None or score < best_score:
            best_candidate = (candidate_width, candidate_height)
            best_score = score

    if best_candidate is None:
        raise ValueError(
            f"Could not derive a valid {PREFERRED_IMAGE_TOOL_MODEL} size for {width}x{height}."
        )

    return best_candidate


def _get_legacy_generation_size_for_target(width: int, height: int) -> str:
    legacy_sizes = {
        "square": (1.0, "1024x1024"),
        "landscape": (1536 / 1024, "1536x1024"),
        "portrait": (1024 / 1536, "1024x1536"),
    }
    target_ratio = width / height
    closest_key = min(
        legacy_sizes.keys(),
        key=lambda key: abs(legacy_sizes[key][0] - target_ratio),
    )
    return legacy_sizes[closest_key][1]


def get_generation_size_for_target(width: int, height: int) -> GenerationSizePlan:
    """
    Compute the preferred generation size for a requested final output size.
    """
    if width <= 0 or height <= 0:
        raise ValueError("Target size must use positive integers.")

    requested_size = (width, height)
    if requested_size in PRESET_GENERATION_SIZES:
        generation_width, generation_height = PRESET_GENERATION_SIZES[requested_size]
    elif _is_valid_generation_size(width, height):
        generation_width, generation_height = width, height
    else:
        ratio = width / height
        inverse_ratio = height / width

        if ratio > MAX_ASPECT_RATIO:
            generation_width, generation_height = 3072, 1024
        elif inverse_ratio > MAX_ASPECT_RATIO:
            generation_width, generation_height = 1024, 3072
        else:
            generation_width, generation_height = _find_best_valid_size_for_ratio(width, height)

    warning = None
    if (generation_width, generation_height) != requested_size:
        warning = (
            f"OpenAI will render at {generation_width}x{generation_height}; "
            f"the app will crop and/or resize to {width}x{height}."
        )

    return GenerationSizePlan(
        requested_width=width,
        requested_height=height,
        generation_width=generation_width,
        generation_height=generation_height,
        warning=warning,
    )


def _get_request_id_from_error(exc: Exception) -> Optional[str]:
    request_id = getattr(exc, "request_id", None)
    if request_id:
        return str(request_id)

    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if headers:
        return headers.get("x-request-id")
    return None


def _get_bad_request_details(exc: openai.BadRequestError) -> tuple[Optional[str], Optional[str], str]:
    error_body = exc.body
    if isinstance(error_body, dict):
        error = error_body.get("error", error_body)
        if not isinstance(error, dict):
            return None, None, str(exc)
        return error.get("code"), error.get("param"), str(error.get("message") or "")
    return None, None, str(exc)


def _extract_image_result_b64(response: Any) -> Optional[str]:
    outputs = getattr(response, "output", None) or []
    for output in outputs:
        if getattr(output, "type", None) == "image_generation_call" and getattr(output, "result", None):
            return str(output.result)
        if isinstance(output, dict) and output.get("type") == "image_generation_call" and output.get("result"):
            return str(output["result"])
    return None


def _build_image_generation_tool(
    size: str,
    quality: str,
    moderation: str,
    output_format: str,
    output_compression: Optional[int],
) -> dict[str, Any]:
    tool: dict[str, Any] = {
        "type": "image_generation",
        "action": "edit",
        "model": PREFERRED_IMAGE_TOOL_MODEL,
        "size": size,
        "quality": quality,
        "moderation": moderation,
        "output_format": output_format,
    }
    if output_compression is not None:
        tool["output_compression"] = output_compression
    return tool


def _responses_create_image_with_fallback(
    client,
    *,
    input_payload: list[dict[str, Any]],
    tool_payload: dict[str, Any],
    legacy_fallback_size: str,
):
    controller_models = list(RESPONSES_CONTROLLER_MODEL_CANDIDATES)
    current_controller_model = controller_models.pop(0)
    current_tool_payload = dict(tool_payload)

    while True:
        try:
            return client.responses.create(
                model=current_controller_model,
                input=input_payload,
                tool_choice={"type": "image_generation"},
                tools=[current_tool_payload],
            )
        except openai.BadRequestError as exc:
            error_code, error_param, error_message = _get_bad_request_details(exc)
            error_param_lower = (error_param or "").lower()
            error_message_lower = error_message.lower()

            controller_model_invalid = (
                error_param_lower == "model"
                and current_controller_model.lower() in error_message_lower
            ) or (
                error_code == "model_not_found"
                and current_controller_model.lower() in error_message_lower
            )
            if controller_model_invalid and controller_models:
                current_controller_model = controller_models.pop(0)
                print(
                    f"Retrying Responses API with fallback controller model: {current_controller_model}"
                )
                continue

            # Never silently drop the selected model or its cost/output controls.
            if error_code == "unknown_parameter":
                raise

            size_invalid = (
                "size" in error_param_lower
                or ("size" in error_message_lower and "invalid" in error_message_lower)
            )
            if size_invalid and current_tool_payload.get("size") != legacy_fallback_size:
                current_tool_payload["size"] = legacy_fallback_size
                print(
                    f"Retrying image generation tool with legacy-compatible size: {legacy_fallback_size}"
                )
                continue

            raise


def generate_banner_with_gpt_image_2(
    original_image_pil: Image.Image,
    instruction_prompt: str,
    size_plan: GenerationSizePlan,
    quality: str = DEFAULT_GENERATION_QUALITY,
    moderation: str = "auto",
    output_format: str = DEFAULT_OUTPUT_FORMAT,
    output_compression: Optional[int] = None,
) -> Image.Image:
    """
    Generate with GPT Image 2.5 Flare via the Responses image_generation tool.

    The function name is retained for compatibility with existing callers.
    """
    if not instruction_prompt or not instruction_prompt.strip():
        raise ValueError(f"Instruction prompt cannot be empty for {PREFERRED_IMAGE_TOOL_MODEL}.")
    if not original_image_pil:
        raise ValueError(f"Original image (PIL) must be provided for {PREFERRED_IMAGE_TOOL_MODEL}.")
    if quality not in VALID_QUALITY_OPTIONS:
        raise ValueError(
            f"Invalid quality setting: {quality}. Must be one of {sorted(VALID_QUALITY_OPTIONS)}."
        )
    if moderation not in VALID_MODERATION_OPTIONS:
        raise ValueError(
            f"Invalid moderation setting: {moderation}. Must be one of {sorted(VALID_MODERATION_OPTIONS)}."
        )
    if output_format not in SUPPORTED_OUTPUT_FORMATS:
        raise ValueError(
            f"Invalid output format: {output_format}. Must be one of {sorted(SUPPORTED_OUTPUT_FORMATS)}."
        )
    if output_compression is not None:
        if output_format not in {"jpeg", "webp"}:
            raise ValueError(
                "Output compression is only supported when output format is jpeg or webp."
            )
        if not 0 <= output_compression <= 100:
            raise ValueError("Output compression must be between 0 and 100.")
    elif output_format in {"jpeg", "webp"}:
        output_compression = DEFAULT_OUTPUT_COMPRESSION

    try:
        client = get_openai_client()
        input_payload = [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": instruction_prompt},
                    {
                        "type": "input_image",
                        "image_url": pil_to_data_url(original_image_pil, image_format="PNG"),
                    },
                ],
            }
        ]
        tool_payload = _build_image_generation_tool(
            size=size_plan.generation_size_str,
            quality=quality,
            moderation=moderation,
            output_format=output_format,
            output_compression=output_compression,
        )
        response = _responses_create_image_with_fallback(
            client,
            input_payload=input_payload,
            tool_payload=tool_payload,
            legacy_fallback_size=_get_legacy_generation_size_for_target(
                size_plan.requested_width,
                size_plan.requested_height,
            ),
        )

        image_b64 = _extract_image_result_b64(response)
        if image_b64:
            image_data_bytes = base64.b64decode(image_b64)
            generated_image_pil = Image.open(BytesIO(image_data_bytes))
            return generated_image_pil.convert("RGB")

        raise ValueError("No image data received from the Responses image-generation tool.")

    except openai.BadRequestError as exc:
        request_id = _get_request_id_from_error(exc)
        error_code, error_param, detail = _get_bad_request_details(exc)
        error_message = f"{PREFERRED_IMAGE_TOOL_MODEL} API bad request: {detail or exc}"
        if error_code == "content_policy_violation":
            error_message = (
                f"{PREFERRED_IMAGE_TOOL_MODEL} rejected the request due to content policy. "
                "Please revise the prompt."
            )
        elif "billing" in str(exc.body).lower():
            error_message = (
                f"{PREFERRED_IMAGE_TOOL_MODEL} image generation failed. "
                "Please check your OpenAI billing status."
            )
        if "model" in (error_param or "").lower():
            error_message += " No alternate image model was used."

        if request_id:
            print(f"OpenAI request id: {request_id}")
            error_message = f"{error_message} (request_id={request_id})"
        print(f"Original BadRequestError: {exc}")
        print(f"Parsed error message for UI: {error_message}")

        raise ValueError(error_message) from exc

    except openai.APIError as exc:
        request_id = _get_request_id_from_error(exc)
        error_message = f"OpenAI {PREFERRED_IMAGE_TOOL_MODEL} API error: {exc}"
        if request_id:
            error_message = f"{error_message} (request_id={request_id})"
        print(error_message)
        raise ValueError(error_message) from exc

    except Exception as exc:
        print(f"An unexpected error occurred during {PREFERRED_IMAGE_TOOL_MODEL} image generation: {exc}")
        raise
