import importlib.util
import pathlib
import unittest

spec = importlib.util.spec_from_file_location('ladder', pathlib.Path(__file__).with_name('live-routing-ladder.py'))
ladder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ladder)

class SSEAcceptanceTests(unittest.TestCase):
    def test_chat_requires_stop_and_done(self):
        data = b'data: {"id":"a","model":"m","choices":[{"delta":{"content":"hello"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n'
        self.assertEqual(ladder.decode_sse('chat', data)['choices'][0]['message']['content'], 'hello')
        self.assertEqual(ladder.decode_sse('chat', data.split(b'data: [DONE]')[0]), {})

    def test_responses_rejects_partial_or_failed(self):
        partial = b'data: {"type":"response.created","response":{"id":"a"}}\n\n'
        self.assertEqual(ladder.decode_sse('responses', partial), {})
        completed = b'data: {"type":"response.completed","response":{"id":"a","status":"completed"}}\n\n'
        self.assertEqual(ladder.decode_sse('responses', completed)['status'], 'completed')
        self.assertEqual(ladder.decode_sse('responses', completed + b'data: {"type":"response.failed"}\n\n'), {})

    def test_anthropic_retains_signature_and_requires_message_stop(self):
        data = b'data: {"type":"message_start","message":{"id":"a","model":"m"}}\n\ndata: {"type":"content_block_start","index":0,"content_block":{"type":"thinking","thinking":"","signature":""}}\n\ndata: {"type":"content_block_delta","index":0,"delta":{"type":"signature_delta","signature":"signed"}}\n\ndata: {"type":"message_delta","delta":{"stop_reason":"end_turn"}}\n\n'
        self.assertEqual(ladder.decode_sse('anthropic', data), {})
        completed = ladder.decode_sse('anthropic', data + b'data: {"type":"message_stop"}\n\n')
        self.assertEqual(completed['content'][0]['signature'], 'signed')
