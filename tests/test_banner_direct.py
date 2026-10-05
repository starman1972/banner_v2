import os
import runpy
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from PIL import Image
from streamlit.testing.v1 import AppTest


DIRECT_PAGE = next((Path(__file__).resolve().parents[1] / "pages").glob("*Banner_Generator_(Direct).py"))


class BannerDirectTests(unittest.TestCase):
    def setUp(self):
        # Exercise the actual page with no account credentials or paid API calls.
        self.enterContext(patch.dict(os.environ, {"OPENAI_API_KEY": ""}))
        self.enterContext(patch("utils.load_css"))
        self.enterContext(patch("utils.load_sku_data", return_value=pd.DataFrame(columns=["sku", "image_url"])))
        self.generate = self.enterContext(patch(
            "logic.generation_v2.generate_banner_with_gpt_image_2",
            return_value=Image.new("RGB", (1024, 1024), "white"),
        ))
        self.app = AppTest.from_file(str(DIRECT_PAGE), default_timeout=20)
        self.app.secrets["OPENAI_API_KEY"] = "test-only"
        self.app.session_state["banner_gen_image_input"] = Image.new("RGB", (32, 32), "red")
        self.app.session_state["banner_gen_image_input_name"] = "reference.png"
        self.app.run()
        self.assertEqual(len(self.app.exception), 0)

    def generation_button(self):
        return next(button for button in self.app.button if "KI-Banner generieren" in button.label)

    def test_flare_defaults_and_generation_time_are_visible(self):
        self.assertEqual(self.app.radio(key="banner_gen_quality_choice").value, "medium")
        self.assertEqual(self.app.radio(key="banner_gen_output_format_choice").value, "jpeg")
        self.assertEqual(self.app.slider(key="banner_gen_output_compression").value, 50)
        self.assertIn("GPT Image 2.5 Flare", self.generation_button().label)
        self.assertTrue(any("GPT Image 2.5 Flare" in item.value for item in self.app.markdown))

        self.generation_button().click().run()
        self.assertEqual(len(self.app.exception), 0)
        sent = self.generate.call_args.kwargs
        self.assertEqual(sent["quality"], "medium")
        self.assertEqual(sent["output_format"], "jpeg")
        self.assertEqual(sent["output_compression"], 50)
        self.assertIn("GPT Image 2.5 Flare", self.app.success[0].value)
        self.assertIn("Generierungsdauer:", self.app.success[0].value)

        self.app.radio(key="banner_gen_quality_choice").set_value("high").run()
        self.app.slider(key="banner_gen_output_compression").set_value(75).run()
        self.generation_button().click().run()
        self.assertEqual(self.generate.call_args.kwargs["quality"], "high")
        self.assertEqual(self.generate.call_args.kwargs["output_compression"], 75)

    def test_square_prompt_is_sent_displayed_and_quality_is_preserved(self):
        self.app.radio(key="banner_gen_ratio_choice").set_value("Square (1:1)").run()
        self.app.checkbox(key="banner_gen_include_text").check().run()
        self.assertTrue(self.generation_button().disabled)
        self.generate.assert_not_called()
        self.app.text_area(key="banner_gen_user_text").set_value("G. D. VAJRA").run()
        self.app.radio(key="banner_gen_text_position").set_value("rechts").run()
        self.app.radio(key="banner_gen_quality_choice").set_value("low").run()
        self.generation_button().click().run()
        self.assertEqual(len(self.app.exception), 0)
        sent = self.generate.call_args.kwargs
        self.assertEqual(sent["quality"], "low")
        self.assertEqual(sent["size_plan"].generation_size_str, "1024x1024")
        self.assertTrue(sent["instruction_prompt"].startswith("Create a square"))
        self.assertIn("Place the text toward the right side", sent["instruction_prompt"])
        self.assertEqual(self.app.code[0].value, sent["instruction_prompt"])

        old_cropper_version = self.app.session_state["banner_gen_cropper_version"]
        self.app.radio(key="banner_gen_prompt_mode").set_value("interpretive").run()
        self.assertIsNone(self.app.session_state["banner_gen_ai_banner_img"])
        self.assertEqual(len(self.app.code), 0)
        self.assertGreater(self.app.session_state["banner_gen_cropper_version"], old_cropper_version)
        self.generation_button().click().run()
        self.assertEqual(len(self.app.exception), 0)
        sent = self.generate.call_args.kwargs
        self.assertIn("new, original composition", sent["instruction_prompt"])
        self.assertEqual(sent["quality"], "low")
        self.assertEqual(self.app.code[0].value, sent["instruction_prompt"])

    def test_default_banner_and_custom_portrait_without_text(self):
        self.assertEqual(self.app.radio(key="banner_gen_prompt_mode").value, "classic")
        self.generation_button().click().run()
        prompt = self.generate.call_args.kwargs["instruction_prompt"]
        self.assertIn("central 66.0% of the canvas height", prompt)
        self.assertIn("Do not include any text", prompt)
        self.assertEqual(len(self.app.exception), 0)

        self.app.radio(key="banner_gen_ratio_choice").set_value("Custom").run()
        self.app.number_input(key="banner_gen_custom_width").set_value(800).run()
        self.app.number_input(key="banner_gen_custom_height").set_value(1200).run()
        self.app.radio(key="banner_gen_prompt_mode").set_value("interpretive").run()
        self.app.radio(key="banner_gen_output_format_choice").set_value("png").run()
        self.generation_button().click().run()
        self.assertEqual(len(self.app.exception), 0)
        sent = self.generate.call_args.kwargs
        self.assertTrue(sent["instruction_prompt"].startswith("Create a portrait"))
        self.assertIn("800x1200", sent["instruction_prompt"])
        self.assertIsNone(sent["output_compression"])

    def test_api_failure_releases_generation_button_and_preserves_prompt(self):
        self.generate.side_effect = ValueError("simulated API failure")
        self.generation_button().click().run()
        self.assertEqual(len(self.app.exception), 0)
        self.assertFalse(self.generation_button().disabled)
        self.assertFalse(self.app.session_state["banner_gen_is_generating"])
        self.assertIsNone(self.app.session_state["banner_gen_ai_banner_img"])
        self.assertIn("simulated API failure", self.app.error[0].value)
        self.assertEqual(self.app.code[0].value, self.generate.call_args.kwargs["instruction_prompt"])


class BannerPageHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch("utils.get_secret", return_value="test-only"), patch("utils.load_css"), patch("streamlit.set_page_config"):
            cls.page = runpy.run_path(str(DIRECT_PAGE), run_name="banner_page_tests")

    def test_same_filename_upload_replaces_changed_image(self):
        state = State()
        callback = self.page["_handle_upload"]
        st = callback.__globals__["st"]
        with patch.object(st, "session_state", state), patch.object(st, "rerun"), patch.object(st, "error") as error:
            self.page["initialize_session_state"]()
            for color in ("red", "blue"):
                buffer = BytesIO()
                Image.new("RGB", (8, 8), color).save(buffer, format="PNG")
                buffer.name = "same-name.png"
                with patch.object(st, "file_uploader", return_value=buffer):
                    callback()
            self.assertEqual(state.banner_gen_image_input.getpixel((0, 0)), (0, 0, 255))
            error.assert_not_called()

    def test_crop_box_uses_exact_ratio_and_largest_centered_area(self):
        for source_size, target_size in (
            ((700, 233), (3000, 660)), ((700, 700), (1024, 1024)),
            ((233, 700), (660, 3000)), ((700, 467), (1500, 1000)),
        ):
            with self.subTest(source=source_size, target=target_size):
                box = self.page["_initial_crop_box"](Image.new("RGB", source_size), target_size)
                self.assertAlmostEqual(box["width"] / box["height"], target_size[0] / target_size[1])
                self.assertGreaterEqual(box["left"], 0)
                self.assertGreaterEqual(box["top"], 0)
                self.assertLessEqual(box["left"] + box["width"], source_size[0] + 1e-9)
                self.assertLessEqual(box["top"] + box["height"], source_size[1] + 1e-9)
                self.assertTrue(abs(box["width"] - source_size[0]) < 1e-9 or abs(box["height"] - source_size[1]) < 1e-9)

    def test_generation_preparation_error_resets_busy_state(self):
        callback = self.page["_perform_banner_generation"]
        st = callback.__globals__["st"]
        state = State()
        with patch.object(st, "session_state", state):
            self.page["initialize_session_state"]()
            state.banner_gen_image_input = Image.new("RGB", (8, 8))
            state.banner_gen_ratio_choice = "Custom"
            state.banner_gen_custom_width = 0
            callback()
            self.assertFalse(state.banner_gen_is_generating)
            self.assertIn("Fehler", state.banner_gen_status_message)

    def test_default_download_is_jpeg_at_compression_50(self):
        callback = self.page["_crop_and_download"]
        st = callback.__globals__["st"]
        state = State()
        with patch.object(st, "session_state", state), patch.object(st, "caption"), \
                patch.object(st, "image"), patch.object(st, "download_button") as download, \
                patch.dict(callback.__globals__, {
                    "_build_download_image": lambda image, width, height: image.resize((width, height)),
                }):
            self.page["initialize_session_state"]()
            state.banner_gen_ai_banner_img = Image.new("RGB", (32, 32), "red")
            state.banner_gen_target_size = (1500, 1000)
            callback()
            result = download.call_args.kwargs
            self.assertEqual(result["mime"], "image/jpeg")
            self.assertTrue(result["file_name"].endswith(".jpg"))
            with Image.open(BytesIO(result["data"])) as image:
                self.assertEqual(image.format, "JPEG")
                self.assertEqual(image.size, (1500, 1000))
                expected = BytesIO()
                Image.new("RGB", image.size, "red").save(expected, format="JPEG", quality=50)
                self.assertEqual(result["data"], expected.getvalue())


class State(dict):
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__


if __name__ == "__main__":
    unittest.main()
