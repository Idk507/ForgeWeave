"""Read-only workflow planning over definitions and persisted attempts."""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import WorkflowDefinition, WorkflowStep, WorkflowStepStatus


_TERMINAL_SUCCESS = {WorkflowStepStatus.SUCCEEDED, WorkflowStepStatus.SKIPPED}
_TERMINAL_FAILURE = {WorkflowStepStatus.FAILED, WorkflowStepStatus.CANCELLED}
_ACTIVE = {WorkflowStepStatus.READY, WorkflowStepStatus.RUNNING, WorkflowStepStatus.WAITING_APPROVAL, WorkflowStepStatus.WAITING_EXTERNAL}


@dataclass(frozen=True)
class WorkflowPlan:
    """Read-only scheduling projection for one workflow run."""

    ready: tuple[str, ...]
    waiting: tuple[str, ...]
    active: tuple[str, ...]
    completed: tuple[str, ...]
    failed: tuple[str, ...]

    @property
    def done(self) -> bool:
        """Return true when no more workflow progress can be scheduled."""

        return not self.ready and not self.waiting and not self.active


@dataclass(frozen=True)
class StepState:
    """Latest observed status for a workflow step."""

    step_id: str
    status: WorkflowStepStatus


def plan_workflow(definition: WorkflowDefinition, states: tuple[StepState, ...] = ()) -> WorkflowPlan:
    """Compute ready and blocked steps without executing side effects."""

    latest = {state.step_id: state.status for state in states}
    known = {step.step_id for step in definition.steps}
    unknown = set(latest) - known
    if unknown:
        raise ValueError(f"states reference unknown workflow steps: {sorted(unknown)}")

    ready: list[str] = []
    waiting: list[str] = []
    active: list[str] = []
    completed: list[str] = []
    failed: list[str] = []

    for step in definition.steps:
        status = latest.get(step.step_id, WorkflowStepStatus.PENDING)
        if status in _TERMINAL_SUCCESS:
            completed.append(step.step_id)
            continue
        if status in _TERMINAL_FAILURE:
            failed.append(step.step_id)
            continue
        if status in _ACTIVE:
            active.append(step.step_id)
            continue
        if _dependencies_succeeded(step, latest):
            ready.append(step.step_id)
        else:
            waiting.append(step.step_id)

    return WorkflowPlan(
        ready=tuple(ready),
        waiting=tuple(waiting),
        active=tuple(active),
        completed=tuple(completed),
        failed=tuple(failed),
    )


def _dependencies_succeeded(step: WorkflowStep, latest: dict[str, WorkflowStepStatus]) -> bool:
    return all(latest.get(dependency) in _TERMINAL_SUCCESS for dependency in step.depends_on)
