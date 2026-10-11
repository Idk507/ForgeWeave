from __future__ import annotations

import unittest

from forgeweave.automation import (
    JoinMode,
    JoinPolicy,
    StepAttempt,
    WorkflowDefinition,
    WorkflowRun,
    WorkflowStep,
    WorkflowStepKind,
    WorkflowStepStatus,
    WorkflowValidationError,
    workflow_input_hash,
)


class WorkflowContractTests(unittest.TestCase):
    def test_valid_workflow_definition_has_stable_hash(self) -> None:
        definition = _valid_definition()
        same = _valid_definition()

        self.assertTrue(definition.definition_hash.startswith("sha256:"))
        self.assertEqual(definition.definition_hash, same.definition_hash)

    def test_rejects_duplicate_step_ids(self) -> None:
        with self.assertRaises(WorkflowValidationError) as raised:
            WorkflowDefinition(
                workflow_id="wf",
                version=1,
                input_schema={"type": "object"},
                output_schema={"type": "object"},
                steps=(
                    WorkflowStep(step_id="a", kind=WorkflowStepKind.TOOL),
                    WorkflowStep(step_id="a", kind=WorkflowStepKind.VERIFICATION),
                ),
            )

        self.assertEqual(raised.exception.code, "DUPLICATE_STEP")

    def test_rejects_unknown_dependency(self) -> None:
        with self.assertRaises(WorkflowValidationError) as raised:
            WorkflowDefinition(
                workflow_id="wf",
                version=1,
                input_schema={"type": "object"},
                output_schema={"type": "object"},
                steps=(WorkflowStep(step_id="b", kind=WorkflowStepKind.TOOL, depends_on=("missing",)),),
            )

        self.assertEqual(raised.exception.code, "UNKNOWN_DEPENDENCY")

    def test_rejects_dependency_cycle(self) -> None:
        with self.assertRaises(WorkflowValidationError) as raised:
            WorkflowDefinition(
                workflow_id="wf",
                version=1,
                input_schema={"type": "object"},
                output_schema={"type": "object"},
                steps=(
                    WorkflowStep(step_id="a", kind=WorkflowStepKind.TOOL, depends_on=("b",)),
                    WorkflowStep(step_id="b", kind=WorkflowStepKind.TOOL, depends_on=("a",)),
                ),
            )

        self.assertEqual(raised.exception.code, "CYCLE")

    def test_join_policy_validates_quorum_bounds(self) -> None:
        with self.assertRaises(WorkflowValidationError) as raised:
            WorkflowDefinition(
                workflow_id="wf",
                version=1,
                input_schema={"type": "object"},
                output_schema={"type": "object"},
                steps=(
                    WorkflowStep(step_id="a", kind=WorkflowStepKind.TOOL),
                    WorkflowStep(step_id="join", kind=WorkflowStepKind.JOIN, depends_on=("a",), join_policy=JoinPolicy(mode=JoinMode.QUORUM, quorum=2)),
                ),
            )

        self.assertEqual(raised.exception.code, "INVALID_QUORUM")

    def test_run_and_attempt_bind_definition_input_and_idempotency(self) -> None:
        definition = _valid_definition()
        input_hash = workflow_input_hash({"issue": 123})
        run = WorkflowRun(run_id="run-1", workflow_id=definition.workflow_id, definition_hash=definition.definition_hash, input_hash=input_hash)
        attempt = StepAttempt(attempt_id="attempt-1", run_id=run.run_id, step_id="test", idempotency_key="run-1:test:1", lease_token="lease-1", status=WorkflowStepStatus.RUNNING)

        self.assertEqual(run.definition_hash, definition.definition_hash)
        self.assertEqual(attempt.idempotency_key, "run-1:test:1")
        self.assertEqual(attempt.status, WorkflowStepStatus.RUNNING)


def _valid_definition() -> WorkflowDefinition:
    return WorkflowDefinition(
        workflow_id="research-plan-test",
        version=1,
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        steps=(
            WorkflowStep(step_id="research", kind=WorkflowStepKind.AGENT, capability="research"),
            WorkflowStep(step_id="plan", kind=WorkflowStepKind.AGENT, capability="plan", depends_on=("research",)),
            WorkflowStep(step_id="test", kind=WorkflowStepKind.VERIFICATION, depends_on=("plan",), max_attempts=2),
            WorkflowStep(
                step_id="join",
                kind=WorkflowStepKind.JOIN,
                depends_on=("research", "plan", "test"),
                join_policy=JoinPolicy(mode=JoinMode.ALL_SETTLED),
            ),
        ),
    )


if __name__ == "__main__":
    unittest.main()
