# Vereinfachter Prompt für gpt-image-1, da das Modell das Bild direkt sieht

GPT_IMAGE_1_BANNER_PROMPT_TEMPLATE: str = """
Create a wide-format artistic composition (approximately 3:1 aspect ratio or as specified by output dimensions) visually inspired by the provided image.
Focus on replicating the label's dominant colors, geometric shapes, textures, and overall artistic style.
The composition should be seamless, visually harmonious, and continuous from edge to edge.
Do **not** include any text, words, or typography.
Do **not** depict the bottle, the label itself, or any product.
Avoid natural landscapes or sceneries unless they are explicitly part of the original label's artistic design.
Output only the generated image.
"""

GPT_IMAGE_1_BANNER_WITH_TEXT_PROMPT_TEMPLATE: str = """
Create a wide-format artistic composition (approximately 3:1 aspect ratio or as specified by output dimensions) visually inspired by the provided image.
Integrate the following text prominently and legibly into the design: "{user_text}".
Render the text "{user_text}" in a style that closely matches the typography and font characteristics of the provided reference image.
Try to place the text {text_position}.
Focus on replicating the label's dominant colors, geometric shapes, textures, and overall artistic style for the non-textual elements.
The composition should be seamless, visually harmonious, and continuous from edge to edge.
Do **not** depict the bottle, the label itself, or any product.
Avoid natural landscapes or sceneries unless they are explicitly part of the original label's artistic design.
Output only the generated image.
"""

def build_gpt_image_1_banner_prompt() -> str:
    """Gibt den vordefinierten Prompt-Template für die gpt-image-1 Bannergenerierung ohne Text zurück."""
    return GPT_IMAGE_1_BANNER_PROMPT_TEMPLATE

def build_gpt_image_1_banner_with_text_prompt(user_text: str, text_position: str) -> str:
    """
    Erstellt den Prompt-Text für gpt-image-1 unter Einbindung von Benutzertext und Platzierungspräferenz,
    wobei der Schriftstil vom Referenzbild emuliert werden soll.
    :param user_text: Der vom Nutzer eingegebene Text, der in das Banner integriert werden soll.
    :param text_position: Die bevorzugte Position des Textes (z.B. "zentral", "oben", "unten").
    """
    if not user_text.strip(): # Sicherstellen, dass user_text nicht leer ist, um Fehler im Prompt zu vermeiden
        # Fallback auf den Prompt ohne Text, wenn kein Text eingegeben wurde, obwohl die Option aktiviert ist.
        # Alternativ könnte man hier einen Fehler werfen oder einen Standardtext verwenden.
        # Fürs Erste: Wenn kein Text, dann als ob Text deaktiviert wäre (vereinfacht die aufrufende Logik)
        # Besser: Die aufrufende Logik sollte sicherstellen, dass user_text vorhanden ist, wenn diese Funktion gerufen wird.
        # Wir gehen davon aus, dass der Aufrufer dies sicherstellt.
        pass

    prompt = GPT_IMAGE_1_BANNER_WITH_TEXT_PROMPT_TEMPLATE.replace("{user_text}", user_text).replace("{text_position}", text_position)
    return prompt