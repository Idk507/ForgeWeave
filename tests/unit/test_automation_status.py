from __future__ import annotations

from pathlib import Path
import tempfile
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
    WorkflowStore,
    workflow_input_hash,
    workflow_status_view,
)


class WorkflowStatusTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.store = WorkflowStore.open(self.root / "workflows.db")
        self.addCleanup(self.store.close)
        self.definition = _definition()
        self.store.record_definition(self.definition)
        self.run = self.store.admit_run(
            WorkflowRun(
                run_id="run-1",
                workflow_id=self.definition.workflow_id,
                definition_hash=self.definition.definition_hash,
                input_hash=workflow_input_hash({"issue": 1}),
            )
        )

    def test_status_marks_root_ready_before_attempts(self) -> None:
        view = workflow_status_view(self.store, run_id=self.run.run_id)

        self.assertEqual(view.ready, ("research",))
        self.assertEqual(view.waiting, ("plan", "test", "join"))
        self.assertEqual(view.steps[0].step_id, "research")
        self.assertEqual(view.steps[0].status, WorkflowStepStatus.READY)
        self.assertEqual(view.steps[0].attempt_count, 0)
        self.assertFalse(view.done)

    def test_status_uses_latest_attempt_state_and_counts_attempts(self) -> None:
        self.store.record_attempt(StepAttempt(attempt_id="attempt-1", run_id=self.run.run_id, step_id="research", idempotency_key="research:1", status=WorkflowStepStatus.FAILED))
        self.store.record_attempt(StepAttempt(attempt_id="attempt-2", run_id=self.run.run_id, step_id="research", idempotency_key="research:2", status=WorkflowStepStatus.SUCCEEDED))
        self.store.record_attempt(StepAttempt(attempt_id="attempt-3", run_id=self.run.run_id, step_id="plan", idempotency_key="plan:1", status=WorkflowStepStatus.RUNNING))

        view = workflow_status_view(self.store, run_id=self.run.run_id)

        research = next(step for step in view.steps if step.step_id == "research")
        plan = next(step for step in view.steps if step.step_id == "plan")
        self.assertEqual(research.status, WorkflowStepStatus.SUCCEEDED)
        self.assertEqual(research.latest_attempt_id, "attempt-2")
        self.assertEqual(research.attempt_count, 2)
        self.assertEqual(plan.status, WorkflowStepStatus.RUNNING)
        self.assertEqual(view.active, ("plan",))
        self.assertEqual(view.ready, ())

    def test_status_reports_done_when_all_steps_succeeded(self) -> None:
        for index, step_id in enumerate(("research", "plan", "test", "join"), start=1):
            self.store.record_attempt(
                StepAttempt(
                    attempt_id=f"attempt-{index}",
                    run_id=self.run.run_id,
                    step_id=step_id,
                    idempotency_key=f"{step_id}:1",
                    status=WorkflowStepStatus.SUCCEEDED,
                )
            )

        view = workflow_status_view(self.store, run_id=self.run.run_id)

        self.assertTrue(view.done)
        self.assertEqual(view.completed, ("research", "plan", "test", "join"))


def _definition() -> WorkflowDefinition:
    return WorkflowDefinition(
        workflow_id="wf",
        version=1,
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        steps=(
            WorkflowStep(step_id="research", kind=WorkflowStepKind.AGENT),
            WorkflowStep(step_id="plan", kind=WorkflowStepKind.AGENT, depends_on=("research",)),
            WorkflowStep(step_id="test", kind=WorkflowStepKind.VERIFICATION, depends_on=("plan",)),
            WorkflowStep(step_id="join", kind=WorkflowStepKind.JOIN, depends_on=("research", "plan", "test"), join_policy=JoinPolicy(mode=JoinMode.ALL_SUCCESS)),
        ),
    )


if __name__ == "__main__":
    unittest.main()
