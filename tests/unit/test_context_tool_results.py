from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from forgeweave.context import ToolResultProjector
from forgeweave.events import ArtifactStore


class ToolResultProjectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.artifacts = ArtifactStore(self.root / "artifacts")

    def test_small_tool_result_stays_inline_without_artifact(self) -> None:
        projector = ToolResultProjector(artifact_store=self.artifacts, inline_cap_bytes=100)

        item = projector.project_text_result(task_id="task-1", call_id="call-1", tool_name="read_file", text="short output")

        self.assertEqual(item.item_id, "tool-result:call-1")
        self.assertIn("short output", item.text)
        self.assertNotIn("artifact://", item.text)
        self.assertFalse(item.redacted)

    def test_large_tool_result_is_capped_with_artifact_pointer(self) -> None:
        projector = ToolResultProjector(artifact_store=self.artifacts, inline_cap_bytes=12)

        item = projector.project_text_result(task_id="task-1", call_id="call-1", tool_name="run_tests", text="0123456789abcdef")

        self.assertIn("0123456789ab", item.text)
        self.assertIn("truncated", item.text)
        self.assertIn("artifact://task-1/", item.text)
        self.assertIn("sha256:", item.text)
        self.assertTrue(item.redacted)

    def test_rehydrate_artifact_restores_full_output(self) -> None:
        projector = ToolResultProjector(artifact_store=self.artifacts, inline_cap_bytes=4)
        item = projector.project_text_result(task_id="task-1", call_id="call-1", tool_name="shell", text="abcdef")
        uri = next(part for part in item.text.split() if part.startswith("artifact://"))

        restored = projector.rehydrate_text(uri)

        self.assertEqual(restored, "abcdef")


if __name__ == "__main__":
    unittest.main()
