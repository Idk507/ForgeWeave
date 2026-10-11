from __future__ import annotations

import unittest

from forgeweave.automation import (
    JoinMode,
    JoinPolicy,
    StepState,
    WorkflowDefinition,
    WorkflowStep,
    WorkflowStepKind,
    WorkflowStepStatus,
    plan_workflow,
)


class WorkflowPlannerTests(unittest.TestCase):
    def test_initial_plan_marks_roots_ready_and_dependents_waiting(self) -> None:
        plan = plan_workflow(_definition())

        self.assertEqual(plan.ready, ("research",))
        self.assertEqual(plan.waiting, ("plan", "test", "join"))
        self.assertEqual(plan.active, ())
        self.assertEqual(plan.completed, ())
        self.assertFalse(plan.done)

    def test_completed_dependency_releases_next_step(self) -> None:
        plan = plan_workflow(_definition(), (StepState("research", WorkflowStepStatus.SUCCEEDED),))

        self.assertEqual(plan.ready, ("plan",))
        self.assertEqual(plan.waiting, ("test", "join"))
        self.assertEqual(plan.completed, ("research",))

    def test_active_and_failed_steps_are_not_rescheduled(self) -> None:
        plan = plan_workflow(
            _definition(),
            (
                StepState("research", WorkflowStepStatus.SUCCEEDED),
                StepState("plan", WorkflowStepStatus.RUNNING),
                StepState("test", WorkflowStepStatus.FAILED),
            ),
        )

        self.assertEqual(plan.ready, ())
        self.assertEqual(plan.active, ("plan",))
        self.assertEqual(plan.failed, ("test",))
        self.assertEqual(plan.waiting, ("join",))

    def test_all_terminal_success_is_done(self) -> None:
        plan = plan_workflow(
            _definition(),
            (
                StepState("research", WorkflowStepStatus.SUCCEEDED),
                StepState("plan", WorkflowStepStatus.SUCCEEDED),
                StepState("test", WorkflowStepStatus.SUCCEEDED),
                StepState("join", WorkflowStepStatus.SUCCEEDED),
            ),
        )

        self.assertTrue(plan.done)
        self.assertEqual(plan.completed, ("research", "plan", "test", "join"))

    def test_unknown_step_state_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            plan_workflow(_definition(), (StepState("missing", WorkflowStepStatus.SUCCEEDED),))


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
