"""Workflow status projection for CLI/SDK inspection."""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import WorkflowRun, WorkflowStepStatus
from .planner import StepState, WorkflowPlan, plan_workflow
from .store import WorkflowStore


@dataclass(frozen=True)
class WorkflowStepView:
    """Inspectable status for one workflow step."""

    step_id: str
    status: WorkflowStepStatus
    latest_attempt_id: str | None
    attempt_count: int


@dataclass(frozen=True)
class WorkflowStatusView:
    """Inspectable workflow run projection without executing steps."""

    run: WorkflowRun
    ready: tuple[str, ...]
    waiting: tuple[str, ...]
    active: tuple[str, ...]
    completed: tuple[str, ...]
    failed: tuple[str, ...]
    steps: tuple[WorkflowStepView, ...]

    @property
    def done(self) -> bool:
        """Return true when the underlying planner has no pending progress."""

        return not self.ready and not self.waiting and not self.active


def workflow_status_view(store: WorkflowStore, *, run_id: str) -> WorkflowStatusView:
    """Build a read-only workflow status projection from persisted state."""

    run = store.get_run(run_id)
    definition = store.get_definition(run.definition_hash)
    attempts = store.list_attempts(run_id)
    latest_by_step: dict[str, object] = {}
    counts: dict[str, int] = {}
    for attempt in attempts:
        counts[attempt.step_id] = counts.get(attempt.step_id, 0) + 1
        latest_by_step[attempt.step_id] = attempt

    states = tuple(
        StepState(step_id=step_id, status=attempt.status)
        for step_id, attempt in latest_by_step.items()
    )
    plan = plan_workflow(definition, states)
    return WorkflowStatusView(
        run=run,
        ready=plan.ready,
        waiting=plan.waiting,
        active=plan.active,
        completed=plan.completed,
        failed=plan.failed,
        steps=tuple(_step_view(step_id=step.step_id, latest=latest_by_step.get(step.step_id), count=counts.get(step.step_id, 0), plan=plan) for step in definition.steps),
    )


def _step_view(*, step_id: str, latest: object | None, count: int, plan: WorkflowPlan) -> WorkflowStepView:
    if latest is not None:
        return WorkflowStepView(
            step_id=step_id,
            status=latest.status,  # type: ignore[attr-defined]
            latest_attempt_id=latest.attempt_id,  # type: ignore[attr-defined]
            attempt_count=count,
        )
    if step_id in plan.ready:
        status = WorkflowStepStatus.READY
    else:
        status = WorkflowStepStatus.PENDING
    return WorkflowStepView(step_id=step_id, status=status, latest_attempt_id=None, attempt_count=0)
