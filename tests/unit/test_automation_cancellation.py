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
    cancel_workflow_run,
    workflow_input_hash,
)


class WorkflowCancellationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.store = WorkflowStore.open(Path(self._tmp.name) / "workflows.db")
        self.addCleanup(self.store.close)
        self.definition = WorkflowDefinition(
            workflow_id="wf-cancel",
            version=1,
            input_schema={},
            output_schema={},
            steps=(WorkflowStep(step_id="step", kind=WorkflowStepKind.AGENT),),
        )
        self.store.record_definition(self.definition)
        self.run = self.store.admit_run(
            WorkflowRun(
                run_id="run-cancel",
                workflow_id=self.definition.workflow_id,
                definition_hash=self.definition.definition_hash,
                input_hash=workflow_input_hash({}),
                status=WorkflowRunStatus.RUNNING,
            )
        )

    def test_cancels_run_and_active_attempts_within_bound(self) -> None:
        self.store.record_attempt(
            StepAttempt(
                attempt_id="attempt-active",
                run_id=self.run.run_id,
                step_id="step",
                idempotency_key="active",
                status=WorkflowStepStatus.WAITING_EXTERNAL,
            )
        )
        self.store.record_attempt(
            StepAttempt(
                attempt_id="attempt-done",
                run_id=self.run.run_id,
                step_id="step",
                idempotency_key="done",
                status=WorkflowStepStatus.SUCCEEDED,
            )
        )

        result = cancel_workflow_run(self.store, run_id=self.run.run_id, reason="stop", max_attempts=1)

        self.assertEqual(result.run_status, WorkflowRunStatus.CANCELLED)
        self.assertEqual(result.cancelled_attempt_ids, ("attempt-active",))
        self.assertEqual(self.store.get_run(self.run.run_id).status, WorkflowRunStatus.CANCELLED)
        self.assertEqual(self.store.get_attempt("attempt-active").status, WorkflowStepStatus.CANCELLED)
        self.assertEqual(self.store.get_attempt("attempt-done").status, WorkflowStepStatus.SUCCEEDED)

    def test_refuses_to_cancel_more_attempts_than_bound(self) -> None:
        for index in range(2):
            self.store.record_attempt(
                StepAttempt(
                    attempt_id=f"attempt-{index}",
                    run_id=self.run.run_id,
                    step_id="step",
                    idempotency_key=f"active-{index}",
                    status=WorkflowStepStatus.RUNNING,
                )
            )

        with self.assertRaises(WorkflowStoreError) as raised:
            cancel_workflow_run(self.store, run_id=self.run.run_id, reason="stop", max_attempts=1)

        self.assertEqual(raised.exception.code, "CANCELLATION_BOUND_EXCEEDED")
        self.assertEqual(self.store.get_run(self.run.run_id).status, WorkflowRunStatus.RUNNING)
        self.assertEqual(self.store.get_attempt("attempt-0").status, WorkflowStepStatus.RUNNING)

    def test_refuses_terminal_run(self) -> None:
        self.store.update_run_status(self.run.run_id, WorkflowRunStatus.SUCCEEDED)

        with self.assertRaises(WorkflowStoreError) as raised:
            cancel_workflow_run(self.store, run_id=self.run.run_id, reason="stop", max_attempts=0)

        self.assertEqual(raised.exception.code, "RUN_ALREADY_TERMINAL")


if __name__ == "__main__":
    unittest.main()
