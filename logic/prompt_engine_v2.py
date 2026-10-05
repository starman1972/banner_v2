"""Compose reference-image prompts independently of the image model."""

import json
from math import gcd


PROMPT_MODE_LABELS = {"classic": "Classic", "interpretive": "Interpretive"}
PROMPT_MODE_DESCRIPTIONS = {
    "classic": "Nah an Farben, Formen und Stil der Etikette; vertraute Markenwelt.",
    "interpretive": "Freie Interpretation der Farbwelt und Stimmung; eigenständige Komposition.",
}
DEFAULT_TARGET_SIZE = (3000, 660)

STYLE_BRIEFS = {
    "classic": """Draw closely from the label's dominant colors, shapes, textures, patterns, and overall artistic style.
Preserve its mood and visual identity while arranging these elements into a cohesive standalone composition.
Do not reproduce the label layout, the exact illustration, or any single graphic element one-to-one.
The composition should be seamless, visually harmonious, and continuous from edge to edge.""",
    "interpretive": """Use the provided image as visual inspiration rather than as a template.
Translate the label's color palette, atmosphere, textures, artistic motifs, and visual rhythm into a new, original composition.
Do not recreate its layout, illustration, decorative elements, or typography literally. Reinterpret them into a visually independent artwork that still feels connected to the reference.
Create an elegant, compositionally strong design with a clear visual hierarchy and calm areas that balance the more expressive elements.
Let depth and texture follow the reference's artistic language; keep flat graphic designs graphic rather than forcing photorealism.""",
}

TEXT_POSITION_MAP = {
    "zentral": "centrally",
    "oben": "near the top",
    "unten": "near the bottom",
    "links": "toward the left side",
    "rechts": "toward the right side",
}


def _validate_size(size: tuple[int, int]) -> None:
    if len(size) != 2 or any(type(edge) is not int or edge <= 0 for edge in size):
        raise ValueError("Image dimensions must be two positive integers.")


def _format_brief(
    target_size: tuple[int, int], generation_size: tuple[int, int] | None
) -> str:
    width, height = target_size
    if width == height:
        descriptor = "square"
    elif width >= 2 * height:
        descriptor = "wide-format"
    elif width > height:
        descriptor = "landscape"
    else:
        descriptor = "portrait"

    divisor = gcd(width, height)
    lines = [
        f"Create a {descriptor} artistic composition visually inspired by the provided image.",
        f"Final output: {width}x{height} pixels ({width // divisor}:{height // divisor} aspect ratio).",
    ]
    if generation_size is not None and generation_size != target_size:
        gen_width, gen_height = generation_size
        lines.append(
            f"Requested rendering canvas: {gen_width}x{gen_height} pixels. "
            "The app will crop and/or resize this canvas to the final output dimensions."
        )
        if width * gen_height > height * gen_width:
            retained_height = gen_width * height / (width * gen_height)
            lines.append(
                "Compose for a centered horizontal crop: keep all text and essential motifs "
                f"within the central {retained_height:.1%} of the canvas height."
            )
        elif width * gen_height < height * gen_width:
            retained_width = gen_height * width / (height * gen_width)
            lines.append(
                "Compose for a centered vertical crop: keep all text and essential motifs "
                f"within the central {retained_width:.1%} of the canvas width."
            )
    return "\n".join(lines)


def build_banner_prompt(
    *,
    mode: str = "classic",
    target_size: tuple[int, int] = DEFAULT_TARGET_SIZE,
    generation_size: tuple[int, int] | None = None,
    user_text: str = "",
    text_position: str = "zentral",
) -> str:
    """Build the full prompt; blank text explicitly selects a text-free design."""
    if mode not in STYLE_BRIEFS:
        raise ValueError(f"Unknown prompt mode: {mode}")
    _validate_size(target_size)
    if generation_size is not None:
        _validate_size(generation_size)

    blocks = [_format_brief(target_size, generation_size), STYLE_BRIEFS[mode]]
    if user_text.strip():
        position = TEXT_POSITION_MAP.get(text_position.strip().lower(), "in a balanced position")
        # Encode once so quotes, newlines and placeholder-like text stay literal.
        quoted_text = json.dumps(user_text, ensure_ascii=False)
        blocks.append(
            f"Integrate this exact text prominently and legibly: {quoted_text}.\n"
            "Preserve its spelling, punctuation and capitalization; do not translate it.\n"
            f"Place the text {position} within the final visible composition, "
            "inside any crop-safe area described above, with comfortable margins.\n"
            "Use typography that harmonizes with the label's visual language without copying it exactly.\n"
            "Ensure strong readability and contrast. Do not add any other text, words or logos."
        )
    else:
        blocks.append("Do not include any text, words, typography or logos.")

    blocks.append(
        "Do not depict the bottle, the label itself, or any product.\n"
        "Avoid natural landscapes or scenery unless they are clearly part of the label's original artistic design.\n"
        "Output only the generated image."
    )
    return "\n\n".join(blocks)


def build_gpt_image_1_banner_prompt() -> str:
    """Compatibility entry point for callers using the original prompt builder."""
    return build_banner_prompt()


def build_gpt_image_1_banner_with_text_prompt(user_text: str, text_position: str) -> str:
    """Compatibility entry point; empty text falls back to the text-free prompt."""
    return build_banner_prompt(user_text=user_text, text_position=text_position)
