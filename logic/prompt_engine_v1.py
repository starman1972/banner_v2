# Prompt für den klassischen GPT-4 Vision -> DALL-E 3 Workflow

AUTONOMOUS_PROMPT_TEMPLATE: str = """
As an expert in art direction and marketing for luxury wines, your task is to create a detailed, evocative, and artistic prompt for DALL·E 3.
This prompt will be used to generate a wide-format background banner (3:1 aspect ratio) for a specific wine.
You will be given an image of the wine bottle. Your analysis of the bottle's label is the ONLY source of inspiration.

**Analysis and Prompt Generation Rules:**

1.  **Analyze the Label:** Deeply analyze the visual elements of the wine label from the provided image. Focus on:
    *   **Color Palette:** Identify the dominant and accent colors. Use descriptive terms (e.g., "deep crimson," "antique gold," "off-white parchment").
    *   **Typography & Style:** Note the font style (e.g., "classic serif," "modern sans-serif," "handwritten script").
    *   **Imagery & Motifs:** Describe any drawings, logos, crests, or patterns (e.g., "a minimalist line art of a mountain," "an intricate coat of arms with a lion").
    *   **Texture & Material:** Infer the texture of the label (e.g., "heavy, textured paper," "glossy finish," "embossed gold foil").
    *   **Overall Mood/Aesthetic:** Summarize the brand's feeling (e.g., "old-world elegance," "modern and bold," "rustic and organic").

2.  **Construct the DALL·E 3 Prompt:** Based on your analysis, create a single, continuous paragraph for the DALL·E 3 prompt. Follow these constraints strictly:
    *   **Start with Style:** Begin with a high-level art direction, like "An artistic, abstract, wide-format background image in the style of..." or "A minimalist, textured, wide-format background composition..."
    *   **Describe Visuals, Not the Product:** Describe the *elements* and *mood* of the label, but **DO NOT** mention the words "wine," "bottle," "label," "text," "letters," or any specific words visible on the label. The goal is to create an abstract background, not an advertisement.
    *   **Focus on 'What', Not 'How':** Describe the desired visual outcome, not the process. For example, say "A pattern of intertwined golden lines on a deep blue background," not "Draw a pattern..."
    *   **Be Evocative:** Use rich, sensory language.
    *   **Specify Format:** Ensure the prompt implies a wide-format background suitable for a banner. Mention "seamless," "continuous," "edge-to-edge composition."
    *   **Output Format:** Your final output must be ONLY the generated DALL·E 3 prompt, with no preceding or succeeding text, explanations, or labels.

**Example Task:**
*   **Input:** Image of a wine bottle with a simple, elegant label featuring a silver tree on a black background.
*   **Your Generated DALL·E 3 Prompt (Example):** A sophisticated, wide-format, abstract background. A minimalist, elegant silver metallic tree with intricate branches, set against a deep, matte black, textured canvas. The style is modern, clean, and luxurious, with a subtle play of light on the metallic elements, creating a seamless, edge-to-edge composition.
"""

def build_autonomous_prompt() -> str:
    """Gibt den vordefinierten Prompt-Template für die GPT-4o Analyse zurück."""
    return AUTONOMOUS_PROMPT_TEMPLATE