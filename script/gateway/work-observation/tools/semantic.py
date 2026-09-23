#!/usr/bin/env python3
"""Run bounded, local-only Guard and Auto replay reviews.

The source event remains the actual production observation. Results written by
this module are explicitly offline analysis metadata: they never change the
captured outcome, routing, quarantine state, or any business/tool execution.
Only configured loopback/private HTTP endpoints are accepted. Guard reads the
normalized request and visible response from the immutable source record;
Auto receives a bounded request-context replay (with an explicit legacy
fallback when no request parts exist). Bodies are never copied into the
analysis database or ordinary worker output.
"""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import http.client
import hashlib
import ipaddress
import json
import math
import os
from pathlib import Path
import socket
import stat
from urllib.parse import urlsplit


MAX_REPLAY_BODY = 8 << 20
MAX_MESSAGE_CHARS = 2 << 20
MAX_RESPONSE_BYTES = 1 << 20

# A stage result is safe to reuse only for a short, explicit window.  The
# version is bumped whenever the Guard/Auto result contract changes.  The
# endpoint fingerprint is folded into the stored per-stage version below so
# changing a private preview URL also invalidates the cached stage.
SEMANTIC_RESULT_VERSION = 'offline-stage-reuse-v1'
DEFAULT_STAGE_REUSE_TTL_SECONDS = 60 * 60
MAX_STAGE_REUSE_TTL_SECONDS = 7 * 24 * 60 * 60

# Auto is used here as a routing observation surface.  It does not need the
# full response transcript (and sending a multi-megabyte transcript makes the
# classifier timeout much more likely), so replay gets a deliberately smaller
# and explicit budget.  Guard keeps using its existing normalized full event.
AUTO_MAX_MESSAGE_BYTES = 24 << 10
AUTO_MAX_MESSAGES_BYTES = 160 << 10
AUTO_MAX_TOOL_SCHEMA_BYTES = 8 << 10
AUTO_MAX_TOOLS_BYTES = 24 << 10
AUTO_MAX_STRUCTURED_BYTES = 8 << 10
AUTO_MAX_REPLAY_BYTES = 192 << 10
AUTO_MAX_RECENT_MESSAGES = 8
AUTO_MAX_TOOLS = 24
AUTO_MAX_TOOL_NAME_BYTES = 256
AUTO_MAX_TOOL_DESCRIPTION_BYTES = 4 << 10
AUTO_TRUNCATION_MARKER = '[offline replay truncated: earlier request context omitted]'


# Keep the worker single-threaded by default for compatibility with the
# original timer behavior.  Deployments that have measured endpoint capacity
# can opt into bounded job-level concurrency through ``max_workers``.  The
# cap is deliberately small: each job still calls Guard and Auto in order,
# so this limits the total number of in-flight replay pairs and avoids a
# nested request pool.
DEFAULT_MAX_WORKERS = 1
MAX_WORKERS = 16

# A temporary endpoint outage must not turn the rolling worker into an
# infinite retry loop.  ``attempts`` counts total processing attempts for a
# job, including the first call; exhausted jobs are moved to ``deferred`` and
# can be explicitly requeued after the endpoint is repaired.
DEFAULT_MAX_ATTEMPTS = 3
MAX_ATTEMPTS = 10


def ensure_schema(db):
    db.executescript('''
        CREATE TABLE IF NOT EXISTS semantic_reviews (
            region TEXT NOT NULL, event_id TEXT NOT NULL, source_path TEXT NOT NULL,
            source_sha TEXT NOT NULL, plane TEXT NOT NULL DEFAULT 'offline_analysis',
            state TEXT NOT NULL, guard_state TEXT NOT NULL, guard_decision TEXT,
            guard_risk_level TEXT, guard_categories TEXT, guard_reason_codes TEXT,
            guard_http_status INTEGER, auto_state TEXT NOT NULL, auto_model TEXT,
            auto_effort TEXT, auto_action TEXT, auto_reason TEXT,
            auto_classification TEXT, auto_http_status INTEGER, attempts INTEGER NOT NULL DEFAULT 0,
            error_code TEXT, reviewed_at TEXT,
            PRIMARY KEY(region,event_id)
        );
        CREATE INDEX IF NOT EXISTS semantic_reviews_state ON semantic_reviews(state,reviewed_at);
    ''')
    columns = {row[1] for row in db.execute('PRAGMA table_info(semantic_reviews)')}
    for name, definition in (
        ('guard_reviewed_at', 'TEXT'),
        ('auto_reviewed_at', 'TEXT'),
        ('guard_result_version', "TEXT NOT NULL DEFAULT ''"),
        ('auto_result_version', "TEXT NOT NULL DEFAULT ''"),
    ):
        if name not in columns:
            db.execute('ALTER TABLE semantic_reviews ADD COLUMN ' + name + ' ' + definition)
    columns = {row[1] for row in db.execute('PRAGMA table_info(review_jobs)')}
    for name, definition in (
        ('attempts', 'INTEGER NOT NULL DEFAULT 0'),
        ('claimed_at', 'TEXT'),
        ('last_error', 'TEXT'),
    ):
        if name not in columns:
            db.execute('ALTER TABLE review_jobs ADD COLUMN ' + name + ' ' + definition)


def _local_url(url):
    """Reject public endpoints so a config typo cannot export captured text."""
    if not isinstance(url, str) or not url:
        raise ValueError('semantic_endpoint_required')
    parsed = urlsplit(url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('semantic_endpoint_must_be_private_http')
    host = parsed.hostname.lower().rstrip('.')
    if host == 'localhost':
        return parsed
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        raise ValueError('semantic_endpoint_host_must_be_private_ip')
    if not (address.is_private or address.is_loopback or address.is_link_local):
        raise ValueError('semantic_endpoint_host_must_be_private_ip')
    return parsed


def _auth_headers(path, header='Authorization'):
    """Read a dedicated offline-review token without putting it in config/DB."""
    if not path:
        return {}
    if header not in ('Authorization', 'X-API-Key'):
        raise ValueError('semantic_auth_header_invalid')
    path = Path(path)
    if not path.is_absolute() or path.is_symlink():
        raise ValueError('semantic_auth_file_invalid')
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as exc:
        raise ValueError('semantic_auth_file_unavailable') from exc
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size < 1 or info.st_size > 4096 or (stat.S_IMODE(info.st_mode) & 0o077):
            raise ValueError('semantic_auth_file_invalid')
        raw = os.read(fd, 4097).decode('utf-8').strip()
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError('semantic_auth_file_invalid') from exc
    finally:
        os.close(fd)
    if not raw or '\r' in raw or '\n' in raw:
        raise ValueError('semantic_auth_file_invalid')
    if header == 'Authorization' and not raw.lower().startswith('bearer '):
        raw = 'Bearer ' + raw
    return {header: raw}


def _post(url, payload, timeout, headers=None):
    parsed = _local_url(url)
    body = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode()
    if len(body) > MAX_REPLAY_BODY:
        raise ValueError('semantic_replay_payload_too_large')
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == 'https' else 80)
    connection = http.client.HTTPSConnection(host, port, timeout=timeout) if parsed.scheme == 'https' else http.client.HTTPConnection(host, port, timeout=timeout)
    path = parsed.path or '/'
    if parsed.query:
        path += '?' + parsed.query
    try:
        request_headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
        if headers:
            request_headers.update(headers)
        connection.request('POST', path, body=body, headers=request_headers)
        response = connection.getresponse()
        raw = response.read(MAX_RESPONSE_BYTES + 1)
        status = response.status
    finally:
        connection.close()
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError('semantic_response_too_large')
    try:
        decoded = json.loads(raw.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        decoded = {}
    return status, decoded if isinstance(decoded, dict) else {}


def _text(value, limit=MAX_MESSAGE_CHARS):
    if isinstance(value, str):
        return value[:limit]
    if value is None:
        return ''
    try:
        text = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
    except (TypeError, ValueError):
        text = str(value)
    return text[:limit]


def _append_message(messages, role, value):
    if isinstance(value, list):
        for item in value:
            _append_message(messages, role, item)
        return
    if isinstance(value, dict):
        # Preserve text parts and tool results while avoiding a second copy of
        # the complete provider envelope in the Guard request.
        if isinstance(value.get('text'), str):
            messages.append({'role': role, 'content': value['text'][:MAX_MESSAGE_CHARS]})
            return
        if isinstance(value.get('content'), (str, list, dict)):
            _append_message(messages, value.get('role', role), value['content'])
            return
        if value.get('type') in ('function_call', 'tool_use', 'function_call_output', 'tool_result'):
            messages.append({'role': 'tool' if value['type'].endswith(('output', 'result')) else 'assistant', 'content': _text(value)})
            return
    text = _text(value)
    if text:
        messages.append({'role': role, 'content': text})


def _request_parts(request):
    messages = []
    if isinstance(request, dict) and request.get('type') == 'response.create' and isinstance(request.get('response'), dict):
        request = request['response']
    if isinstance(request, dict):
        if 'instructions' in request:
            _append_message(messages, 'system', request['instructions'])
        if 'system' in request:
            _append_message(messages, 'system', request['system'])
        if 'messages' in request:
            for item in request['messages'] if isinstance(request['messages'], list) else [request['messages']]:
                if isinstance(item, dict):
                    _append_message(messages, item.get('role', 'user'), item.get('content', item))
                else:
                    _append_message(messages, 'user', item)
        if 'input' in request:
            _append_message(messages, 'user', request['input'])
        if 'prompt' in request:
            _append_message(messages, 'user', request['prompt'])
        if not messages:
            _append_message(messages, 'user', request)
    elif request is not None:
        _append_message(messages, 'user', request)
    return messages


def _response_parts(response):
    messages = []
    def walk(value):
        if isinstance(value, list):
            for item in value:
                walk(item)
            return
        if isinstance(value, dict):
            if value.get('_capture_transport') == 'sse':
                walk(value.get('data'))
                return
            if isinstance(value.get('response'), dict):
                walk(value['response'])
                return
            if isinstance(value.get('choices'), list):
                for choice in value['choices']:
                    if not isinstance(choice, dict):
                        continue
                    item = choice.get('message', choice.get('delta', choice.get('text')))
                    if isinstance(item, dict):
                        _append_message(messages, item.get('role', 'assistant'), item.get('content', item))
                    elif item is not None:
                        _append_message(messages, 'assistant', item)
                return
            if 'output' in value:
                _append_message(messages, 'assistant', value['output'])
                return
            if value.get('type') in ('error', 'response.failed', 'response.incomplete'):
                _append_message(messages, 'assistant', value)
                return
            if 'content' in value or 'message' in value:
                _append_message(messages, value.get('role', 'assistant'), value.get('content', value.get('message')))
    walk(response)
    return messages


def _event_messages(event):
    messages = _request_parts(event.get('request'))
    messages.extend(_response_parts(event.get('response')))
    return messages or [{'role': 'user', 'content': '[empty captured request]'}]


def _tools(request):
    if not isinstance(request, dict) or not isinstance(request.get('tools'), list):
        return []
    result = []
    for item in request['tools'][:32]:
        if isinstance(item, dict):
            function = item.get('function')
            name = item.get('name') or (function.get('name') if isinstance(function, dict) else None)
            result.append({'name': str(name or 'tool')[:256], 'schema': _text(item)[:MAX_MESSAGE_CHARS]})
    return result


def _request_body(event):
    request = event.get('request')
    if isinstance(request, (dict, list)):
        return request
    return {'messages': _event_messages(event)}


def _utf8_text(value, limit, marker=''):
    """Return text bounded by UTF-8 bytes, without cutting a code point."""
    text = value if isinstance(value, str) else _text(value)
    raw = text.encode('utf-8')
    if len(raw) <= limit:
        return text
    marker_raw = marker.encode('utf-8') if marker else b''
    if len(marker_raw) >= limit:
        return raw[:limit].decode('utf-8', 'ignore')
    keep = max(0, limit - len(marker_raw))
    return raw[:keep].decode('utf-8', 'ignore') + marker


def _json_size(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))


def _message_for_auto(message):
    """Normalize the already extracted message to a small JSON envelope."""
    if not isinstance(message, dict):
        return {'role': 'user', 'content': _utf8_text(message, AUTO_MAX_MESSAGE_BYTES)}
    role = str(message.get('role') or 'user').strip()[:64] or 'user'
    content = _utf8_text(message.get('content', ''), AUTO_MAX_MESSAGE_BYTES)
    return {'role': role, 'content': content}


def _shrink_message(message, target_bytes):
    """Shorten one message while keeping a visible, valid truncation marker."""
    content = message.get('content', '')
    raw = content.encode('utf-8') if isinstance(content, str) else _text(content).encode('utf-8')
    if len(raw) <= target_bytes:
        return False
    message['content'] = _utf8_text(content, max(0, target_bytes), AUTO_TRUNCATION_MARKER)
    return True


def _fit_auto_messages(messages, budget):
    """Fit messages into a byte budget without dropping the latest turn first."""
    messages = [dict(item) for item in messages]
    if _json_size(messages) <= budget:
        return messages, False
    changed = True
    # First discard the oldest non-system context.  System instructions and
    # the latest user/tool turn carry the strongest routing signal.
    while _json_size(messages) > budget:
        latest_non_system = next(
            (index for index in range(len(messages) - 1, -1, -1)
             if str(messages[index].get('role', '')).lower() not in ('system', 'developer')),
            None,
        )
        removable = [
            index for index, item in enumerate(messages[:-1])
            if str(item.get('role', '')).lower() not in ('system', 'developer') and index != latest_non_system
        ]
        if not removable:
            break
        messages.pop(removable[0])
    # If system instructions or the retained tail alone are large, shorten
    # the largest content fields.  This always produces valid JSON because it
    # truncates strings before serialization.
    rounds = 0
    while _json_size(messages) > budget and rounds < 128:
        candidates = [
            (len(str(item.get('content', '')).encode('utf-8')), index)
            for index, item in enumerate(messages)
            if item.get('content')
        ]
        if not candidates:
            break
        size, index = max(candidates)
        target = max(1, size // 2)
        if not _shrink_message(messages[index], target):
            break
        rounds += 1
    # The envelope overhead is tiny compared with the configured budget.  If
    # an unusually large role list still exceeds it, remove the oldest system
    # item as the final hard-boundary fallback rather than sending an oversized
    # request.
    while _json_size(messages) > budget and len(messages) > 1:
        messages.pop(0)
    return messages, changed


def _compact_messages(messages):
    """Keep system messages and the recent request tail under a hard budget."""
    normalized = [_message_for_auto(item) for item in messages]
    if not normalized:
        normalized = [{'role': 'user', 'content': '[empty captured request]'}]
    system_indexes = [
        index for index, item in enumerate(normalized)
        if str(item.get('role', '')).lower() in ('system', 'developer')
    ]
    non_system_indexes = [index for index in range(len(normalized)) if index not in system_indexes]
    selected_indexes = set(system_indexes)
    selected_indexes.update(non_system_indexes[-AUTO_MAX_RECENT_MESSAGES:])
    selected = [normalized[index] for index in sorted(selected_indexes)]
    truncated = len(selected_indexes) != len(normalized)
    # Per-message clipping above may already have changed text.  Compare byte
    # lengths to expose that fact in metadata without retaining source text.
    for original, compact in zip(messages, normalized):
        if _utf8_text(original.get('content', '') if isinstance(original, dict) else original, AUTO_MAX_MESSAGE_BYTES) != compact.get('content'):
            truncated = True
            break
    if truncated:
        selected.append({'role': 'system', 'content': AUTO_TRUNCATION_MARKER})
    selected, fit_changed = _fit_auto_messages(selected, AUTO_MAX_MESSAGES_BYTES)
    if fit_changed and not any(item.get('content') == AUTO_TRUNCATION_MARKER for item in selected):
        # The first fit can discover that the selected tail itself is too
        # large.  Make that second form of omission visible to the classifier
        # as well as to metadata, then fit once more around the marker.
        selected.append({'role': 'system', 'content': AUTO_TRUNCATION_MARKER})
        selected, _ = _fit_auto_messages(selected, AUTO_MAX_MESSAGES_BYTES)
    return selected, bool(truncated or fit_changed), len(normalized)


def _schema_for_auto(value, depth=0):
    """Copy a tool schema as valid JSON while dropping unbounded branches."""
    if depth > 5:
        return {}
    if isinstance(value, dict):
        result = {}
        scalar_keys = ('type', 'title', 'format', 'default', 'additionalProperties')
        for key in scalar_keys:
            if key not in value:
                continue
            item = value.get(key)
            if isinstance(item, float) and not math.isfinite(item):
                continue
            if isinstance(item, (str, int, float, bool)) or item is None:
                result[key] = _utf8_text(item, 256) if isinstance(item, str) else item
        if isinstance(value.get('description'), str):
            result['description'] = _utf8_text(value['description'], AUTO_MAX_TOOL_DESCRIPTION_BYTES)
        if isinstance(value.get('enum'), list):
            enum_values = []
            for item in value['enum'][:32]:
                if isinstance(item, float) and not math.isfinite(item):
                    continue
                enum_values.append(_utf8_text(item, 256) if isinstance(item, str) else item)
            result['enum'] = enum_values
        if isinstance(value.get('required'), list):
            result['required'] = [_utf8_text(item, 256) for item in value['required'][:64] if isinstance(item, str)]
        if isinstance(value.get('items'), (dict, list)):
            result['items'] = _schema_for_auto(value['items'], depth + 1)
        properties = value.get('properties')
        if isinstance(properties, dict):
            result['properties'] = {
                _utf8_text(name, 256): _schema_for_auto(schema, depth + 1)
                for name, schema in list(properties.items())[:64]
            }
        # Preserve a small amount of provider-specific structure when it is
        # scalar, but never copy arbitrary nested blobs from the capture.
        if not result and isinstance(value.get('type'), str):
            result['type'] = _utf8_text(value['type'], 64)
        if _json_size(result) > AUTO_MAX_TOOL_SCHEMA_BYTES:
            # Names and the top-level type remain useful to Auto; dropping the
            # schema is preferable to sending a syntactically invalid suffix.
            return {'type': result.get('type', 'object')}
        return result
    if isinstance(value, list):
        result = [_schema_for_auto(item, depth + 1) for item in value[:16]]
        return result if _json_size(result) <= AUTO_MAX_TOOL_SCHEMA_BYTES else []
    if isinstance(value, str):
        return _utf8_text(value, 256)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value if isinstance(value, (int, float, bool)) or value is None else {}


def _tool_name_and_schema(item):
    if not isinstance(item, dict):
        return 'tool', '', {}, str(item.get('type', '')) if isinstance(item, dict) else ''
    function = item.get('function') if isinstance(item.get('function'), dict) else {}
    source = function or item
    name = source.get('name') or item.get('name') or 'tool'
    description = source.get('description') or item.get('description') or ''
    schema = source.get('parameters')
    if schema is None:
        schema = source.get('input_schema')
    if schema is None:
        schema = item.get('parameters') or item.get('input_schema') or {}
    return str(name), str(description) if description is not None else '', schema, str(item.get('type', ''))


def _compact_tools(request, protocol):
    """Build protocol-shaped tools with bounded, valid schemas."""
    if not isinstance(request, dict) or not isinstance(request.get('tools'), list):
        return [], False
    result = []
    truncated = len(request['tools']) > AUTO_MAX_TOOLS
    for item in request['tools'][:AUTO_MAX_TOOLS]:
        name, description, schema, tool_type = _tool_name_and_schema(item)
        name = _utf8_text(name, AUTO_MAX_TOOL_NAME_BYTES)
        description = _utf8_text(description, AUTO_MAX_TOOL_DESCRIPTION_BYTES)
        if protocol == 'chat':
            # Chat Completions expects function details nested under function.
            compact = {'type': 'function', 'function': {'name': name, 'description': description,
                                                        'parameters': _schema_for_auto(schema)}}
        elif protocol == 'anthropic':
            compact = {'name': name, 'description': description, 'input_schema': _schema_for_auto(schema)}
        else:
            # Responses accepts the flat function tool shape.  Preserve
            # non-function tool types such as image_generation as a tiny,
            # bounded descriptor so modality remains visible to Auto.
            if tool_type and tool_type != 'function':
                compact = {'type': _utf8_text(tool_type, 128)}
                if name and name != 'tool':
                    compact['name'] = name
                if isinstance(item, dict) and isinstance(item.get('model'), str):
                    compact['model'] = _utf8_text(item['model'], 256)
            else:
                compact = {'type': 'function', 'name': name, 'description': description,
                           'parameters': _schema_for_auto(schema)}
        result.append(compact)
    if _json_size(result) > AUTO_MAX_TOOLS_BYTES:
        truncated = True
        # Remove schema details first while preserving every tool name/type.
        for item in result:
            if 'function' in item and isinstance(item['function'], dict):
                item['function']['description'] = _utf8_text(item['function'].get('description', ''), 512)
                item['function']['parameters'] = {}
            elif 'input_schema' in item:
                item['description'] = _utf8_text(item.get('description', ''), 512)
                item['input_schema'] = {}
            elif 'parameters' in item:
                item['description'] = _utf8_text(item.get('description', ''), 512)
                item['parameters'] = {}
            if _json_size(result) <= AUTO_MAX_TOOLS_BYTES:
                break
    while _json_size(result) > AUTO_MAX_TOOLS_BYTES and len(result) > 1:
        result.pop()
    return result, truncated


def _compact_output_format(value):
    """Retain only bounded, routing-relevant structured-output metadata."""
    if not isinstance(value, dict):
        return {}
    result = {}
    for key in ('type', 'name', 'description', 'verbosity'):
        item = value.get(key)
        if isinstance(item, str):
            result[key] = _utf8_text(item, 256 if key != 'description' else 1024)
    if isinstance(value.get('strict'), bool):
        result['strict'] = value['strict']
    if isinstance(value.get('schema'), (dict, list)):
        result['schema'] = _schema_for_auto(value['schema'])
    # OpenAI response_format nests the schema one level further, while
    # Responses/Anthropic use a `format` object.  Both are safe to preserve as
    # compact structured JSON and are consumed only by NormalizeProtocolRequest.
    for key in ('json_schema', 'format'):
        nested = value.get(key)
        if isinstance(nested, dict):
            result[key] = _compact_output_format(nested)
    return result


def _compact_structured_fields(request):
    """Copy output-shape hints without carrying model/reasoning or free text."""
    if not isinstance(request, dict):
        return {}
    result = {}
    # Keep all three names because captures can contain legacy cross-provider
    # fields.  The protocol decoder will consult only the field native to its
    # envelope; retaining a small legacy hint avoids losing structured-output
    # capability during a format migration.
    for key in ('response_format', 'text', 'output_config'):
        value = request.get(key)
        if isinstance(value, dict):
            compact = _compact_output_format(value)
            if compact:
                result[key] = compact
    if _json_size(result) <= AUTO_MAX_STRUCTURED_BYTES:
        return result
    # Preserve the format kind and discard nested schemas if a pathological
    # capture still fills the structured-output budget.
    summary = {}
    for key, value in result.items():
        compact = {}
        if isinstance(value.get('type'), str):
            compact['type'] = value['type']
        if isinstance(value.get('verbosity'), str):
            compact['verbosity'] = value['verbosity']
        for nested_key in ('json_schema', 'format'):
            nested = value.get(nested_key)
            if isinstance(nested, dict):
                nested_summary = {}
                if isinstance(nested.get('type'), str):
                    nested_summary['type'] = nested['type']
                if isinstance(nested.get('name'), str):
                    nested_summary['name'] = nested['name']
                if nested_summary:
                    compact[nested_key] = nested_summary
        summary[key] = compact
    return summary


def guard_payload(event):
    request = event.get('request') if isinstance(event.get('request'), dict) else {}
    attachments = request.get('attachments', []) if isinstance(request, dict) else []
    if not isinstance(attachments, list):
        attachments = []
    return {
        'request_id': str(event.get('id', '')),
        'protocol': str(event.get('protocol', 'unknown')),
        'provider': str(event.get('provider', 'openai')),
        'model': str(event.get('model') or request.get('model') or 'auto')[:256],
        'region': str(event.get('region', '')),
        'session_hash': str(event.get('root_session_hash') or event.get('session_hash') or ''),
        'messages': _event_messages(event),
        'tools': _tools(request),
        'attachments': [item for item in attachments[:16] if isinstance(item, dict)],
        'metadata': {'plane': 'offline_analysis', 'ingress': str(event.get('ingress', '')), 'client': str(event.get('client', ''))},
    }


def auto_payload(event):
    request = event.get('request')
    observed_protocol = str(event.get('protocol') or '').strip().lower()
    protocol_aliases = {
        'chat': 'chat',
        'chat.completions': 'chat',
        'openai-chat': 'chat',
        'responses': 'responses',
        'openai-responses': 'responses',
        'anthropic': 'anthropic',
        'messages': 'anthropic',
        'anthropic-messages': 'anthropic',
    }
    protocol = protocol_aliases.get(observed_protocol)
    if protocol is None:
        # Some older captures have protocol="other" even though the event
        # still contains a complete normalized conversation.  Route preview
        # accepts only the three public envelopes; replay that conversation as
        # chat instead of turning a usable sample into a permanent 400.
        protocol = 'chat'
    request_messages = _request_parts(request)
    # `_request_parts` intentionally has a broad Guard fallback that renders
    # an otherwise opaque request dict as one user message.  Auto should use
    # the response fallback only when there is no recognizable request
    # conversation field, so opaque legacy envelopes do not masquerade as
    # meaningful request context.
    if isinstance(request, dict) and not any(
        key in request for key in ('instructions', 'system', 'messages', 'input', 'prompt')
    ):
        request_messages = []
    source = 'request'
    if not request_messages:
        # A handful of legacy records contain only transport metadata in the
        # request.  Keep the old normalized fallback so those records remain
        # analyzable, while making the fallback explicit in metadata.
        request_messages = _event_messages(event)
        source = 'event_messages_fallback'
    messages, messages_truncated, original_message_count = _compact_messages(request_messages)
    tools, tools_truncated = _compact_tools(request, protocol)
    stream_requested = bool(
        isinstance(request, dict) and isinstance(request.get('stream'), bool) and request.get('stream')
    )
    structured_fields = _compact_structured_fields(request)

    # The route preview decoder accepts the same public envelopes as the live
    # clients.  Keep system instructions in their protocol-native field and
    # leave only the user/assistant/tool turn list in input/messages where the
    # provider expects it.
    system_messages = [
        item for item in messages
        if str(item.get('role', '')).lower() in ('system', 'developer')
    ]
    conversation_messages = [
        item for item in messages
        if str(item.get('role', '')).lower() not in ('system', 'developer')
    ]
    system_text = '\n\n'.join(str(item.get('content', '')) for item in system_messages if item.get('content'))
    if protocol == 'responses':
        body = {'input': conversation_messages}
        if system_text:
            body['instructions'] = system_text
    elif protocol == 'anthropic':
        body = {'messages': conversation_messages}
        if system_text:
            body['system'] = system_text
    else:
        # Chat Completions carries system/developer turns in messages.
        body = {'messages': messages}
    # Preserve only routing-relevant request capabilities.  In particular,
    # never copy model/reasoning fields or anything from the response body.
    body['stream'] = stream_requested
    body.update(structured_fields)
    if tools:
        body['tools'] = tools

    # A final envelope bound covers protocol fields, tool descriptors and the
    # metadata below.  In practice the message/tool budgets leave ample room;
    # this guard makes the invariant explicit if constants are changed later.
    if _json_size(body) > AUTO_MAX_REPLAY_BYTES:
        message_budget = max(1, AUTO_MAX_REPLAY_BYTES - AUTO_MAX_TOOLS_BYTES - _json_size(structured_fields) - 1024)
        messages, _, _ = _fit_auto_messages(messages, message_budget)
        system_messages = [item for item in messages if str(item.get('role', '')).lower() in ('system', 'developer')]
        conversation_messages = [item for item in messages if str(item.get('role', '')).lower() not in ('system', 'developer')]
        system_text = '\n\n'.join(str(item.get('content', '')) for item in system_messages if item.get('content'))
        if protocol == 'responses':
            body = {'input': conversation_messages}
            if system_text:
                body['instructions'] = system_text
        elif protocol == 'anthropic':
            body = {'messages': conversation_messages}
            if system_text:
                body['system'] = system_text
        else:
            body = {'messages': messages}
        body['stream'] = stream_requested
        body.update(structured_fields)
        if tools:
            body['tools'] = tools
        messages_truncated = True
    return {
        'protocol': protocol,
        'provider': str(event.get('provider', 'openai')),
        # Route preview is the Auto policy surface. Always use its public
        # model name; the original requested model remains in the captured
        # body and is stripped by the same normalizer as a live request.
        'model': 'auto',
        'body': body,
        'turn': 1,
        'new_task_epoch': False,
        'tool_loop': bool(tools),
        'hard_capability_failure': False,
        'stream_active': stream_requested,
        'session_id': str(event.get('root_session_hash') or event.get('session_hash') or ''),
        'metadata': {
            'plane': 'offline_analysis',
            'replay': 'bounded_request_context',
            'source': source,
            'truncated': bool(messages_truncated or tools_truncated),
            'original_message_count': original_message_count,
            'replayed_message_count': len(messages),
            'replayed_tool_count': len(tools),
        },
    }


def _json_field(value):
    return json.dumps(value if isinstance(value, (list, dict)) else [], ensure_ascii=False, separators=(',', ':'))


def _guard_result(status, body):
    decision = body.get('decision') if isinstance(body.get('decision'), str) else None
    if status < 200 or status >= 300:
        return {'state': 'unavailable' if status in (502, 503, 504) else 'http_error', 'decision': decision,
                'risk_level': None, 'categories': [], 'reason_codes': [], 'http_status': status, 'error': body.get('error', 'guard_http_error')}
    if decision not in ('allow', 'block', 'unavailable'):
        return {'state': 'invalid', 'decision': None, 'risk_level': None, 'categories': [], 'reason_codes': [], 'http_status': status, 'error': 'invalid_guard_decision'}
    if decision == 'unavailable':
        # A successful HTTP response can still mean that Guard reached no
        # safety conclusion.  Keep that distinct from allow/block and make it
        # retryable; it must never become an implicit allow or a training label.
        return {'state': 'unavailable', 'decision': 'unavailable', 'risk_level': body.get('risk_level'),
                'categories': body.get('categories', []) if isinstance(body.get('categories'), list) else [],
                'reason_codes': body.get('reason_codes', []) if isinstance(body.get('reason_codes'), list) else [],
                'http_status': status, 'error': body.get('error', 'guard_unavailable')}
    return {'state': 'complete', 'decision': decision, 'risk_level': body.get('risk_level'),
            'categories': body.get('categories', []) if isinstance(body.get('categories'), list) else [],
            'reason_codes': body.get('reason_codes', []) if isinstance(body.get('reason_codes'), list) else [], 'http_status': status}


def _auto_result(status, body):
    if status < 200 or status >= 300:
        error = body.get('error') if isinstance(body.get('error'), str) else 'auto_http_error'
        return {'state': 'blocked' if status == 403 else ('unavailable' if status in (502, 503, 504) else 'http_error'), 'model': None, 'effort': None, 'action': None, 'reason': error, 'error': error, 'classification': {}, 'http_status': status}
    model = body.get('effective_model')
    if not isinstance(model, str) or not model:
        return {'state': 'invalid', 'model': None, 'effort': None, 'action': None, 'reason': None, 'error': 'invalid_auto_result', 'classification': {}, 'http_status': status}
    return {'state': 'complete', 'model': model[:256], 'effort': body.get('effective_reasoning_effort'), 'action': body.get('action'), 'reason': body.get('reason'), 'classification': body.get('classification', {}) if isinstance(body.get('classification'), dict) else {}, 'http_status': status}


def _not_run_auto(reason):
    """Represent an Auto stage that was correctly skipped by the gate."""
    return {
        'state': 'not_run', 'model': None, 'effort': None, 'action': None,
        'reason': reason, 'classification': {}, 'http_status': None,
    }


def _stage_result_version(role, url, headers=None):
    """Return a body-free version key for one private analysis stage.

    The static contract version is deliberately combined with the endpoint
    identity.  A URL change therefore cannot reuse a result produced by a
    different preview service, while token rotation on the same endpoint does
    not unnecessarily invalidate a short-lived observation.
    """
    header_name = 'Authorization'
    if isinstance(headers, dict) and 'X-API-Key' in headers:
        header_name = 'X-API-Key'
    material = '\0'.join((SEMANTIC_RESULT_VERSION, str(role), str(url), header_name))
    digest = hashlib.sha256(material.encode('utf-8')).hexdigest()[:16]
    return f'{SEMANTIC_RESULT_VERSION}:{digest}'


def _as_utc(value):
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _stage_is_reusable(prior, role, source_sha, expected_version, now, ttl_seconds):
    """Check all freshness boundaries before reusing a persisted stage.

    A missing timestamp/version is intentionally a cache miss.  That keeps
    rows created by older schema versions compatible without treating their
    long-lived terminal state as a fresh classifier conclusion.
    """
    if not isinstance(prior, dict) or ttl_seconds <= 0:
        return False
    if not source_sha or prior.get('source_sha') != source_sha:
        return False
    if prior.get(f'{role}_result_version') != expected_version:
        return False
    state = prior.get(f'{role}_state')
    if role == 'guard':
        # A 2xx ``decision=unavailable`` is displayed as a Guard
        # non-conclusion and remains retryable; do not turn it into a cached
        # policy decision merely because the row's transport state is
        # otherwise complete.
        if state != 'complete' or prior.get('guard_decision') == 'unavailable':
            return False
    elif state not in ('complete', 'blocked'):
        return False
    stamped = _as_utc(prior.get(f'{role}_reviewed_at'))
    if stamped is None or stamped > now:
        return False
    return (now - stamped).total_seconds() <= ttl_seconds


def _json_list(value):
    if isinstance(value, list):
        return value
    if not isinstance(value, str) or not value:
        return []
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError):
        return []
    return decoded if isinstance(decoded, list) else []


def _json_dict(value):
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value:
        return {}
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return decoded if isinstance(decoded, dict) else {}


def _persisted_stage_result(prior, role):
    """Convert metadata-only DB columns back to a bounded stage result."""
    if role == 'guard':
        return {
            'state': prior.get('guard_state'),
            'decision': prior.get('guard_decision'),
            'risk_level': prior.get('guard_risk_level'),
            'categories': _json_list(prior.get('guard_categories')),
            'reason_codes': _json_list(prior.get('guard_reason_codes')),
            'http_status': prior.get('guard_http_status'),
        }
    return {
        'state': prior.get('auto_state'),
        'model': prior.get('auto_model'),
        'effort': prior.get('auto_effort'),
        'action': prior.get('auto_action'),
        'reason': prior.get('auto_reason'),
        'classification': _json_dict(prior.get('auto_classification')),
        'http_status': prior.get('auto_http_status'),
    }


def _event_headers(event, headers=None):
    """Preserve the observed client identity on an offline Auto replay.

    Credentials remain supplied separately by the restricted auth file; an
    event never supplies or reconstructs an Authorization header.
    """
    result = dict(headers or {})
    user_agent = event.get('user_agent')
    if isinstance(user_agent, str) and user_agent:
        result['User-Agent'] = user_agent[:512]
    return result


def review_event(event, guard_url, auto_url, timeout, guard_headers=None, auto_headers=None,
                 prior=None, source_sha='', now=None,
                 stage_reuse_ttl_seconds=DEFAULT_STAGE_REUSE_TTL_SECONDS):
    """Run the two private stages, reusing only fresh compatible results.

    ``prior`` contains metadata loaded from ``semantic_reviews``; it never
    contains a request or response body.  The optional arguments preserve the
    old call shape for direct callers and tests.  A cached stage is treated as
    an observation with the same terminal semantics as a fresh call, while a
    stale, old-version, or source-mismatched stage is called again.
    """
    current = _as_utc(now) or datetime.now(timezone.utc)
    try:
        ttl = float(stage_reuse_ttl_seconds)
    except (TypeError, ValueError):
        ttl = 0
    ttl = min(max(ttl, 0), MAX_STAGE_REUSE_TTL_SECONDS)
    guard_version = _stage_result_version('guard', guard_url, guard_headers)
    # The event's User-Agent is intentionally not part of the version key: it
    # describes the observed client, not the classifier implementation.
    auto_version = _stage_result_version('auto', auto_url, auto_headers)
    result = {'guard': None, 'auto': None, '_reused': {'guard': False, 'auto': False},
              '_stage_meta': {}}

    if _stage_is_reusable(prior, 'guard', source_sha, guard_version, current, ttl):
        result['guard'] = _persisted_stage_result(prior, 'guard')
        result['_reused']['guard'] = True
        result['_stage_meta']['guard_reviewed_at'] = prior.get('guard_reviewed_at')
    else:
        try:
            if guard_headers:
                result['guard'] = _guard_result(*_post(guard_url, guard_payload(event), timeout, guard_headers))
            else:
                result['guard'] = _guard_result(*_post(guard_url, guard_payload(event), timeout))
        except (OSError, ValueError, socket.error, http.client.HTTPException) as exc:
            result['guard'] = {'state': 'unavailable', 'decision': None, 'risk_level': None, 'categories': [], 'reason_codes': [], 'http_status': None, 'error': type(exc).__name__}
        result['_stage_meta']['guard_reviewed_at'] = current.isoformat()

    result['_stage_meta']['guard_result_version'] = guard_version
    guard = result['guard']
    # Auto is downstream of Guard in the real path.  Do not spend classifier
    # capacity, or create a misleading model label, when Guard has blocked the
    # request or produced no usable conclusion.  The explicit ``not_run``
    # state lets the review UI distinguish this from an Auto transport error.
    if guard.get('state') != 'complete' or guard.get('decision') != 'allow':
        reason = 'guard_block' if guard.get('decision') == 'block' else 'guard_no_conclusion'
        result['auto'] = _not_run_auto(reason)
        result['_stage_meta']['auto_reviewed_at'] = current.isoformat()
        result['_stage_meta']['auto_result_version'] = ''
        result['state'] = 'complete' if guard.get('state') == 'complete' else 'unavailable'
        return result

    if _stage_is_reusable(prior, 'auto', source_sha, auto_version, current, ttl):
        result['auto'] = _persisted_stage_result(prior, 'auto')
        result['_reused']['auto'] = True
        result['_stage_meta']['auto_reviewed_at'] = prior.get('auto_reviewed_at')
    else:
        try:
            if auto_headers:
                result['auto'] = _auto_result(*_post(auto_url, auto_payload(event), timeout, _event_headers(event, auto_headers)))
            else:
                # Keep the no-auth call shape compatible with lightweight local
                # test doubles. Regional previews always use a dedicated auth
                # file, so the observed UA is attached on the real path above.
                result['auto'] = _auto_result(*_post(auto_url, auto_payload(event), timeout))
        except (OSError, ValueError, socket.error, http.client.HTTPException) as exc:
            result['auto'] = {'state': 'unavailable', 'model': None, 'effort': None, 'action': None, 'reason': None, 'classification': {}, 'http_status': None, 'error': type(exc).__name__}
        result['_stage_meta']['auto_reviewed_at'] = current.isoformat()

    result['_stage_meta']['auto_result_version'] = auto_version
    # A model selection is terminal; transport/invalid Auto results remain
    # retryable.  Guard allow is guaranteed by the branch above.
    auto_terminal = result['auto']['state'] in ('complete', 'blocked')
    result['state'] = 'complete' if auto_terminal else 'unavailable'
    return result


def _write_review(db, job, review, attempts, now):
    guard, auto = review['guard'], review['auto']
    error = guard.get('error') or auto.get('error')
    stage_meta = review.get('_stage_meta') if isinstance(review.get('_stage_meta'), dict) else {}
    guard_reviewed_at = stage_meta.get('guard_reviewed_at') or now.isoformat()
    auto_reviewed_at = stage_meta.get('auto_reviewed_at') or now.isoformat()
    guard_result_version = str(stage_meta.get('guard_result_version') or '')
    auto_result_version = str(stage_meta.get('auto_result_version') or '')
    db.execute('''INSERT INTO semantic_reviews
      (region,event_id,source_path,source_sha,plane,state,guard_state,guard_decision,guard_risk_level,guard_categories,guard_reason_codes,guard_http_status,
       auto_state,auto_model,auto_effort,auto_action,auto_reason,auto_classification,auto_http_status,attempts,error_code,reviewed_at,
       guard_reviewed_at,auto_reviewed_at,guard_result_version,auto_result_version)
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
      ON CONFLICT(region,event_id) DO UPDATE SET source_path=excluded.source_path,source_sha=excluded.source_sha,plane=excluded.plane,state=excluded.state,
       guard_state=excluded.guard_state,guard_decision=excluded.guard_decision,guard_risk_level=excluded.guard_risk_level,guard_categories=excluded.guard_categories,
       guard_reason_codes=excluded.guard_reason_codes,guard_http_status=excluded.guard_http_status,auto_state=excluded.auto_state,auto_model=excluded.auto_model,
       auto_effort=excluded.auto_effort,auto_action=excluded.auto_action,auto_reason=excluded.auto_reason,auto_classification=excluded.auto_classification,
       auto_http_status=excluded.auto_http_status,attempts=excluded.attempts,error_code=excluded.error_code,reviewed_at=excluded.reviewed_at,
       guard_reviewed_at=excluded.guard_reviewed_at,auto_reviewed_at=excluded.auto_reviewed_at,
       guard_result_version=excluded.guard_result_version,auto_result_version=excluded.auto_result_version''',
      (job['region'], job['event_id'], job['source_path'], job['sha'], 'offline_analysis', review['state'], guard['state'], guard.get('decision'), guard.get('risk_level'),
       _json_field(guard.get('categories')), _json_field(guard.get('reason_codes')), guard.get('http_status'), auto['state'], auto.get('model'), auto.get('effort'), auto.get('action'),
       auto.get('reason'), json.dumps(auto.get('classification', {}), ensure_ascii=False, separators=(',', ':')), auto.get('http_status'), attempts, error, now.isoformat(),
       guard_reviewed_at, auto_reviewed_at, guard_result_version, auto_result_version))


def _region_config(config, region):
    """Resolve one region without ever falling back to another region's endpoint."""
    regions = config.get('regions')
    if regions is None:
        return config
    if not isinstance(regions, dict):
        return None
    override = regions.get(region)
    if not isinstance(override, dict):
        return None
    resolved = {key: value for key, value in config.items() if key != 'regions'}
    resolved.update(override)
    return resolved


def _pending_jobs(db, limit, max_attempts=DEFAULT_MAX_ATTEMPTS):
    """Select a bounded, region-fair slice of complete HTTP exchanges.

    The capture stream is commonly much busier in one region.  A single
    timestamp-ordered queue would let a slow Tokyo classifier keep the US
    queue invisible forever (and vice versa).  Give each region a small
    quota, interleave the rows, and give a bounded priority to jobs where one
    stage already succeeded.  Those jobs can reuse the fresh stage and only
    retry the failed Guard or Auto call.  Exhausted jobs are excluded here and
    moved to ``deferred`` by ``run`` before selection.
    """
    region_rows = db.execute("""SELECT j.region,MIN(j.at)
        FROM review_jobs j JOIN events e ON e.region=j.region AND e.id=j.event_id
        WHERE j.state='pending' AND e.kind='http_exchange'
        GROUP BY j.region ORDER BY MIN(j.at),j.region""").fetchall()
    regions = [row[0] for row in region_rows]
    if not regions:
        return []
    if len(regions) == 1:
        return db.execute("""SELECT j.region,j.event_id,j.source_path,j.sha,j.attempts
            FROM review_jobs j JOIN events e ON e.region=j.region AND e.id=j.event_id
            LEFT JOIN semantic_reviews s ON s.region=j.region AND s.event_id=j.event_id
            WHERE j.state='pending' AND j.attempts < ? AND e.kind='http_exchange'
            ORDER BY
              CASE
                WHEN j.attempts < ? AND s.state='unavailable'
                 AND ((s.guard_state='complete' AND s.auto_state='unavailable')
                   OR (s.guard_state='unavailable' AND s.auto_state='complete')) THEN 0
                WHEN s.state IS NULL THEN 1
                ELSE 2
              END,
              j.attempts,j.at,j.event_id LIMIT ?""", (max_attempts, max_attempts, limit)).fetchall()
    quota = max(1, (limit + len(regions) - 1) // len(regions))
    buckets = {}
    for region in regions:
        buckets[region] = list(db.execute("""SELECT j.region,j.event_id,j.source_path,j.sha,j.attempts
            FROM review_jobs j JOIN events e ON e.region=j.region AND e.id=j.event_id
            LEFT JOIN semantic_reviews s ON s.region=j.region AND s.event_id=j.event_id
            WHERE j.state='pending' AND j.attempts < ? AND e.kind='http_exchange' AND j.region=?
            ORDER BY
              CASE
                WHEN j.attempts < ? AND s.state='unavailable'
                 AND ((s.guard_state='complete' AND s.auto_state='unavailable')
                   OR (s.guard_state='unavailable' AND s.auto_state='complete')) THEN 0
                WHEN s.state IS NULL THEN 1
                ELSE 2
              END,
              j.attempts,j.at,j.event_id LIMIT ?""", (max_attempts, region, max_attempts, quota)).fetchall())
    selected = []
    while len(selected) < limit:
        progressed = False
        for region in regions:
            if buckets[region]:
                selected.append(buckets[region].pop(0))
                progressed = True
                if len(selected) >= limit:
                    break
        if not progressed:
            break
    return selected


def _defer_exhausted_jobs(db, max_attempts):
    """Stop retrying pending jobs once their bounded attempt budget is spent."""
    cursor = db.execute(
        """UPDATE review_jobs
           SET state='deferred',last_error='retry_limit_exceeded',claimed_at=NULL
         WHERE state='pending' AND attempts >= ?""",
        (max_attempts,),
    )
    return cursor.rowcount


def _unavailable_review(error='semantic_worker_exception'):
    """Build a body-free retryable result for an unexpected worker failure."""
    guard = {
        'state': 'unavailable', 'decision': None, 'risk_level': None,
        'categories': [], 'reason_codes': [], 'http_status': None,
        'error': error,
    }
    auto = {
        'state': 'unavailable', 'model': None, 'effort': None,
        'action': None, 'reason': None, 'classification': {},
        'http_status': None, 'error': error,
    }
    return {'guard': guard, 'auto': auto, 'state': 'unavailable'}


_PRIOR_REVIEW_COLUMNS = (
    'source_sha', 'guard_state', 'guard_decision', 'guard_risk_level',
    'guard_categories', 'guard_reason_codes', 'guard_http_status',
    'auto_state', 'auto_model', 'auto_effort', 'auto_action', 'auto_reason',
    'auto_classification', 'auto_http_status', 'guard_reviewed_at',
    'auto_reviewed_at', 'guard_result_version', 'auto_result_version',
)


def _load_prior_review(db, region, event_id):
    """Load only metadata needed for stage reuse; never load captured text."""
    row = db.execute('''SELECT source_sha,guard_state,guard_decision,guard_risk_level,
               guard_categories,guard_reason_codes,guard_http_status,auto_state,
               auto_model,auto_effort,auto_action,auto_reason,auto_classification,
               auto_http_status,guard_reviewed_at,auto_reviewed_at,
               guard_result_version,auto_result_version
            FROM semantic_reviews WHERE region=? AND event_id=?''', (region, event_id)).fetchone()
    if row is None:
        return None
    return dict(zip(_PRIOR_REVIEW_COLUMNS, row))


def _review_claimed_job(job, config, timeout, now=None):
    """Read and review one already-claimed job without touching SQLite.

    Threads only handle immutable source reads and private endpoint calls.  A
    compact result is returned to the caller, which performs every database
    write on its single SQLite connection in deterministic queue order.
    """
    region_config = _region_config(config, job['region'])
    if not region_config or not region_config.get('guard_url') or not region_config.get('auto_url'):
        return {'kind': 'unavailable', 'error': 'semantic_region_not_configured'}
    try:
        guard_headers = _auth_headers(region_config.get('guard_auth_file', ''), region_config.get('guard_auth_header', 'Authorization'))
        auto_headers = _auth_headers(region_config.get('auto_auth_file', ''), region_config.get('auto_auth_header', 'Authorization'))
    except (OSError, ValueError, TypeError):
        return {'kind': 'unavailable', 'error': 'semantic_auth_unavailable', 'auth_error': True}
    try:
        # Import lazily to preserve the standalone semantic module behavior
        # and avoid a module-level rolling/semantic import cycle.
        import rolling
        event, digest = rolling.read_record(Path(job['source_path']))
        if digest != job['sha'] or event.get('id') != job['event_id']:
            raise ValueError('source_changed')
    except (OSError, ValueError, KeyError, TypeError):
        return {'kind': 'failed', 'error': 'source_validation_failed'}
    try:
        review = review_event(
            event,
            region_config['guard_url'],
            region_config['auto_url'],
            timeout,
            guard_headers,
            auto_headers,
            prior=job.get('prior_review'),
            source_sha=job.get('sha', ''),
            now=now,
            stage_reuse_ttl_seconds=config.get('stage_reuse_ttl_seconds', DEFAULT_STAGE_REUSE_TTL_SECONDS),
        )
    except Exception:
        # Do not let an unexpected parser/client exception strand a claimed
        # row in ``running``.  The retryable result intentionally exposes only
        # a stable code, never an exception string that could quote source
        # text or credentials.
        review = _unavailable_review()
    if (not isinstance(review, dict) or review.get('state') not in ('complete', 'unavailable')
            or not isinstance(review.get('guard'), dict) or not isinstance(review.get('auto'), dict)):
        review = _unavailable_review('semantic_invalid_worker_result')
    return {'kind': 'review', 'review': review}


def run(db, config, now=None):
    """Process a small queue slice. Disabled/missing endpoints stay pending."""
    ensure_schema(db)
    config = config if isinstance(config, dict) else {}
    if not config.get('enabled'):
        pending = db.execute("SELECT COUNT(*) FROM review_jobs j JOIN events e ON e.region=j.region AND e.id=j.event_id WHERE j.state='pending' AND e.kind='http_exchange'").fetchone()[0]
        return {'status': 'disabled', 'processed': 0, 'pending': pending, 'complete': 0, 'unavailable': 0}
    if config.get('regions') is None and (not config.get('guard_url') or not config.get('auto_url')):
        pending = db.execute("SELECT COUNT(*) FROM review_jobs j JOIN events e ON e.region=j.region AND e.id=j.event_id WHERE j.state='pending' AND e.kind='http_exchange'").fetchone()[0]
        return {'status': 'pending_local_worker', 'processed': 0, 'pending': pending, 'complete': 0, 'unavailable': 0}
    timeout = min(max(float(config.get('timeout_seconds', 3)), 0.1), 30.0)
    limit = min(max(int(config.get('max_jobs', 20)), 1), 1000)
    try:
        stage_reuse_ttl = float(config.get('stage_reuse_ttl_seconds', DEFAULT_STAGE_REUSE_TTL_SECONDS))
    except (TypeError, ValueError):
        raise ValueError('invalid_stage_reuse_ttl')
    if not math.isfinite(stage_reuse_ttl) or not 0 <= stage_reuse_ttl <= MAX_STAGE_REUSE_TTL_SECONDS:
        raise ValueError('invalid_stage_reuse_ttl')
    try:
        max_attempts = int(config.get('max_attempts', DEFAULT_MAX_ATTEMPTS))
    except (TypeError, ValueError):
        raise ValueError('invalid_max_attempts')
    if not 1 <= max_attempts <= MAX_ATTEMPTS:
        raise ValueError('invalid_max_attempts')
    # Resolve the bounded concurrency before claiming rows.  A malformed
    # direct-call config therefore fails without leaving jobs in ``running``;
    # normal timer entry also validates this field in rolling.read_config.
    workers = min(max(int(config.get('max_workers', DEFAULT_MAX_WORKERS)), 1), MAX_WORKERS)
    now = now or datetime.now(timezone.utc)
    # A killed timer must not strand a queue item forever. The global rolling
    # lock prevents a concurrent worker, while this age check recovers a stale
    # claim from a previous process.
    stale_before = (now.timestamp() - max(timeout * 4, 60))
    stale_rows = db.execute("SELECT region,event_id,claimed_at FROM review_jobs WHERE state='running'").fetchall()
    for region, event_id, claimed_at in stale_rows:
        try:
            stale = datetime.fromisoformat(claimed_at).timestamp() < stale_before
        except (TypeError, ValueError):
            stale = True
        if stale:
            db.execute("UPDATE review_jobs SET state='pending',last_error='worker_restart',claimed_at=NULL WHERE region=? AND event_id=?", (region, event_id))
    deferred_before = _defer_exhausted_jobs(db, max_attempts)
    db.commit()
    selected_jobs = _pending_jobs(db, limit, max_attempts)
    # Claim the complete fair slice before starting threads.  The rolling
    # timer normally holds a process lock, but the conditional UPDATE keeps a
    # direct/concurrent caller from double-processing a row selected just
    # before another writer claimed it.
    jobs = []
    for row in selected_jobs:
        attempts = int(row[4] or 0) + 1
        cursor = db.execute(
            """UPDATE review_jobs SET state='running',attempts=?,claimed_at=?,last_error=NULL
               WHERE state='pending' AND region=? AND event_id=?""",
            (attempts, now.isoformat(), row[0], row[1]),
        )
        if cursor.rowcount:
            jobs.append({
                'region': row[0],
                'event_id': row[1],
                'source_path': row[2],
                'sha': row[3],
                'attempts': attempts,
                'prior_review': _load_prior_review(db, row[0], row[1]),
            })
    db.commit()
    counts = Counter()
    auth_error = None
    # The default is one worker, preserving historical ordering and endpoint
    # load.  An explicit bounded value enables job-level overlap while keeping
    # all SQLite work in this thread.
    outcomes = []
    if jobs:
        with ThreadPoolExecutor(max_workers=min(workers, len(jobs))) as pool:
            worker_config = dict(config)
            worker_config['stage_reuse_ttl_seconds'] = stage_reuse_ttl
            futures = [pool.submit(_review_claimed_job, job, worker_config, timeout, now) for job in jobs]
            # Reading futures in submission order keeps database writes and
            # counters deterministic even when endpoint calls finish out of
            # order.  The executor still overlaps the network calls.
            for job, future in zip(jobs, futures):
                try:
                    outcome = future.result()
                except Exception:
                    outcome = {'kind': 'review', 'review': _unavailable_review()}
                outcomes.append((job, outcome))

    for job, outcome in outcomes:
        region, event_id = job['region'], job['event_id']
        attempts = job['attempts']
        kind = outcome.get('kind')
        if kind == 'unavailable':
            error = outcome.get('error', 'semantic_unavailable')
            if attempts >= max_attempts:
                db.execute("UPDATE review_jobs SET state='deferred',last_error='retry_limit_exceeded',claimed_at=NULL WHERE region=? AND event_id=?", (region, event_id))
                counts['deferred'] += 1
            else:
                db.execute("UPDATE review_jobs SET state='pending',last_error=?,claimed_at=NULL WHERE region=? AND event_id=?", (error, region, event_id))
            counts['unavailable'] += 1
            if outcome.get('auth_error'):
                auth_error = 'semantic_auth_unavailable'
            db.commit()
            continue
        if kind == 'failed':
            db.execute("UPDATE review_jobs SET state='failed',last_error='source_validation_failed',claimed_at=NULL WHERE region=? AND event_id=?", (region, event_id))
            db.execute('''INSERT OR REPLACE INTO semantic_reviews
                (region,event_id,source_path,source_sha,plane,state,guard_state,auto_state,attempts,error_code,reviewed_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)''', (region, event_id, job['source_path'], job['sha'], 'offline_analysis', 'failed', 'not_run', 'not_run', attempts, 'source_validation_failed', now.isoformat()))
            counts['failed'] += 1
            db.commit()
            continue
        review = outcome.get('review') or _unavailable_review()
        _write_review(db, job, review, attempts, now)
        reused = review.get('_reused') if isinstance(review.get('_reused'), dict) else {}
        if reused.get('guard'):
            counts['guard_reused'] += 1
        if reused.get('auto'):
            counts['auto_reused'] += 1
        if review['state'] == 'complete':
            db.execute("UPDATE review_jobs SET state='complete',last_error=NULL,claimed_at=NULL WHERE region=? AND event_id=?", (region, event_id))
            counts['complete'] += 1
        else:
            error = review['guard'].get('error') or review['auto'].get('error') or 'semantic_unavailable'
            if attempts >= max_attempts:
                db.execute("UPDATE review_jobs SET state='deferred',last_error='retry_limit_exceeded',claimed_at=NULL WHERE region=? AND event_id=?", (region, event_id))
                counts['deferred'] += 1
            else:
                db.execute("UPDATE review_jobs SET state='pending',last_error=?,claimed_at=NULL WHERE region=? AND event_id=?", (str(error)[:128], region, event_id))
            counts['unavailable'] += 1
        db.commit()
    pending = db.execute("""SELECT COUNT(*) FROM review_jobs j JOIN events e
        ON e.region=j.region AND e.id=j.event_id
        WHERE j.state IN ('pending','running') AND e.kind='http_exchange'""").fetchone()[0]
    counts['deferred'] += deferred_before
    # Include jobs deferred before this batch in the public counters as well
    # as in the status calculation.  Otherwise the run ledger would report
    # zero deferred jobs even though the queue was just bounded.
    result = dict(counts)
    status = 'degraded_local' if counts['failed'] or counts['deferred'] else ('complete_local' if pending == 0 and jobs else ('pending_local_worker' if counts['unavailable'] or pending else 'idle'))
    result.update({'status': status,
                   'processed': len(jobs), 'pending': pending})
    if auth_error:
        result['auth_error'] = auth_error
    return result


def main():
    raise SystemExit('use rolling.py with semantic.enabled=true')


if __name__ == '__main__':
    main()
