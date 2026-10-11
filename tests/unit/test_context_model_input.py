from __future__ import annotations

import unittest

from forgeweave.context import ContextModelInput
from forgeweave.context.assembler import ContextPacket
from forgeweave.contracts import ContextManifest


class ContextModelInputTests(unittest.TestCase):
    def test_builds_ordered_model_messages_from_context_packet(self) -> None:
        model_input = ContextModelInput.from_packet(
            _packet(),
            user_message="Implement the next slice.",
        )

        self.assertEqual(
            model_input.messages,
            [
                {"role": "system", "content": "Context span latest-user-request from user:latest-request:\nBuild the feature."},
                {"role": "system", "content": "Context span recent-turn from event:turn-1:\nPrevious summary."},
                {"role": "user", "content": "Implement the next slice."},
            ],
        )
        self.assertEqual(model_input.diagnostics.context_manifest, _packet().manifest)
        self.assertEqual(model_input.diagnostics_ref, "context-manifest://ctx-1")

    def test_rejects_missing_span_text_in_packet(self) -> None:
        packet = ContextPacket(manifest=_manifest(), text_by_span_id={"latest-user-request": "Build the feature."})

        with self.assertRaises(ValueError):
            ContextModelInput.from_packet(packet, user_message="Implement")

    def test_rejects_blank_user_message(self) -> None:
        with self.assertRaises(ValueError):
            ContextModelInput.from_packet(_packet(), user_message=" ")


def _packet() -> ContextPacket:
    return ContextPacket(
        manifest=_manifest(),
        text_by_span_id={
            "latest-user-request": "Build the feature.",
            "recent-turn": "Previous summary.",
        },
    )


def _manifest() -> ContextManifest:
    from forgeweave.contracts import ContextSpan

    return ContextManifest(
        request_id="ctx-1",
        task_id="task-1",
        attempt_id="attempt-1",
        provider="fake",
        model="fake-model",
        adapter_version="adapter-v1",
        effective_policy_hash="sha256:policy",
        effective_config_hash="sha256:config",
        workspace_revision="sha256:workspace",
        catalog_version="tools-v1",
        spans=(
            ContextSpan(
                span_id="latest-user-request",
                source="user:latest-request",
                source_hash="sha256:latest",
                authority="task",
                sensitivity="normal",
                token_estimate=4,
            ),
            ContextSpan(
                span_id="recent-turn",
                source="event:turn-1",
                source_hash="sha256:turn",
                authority="conversation",
                sensitivity="normal",
                token_estimate=3,
            ),
        ),
        token_estimate=7,
    )


if __name__ == "__main__":
    unittest.main()
