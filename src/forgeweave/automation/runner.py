"""Safe workflow runner foundation.

This module only advances persisted workflow state. It does not dispatch agents,
tools, shell commands, browser actions, network requests or publication effects.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .artifacts import artifact_records_from_output, validate_artifact_bindings
from .contracts import StepAttempt, WorkflowRunStatus, WorkflowStep, WorkflowStepKind, WorkflowStepStatus
from .executors import WorkflowExecutionContext, WorkflowExecutionResult, WorkflowExecutorRegistry
from .idempotency import workflow_attempt_identity
from .planner import StepState, plan_workflow
from .store import WorkflowStore
from .worker_leases import workflow_worker_lease_token


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


def run_workflow_once(
    store: WorkflowStore,
    *,
    run_id: str,
    max_ready_steps: int | None = None,
    executors: WorkflowExecutorRegistry | None = None,
    lease_token_factory: Callable[[str, str, int], str | None] | None = None,
    worker_id: str | None = None,
) -> WorkflowRunnerResult:
    """Advance ready workflow steps into persisted attempts without executing effects."""

    run = store.get_run(run_id)
    definition = store.get_definition(run.definition_hash)
    attempts = store.list_attempts(run_id)
    step_by_id = {step.step_id: step for step in definition.steps}
    latest = _latest_attempts(attempts)
    counts = _attempt_counts(attempts)
    states = _retry_aware_states(step_by_id, latest, counts)
    plan = plan_workflow(definition, states)
    if run.status in {WorkflowRunStatus.PENDING, WorkflowRunStatus.WAITING_EXTERNAL} and (plan.ready or plan.active):
        run = store.update_run_status(run_id, WorkflowRunStatus.RUNNING)
    elif run.status in {WorkflowRunStatus.FAILED, WorkflowRunStatus.CANCELLED, WorkflowRunStatus.SUCCEEDED}:
        return WorkflowRunnerResult(run_id=run.run_id, run_status=run.status, ready_before=plan.ready, recorded_steps=())

    ready = plan.ready if max_ready_steps is None else plan.ready[:max_ready_steps]
    recorded: list[WorkflowRunnerStep] = []
    for step_id in ready:
        step = step_by_id[step_id]
        attempt_count = counts.get(step_id, 0)
        status, reason, execution_result = _safe_status_for_step(
            step,
            run_id=run_id,
            workflow_id=definition.workflow_id,
            attempt_count=attempt_count,
            executors=executors,
        )
        attempt_number = attempt_count + 1
        identity = workflow_attempt_identity(run_id=run_id, step_id=step_id, attempt_number=attempt_number)
        lease_token = _lease_token_for_attempt(
            run_id=run_id,
            step_id=step_id,
            attempt_number=attempt_number,
            lease_token_factory=lease_token_factory,
            worker_id=worker_id,
        )
        attempt = store.record_attempt(
            StepAttempt(
                attempt_id=identity.attempt_id,
                run_id=run_id,
                step_id=step_id,
                idempotency_key=identity.idempotency_key,
                lease_token=lease_token,
                worker_id=worker_id,
                status=status,
            )
        )
        if execution_result is not None and attempt.status is WorkflowStepStatus.SUCCEEDED:
            for artifact in artifact_records_from_output(
                run_id=run_id,
                step_id=step_id,
                attempt_id=attempt.attempt_id,
                output=execution_result.output,
            ):
                store.record_artifact(artifact)
        recorded.append(WorkflowRunnerStep(step_id=step_id, attempt_id=attempt.attempt_id, status=attempt.status, reason=reason))

    if any(step.status is WorkflowStepStatus.WAITING_APPROVAL for step in recorded):
        run = store.update_run_status(run_id, WorkflowRunStatus.WAITING_APPROVAL)
    elif not recorded and plan.done and not plan.failed:
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


def _safe_status_for_step(
    step: WorkflowStep,
    *,
    run_id: str,
    workflow_id: str,
    attempt_count: int,
    executors: WorkflowExecutorRegistry | None,
) -> tuple[WorkflowStepStatus, str, WorkflowExecutionResult | None]:
    if step.kind is WorkflowStepKind.JOIN:
        return WorkflowStepStatus.SUCCEEDED, "join satisfied by persisted dependency state", None
    if step.kind is WorkflowStepKind.APPROVAL:
        return WorkflowStepStatus.WAITING_APPROVAL, "approval step requires an external approval boundary", None
    if executors is not None:
        result = executors.execute(
            WorkflowExecutionContext(
                run_id=run_id,
                workflow_id=workflow_id,
                step=step,
                attempt_number=attempt_count + 1,
            )
        )
        if result.status is WorkflowStepStatus.SUCCEEDED:
            artifacts = validate_artifact_bindings(step, result.output)
            if not artifacts.valid:
                return WorkflowStepStatus.FAILED, artifacts.reason, result
        return result.status, result.reason, result
    if attempt_count:
        return WorkflowStepStatus.WAITING_EXTERNAL, f"retry {attempt_count + 1} is deferred until a mediated executor is available", None
    return WorkflowStepStatus.WAITING_EXTERNAL, f"{step.kind.value} execution is deferred until a mediated executor is available", None



def _lease_token_for_attempt(
    *,
    run_id: str,
    step_id: str,
    attempt_number: int,
    lease_token_factory: Callable[[str, str, int], str | None] | None,
    worker_id: str | None,
) -> str | None:
    if lease_token_factory is not None:
        return lease_token_factory(run_id, step_id, attempt_number)
    if worker_id is not None:
        return workflow_worker_lease_token(worker_id=worker_id, run_id=run_id, step_id=step_id, attempt_number=attempt_number)
    return None
