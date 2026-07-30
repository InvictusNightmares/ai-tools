#!/usr/bin/env python3

import json
import pathlib
import stat
import subprocess
import sys
import tempfile
import unittest


SCRIPT_PATH = pathlib.Path(__file__).with_name(
    "prepare-foundry-sync-template.py"
)


def sync_body():
    source_metadata = {
        "guid": "1:2",
        "sha1Hash": "a" * 40,
        "version": "v1",
    }
    source_entry_metadata = {
        "assetVersion": "asset",
        "collaborativeVersion": "collab",
        "guid": "1:2",
        "makeLibraryId": "",
        "sha1Hash": "a" * 40,
        "version": "v1",
    }
    pdf_path = "src/imports/private.pdf"
    return {
        "codeLastEditedBy": "assistant",
        "codeLibraryFormat": 2,
        "entrypointsByIdentifier": {"Code0_8": "src/App.tsx"},
        "featureType": "figmake",
        "filePathToMetadata": {
            "src/App.tsx": source_metadata,
            "pnpm-lock.yaml": {
                "guid": "1:4",
                "sha1Hash": "c" * 40,
                "version": "v2",
            },
            pdf_path: {"guid": "1:3", "version": ""},
        },
        "importedLibraryPaths": [],
        "originHost": "test-v3-figmaiframepreview.figma.site",
        "scopeKey": "0:9",
        "scopeType": "node",
        "selectedModel": "default",
        "sourceCodeHash": "b" * 40,
        "vfsChangeByPath": {
            "src/App.tsx": {
                "entry": {
                    "contents": "export default 1",
                    "metadata": source_entry_metadata,
                    "path": "src/App.tsx",
                },
                "type": "upsert",
            },
            pdf_path: {
                "entry": {
                    "downloadUrl": (
                        "https://www.figma.com/blobs/private"
                        "?X-Amz-Signature=PRIVATE_SIGNATURE"
                    ),
                    "metadata": {
                        "assetVersion": "1",
                        "blobRef": "d" * 40,
                        "guid": "1:3",
                        "mimeType": "application/pdf",
                        "version": "",
                    },
                    "path": pdf_path,
                },
                "type": "upsert",
            },
        },
    }


def curl_capture(body, cookie="PRIVATE_COOKIE"):
    return (
        "curl https://www.figma.com/api/cortex/foundry/sync "
        "-H 'TSID: captured-tsid' "
        "-H 'Cookie: %s' "
        "--data-raw '%s'"
        % (cookie, json.dumps(body, separators=(",", ":")))
    )


def run_cli(capture, *arguments):
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH)] + list(arguments),
        input=capture,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


class PrepareFoundrySyncTemplateTest(unittest.TestCase):
    def test_requires_explicit_local_sensitive_capture_mode(self):
        secret = "PRIVATE_COOKIE_SENTINEL"
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory) / "sync.json"
            result = run_cli(
                curl_capture(sync_body(), secret),
                "--output",
                str(output),
            )

            self.assertEqual(result.returncode, 2)
            self.assertFalse(output.exists())
            self.assertNotIn(secret, result.stdout)
            self.assertNotIn(secret, result.stderr)

    def test_writes_source_only_private_runtime_template(self):
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory) / "sync.json"
            result = run_cli(
                curl_capture(sync_body()),
                "--allow-sensitive-input",
                "--output",
                str(output),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)
            document = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(
                document["format"],
                "figma-foundry-sync-runtime-template-v1",
            )
            self.assertEqual(
                set(document["body"]["vfsChangeByPath"]),
                {"src/App.tsx"},
            )
            self.assertEqual(
                set(document["body"]["filePathToMetadata"]),
                {"src/App.tsx", "pnpm-lock.yaml"},
            )
            serialized = output.read_text(encoding="utf-8")
            self.assertNotIn("PRIVATE_COOKIE", serialized)
            self.assertNotIn("PRIVATE_SIGNATURE", serialized)
            self.assertNotIn("downloadUrl", serialized)

    def test_rejects_unreviewed_vfs_entry(self):
        body = sync_body()
        body["vfsChangeByPath"]["src/App.tsx"]["entry"]["private"] = True
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory) / "sync.json"
            result = run_cli(
                json.dumps(body),
                "--output",
                str(output),
            )

            self.assertEqual(result.returncode, 2)
            self.assertFalse(output.exists())
            self.assertIn("unreviewed Foundry sync entry", result.stderr)


if __name__ == "__main__":
    unittest.main()
