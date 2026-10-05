import json
import unittest

from logic.prompt_engine_v2 import (
    build_banner_prompt,
    build_gpt_image_1_banner_prompt,
    build_gpt_image_1_banner_with_text_prompt,
)


class BannerPromptTests(unittest.TestCase):
    def test_both_styles_follow_output_format_with_and_without_text(self):
        formats = [
            ((3000, 660), "wide-format", "50:11"),
            ((1024, 1024), "square", "1:1"),
            ((1500, 1000), "landscape", "3:2"),
            ((1920, 1080), "landscape", "16:9"),
            ((800, 1200), "portrait", "2:3"),
        ]
        for mode in ("classic", "interpretive"):
            for size, descriptor, ratio in formats:
                for text in ("", "G. D. VAJRA"):
                    with self.subTest(mode=mode, size=size, text=text):
                        prompt = build_banner_prompt(mode=mode, target_size=size, user_text=text)
                        self.assertTrue(prompt.startswith(f"Create a {descriptor} artistic composition"))
                        self.assertIn(f"({ratio} aspect ratio)", prompt)
                        self.assertNotIn("approximately 3:1", prompt)
                        self.assertEqual("Integrate this exact text" in prompt, bool(text))
                        self.assertEqual("Do not include any text" in prompt, not bool(text))
                        self.assertIn("Do not depict the bottle", prompt)

    def test_styles_give_distinct_creative_instructions(self):
        classic = build_banner_prompt(mode="classic")
        interpretive = build_banner_prompt(mode="interpretive")
        self.assertIn("Draw closely from the label", classic)
        self.assertIn("new, original composition", interpretive)
        self.assertNotEqual(classic, interpretive)

    def test_text_positions_are_english_in_both_styles(self):
        positions = {
            "zentral": "centrally", "oben": "near the top", "unten": "near the bottom",
            "links": "toward the left side", "rechts": "toward the right side",
        }
        for mode in ("classic", "interpretive"):
            for position, english in positions.items():
                with self.subTest(mode=mode, position=position):
                    prompt = build_banner_prompt(mode=mode, user_text="VAJRA", text_position=position)
                    self.assertIn(f"Place the text {english}", prompt)
                    self.assertNotIn(f"Place the text {position}", prompt)

    def test_banner_crop_keeps_text_in_visible_band(self):
        prompt = build_banner_prompt(
            target_size=(3000, 660), generation_size=(3072, 1024),
            user_text="VAJRA", text_position="oben",
        )
        self.assertIn("Requested rendering canvas: 3072x1024", prompt)
        self.assertIn("central 66.0% of the canvas height", prompt)
        self.assertIn("near the top within the final visible composition", prompt)
        portrait = build_banner_prompt(target_size=(660, 3000), generation_size=(1024, 3072))
        self.assertIn("central 66.0% of the canvas width", portrait)
        resized = build_banner_prompt(target_size=(1920, 1080), generation_size=(2048, 1152))
        self.assertNotIn("centered horizontal crop", resized)
        self.assertNotIn("centered vertical crop", resized)

    def test_literal_user_text_is_not_reinterpreted_as_template(self):
        text = 'Weingut "A" {text_position}\n{user_text} & B'
        prompt = build_banner_prompt(user_text=text, text_position="rechts")
        self.assertIn(json.dumps(text), prompt)
        self.assertIn("Place the text toward the right side", prompt)

    def test_blank_text_uses_no_text_instruction_in_legacy_entry_point(self):
        self.assertEqual(
            build_gpt_image_1_banner_with_text_prompt(" \n ", "oben"),
            build_gpt_image_1_banner_prompt(),
        )

    def test_invalid_prompt_options_fail_before_generation(self):
        for kwargs in (
            {"mode": "unknown"}, {"target_size": (0, 1024)},
            {"target_size": (1.5, 1024)}, {"generation_size": (1024, -1)},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                build_banner_prompt(**kwargs)


if __name__ == "__main__":
    unittest.main()
