#!/usr/bin/env python3

import importlib.util
import json
import pathlib
import stat
import subprocess
import sys
import tempfile
import unittest


SCRIPT_PATH = pathlib.Path(__file__).with_name("prepare-request-template.py")
SPEC = importlib.util.spec_from_file_location(
    "figma_prepare_request_template",
    SCRIPT_PATH,
)
preparer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preparer)


def runtime_body(file_count):
    return {
        "model": "captured-model",
        "aiChatThreadId": "thread-1",
        "aiChatMessages": [
            {
                "role": "user",
                "guid": "12:34",
                "clientId": "client-1",
                "content": [{"type": "text", "text": "PRIVATE_PROMPT"}],
            }
        ],
        "files": {
            "/src/generated-%02d.tsx" % index: "export default %d" % index
            for index in range(file_count)
        },
        "fileMetadata": [
            {
                "guid": "0:%s" % index,
                "version": "v%s" % index,
            }
            for index in range(file_count)
        ],
        "chats": [{"content": "PRIVATE_CHAT"}],
    }


def run_cli(input_text, *arguments):
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH)] + list(arguments),
        input=input_text,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )


class PrepareRequestTemplateTest(unittest.TestCase):
    def test_clipboard_decoder_repairs_one_invalid_utf8_byte(self):
        decoded = preparer.decode_capture_bytes(
            b"curl https://www.figma.com --data-raw '"
            b'{"text":"safe ' + b"\xa1" + b' marker"}'
            b"'"
        )

        self.assertIn("\ufffd", decoded)
        self.assertTrue(decoded.startswith("curl "))

    def test_clipboard_decoder_rejects_many_invalid_utf8_bytes(self):
        with self.assertRaises(preparer.PreparationError):
            preparer.decode_capture_bytes(b"curl " + (b"\xff" * 32))

    def test_attachment_capture_decoder_can_discard_invalid_source_text(self):
        decoded = preparer.decode_capture_bytes(
            b'{"files":{"/src/private.tsx":"'
            + (b"\xff" * 128)
            + b'"}}',
            preparer.MAX_ATTACHMENT_CAPTURE_INVALID_UTF8_SEQUENCES,
        )

        self.assertEqual(decoded.count("\ufffd"), 128)

    def test_invalid_text_is_allowed_only_in_project_file_content(self):
        body = runtime_body(1)
        body["files"]["/src/generated-00.tsx"] += "\ufffd"

        prepared = preparer.prepare_template(
            json.dumps(body, ensure_ascii=False),
            max_project_files=64,
        )

        self.assertEqual(
            preparer.retained_invalid_text_paths(prepared),
            [],
        )
        body["scopeKey"] = "unsafe\ufffdmetadata"
        with self.assertRaises(preparer.PreparationError):
            preparer.prepare_template(
                json.dumps(body, ensure_ascii=False),
                max_project_files=64,
            )

    def test_rejects_capture_without_a_user_message(self):
        body = runtime_body(3)
        body["aiChatMessages"] = []

        with tempfile.TemporaryDirectory() as directory:
            output_path = pathlib.Path(directory) / "runtime-template.json"
            result = run_cli(
                json.dumps(body),
                "--output",
                str(output_path),
            )

            self.assertEqual(result.returncode, 2)
            self.assertFalse(output_path.exists())

    def test_rejects_capture_with_more_than_ten_project_files(self):
        secret = "PRIVATE_SOURCE_SENTINEL"
        body = runtime_body(62)
        body["files"]["/src/generated-00.tsx"] = secret

        with tempfile.TemporaryDirectory() as directory:
            output_path = pathlib.Path(directory) / "runtime-template.json"
            result = run_cli(
                json.dumps(body),
                "--output",
                str(output_path),
            )

            self.assertEqual(result.returncode, 2)
            self.assertFalse(output_path.exists())
            self.assertIn("10", result.stderr)
            self.assertNotIn(secret, result.stdout)
            self.assertNotIn(secret, result.stderr)

    def test_explicit_reviewed_limit_accepts_synthetic_starter_files(self):
        body = runtime_body(59)

        with tempfile.TemporaryDirectory() as directory:
            output_path = pathlib.Path(directory) / "runtime-template.json"
            result = run_cli(
                json.dumps(body),
                "--max-project-files",
                "64",
                "--output",
                str(output_path),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            prepared = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(len(prepared["body"]["files"]), 59)
            self.assertEqual(
                prepared["format"],
                "figma-anthropic-runtime-template-v1",
            )

    def test_full_template_discards_attachment_file_metadata(self):
        body = runtime_body(2)
        body["fileMetadata"] = [
            {
                "guid": "source-1",
                "version": "v1",
                "private": "discard-me",
            },
            {
                "guid": "attachment-1",
                "version": "",
            },
            {
                "guid": "source-2",
                "version": "v2",
            },
            None,
        ]

        prepared = preparer.prepare_template(json.dumps(body))

        self.assertEqual(
            prepared["body"]["fileMetadata"],
            [
                {"guid": "source-1", "version": "v1"},
                {"guid": "source-2", "version": "v2"},
            ],
        )

    def test_reviewed_limit_cannot_exceed_runtime_hard_limit(self):
        body = runtime_body(65)

        with tempfile.TemporaryDirectory() as directory:
            output_path = pathlib.Path(directory) / "runtime-template.json"
            result = run_cli(
                json.dumps(body),
                "--max-project-files",
                "65",
                "--output",
                str(output_path),
            )

            self.assertEqual(result.returncode, 2)
            self.assertFalse(output_path.exists())

    def test_attachment_runtime_only_discards_starter_sources_and_extra_fields(
        self,
    ):
        secret = "PRIVATE_STARTER_SOURCE_SENTINEL"
        body = runtime_body(59)
        body["files"]["/src/generated-00.tsx"] = secret
        body["chatSdkEnabled"] = True
        body["fsSnapshotOptions"] = {
            "path": "/private/source/root",
            "listing": "files",
            "content": "contents",
            "ignorePatterns": ["PRIVATE_IGNORE_PATTERN"],
            "respectGitignore": True,
        }
        body["sboxdUrl"] = "https://runtime.figma.com/session?signed=1"
        body["fileMetadata"] = [{"path": "/src/private.tsx"}]
        body["chatCompression"] = {
            "summary": "PRIVATE_SUMMARY",
            "totalSummarized": 99,
        }
        body["rawUserChatDetails"] = {
            "rawUserMessage": "PRIVATE_RAW_PROMPT",
            "attachments": [{"label": "private.pdf"}],
        }
        body["userMessageContent"] = {
            "plainText": "PRIVATE_PLAIN_TEXT",
            "imports": [{"path": "/src/imports/private.pdf"}],
        }
        body["unknownRuntimeField"] = "PRIVATE_UNKNOWN_FIELD"
        curl = (
            "curl https://www.figma.com/api/cortex/shared/figmake "
            "-H 'TSID: must-be-discarded' "
            "-H 'X-Figma-Support-Request-ID: support-1' "
            "--data-raw '%s'"
            % json.dumps(body, separators=(",", ":"))
        )

        with tempfile.TemporaryDirectory() as directory:
            output_path = pathlib.Path(directory) / "runtime-template.json"
            result = run_cli(
                curl,
                "--attachment-runtime-only",
                "--output",
                str(output_path),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            prepared_text = output_path.read_text(encoding="utf-8")
            prepared = json.loads(prepared_text)
            self.assertEqual(
                set(prepared["body"]),
                {
                    "aiChatMessages",
                    "chatCompression",
                    "chats",
                    "fileMetadata",
                    "files",
                    "fsSnapshotOptions",
                    "rawUserChatDetails",
                    "sboxdUrl",
                    "serverSideCommitEnabled",
                    "chatSdkEnabled",
                    "userMessageContent",
                },
            )
            self.assertEqual(prepared["body"]["files"], {})
            self.assertEqual(prepared["body"]["fileMetadata"], [])
            self.assertEqual(prepared["body"]["chats"], [])
            self.assertTrue(prepared["body"]["chatSdkEnabled"])
            self.assertEqual(
                prepared["body"]["fsSnapshotOptions"],
                preparer.SAFE_FS_SNAPSHOT_OPTIONS,
            )
            self.assertEqual(
                prepared["body"]["sboxdUrl"],
                "https://runtime.figma.com/session?signed=1",
            )
            self.assertEqual(
                prepared["body"]["chatCompression"],
                {"summary": "", "totalSummarized": 0},
            )
            self.assertEqual(
                prepared["body"]["rawUserChatDetails"],
                {"rawUserMessage": "", "attachments": []},
            )
            self.assertEqual(
                prepared["body"]["userMessageContent"],
                {
                    "chatMode": "build",
                    "hidden": False,
                    "imports": [],
                    "libraryKeys": [],
                    "plainText": "",
                    "selectedNodeIds": [],
                },
            )
            self.assertEqual(
                prepared["body"]["aiChatMessages"],
                [
                    {
                        "clientId": "client-1",
                        "guid": "12:34",
                        "role": "user",
                        "content": [],
                    }
                ],
            )
            self.assertEqual(
                prepared["headers"],
                {"x-figma-support-request-id": "support-1"},
            )
            self.assertNotIn(secret, prepared_text)
            self.assertNotIn("must-be-discarded", prepared_text)
            self.assertNotIn("PRIVATE_", prepared_text)
            self.assertNotIn("unknownRuntimeField", prepared_text)

    def test_attachment_runtime_only_rejects_missing_or_unsafe_runtime_fields(
        self,
    ):
        base = runtime_body(1)
        base["sboxdUrl"] = "https://runtime.figma.com/session?signed=1"
        base["fsSnapshotOptions"] = {
            "path": "/tmp/sandbox",
            "listing": "recursive",
            "content": "snapshot",
            "ignorePatterns": [],
            "respectGitignore": True,
        }
        cases = []
        without_user = json.loads(json.dumps(base))
        without_user["aiChatMessages"] = []
        cases.append(without_user)
        without_url = json.loads(json.dumps(base))
        without_url.pop("sboxdUrl")
        cases.append(without_url)
        without_fs = json.loads(json.dumps(base))
        without_fs.pop("fsSnapshotOptions")
        cases.append(without_fs)
        unsafe_url = json.loads(json.dumps(base))
        unsafe_url["sboxdUrl"] = "https://127.0.0.1/runtime"
        cases.append(unsafe_url)
        unsafe_fs = json.loads(json.dumps(base))
        unsafe_fs["fsSnapshotOptions"]["unknown"] = "PRIVATE_SOURCE"
        cases.append(unsafe_fs)

        for body in cases:
            with self.subTest(body_keys=sorted(body)):
                with tempfile.TemporaryDirectory() as directory:
                    output_path = (
                        pathlib.Path(directory) / "runtime-template.json"
                    )
                    result = run_cli(
                        json.dumps(body),
                        "--attachment-runtime-only",
                        "--output",
                        str(output_path),
                    )

                    self.assertEqual(result.returncode, 2)
                    self.assertFalse(output_path.exists())

    def test_writes_sanitized_three_file_template_and_runtime_env(self):
        body = runtime_body(3)
        body["aiChatMessages"].insert(
            0,
            {
                "role": "assistant",
                "content": [{"type": "text", "text": "PRIVATE_HISTORY"}],
            },
        )
        body["files"]["/src/imports/old.pdf"] = {
            "blobRef": "private-blob",
            "mimeType": "application/pdf",
            "type": "binary",
        }
        body["rawUserChatDetails"] = {
            "rawUserMessage": "PRIVATE_RAW_PROMPT",
            "attachments": [{"label": "private.pdf"}],
            "preserved": True,
        }
        body["userMessageContent"] = {
            "plainText": "PRIVATE_PLAIN_TEXT",
            "imports": [{"path": "/src/imports/old.pdf"}],
            "preserved": True,
        }
        body["fsSnapshotOptions"] = {"enabled": True}
        body["sboxdUrl"] = "https://runtime.example"
        curl = (
            "curl 'https://www.figma.com/api/cortex/shared/figmake' "
            "-H 'TSID: runtime-tsid' "
            "-H 'X-Figma-Support-Request-ID: support-1' "
            "-H 'X-Figma-User-ID: user-1' "
            "-H 'X-Figma-File-Key: file-1' "
            "--data-raw '%s'"
            % json.dumps(body, separators=(",", ":"))
        )

        with tempfile.TemporaryDirectory() as directory:
            output_path = pathlib.Path(directory) / "runtime-template.json"
            env_path = pathlib.Path(directory) / "runtime-template.env"
            result = run_cli(
                curl,
                "--output",
                str(output_path),
                "--env-output",
                str(env_path),
                "--foundry-origin-host",
                "test-v3-figmaiframepreview.figma.site",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "")
            self.assertEqual(
                stat.S_IMODE(output_path.stat().st_mode),
                0o600,
            )
            self.assertEqual(stat.S_IMODE(env_path.stat().st_mode), 0o600)

            prepared = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(
                set(prepared),
                {"format", "body", "headers", "config"},
            )
            self.assertEqual(
                prepared["format"],
                "figma-anthropic-runtime-template-v1",
            )
            self.assertEqual(
                prepared["headers"],
                {
                    "tsid": "runtime-tsid",
                    "x-figma-support-request-id": "support-1",
                },
            )
            self.assertEqual(
                set(prepared["body"]["files"]),
                {
                    "/src/generated-00.tsx",
                    "/src/generated-01.tsx",
                    "/src/generated-02.tsx",
                },
            )
            self.assertEqual(prepared["body"]["chats"], [])
            self.assertEqual(
                prepared["body"]["aiChatMessages"],
                [
                    {
                        "role": "user",
                        "guid": "12:34",
                        "clientId": "client-1",
                        "content": [],
                    }
                ],
            )
            self.assertEqual(
                prepared["body"]["rawUserChatDetails"],
                {
                    "rawUserMessage": "",
                    "attachments": [],
                    "preserved": True,
                },
            )
            self.assertEqual(
                prepared["body"]["userMessageContent"],
                {
                    "plainText": "",
                    "imports": [],
                    "preserved": True,
                },
            )
            self.assertEqual(
                prepared["config"],
                {
                    "FIGMA_USER_ID": "user-1",
                    "FIGMA_FILE_KEY": "file-1",
                    "FIGMA_THREAD_ID": "thread-1",
                    "FIGMA_ATTACHMENT_GUID": "12:1000034",
                    "FIGMA_FOUNDRY_ORIGIN_HOST": (
                        "test-v3-figmaiframepreview.figma.site"
                    ),
                },
            )
            serialized = output_path.read_text(encoding="utf-8")
            self.assertNotIn("PRIVATE_", serialized)
            env_text = env_path.read_text(encoding="utf-8")
            self.assertIn(
                'FIGMA_REQUEST_TEMPLATE_FILE="%s"' % output_path.resolve(),
                env_text,
            )
            self.assertIn('FIGMA_USER_ID="user-1"', env_text)
            self.assertIn('FIGMA_FILE_KEY="file-1"', env_text)
            self.assertIn('FIGMA_THREAD_ID="thread-1"', env_text)
            self.assertIn(
                'FIGMA_ATTACHMENT_GUID="12:1000034"',
                env_text,
            )
            self.assertIn(
                (
                    "FIGMA_FOUNDRY_ORIGIN_HOST="
                    '"test-v3-figmaiframepreview.figma.site"'
                ),
                env_text,
            )
            self.assertNotIn("PRIVATE_", env_text)

    def test_rejects_invalid_foundry_origin_host(self):
        with tempfile.TemporaryDirectory() as directory:
            output_path = pathlib.Path(directory) / "runtime-template.json"
            result = run_cli(
                json.dumps(runtime_body(3)),
                "--output",
                str(output_path),
                "--foundry-origin-host",
                "https://preview.figma.site/path",
            )

            self.assertEqual(result.returncode, 2)
            self.assertFalse(output_path.exists())
            self.assertIn("Foundry origin host", result.stderr)

    def test_rejects_sensitive_capture_headers_without_echoing_values(self):
        cookie_secret = "COOKIE_SECRET_SENTINEL"
        bearer_secret = "BEARER_SECRET_SENTINEL"
        curl = (
            "curl https://www.figma.com/api/cortex/shared/figmake "
            "-H 'Cookie: %s' "
            "-H 'Authorization: Bearer %s' "
            "--data-raw '%s'"
            % (
                cookie_secret,
                bearer_secret,
                json.dumps(runtime_body(3), separators=(",", ":")),
            )
        )

        with tempfile.TemporaryDirectory() as directory:
            output_path = pathlib.Path(directory) / "runtime-template.json"
            result = run_cli(curl, "--output", str(output_path))

            self.assertEqual(result.returncode, 2)
            self.assertFalse(output_path.exists())
            self.assertIn("sensitive authentication headers", result.stderr)
            self.assertNotIn(cookie_secret, result.stderr)
            self.assertNotIn(bearer_secret, result.stderr)
            self.assertNotIn(cookie_secret, result.stdout)
            self.assertNotIn(bearer_secret, result.stdout)

    def test_explicit_local_capture_mode_strips_cookie_and_authorization(self):
        cookie_secret = "COOKIE_SECRET_SENTINEL"
        bearer_secret = "BEARER_SECRET_SENTINEL"
        curl = (
            "curl https://www.figma.com/api/cortex/shared/figmake "
            "-H 'TSID: runtime-tsid' "
            "-H 'Cookie: %s' "
            "-H 'Authorization: Bearer %s' "
            "--data-raw '%s'"
            % (
                cookie_secret,
                bearer_secret,
                json.dumps(runtime_body(3), separators=(",", ":")),
            )
        )

        with tempfile.TemporaryDirectory() as directory:
            output_path = pathlib.Path(directory) / "runtime-template.json"
            result = run_cli(
                curl,
                "--allow-sensitive-input",
                "--output",
                str(output_path),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            prepared_text = output_path.read_text(encoding="utf-8")
            prepared = json.loads(prepared_text)
            self.assertEqual(prepared["headers"], {"tsid": "runtime-tsid"})
            self.assertNotIn("cookie", prepared_text.lower())
            self.assertNotIn("authorization", prepared_text.lower())
            self.assertNotIn(cookie_secret, prepared_text)
            self.assertNotIn(bearer_secret, prepared_text)

    def test_env_fragment_can_target_the_server_runtime_path(self):
        runtime_path = "/opt/figma-claude/runtime-template.json"
        with tempfile.TemporaryDirectory() as directory:
            output_path = pathlib.Path(directory) / "runtime-template.json"
            env_path = pathlib.Path(directory) / "runtime-template.env"
            result = run_cli(
                json.dumps(runtime_body(3)),
                "--output",
                str(output_path),
                "--env-output",
                str(env_path),
                "--runtime-template-path",
                runtime_path,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            env_text = env_path.read_text(encoding="utf-8")
            self.assertIn(
                'FIGMA_REQUEST_TEMPLATE_FILE="%s"' % runtime_path,
                env_text,
            )
            self.assertNotIn(str(output_path), env_text)


if __name__ == "__main__":
    unittest.main()
