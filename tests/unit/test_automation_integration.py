from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from forgeweave.automation import (
    JoinMode,
    JoinPolicy,
    WorkflowDefinition,
    WorkflowExecutionContext,
    WorkflowExecutionResult,
    WorkflowExecutorRegistry,
    WorkflowRun,
    WorkflowRunStatus,
    WorkflowStep,
    WorkflowStepKind,
    WorkflowStepStatus,
    WorkflowStore,
    approve_workflow_step,
    run_workflow_once,
    workflow_input_hash,
    workflow_worker_lease_token,
)


class WorkflowIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.store = WorkflowStore.open(Path(self._tmp.name) / "workflows.db")
        self.addCleanup(self.store.close)

    def test_persisted_coding_workflow_reaches_success_with_artifacts_approval_verification_and_join(self) -> None:
        definition = _coding_workflow_definition()
        self.store.record_definition(definition)
        run = self.store.admit_run(
            WorkflowRun(
                run_id="run-integration-1",
                workflow_id=definition.workflow_id,
                definition_hash=definition.definition_hash,
                input_hash=workflow_input_hash({"issue": "fix parser regression"}),
            )
        )
        executors = _workflow_executors()

        implement = run_workflow_once(self.store, run_id=run.run_id, executors=executors, worker_id="worker-a")
        approval = run_workflow_once(self.store, run_id=run.run_id, executors=executors, worker_id="worker-a")
        approved = approve_workflow_step(self.store, run_id=run.run_id, step_id="approve", reason="human reviewed patch")
        verify = run_workflow_once(self.store, run_id=run.run_id, executors=executors, worker_id="worker-a")
        join = run_workflow_once(self.store, run_id=run.run_id, executors=executors, worker_id="worker-a")
        completed = run_workflow_once(self.store, run_id=run.run_id, executors=executors, worker_id="worker-a")

        attempts = self.store.list_attempts(run.run_id)
        attempt_by_step = {attempt.step_id: attempt for attempt in attempts}
        artifacts = self.store.list_artifacts(run_id=run.run_id)
        artifact_names = {artifact.name for artifact in artifacts}

        self.assertEqual(implement.ready_before, ("implement",))
        self.assertEqual(implement.recorded_steps[0].status, WorkflowStepStatus.SUCCEEDED)
        self.assertEqual(approval.ready_before, ("approve",))
        self.assertEqual(approval.run_status, WorkflowRunStatus.WAITING_APPROVAL)
        self.assertEqual(approval.recorded_steps[0].status, WorkflowStepStatus.WAITING_APPROVAL)
        self.assertEqual(approved.run_status, WorkflowRunStatus.RUNNING)
        self.assertEqual(verify.ready_before, ("verify",))
        self.assertEqual(verify.recorded_steps[0].status, WorkflowStepStatus.SUCCEEDED)
        self.assertEqual(join.ready_before, ("join",))
        self.assertEqual(join.recorded_steps[0].status, WorkflowStepStatus.SUCCEEDED)
        self.assertEqual(completed.run_status, WorkflowRunStatus.SUCCEEDED)
        self.assertEqual(completed.recorded_steps, ())
        self.assertEqual(self.store.get_run(run.run_id).status, WorkflowRunStatus.SUCCEEDED)
        self.assertEqual(
            {step_id: attempt.status for step_id, attempt in attempt_by_step.items()},
            {
                "implement": WorkflowStepStatus.SUCCEEDED,
                "approve": WorkflowStepStatus.SUCCEEDED,
                "verify": WorkflowStepStatus.SUCCEEDED,
                "join": WorkflowStepStatus.SUCCEEDED,
            },
        )
        self.assertEqual(attempt_by_step["implement"].worker_id, "worker-a")
        self.assertEqual(
            attempt_by_step["implement"].lease_token,
            workflow_worker_lease_token(worker_id="worker-a", run_id=run.run_id, step_id="implement", attempt_number=1),
        )
        self.assertEqual(artifact_names, {"patch", "verification"})
        self.assertEqual(len(attempts), 4)


def _coding_workflow_definition() -> WorkflowDefinition:
    return WorkflowDefinition(
        workflow_id="coding-workflow",
        version=1,
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        steps=(
            WorkflowStep(step_id="implement", kind=WorkflowStepKind.AGENT, parameters={"artifacts": ["patch"]}),
            WorkflowStep(step_id="approve", kind=WorkflowStepKind.APPROVAL, depends_on=("implement",)),
            WorkflowStep(step_id="verify", kind=WorkflowStepKind.VERIFICATION, depends_on=("approve",), parameters={"artifacts": ["verification"]}),
            WorkflowStep(
                step_id="join",
                kind=WorkflowStepKind.JOIN,
                depends_on=("implement", "approve", "verify"),
                join_policy=JoinPolicy(mode=JoinMode.ALL_SUCCESS),
            ),
        ),
    )


def _workflow_executors() -> WorkflowExecutorRegistry:
    executors = WorkflowExecutorRegistry()

    def implement(context: WorkflowExecutionContext) -> WorkflowExecutionResult:
        return WorkflowExecutionResult(
            status=WorkflowStepStatus.SUCCEEDED,
            reason=f"patch produced on attempt {context.attempt_number}",
            output={"artifacts": {"patch": {"uri": "artifact://patch-1", "sha256": "abc123"}}},
        )

    def verify(context: WorkflowExecutionContext) -> WorkflowExecutionResult:
        return WorkflowExecutionResult(
            status=WorkflowStepStatus.SUCCEEDED,
            reason=f"verification passed on attempt {context.attempt_number}",
            output={"artifacts": {"verification": {"uri": "artifact://verification-1", "sha256": "def456"}}},
        )

    executors.register(WorkflowStepKind.AGENT, implement)
    executors.register(WorkflowStepKind.VERIFICATION, verify)
    return executors


if __name__ == "__main__":
    unittest.main()
