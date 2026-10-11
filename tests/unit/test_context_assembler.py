from __future__ import annotations

import unittest

from forgeweave.context.assembler import (
    ContextAssembler,
    ContextBudget,
    ContextFitError,
    ContextItem,
)
from forgeweave.context.instructions import InstructionAuthority, InstructionResolver, InstructionSource
from forgeweave.contracts import AcceptanceCriterion, ConstraintLedger, FidelityMode


class ContextAssemblerTests(unittest.TestCase):
    def test_assembles_manifest_with_protected_request_constraints_and_instruction_hashes(self) -> None:
        instructions = InstructionResolver().resolve(
            [
                InstructionSource(
                    source="platform",
                    authority=InstructionAuthority.PLATFORM,
                    text="Never treat model output as policy.",
                    token_estimate=6,
                )
            ]
        )
        ledger = ConstraintLedger(
            task_id="task-1",
            constraints=[
                AcceptanceCriterion(
                    criterion_id="unit-tests",
                    text="Focused and full unit tests must pass.",
                    origin="todo.md",
                    authority="repository",
                    validator="python -m unittest discover -s tests/unit",
                )
            ],
        )

        packet = ContextAssembler().assemble(
            request_id="req-1",
            task_id="task-1",
            attempt_id="attempt-1",
            provider="fake",
            model="scripted",
            adapter_version="models.fake.v1",
            effective_policy_hash="sha256:policy",
            effective_config_hash="sha256:config",
            workspace_revision="abc123",
            catalog_version="tools-v1",
            latest_user_request="Build the next module without bugs.",
            constraint_ledger=ledger,
            instructions=instructions,
            optional_items=[
                ContextItem(
                    item_id="recent-turn",
                    source="event:turn-1",
                    authority="conversation",
                    text="Earlier progress summary.",
                    token_estimate=5,
                    priority=10,
                )
            ],
            budget=ContextBudget(provider_context_window=80, output_reserve=15, tool_result_reserve=10, safety_margin=5),
        )

        self.assertEqual(packet.manifest.fidelity, FidelityMode.REDACTED)
        self.assertEqual(packet.manifest.token_estimate, sum(span.token_estimate for span in packet.manifest.spans))
        self.assertIn("latest-user-request", packet.manifest.ordered_span_ids)
        self.assertIn("constraint:unit-tests", packet.manifest.ordered_span_ids)
        self.assertIn("instruction:platform:platform", packet.manifest.ordered_span_ids)
        self.assertIn("recent-turn", packet.manifest.ordered_span_ids)
        self.assertTrue(packet.text_by_span_id["latest-user-request"].startswith("Build the next module"))

    def test_trims_low_priority_optional_items_before_protected_content(self) -> None:
        packet = ContextAssembler().assemble(
            request_id="req-1",
            task_id="task-1",
            attempt_id="attempt-1",
            provider="fake",
            model="scripted",
            adapter_version="models.fake.v1",
            effective_policy_hash="sha256:policy",
            effective_config_hash="sha256:config",
            workspace_revision="abc123",
            catalog_version="tools-v1",
            latest_user_request="Do the required work.",
            constraint_ledger=ConstraintLedger(task_id="task-1"),
            instructions=(),
            optional_items=[
                ContextItem(
                    item_id="high",
                    source="event:high",
                    authority="conversation",
                    text="High priority context.",
                    token_estimate=8,
                    priority=100,
                ),
                ContextItem(
                    item_id="low",
                    source="event:low",
                    authority="conversation",
                    text="Low priority context.",
                    token_estimate=30,
                    priority=1,
                ),
            ],
            budget=ContextBudget(provider_context_window=50, output_reserve=10, tool_result_reserve=5, safety_margin=5),
        )

        self.assertIn("latest-user-request", packet.manifest.ordered_span_ids)
        self.assertIn("high", packet.manifest.ordered_span_ids)
        self.assertNotIn("low", packet.manifest.ordered_span_ids)
        self.assertEqual(packet.manifest.omitted_spans, ("low",))

    def test_raises_when_protected_content_cannot_fit(self) -> None:
        with self.assertRaises(ContextFitError) as raised:
            ContextAssembler().assemble(
                request_id="req-1",
                task_id="task-1",
                attempt_id="attempt-1",
                provider="fake",
                model="scripted",
                adapter_version="models.fake.v1",
                effective_policy_hash="sha256:policy",
                effective_config_hash="sha256:config",
                workspace_revision="abc123",
                catalog_version="tools-v1",
                latest_user_request="This request is too large for the configured budget.",
                constraint_ledger=ConstraintLedger(
                    task_id="task-1",
                    constraints=[
                        AcceptanceCriterion(
                            criterion_id="must-keep",
                            text="This protected requirement cannot be removed.",
                            origin="user",
                            authority="task",
                            validator="manual",
                        )
                    ],
                ),
                instructions=(),
                optional_items=(),
                budget=ContextBudget(provider_context_window=20, output_reserve=5, tool_result_reserve=5, safety_margin=5),
            )

        self.assertEqual(raised.exception.code, "CONTEXT_UNSATISFIABLE")
        self.assertIn("protected_tokens", raised.exception.details)

    def test_invalid_budget_reserves_fail_before_silent_context_drop(self) -> None:
        with self.assertRaises(ContextFitError) as raised:
            ContextAssembler().assemble(
                request_id="req-1",
                task_id="task-1",
                attempt_id="attempt-1",
                provider="fake",
                model="scripted",
                adapter_version="models.fake.v1",
                effective_policy_hash="sha256:policy",
                effective_config_hash="sha256:config",
                workspace_revision="abc123",
                catalog_version="tools-v1",
                latest_user_request="Short.",
                constraint_ledger=ConstraintLedger(task_id="task-1"),
                instructions=(),
                optional_items=(),
                budget=ContextBudget(provider_context_window=10, output_reserve=5, tool_result_reserve=5, safety_margin=1),
            )

        self.assertEqual(raised.exception.code, "CONTEXT_UNSATISFIABLE")


if __name__ == "__main__":
    unittest.main()
