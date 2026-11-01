from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from forgeweave.automation import (
    StepAttempt,
    WorkflowDefinition,
    WorkflowRun,
    WorkflowRunStatus,
    WorkflowStep,
    WorkflowStepKind,
    WorkflowStepStatus,
    WorkflowStore,
    WorkflowStoreError,
    approve_workflow_step,
    cancel_workflow_step_approval,
    reject_workflow_step,
    run_workflow_once,
    workflow_input_hash,
)


class WorkflowApprovalTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.store = WorkflowStore.open(Path(self._tmp.name) / "workflows.db")
        self.addCleanup(self.store.close)

    def test_runner_pauses_run_when_approval_step_is_ready(self) -> None:
        run = self._admit(_approval_definition())
        self.store.record_attempt(_attempt(run.run_id, "prepare", WorkflowStepStatus.SUCCEEDED))

        result = run_workflow_once(self.store, run_id=run.run_id)

        attempts = self.store.list_attempts(run.run_id)
        self.assertEqual(result.run_status, WorkflowRunStatus.WAITING_APPROVAL)
        self.assertEqual(result.recorded_steps[0].step_id, "approve")
        self.assertEqual(result.recorded_steps[0].status, WorkflowStepStatus.WAITING_APPROVAL)
        approval_attempt = next(attempt for attempt in attempts if attempt.step_id == "approve")
        self.assertEqual(approval_attempt.status, WorkflowStepStatus.WAITING_APPROVAL)

    def test_approve_waiting_step_resumes_run_and_allows_next_step(self) -> None:
        run = self._admit(_approval_definition())
        self.store.record_attempt(_attempt(run.run_id, "prepare", WorkflowStepStatus.SUCCEEDED))
        run_workflow_once(self.store, run_id=run.run_id)

        approval = approve_workflow_step(self.store, run_id=run.run_id, step_id="approve", reason="human approved")
        next_tick = run_workflow_once(self.store, run_id=run.run_id)

        self.assertEqual(approval.step_status, WorkflowStepStatus.SUCCEEDED)
        self.assertEqual(approval.run_status, WorkflowRunStatus.RUNNING)
        self.assertEqual(next_tick.ready_before, ("verify",))
        self.assertEqual(next_tick.recorded_steps[0].step_id, "verify")

    def test_reject_waiting_step_fails_run(self) -> None:
        run = self._admit(_approval_definition())
        self.store.record_attempt(_attempt(run.run_id, "prepare", WorkflowStepStatus.SUCCEEDED))
        run_workflow_once(self.store, run_id=run.run_id)

        result = reject_workflow_step(self.store, run_id=run.run_id, step_id="approve", reason="unsafe")

        self.assertEqual(result.step_status, WorkflowStepStatus.FAILED)
        self.assertEqual(result.run_status, WorkflowRunStatus.FAILED)
        self.assertEqual(self.store.get_run(run.run_id).status, WorkflowRunStatus.FAILED)

    def test_cancel_waiting_step_cancels_run(self) -> None:
        run = self._admit(_approval_definition())
        self.store.record_attempt(_attempt(run.run_id, "prepare", WorkflowStepStatus.SUCCEEDED))
        run_workflow_once(self.store, run_id=run.run_id)

        result = cancel_workflow_step_approval(self.store, run_id=run.run_id, step_id="approve", reason="user cancelled")

        self.assertEqual(result.step_status, WorkflowStepStatus.CANCELLED)
        self.assertEqual(result.run_status, WorkflowRunStatus.CANCELLED)

    def test_approval_rejects_non_waiting_or_non_approval_steps(self) -> None:
        run = self._admit(_approval_definition())
        self.store.record_attempt(_attempt(run.run_id, "prepare", WorkflowStepStatus.SUCCEEDED))

        with self.assertRaises(WorkflowStoreError) as non_approval:
            approve_workflow_step(self.store, run_id=run.run_id, step_id="prepare")
        self.assertEqual(non_approval.exception.code, "NOT_APPROVAL_STEP")

        self.store.record_attempt(_attempt(run.run_id, "approve", WorkflowStepStatus.SUCCEEDED))
        with self.assertRaises(WorkflowStoreError) as not_waiting:
            approve_workflow_step(self.store, run_id=run.run_id, step_id="approve")
        self.assertEqual(not_waiting.exception.code, "APPROVAL_NOT_WAITING")

    def _admit(self, definition: WorkflowDefinition) -> WorkflowRun:
        self.store.record_definition(definition)
        return self.store.admit_run(
            WorkflowRun(
                run_id="run-approval",
                workflow_id=definition.workflow_id,
                definition_hash=definition.definition_hash,
                input_hash=workflow_input_hash({}),
            )
        )


def _approval_definition() -> WorkflowDefinition:
    return WorkflowDefinition(
        workflow_id="wf-approval",
        version=1,
        input_schema={},
        output_schema={},
        steps=(
            WorkflowStep(step_id="prepare", kind=WorkflowStepKind.AGENT),
            WorkflowStep(step_id="approve", kind=WorkflowStepKind.APPROVAL, depends_on=("prepare",)),
            WorkflowStep(step_id="verify", kind=WorkflowStepKind.VERIFICATION, depends_on=("approve",)),
        ),
    )


def _attempt(run_id: str, step_id: str, status: WorkflowStepStatus) -> StepAttempt:
    return StepAttempt(
        attempt_id=f"{run_id}-{step_id}-seed",
        run_id=run_id,
        step_id=step_id,
        idempotency_key=f"{run_id}:{step_id}:seed",
        status=status,
    )


if __name__ == "__main__":
    unittest.main()
