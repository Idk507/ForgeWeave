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
    JoinMode,
    JoinPolicy,
    run_workflow_once,
    recover_workflow_after_restart,
    workflow_input_hash,
)


class WorkflowRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.store = WorkflowStore.open(Path(self._tmp.name) / "workflows.db")
        self.addCleanup(self.store.close)
        definition = WorkflowDefinition(
            workflow_id="wf-recovery",
            version=1,
            input_schema={},
            output_schema={},
            steps=(WorkflowStep(step_id="step", kind=WorkflowStepKind.AGENT),),
        )
        self.store.record_definition(definition)
        self.run = self.store.admit_run(
            WorkflowRun(
                run_id="run-recovery",
                workflow_id=definition.workflow_id,
                definition_hash=definition.definition_hash,
                input_hash=workflow_input_hash({}),
                status=WorkflowRunStatus.RUNNING,
            )
        )

    def test_marks_running_attempt_waiting_external_after_restart(self) -> None:
        self.store.record_attempt(
            StepAttempt(
                attempt_id="attempt-running",
                run_id=self.run.run_id,
                step_id="step",
                idempotency_key="running",
                status=WorkflowStepStatus.RUNNING,
            )
        )

        result = recover_workflow_after_restart(self.store, run_id=self.run.run_id, max_attempts=1)

        self.assertEqual(result.run_status, WorkflowRunStatus.WAITING_EXTERNAL)
        self.assertEqual(result.attentions[0].attempt_id, "attempt-running")
        self.assertEqual(result.attentions[0].previous_status, WorkflowStepStatus.RUNNING)
        self.assertEqual(result.attentions[0].recovered_status, WorkflowStepStatus.WAITING_EXTERNAL)
        self.assertEqual(self.store.get_attempt("attempt-running").status, WorkflowStepStatus.WAITING_EXTERNAL)

    def test_inspect_only_reports_without_mutating(self) -> None:
        self.store.record_attempt(
            StepAttempt(
                attempt_id="attempt-running",
                run_id=self.run.run_id,
                step_id="step",
                idempotency_key="running",
                status=WorkflowStepStatus.RUNNING,
            )
        )

        result = recover_workflow_after_restart(self.store, run_id=self.run.run_id, max_attempts=1, mark_waiting_external=False)

        self.assertEqual(result.run_status, WorkflowRunStatus.RUNNING)
        self.assertEqual(result.attentions[0].recovered_status, WorkflowStepStatus.RUNNING)
        self.assertEqual(self.store.get_attempt("attempt-running").status, WorkflowStepStatus.RUNNING)


    def test_resumed_join_after_recovered_dependency_succeeds(self) -> None:
        definition = WorkflowDefinition(
            workflow_id="wf-recovered-join",
            version=1,
            input_schema={},
            output_schema={},
            steps=(
                WorkflowStep(step_id="research", kind=WorkflowStepKind.AGENT),
                WorkflowStep(step_id="implement", kind=WorkflowStepKind.AGENT),
                WorkflowStep(
                    step_id="join",
                    kind=WorkflowStepKind.JOIN,
                    depends_on=("research", "implement"),
                    join_policy=JoinPolicy(mode=JoinMode.ALL_SUCCESS),
                ),
            ),
        )
        self.store.record_definition(definition)
        run = self.store.admit_run(
            WorkflowRun(
                run_id="run-join",
                workflow_id=definition.workflow_id,
                definition_hash=definition.definition_hash,
                input_hash=workflow_input_hash({}),
                status=WorkflowRunStatus.RUNNING,
            )
        )
        self.store.record_attempt(
            StepAttempt(
                attempt_id="attempt-research",
                run_id=run.run_id,
                step_id="research",
                idempotency_key="research",
                status=WorkflowStepStatus.SUCCEEDED,
            )
        )
        self.store.record_attempt(
            StepAttempt(
                attempt_id="attempt-implement",
                run_id=run.run_id,
                step_id="implement",
                idempotency_key="implement",
                status=WorkflowStepStatus.RUNNING,
            )
        )
        recover_workflow_after_restart(self.store, run_id=run.run_id, max_attempts=1)
        self.store.update_attempt_status("attempt-implement", WorkflowStepStatus.SUCCEEDED)

        result = run_workflow_once(self.store, run_id=run.run_id)

        self.assertEqual(result.run_status, WorkflowRunStatus.RUNNING)
        self.assertEqual(result.ready_before, ("join",))
        self.assertEqual(result.recorded_steps[0].step_id, "join")
        self.assertEqual(result.recorded_steps[0].status, WorkflowStepStatus.SUCCEEDED)
        self.assertEqual(self.store.get_run(run.run_id).status, WorkflowRunStatus.RUNNING)

    def test_refuses_recovery_over_bound(self) -> None:
        for index in range(2):
            self.store.record_attempt(
                StepAttempt(
                    attempt_id=f"attempt-{index}",
                    run_id=self.run.run_id,
                    step_id="step",
                    idempotency_key=f"running-{index}",
                    status=WorkflowStepStatus.RUNNING,
                )
            )

        with self.assertRaises(WorkflowStoreError) as raised:
            recover_workflow_after_restart(self.store, run_id=self.run.run_id, max_attempts=1)

        self.assertEqual(raised.exception.code, "RECOVERY_BOUND_EXCEEDED")


if __name__ == "__main__":
    unittest.main()
