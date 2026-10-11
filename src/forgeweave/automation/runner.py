"""Safe workflow runner foundation.

This module only advances persisted workflow state. It does not dispatch agents,
tools, shell commands, browser actions, network requests or publication effects.
"""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import StepAttempt, WorkflowRunStatus, WorkflowStep, WorkflowStepKind, WorkflowStepStatus
from .planner import StepState, plan_workflow
from .store import WorkflowStore


@dataclass(frozen=True)
class WorkflowRunnerStep:
    """One step decision made by the safe runner foundation."""

    step_id: str
    attempt_id: str
    status: WorkflowStepStatus
    reason: str


@dataclass(frozen=True)
class WorkflowRunnerResult:
    """Persisted result of one bounded workflow runner tick."""

    run_id: str
    run_status: WorkflowRunStatus
    ready_before: tuple[str, ...]
    recorded_steps: tuple[WorkflowRunnerStep, ...]
    execution_started: bool = False


def run_workflow_once(store: WorkflowStore, *, run_id: str, max_ready_steps: int | None = None) -> WorkflowRunnerResult:
    """Advance ready workflow steps into persisted attempts without executing effects."""

    run = store.get_run(run_id)
    definition = store.get_definition(run.definition_hash)
    attempts = store.list_attempts(run_id)
    step_by_id = {step.step_id: step for step in definition.steps}
    latest = _latest_attempts(attempts)
    counts = _attempt_counts(attempts)
    states = _retry_aware_states(step_by_id, latest, counts)
    plan = plan_workflow(definition, states)
    if run.status is WorkflowRunStatus.PENDING and (plan.ready or plan.active):
        run = store.update_run_status(run_id, WorkflowRunStatus.RUNNING)
    elif run.status in {WorkflowRunStatus.FAILED, WorkflowRunStatus.CANCELLED, WorkflowRunStatus.SUCCEEDED}:
        return WorkflowRunnerResult(run_id=run.run_id, run_status=run.status, ready_before=plan.ready, recorded_steps=())

    ready = plan.ready if max_ready_steps is None else plan.ready[:max_ready_steps]
    recorded: list[WorkflowRunnerStep] = []
    for step_id in ready:
        step = step_by_id[step_id]
        status, reason = _safe_status_for_step(step, attempt_count=counts.get(step_id, 0))
        attempt_id = _attempt_id(run_id, step_id, attempts)
        attempt = store.record_attempt(
            StepAttempt(
                attempt_id=attempt_id,
                run_id=run_id,
                step_id=step_id,
                idempotency_key=f"{run_id}:{step_id}:{attempt_id}",
                status=status,
            )
        )
        recorded.append(WorkflowRunnerStep(step_id=step_id, attempt_id=attempt.attempt_id, status=attempt.status, reason=reason))

    if not recorded and plan.done and not plan.failed:
        run = store.update_run_status(run_id, WorkflowRunStatus.SUCCEEDED)
    elif plan.failed:
        run = store.update_run_status(run_id, WorkflowRunStatus.FAILED)
    else:
        run = store.get_run(run_id)

    return WorkflowRunnerResult(run_id=run.run_id, run_status=run.status, ready_before=plan.ready, recorded_steps=tuple(recorded))


def _latest_attempts(attempts: tuple[StepAttempt, ...]) -> dict[str, StepAttempt]:
    latest: dict[str, StepAttempt] = {}
    for attempt in attempts:
        latest[attempt.step_id] = attempt
    return latest


def _attempt_counts(attempts: tuple[StepAttempt, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for attempt in attempts:
        counts[attempt.step_id] = counts.get(attempt.step_id, 0) + 1
    return counts


def _retry_aware_states(
    step_by_id: dict[str, WorkflowStep],
    latest: dict[str, StepAttempt],
    counts: dict[str, int],
) -> tuple[StepState, ...]:
    states: list[StepState] = []
    for step_id, attempt in latest.items():
        step = step_by_id[step_id]
        if attempt.status in {WorkflowStepStatus.FAILED, WorkflowStepStatus.CANCELLED} and counts.get(step_id, 0) < step.max_attempts:
            continue
        states.append(StepState(step_id=step_id, status=attempt.status))
    return tuple(states)


def _safe_status_for_step(step: WorkflowStep, *, attempt_count: int) -> tuple[WorkflowStepStatus, str]:
    if step.kind is WorkflowStepKind.JOIN:
        return WorkflowStepStatus.SUCCEEDED, "join satisfied by persisted dependency state"
    if step.kind is WorkflowStepKind.APPROVAL:
        return WorkflowStepStatus.WAITING_APPROVAL, "approval step requires an external approval boundary"
    if attempt_count:
        return WorkflowStepStatus.WAITING_EXTERNAL, f"retry {attempt_count + 1} is deferred until a mediated executor is available"
    return WorkflowStepStatus.WAITING_EXTERNAL, f"{step.kind.value} execution is deferred until a mediated executor is available"


def _attempt_id(run_id: str, step_id: str, attempts: tuple[StepAttempt, ...]) -> str:
    count = sum(1 for attempt in attempts if attempt.step_id == step_id) + 1
    return f"{run_id}-{step_id}-{count}"
