# Prompt für den klassischen GPT-4 Vision -> DALL-E 3 Workflow

AUTONOMOUS_PROMPT_TEMPLATE: str = """
As an expert in art direction and marketing for luxury wines, your task is to create a detailed, evocative, and artistic prompt for DALL·E 3.
This prompt will be used to generate a wide-format panoramic background banner for a specific wine.
You will be given an image of the wine bottle. Your analysis of the bottle's label is the ONLY source of inspiration.

**Analysis and Prompt Generation Rules:**

1. **Analyze the Label:** Deeply analyze the visual elements of the wine label from the provided image. Focus on:

   * **Color Palette:** Identify the dominant and accent colors. Use descriptive terms (e.g., "deep crimson," "antique gold," "off-white parchment").
   * **Typography & Style:** Note the font style (e.g., "classic serif," "modern sans-serif," "handwritten script").
   * **Imagery & Motifs:** Describe any drawings, logos, crests, or patterns (e.g., "a minimalist line art of a mountain," "an intricate coat of arms with a lion").
   * **Texture & Material:** Infer the texture of the label (e.g., "heavy, textured paper," "glossy finish," "embossed gold foil").
   * **Overall Mood/Aesthetic:** Summarize the brand's feeling (e.g., "old-world elegance," "modern and bold," "rustic and organic").

2. **Construct the DALL·E 3 Prompt:** Based on your analysis, create a single, continuous paragraph for the DALL·E 3 prompt. Follow these constraints strictly:

   * **Start with Style:** Begin with a high-level art direction, such as "A richly detailed, wide-format, abstract background in the style of..." or "A continuous, immersive visual composition inspired by..."
   * **Ensure Full Coverage:** Clearly state that the composition is "evenly distributed across the entire canvas" or "richly adorned from center to edges" to avoid visual clustering only at the borders.
   * **Describe Visuals, Not the Product:** Describe the *elements* and *mood* of the label, but **DO NOT** mention the words "wine," "bottle," "label," "text," "letters," or any specific words visible on the label.
   * **Focus on 'What', Not 'How':** Describe the desired visual outcome, not the process.
   * **Be Evocative:** Use rich, sensory language.
   * **Specify Format:** Emphasize that the result must be suitable as a wide-format background, with "continuous flow," "balanced layout," and "harmonious full-area coverage."
   * **Avoid Framing Language:** Do not use terms like "frame," "border," "edge-focused," or "corner detail" unless explicitly required by the label design.
   * **Output Format:** Your final output must be ONLY the generated DALL·E 3 prompt, with no preceding or succeeding text, explanations, or labels.

**Example Task:**

* **Input:** Image of a wine bottle with a simple, elegant label featuring a silver tree on a black background.
* **Your Generated DALL·E 3 Prompt (Example):** A sophisticated, wide-format, abstract background. A minimalist, elegant silver metallic tree with intricate branches, set against a deep, matte black, textured canvas. The style is modern, clean, and luxurious, with a subtle play of light on the metallic elements. The composition is richly detailed and evenly distributed across the entire canvas, with no central emptiness, creating a seamless and immersive panoramic visual experience.
"""

def build_autonomous_prompt() -> str:
    """Gibt den vordefinierten Prompt-Template für die GPT-4o Analyse zurück."""
    return AUTONOMOUS_PROMPT_TEMPLATE