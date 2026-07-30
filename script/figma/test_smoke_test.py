#!/usr/bin/env python3

import importlib.util
import io
import pathlib
import tempfile
import unittest
from unittest import mock


MODULE_PATH = pathlib.Path(__file__).with_name("smoke-test.py")
SPEC = importlib.util.spec_from_file_location("figma_smoke_test", MODULE_PATH)
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)


class SmokeTestUnitTest(unittest.TestCase):
    def test_test_assets_are_valid_and_contain_only_synthetic_data(self):
        self.assertTrue(
            smoke.quadrant_png().startswith(b"\x89PNG\r\n\x1a\n")
        )
        pdf = smoke.token_pdf("ONLY_TEST_TOKEN")
        self.assertTrue(pdf.startswith(b"%PDF-1.4"))
        self.assertIn(b"ONLY_TEST_TOKEN", pdf)

    def test_quadrant_color_match_requires_all_four_colors_in_order(self):
        self.assertTrue(
            smoke.contains_ordered_quadrant_colors("红, 绿, 蓝, 黄")
        )
        self.assertTrue(
            smoke.contains_ordered_quadrant_colors(
                "red, green, blue, yellow"
            )
        )
        self.assertFalse(
            smoke.contains_ordered_quadrant_colors("蓝, 绿, 红, 黄")
        )
        self.assertFalse(smoke.contains_ordered_quadrant_colors("红色"))

    def test_read_env_value_does_not_require_sourcing_the_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "adapter.env"
            path.write_text(
                "# ignored\nFIGMA_ADAPTER_API_KEY='test-key'\n",
                encoding="utf-8",
            )
            self.assertEqual(
                smoke.read_env_value(path, "FIGMA_ADAPTER_API_KEY"),
                "test-key",
            )

    def test_message_text_falls_back_to_anthropic_error_message(self):
        self.assertEqual(
            smoke.message_text(
                {
                    "type": "error",
                    "error": {
                        "type": "timeout_error",
                        "message": "upstream timed out",
                    },
                }
            ),
            "upstream timed out",
        )

    def test_run_smoke_covers_auth_text_tool_image_and_pdf(self):
        responses = [
            (200, {"ok": True}),
            (401, {"error": {"message": "unauthorized"}}),
            (
                200,
                {
                    "content": [
                        {"type": "text", "text": "FIGMA_TEXT_TOKEN_4821"}
                    ]
                },
            ),
            (
                200,
                {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "return_test_token",
                            "input": {"token": "FIGMA_TOOL_TOKEN_4821"},
                        }
                    ]
                },
            ),
            (
                200,
                {
                    "content": [
                        {"type": "text", "text": "red, green, blue, yellow"}
                    ]
                },
            ),
            (
                200,
                {
                    "content": [
                        {"type": "text", "text": "FIGMA_PDF_TOKEN_4821"}
                    ]
                },
            ),
        ]
        with mock.patch.object(
            smoke,
            "request_json",
            side_effect=responses,
        ) as request:
            results = smoke.run_smoke(
                "http://127.0.0.1:18091",
                "secret-value",
                5,
                True,
            )

        self.assertTrue(all(item["passed"] for item in results.values()))
        self.assertEqual(request.call_count, 6)
        self.assertNotIn("secret-value", repr(results))
        self.assertEqual(request.call_args_list[0].kwargs.get("api_key", ""), "")
        self.assertEqual(request.call_args_list[1].kwargs.get("api_key", ""), "")
        for call in request.call_args_list[2:]:
            self.assertEqual(call.kwargs["api_key"], "secret-value")

    def test_main_prints_non_ascii_responses_on_an_ascii_only_server(self):
        with tempfile.TemporaryDirectory() as directory:
            env_path = pathlib.Path(directory) / "adapter.env"
            env_path.write_text(
                "FIGMA_ADAPTER_API_KEY=test-key\n",
                encoding="utf-8",
            )
            output_bytes = io.BytesIO()
            ascii_stdout = io.TextIOWrapper(output_bytes, encoding="ascii")
            results = {
                "image": {
                    "status": 200,
                    "passed": True,
                    "response": "红色",
                }
            }

            with mock.patch.object(
                smoke,
                "run_smoke",
                return_value=results,
            ):
                with mock.patch.object(smoke.sys, "stdout", ascii_stdout):
                    self.assertIsNone(
                        smoke.main(
                            [
                                "--origin",
                                "http://127.0.0.1:18091",
                                "--env-file",
                                str(env_path),
                            ]
                        )
                    )
                    ascii_stdout.flush()

            self.assertIn(b"\\u7ea2\\u8272", output_bytes.getvalue())


if __name__ == "__main__":
    unittest.main()
