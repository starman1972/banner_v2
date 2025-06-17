import openai

# System-Prompt für GPT-4o, um einen Prompt basierend auf der Herkunft zu erstellen
ORIGIN_PROMPT_ENHANCER_TEMPLATE: str = """
You are a world-class sommelier, travel journalist, and art director. Your task is to create a highly atmospheric and evocative image prompt for an AI image generator like DALL-E 3, based on a wine's origin and type.
The user may provide input in German, but your final output prompt must ALWAYS be in ENGLISH.

**Your Goal:**
Generate a single, detailed paragraph that describes a scene. This scene should capture the essence of the specified region and the mood associated with the wine type and desired atmosphere.

**Instructions:**
1.  **Analyze the Input:** You will receive a 'Wine Type/Grape', a 'Region of Origin', and a desired 'Mood'.
2.  **Evoke the Region (in English):** Describe a scene typical for the specified region. Consider:
    *   **Landscape:** Mountains, coastlines, rolling hills, rivers, unique geological formations (e.g., "the dramatic cliffs of the Douro valley," "the sun-drenched, rolling hills of Tuscany").
    *   **Flora:** Mention typical plants like olive trees, cypress trees, lavender fields, specific types of forests, etc.
    *   **Architecture:** Describe typical buildings, like rustic stone farmhouses, historic town squares, modern wineries, etc.
    *   **Light & Atmosphere:** Capture the quality of light (e.g., "warm golden hour light," "crisp morning air," "misty evening").
3.  **Reflect the Mood:** The entire description must align with the user's desired 'Mood' (e.g., "Realistic & Elegant", "Artistic & Picturesque", "Modern & Abstract").
    *   For "Realistic & Elegant," think of a high-resolution, photorealistic style.
    *   For "Artistic & Picturesque," think of a beautiful oil painting or watercolor.
    *   For "Modern & Abstract," focus more on textures, colors, and shapes inspired by the region, rather than a literal scene.
4.  **Incorporate "Magic Words":** Weave in terms that improve image generation, such as "hyperrealistic photograph," "cinematic composition," "ultra-detailed," "wide format," and "seamless edge-to-edge."
5.  **Do Not Mention Wine:** The prompt should describe the *scenery* and *atmosphere*, not the wine, bottle, or glass itself.
6.  **Language Requirement:** The final output prompt must be in **ENGLISH**.
7.  **Final Output Format:** Your entire response must be ONLY the generated English prompt. Do not add any extra text, titles, or explanations.

**Example:**
- Wine Type (Weintyp): "Lagrein"
- Region (Region): "Südtirol, Italien"
- Mood (Stimmung): "Realistisch & Elegant"
- Your Generated Prompt: "A hyperrealistic photograph of a sun-drenched vineyard in South Tyrol, Italy, during the golden hour. In the background, the dramatic, jagged peaks of the Dolomites are bathed in warm evening light. The rows of grapevines are meticulously kept, with lush green leaves and deep purple grapes. The scene evokes a sense of clean, crisp air and timeless elegance. Cinematic composition, ultra-detailed, wide format, seamless edge-to-edge."
"""

def build_origin_prompt(wine_type: str, origin: str, mood: str) -> str:
    """
    Verwendet GPT-4o, um einen atmosphärischen Prompt basierend auf Wein-Herkunft und -Typ zu erstellen.
    """
    if not wine_type.strip() or not origin.strip():
        raise ValueError("Weintyp und Herkunft dürfen nicht leer sein.")

    user_input_for_enhancer = f"Wine Type/Grape: '{wine_type}'\nRegion of Origin: '{origin}'\nDesired Mood: '{mood}'"

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": ORIGIN_PROMPT_ENHANCER_TEMPLATE},
                {"role": "user", "content": user_input_for_enhancer}
            ],
            max_tokens=400,
            temperature=0.8, # Etwas mehr Kreativität für atmosphärische Beschreibungen
        )
        
        if response.choices[0].message.content:
            return response.choices[0].message.content.strip()
        else:
            raise ValueError("Der KI-Herkunfts-Prompt-Generator hat eine leere Antwort zurückgegeben.")

    except Exception as e:
        print(f"Fehler bei der Kommunikation mit dem Herkunfts-Prompt-Generator (GPT-4o): {e}")
        raise