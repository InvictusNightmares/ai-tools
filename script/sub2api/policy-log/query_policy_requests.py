#!/usr/bin/env python3
"""Query sub2api policy-request records on a server by API key id.

The "异常记录" (policy-log) feature stores each retained upstream-policy
signal as a gzip member inside requests-*.jsonl.gz under the data directory.
This script decompresses the concatenated members and prints, for every
matching api_key_id, the metadata and the decoded request body so an admin
can see what the key actually asked.

Run it *on* the server (it reads the local data dir), piping the script over
SSH and passing the key id as argv[1]:

    ssh -T qiyuan-us   'python3 - 75'  < query_policy_requests.py
    ssh -T qiyuan-tokyo 'python3 - 102' < query_policy_requests.py

Python 3.6 compatible (no walrus operator, no capture_output).
"""

import base64
import glob
import gzip
import json
import os
import sys

DATA_DIR = "/opt/sub2api-deploy/data/policy-requests"


def _decode_body(rec):
    """Return the request body as readable text regardless of encoding."""
    enc = rec.get("body_encoding", "")
    body = rec.get("body")
    if enc == "base64" and isinstance(body, str):
        try:
            return base64.b64decode(body).decode("utf-8", "replace")
        except Exception:
            return body
    if isinstance(body, (dict, list)):
        return json.dumps(body, ensure_ascii=False, indent=2)
    if isinstance(body, str):
        return body
    return str(body)


def _extract_prompts(body_obj):
    """Pull user-facing prompt text out of common OpenAI body shapes."""
    prompts = []
    if not isinstance(body_obj, dict):
        return prompts

    def _add_content(content):
        if isinstance(content, str):
            prompts.append(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    if part.get("type") == "text":
                        prompts.append(part.get("text", ""))
                    else:
                        prompts.append(json.dumps(part, ensure_ascii=False))
                elif isinstance(part, str):
                    prompts.append(part)

    # Chat Completions: messages[] with role == user
    for m in body_obj.get("messages", []) or []:
        if isinstance(m, dict) and m.get("role") == "user":
            _add_content(m.get("content"))

    # Responses API: input (string or list of role/content items)
    inp = body_obj.get("input")
    if isinstance(inp, str):
        prompts.append(inp)
    elif isinstance(inp, list):
        for item in inp:
            if isinstance(item, dict) and item.get("role") == "user":
                _add_content(item.get("content"))

    # Legacy Completions: prompt
    p = body_obj.get("prompt")
    if isinstance(p, str):
        prompts.append(p)
    elif isinstance(p, list):
        prompts.extend(str(x) for x in p)

    return [x for x in prompts if x]


def main():
    key_id = None
    if len(sys.argv) > 1:
        try:
            key_id = int(sys.argv[1])
        except ValueError:
            key_id = None

    files = sorted(glob.glob(os.path.join(DATA_DIR, "requests-*.jsonl.gz")))
    if not files:
        print("No policy-request log files under %s" % DATA_DIR, file=sys.stderr)
        return 1

    found = 0
    for fp in files:
        try:
            handle = gzip.open(fp, "rt", encoding="utf-8", errors="replace")
        except Exception:
            continue
        try:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if key_id is not None and rec.get("api_key_id") != key_id:
                    continue
                found += 1
                body_obj = rec.get("body")
                prompts = _extract_prompts(body_obj) if isinstance(body_obj, dict) else []
                print("=" * 72)
                print("recorded_at     : %s" % rec.get("recorded_at"))
                print("error_code      : %s" % rec.get("error_code"))
                print("error_type      : %s" % rec.get("error_type", ""))
                print("signal_path     : %s" % rec.get("signal_path", ""))
                print("reason          : %s" % rec.get("reason", ""))
                print("upstream_status : %s" % rec.get("upstream_status"))
                print("api_key_id      : %s" % rec.get("api_key_id"))
                print("api_key_name    : %s" % rec.get("api_key_name"))
                print("user_id         : %s" % rec.get("user_id"))
                print("model           : %s" % rec.get("model"))
                print("protocol        : %s" % rec.get("protocol"))
                print("provider        : %s" % rec.get("provider"))
                if prompts:
                    print("-" * 72)
                    print("USER PROMPT:")
                    for p in prompts:
                        print(p)
                        print("~" * 40)
                print("-" * 72)
                print("RAW BODY:")
                print(_decode_body(rec))
        finally:
            handle.close()

    print("=" * 72)
    print("TOTAL matching records: %d" % found)
    print("files scanned: %d" % len(files))
    return 0


if __name__ == "__main__":
    sys.exit(main())
