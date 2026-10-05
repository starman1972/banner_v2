import base64
import json
import unittest
from io import BytesIO
from unittest.mock import patch

import httpx
from openai import OpenAI
from PIL import Image

from logic import generation_v2 as generation


class BannerGenerationTests(unittest.TestCase):
    def setUp(self):
        self.requests = []
        self.queued_errors = []
        self.image = Image.new("RGB", (32, 32), "red")
        self.size_plan = generation.get_generation_size_for_target(3000, 660)
        self.client = self.enterContext(OpenAI(
            api_key="test-only",
            base_url="https://openai.test/v1",
            max_retries=0,
            http_client=httpx.Client(transport=httpx.MockTransport(self.respond)),
        ))
        self.enterContext(patch("logic.generation_v2.get_openai_client", return_value=self.client))
        self.enterContext(patch("builtins.print"))

    def respond(self, request):
        # Exercise the installed SDK's actual serialization without network access.
        self.requests.append(json.loads(request.content))
        self.assertEqual(request.url.path, "/v1/responses")
        if self.queued_errors:
            return httpx.Response(400, json={"error": self.queued_errors.pop(0)},
                                  headers={"x-request-id": "req_test_flare"})
        buffer = BytesIO()
        Image.new("RGB", (32, 32), "blue").save(buffer, format="JPEG")
        return httpx.Response(200, json={
            "id": "resp_test", "object": "response", "created_at": 0,
            "status": "completed", "model": self.requests[-1]["model"],
            "output": [{
                "id": "ig_test", "type": "image_generation_call", "status": "completed",
                "result": base64.b64encode(buffer.getvalue()).decode("ascii"),
            }],
        })

    def generate(self, **kwargs):
        return generation.generate_banner_with_gpt_image_2(
            self.image, "Create a banner from this reference.", self.size_plan, **kwargs,
        )

    def test_sdk_sends_explicit_flare_and_default_settings(self):
        result = self.generate()
        self.assertEqual(result.size, (32, 32))
        self.assertEqual(result.mode, "RGB")
        self.assertEqual(len(self.requests), 1)
        request = self.requests[0]
        self.assertEqual(request["model"], "gpt-4.1-mini")
        self.assertEqual(request["tool_choice"], {"type": "image_generation"})
        self.assertEqual(request["tools"], [{
            "type": "image_generation", "action": "edit", "model": "gpt-image-2.5-flare",
            "size": "3072x1024", "quality": "medium", "moderation": "auto",
            "output_format": "jpeg", "output_compression": 50,
        }])
        self.assertTrue(request["input"][0]["content"][1]["image_url"].startswith("data:image/png;base64,"))

    def test_supported_quality_and_format_choices_are_preserved(self):
        for quality in ("auto", "low", "medium", "high"):
            for output_format in ("png", "jpeg", "webp"):
                with self.subTest(quality=quality, output_format=output_format):
                    compression = None if output_format == "png" else 75
                    self.generate(quality=quality, output_format=output_format,
                                  output_compression=compression, moderation="low")
                    tool = self.requests[-1]["tools"][0]
                    self.assertEqual(tool["model"], "gpt-image-2.5-flare")
                    self.assertEqual(tool["quality"], quality)
                    self.assertEqual(tool["moderation"], "low")
                    self.assertEqual(tool["output_format"], output_format)
                    if compression is None:
                        self.assertNotIn("output_compression", tool)
                    else:
                        self.assertEqual(tool["output_compression"], compression)

    def test_rejected_image_model_does_not_fall_back(self):
        self.queued_errors = [{
            "code": "invalid_value", "param": "tools[0].model",
            "message": "Invalid value: 'gpt-image-2.5-flare'.", "type": "invalid_request_error",
        }]
        with self.assertRaisesRegex(ValueError, "No alternate image model was used.*req_test_flare"):
            self.generate()
        self.assertEqual(len(self.requests), 1)

    def test_unsupported_parameters_are_not_silently_removed(self):
        for parameter in ("model", "quality", "moderation", "output_format", "output_compression", "action"):
            with self.subTest(parameter=parameter):
                self.requests.clear()
                self.queued_errors = [{
                    "code": "unknown_parameter", "param": f"tools[0].{parameter}",
                    "message": f"Unknown parameter: '{parameter}'.", "type": "invalid_request_error",
                }]
                with self.assertRaisesRegex(ValueError, f"gpt-image-2.5-flare.*Unknown parameter: '{parameter}'"):
                    self.generate()
                self.assertEqual(len(self.requests), 1)

    def test_controller_and_size_retries_keep_flare_and_user_settings(self):
        self.queued_errors = [
            {"code": "model_not_found", "param": "model", "message": "gpt-4.1-mini not available"},
            {"code": "invalid_value", "param": "tools[0].size", "message": "Invalid size"},
        ]
        self.generate(quality="high", output_format="webp", output_compression=30)
        self.assertEqual(len(self.requests), 3)
        self.assertEqual(self.requests[-1]["model"], "gpt-4.1")
        self.assertEqual(self.requests[-1]["tools"][0]["size"], "1536x1024")
        for request in self.requests:
            tool = request["tools"][0]
            self.assertEqual(tool["model"], "gpt-image-2.5-flare")
            self.assertEqual(tool["quality"], "high")
            self.assertEqual(tool["output_format"], "webp")
            self.assertEqual(tool["output_compression"], 30)

    def test_policy_error_includes_model_and_request_id(self):
        self.queued_errors = [{
            "code": "content_policy_violation", "param": None, "message": "Request rejected",
        }]
        with self.assertRaisesRegex(ValueError, "gpt-image-2.5-flare.*content policy.*req_test_flare"):
            self.generate()
        self.assertEqual(len(self.requests), 1)

    def test_invalid_inputs_fail_before_request(self):
        for prompt in ("", "   "):
            with self.assertRaisesRegex(ValueError, "cannot be empty"):
                generation.generate_banner_with_gpt_image_2(self.image, prompt, self.size_plan)
        for options in ({"output_compression": 101}, {"output_format": "gif"},
                        {"output_format": "png", "output_compression": 50}, {"quality": "invalid"}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.generate(**options)
        self.assertEqual(self.requests, [])


if __name__ == "__main__":
    unittest.main()
