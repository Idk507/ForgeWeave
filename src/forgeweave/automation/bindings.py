"""Workflow run binding guards for resume and execution."""

from __future__ import annotations

from dataclasses import dataclass

from .store import WorkflowStore, WorkflowStoreError


@dataclass(frozen=True)
class WorkflowRunBindingCheck:
    """Evidence that a workflow run still matches its admitted immutable inputs."""

    run_id: str
    definition_hash: str
    input_hash: str


def require_run_bindings(
    store: WorkflowStore,
    *,
    run_id: str,
    expected_definition_hash: str | None = None,
    expected_input_hash: str | None = None,
) -> WorkflowRunBindingCheck:
    """Raise when supplied definition/input hashes differ from the admitted run."""

    run = store.get_run(run_id)
    if expected_definition_hash is not None and run.definition_hash != expected_definition_hash:
        raise WorkflowStoreError(
            "DEFINITION_CHANGED",
            f"workflow run {run_id} was admitted with definition {run.definition_hash}, not {expected_definition_hash}",
        )
    if expected_input_hash is not None and run.input_hash != expected_input_hash:
        raise WorkflowStoreError(
            "INPUT_CHANGED",
            f"workflow run {run_id} was admitted with input {run.input_hash}, not {expected_input_hash}",
        )
    return WorkflowRunBindingCheck(run_id=run.run_id, definition_hash=run.definition_hash, input_hash=run.input_hash)
