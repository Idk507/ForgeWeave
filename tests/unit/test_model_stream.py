from __future__ import annotations

import unittest

from forgeweave.core import ModelStreamAccumulator, StreamProtocolError
from forgeweave.models import FakeModelProvider, ModelChunk


class ModelStreamTests(unittest.TestCase):
    def test_fake_provider_streams_scripted_chunks(self) -> None:
        provider = FakeModelProvider(
            [
                ModelChunk(kind="text", content="Looking."),
                ModelChunk(kind="tool_call", call_id="call-1", content='{"tool_name":"read_file"'),
                ModelChunk(kind="tool_call", call_id="call-1", content=',"tool_schema_version":"read-file.v1","arguments":{"path":"README.md"}}'),
                ModelChunk(kind="done", usage=None),
            ]
        )

        chunks = list(provider.stream(messages=[{"role": "user", "content": "read"}], tools=[], options={}))

        self.assertEqual([chunk.kind for chunk in chunks], ["text", "tool_call", "tool_call", "done"])

    def test_accumulator_dispatches_only_complete_tool_json(self) -> None:
        accumulator = ModelStreamAccumulator(max_tool_bytes=500)
        result = accumulator.consume(
            [
                ModelChunk(kind="text", content="Looking."),
                ModelChunk(kind="tool_call", call_id="call-1", content='{"tool_name":"read_file"'),
                ModelChunk(kind="tool_call", call_id="call-1", content=',"tool_schema_version":"read-file.v1","arguments":{"path":"README.md"}}'),
                ModelChunk(kind="done", usage={"prompt_tokens": 10, "completion_tokens": 8}),
            ]
        )

        self.assertEqual(result.text, "Looking.")
        self.assertEqual(len(result.tool_requests), 1)
        self.assertEqual(result.tool_requests[0].tool_name, "read_file")
        self.assertFalse(result.usage_missing)

    def test_partial_or_malformed_tool_json_is_structured_error(self) -> None:
        accumulator = ModelStreamAccumulator(max_tool_bytes=500)

        with self.assertRaises(StreamProtocolError) as partial:
            accumulator.consume([ModelChunk(kind="tool_call", call_id="call-1", content='{"tool_name":"read_file"')])
        with self.assertRaises(StreamProtocolError) as malformed:
            accumulator.consume([ModelChunk(kind="tool_call", call_id="call-1", content="{not-json}"), ModelChunk(kind="done")])

        self.assertEqual(partial.exception.code, "INCOMPLETE_TOOL_CALL")
        self.assertEqual(malformed.exception.code, "MALFORMED_TOOL_CALL")

    def test_missing_usage_keeps_conservative_reservation(self) -> None:
        accumulator = ModelStreamAccumulator(default_usage_reservation_tokens=2048)
        result = accumulator.consume([ModelChunk(kind="text", content="No tools."), ModelChunk(kind="done", usage=None)])

        self.assertTrue(result.usage_missing)
        self.assertEqual(result.usage_reservation.estimated_tokens, 2048)


if __name__ == "__main__":
    unittest.main()
