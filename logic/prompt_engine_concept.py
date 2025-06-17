import openai

# NEU: Kategorisierte und kuratierte Liste von Kunststilen
CATEGORIZED_ART_STYLES = {
    "Fotografische Stile": [
        "Photorealistic",
        "Hyperrealistic Photograph",
        "Cinematic",
        "Product Shot",
        "Macro Photography",
        "Analog Film Look",
        "35mm Film Look",
        "Black and White",
        "Sepia",
        "Dramatic Lighting",
        "Golden Hour Lighting",
        "Low Angle",
        "High Angle",
        "Wide-angle Lens",
        "Fish-eye Lens",
    ],
    "Malerische & Künstlerische Stile": [
        "Oil Painting",
        "Watercolor",
        "Acrylic",
        "Impressionism",
        "Expressionism",
        "Surrealism",
        "Cubism",
        "Art Deco",
        "Art Nouveau",
        "Baroque",
        "Gothic",
        "Victorian",
        "Pointillism",
    ],
    "Grafische & Illustrative Stile": [
        "Illustration",
        "Hand-drawn",
        "Pencil Sketch",
        "Charcoal",
        "Ink Wash",
        "Line Art",
        "Minimalist",
        "Woodcut",
        "Linocut",
        "Folk Art",
        "Concept Art",
        "Pop Art",
        "Retro",
    ],
    "Abstrakte & Textur-Stile": [
        "Abstract",
        "Golden Texture",
        "Polished Stone Texture",
        "Crystal Texture",
        "Wooden Texture",
        "Mosaic",
        "High Contrast",
        "Muted Palette",
    ],
    "3D & Digitale Stile": [
        "3D Render",
        "3D Wireframe",
        "Low Polygon",
        "Cyberpunk",
        "Synthwave",
        "Steampunk",
        "Pixel Art",
        "Neon Lights Style",
    ]
}

# System-Prompt für GPT-4o, um den Benutzer-Input anzureichern
CONCEPT_PROMPT_ENHANCER_TEMPLATE: str = """
You are a creative assistant and an expert in writing advanced prompts for image generation models like DALL-E 3.
Your task is to take a user's core idea (a 'Subject') and a desired 'Artistic Style' and expand it into a single, rich, detailed, and evocative paragraph. The user might provide input in German, but your output must ALWAYS be in English.

**Rules for enhancing the prompt:**
1.  **Translate and Enhance:** If the user input is in German, first understand its meaning, then create the enhanced prompt in English.
2.  **Integrate Style and Subject:** Seamlessly merge the 'Artistic Style' with the 'Subject'. The style should define the overall look and feel.
3.  **Add Rich Detail:** Enrich the user's subject with sensory details, specific elements, and a sense of atmosphere. If the subject is "ein Weinberg," describe the type of grapes, the time of day, the quality of light, and the surrounding landscape in English.
4.  **Incorporate "Magic Words":** Always include phrases that improve banner quality, such as "wide format banner," "ultra-detailed," "cinematic lighting," and "seamless edge-to-edge composition."
5.  **Be Concise but Powerful:** The final prompt should be a single, well-structured paragraph.
6.  **Language Requirement:** The final output prompt must be in **ENGLISH**.
7.  **Final Output Format:** Your entire response must be ONLY the generated DALL-E 3 prompt. Do not include any other text, explanations, or labels like "Prompt:".

**Example:**
- User Input Subject: "Ein Strand bei Sonnenuntergang"
- User Input Style: "Impressionismus"
- Your Generated DALL-E 3 Prompt: "An impressionist oil painting of a serene, sun-drenched beach at dusk. Gentle waves lap at the shore, reflecting the pastel colors of the sky. Tall, wispy dune grass sways in the breeze. The scene is captured with soft, broken brushstrokes and a focus on the play of light. Wide format banner, ultra-detailed, cinematic lighting, seamless edge-to-edge composition."
"""

def build_concept_prompt(subject: str, style: str) -> str:
    """
    Verwendet GPT-4o, um einen einfachen Input in einen reichhaltigen DALL-E 3 Prompt zu verwandeln.
    """
    if not subject.strip():
        raise ValueError("Das Motiv / Thema darf nicht leer sein.")

    user_prompt_for_enhancer = f"Subject: '{subject}'\nArtistic Style: '{style}'"

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": CONCEPT_PROMPT_ENHANCER_TEMPLATE},
                {"role": "user", "content": user_prompt_for_enhancer}
            ],
            max_tokens=350,
            temperature=0.7
        )
        
        if response.choices[0].message.content:
            return response.choices[0].message.content.strip()
        else:
            raise ValueError("Der KI-Prompt-Enhancer hat eine leere Antwort zurückgegeben.")

    except Exception as e:
        print(f"Fehler bei der Kommunikation mit dem Prompt-Enhancer (GPT-4o): {e}")
        return f"{style}, {subject}. Wide format banner, ultra-detailed, cinematic lighting, seamless edge-to-edge composition."