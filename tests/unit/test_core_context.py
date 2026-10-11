from __future__ import annotations

import unittest

from forgeweave.context import ContextBudget, ContextItem, ResolvedInstruction
from forgeweave.contracts import AcceptanceCriterion, ConstraintLedger
from forgeweave.core import NativeLoopContextBuilder, NativeLoopContextRequest


class NativeLoopContextBuilderTests(unittest.TestCase):
    def test_builds_loop_ready_context_model_input(self) -> None:
        request = NativeLoopContextRequest(
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
            latest_user_request="Build the next module.",
            constraint_ledger=ConstraintLedger(
                task_id="task-1",
                constraints=(
                    AcceptanceCriterion(
                        criterion_id="tests",
                        text="Focused and full tests must pass.",
                        origin="todo.md",
                        authority="repository",
                        validator="python -m unittest",
                    ),
                ),
            ),
            instructions=(
                ResolvedInstruction(
                    span_id="instruction:system",
                    source="AGENTS.md",
                    authority="repository",
                    text="Do not log secrets.",
                    source_hash="sha256:instruction",
                    precedence=10,
                    token_estimate=4,
                    sensitivity="normal",
                    protected=True,
                ),
            ),
            optional_items=(
                ContextItem(
                    item_id="recent",
                    source="event:turn-1",
                    authority="conversation",
                    text="Previous work summary.",
                    token_estimate=4,
                    priority=5,
                ),
            ),
            budget=ContextBudget(provider_context_window=100, output_reserve=10, tool_result_reserve=10, safety_margin=5),
            user_message="Continue implementation.",
        )

        model_input = NativeLoopContextBuilder().build(request)

        self.assertEqual(model_input.diagnostics_ref, "context-manifest://ctx-1")
        self.assertEqual(model_input.diagnostics.context_manifest.request_id, "ctx-1")
        self.assertEqual(model_input.messages[-1], {"role": "user", "content": "Continue implementation."})
        message_text = "\\n".join(message["content"] for message in model_input.messages)
        self.assertIn("Build the next module.", message_text)
        self.assertIn("Focused and full tests must pass.", message_text)
        self.assertIn("Do not log secrets.", message_text)
        self.assertIn("Previous work summary.", message_text)

    def test_defaults_user_message_to_latest_request(self) -> None:
        request = _minimal_request(user_message=None)

        model_input = NativeLoopContextBuilder().build(request)

        self.assertEqual(model_input.messages[-1], {"role": "user", "content": "Build the next module."})

    def test_rejects_mismatched_context_task_identity(self) -> None:
        request = _minimal_request(task_id="task-2")

        with self.assertRaises(ValueError):
            NativeLoopContextBuilder().build(request)


def _minimal_request(*, task_id: str = "task-1", user_message: str | None = "Continue.") -> NativeLoopContextRequest:
    return NativeLoopContextRequest(
        request_id="ctx-1",
        task_id=task_id,
        attempt_id="attempt-1",
        provider="fake",
        model="fake-model",
        adapter_version="adapter-v1",
        effective_policy_hash="sha256:policy",
        effective_config_hash="sha256:config",
        workspace_revision="sha256:workspace",
        catalog_version="tools-v1",
        latest_user_request="Build the next module.",
        constraint_ledger=ConstraintLedger(task_id="task-1"),
        instructions=(),
        optional_items=(),
        budget=ContextBudget(provider_context_window=50, output_reserve=10, tool_result_reserve=5, safety_margin=5),
        user_message=user_message,
    )


if __name__ == "__main__":
    unittest.main()

