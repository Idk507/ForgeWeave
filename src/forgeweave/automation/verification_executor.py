"""Workflow verification-step executor."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from forgeweave.verify import run_selected_verification

from .contracts import WorkflowStepKind, WorkflowStepStatus
from .executors import WorkflowExecutionContext, WorkflowExecutionResult, WorkflowExecutorError, WorkflowExecutorRegistry


@dataclass(frozen=True)
class VerificationWorkflowExecutorConfig:
    """Default verification execution settings for workflow verification steps."""

    repo_root: Path
    output_dir: Path
    environment_profile_hash: str = "sha256:local"
    timeout_seconds: int = 60
    output_cap_bytes: int = 64_000
    task_id: str = "workflow-verification"


def register_verification_workflow_executor(executors: WorkflowExecutorRegistry, config: VerificationWorkflowExecutorConfig) -> None:
    """Register an executor for WorkflowStepKind.VERIFICATION."""

    executors.register(WorkflowStepKind.VERIFICATION, lambda context: execute_verification_step(context, config))


def execute_verification_step(context: WorkflowExecutionContext, config: VerificationWorkflowExecutorConfig) -> WorkflowExecutionResult:
    """Run selected repository verification for one workflow verification step."""

    parameters = context.step.parameters or {}
    repo_root = _path_parameter(parameters, "repo_root", default=config.repo_root)
    output_dir = _path_parameter(parameters, "output_dir", default=config.output_dir)
    timeout_seconds = _int_parameter(parameters, "timeout_seconds", default=config.timeout_seconds)
    output_cap_bytes = _int_parameter(parameters, "output_cap_bytes", default=config.output_cap_bytes)
    environment_profile_hash = _string_parameter(parameters, "environment_profile_hash", default=config.environment_profile_hash)
    task_id = _string_parameter(parameters, "task_id", default=config.task_id)

    run = run_selected_verification(
        task_id=task_id,
        repo_root=repo_root,
        output_dir=output_dir,
        environment_profile_hash=environment_profile_hash,
        timeout_seconds=timeout_seconds,
        output_cap_bytes=output_cap_bytes,
    )
    output = {
        "command_count": len(run.results),
        "failed_count": len(run.failed_results),
        "config_hash": run.selection.config_hash,
        "sources": list(run.selection.sources),
        "results": [
            {
                "run_id": result.run.run_id,
                "criterion_ids": list(result.run.criterion_ids),
                "outcome": result.run.outcome,
                "exit_code": result.run.exit_code,
                "output_artifact_id": result.run.output_artifact_id,
            }
            for result in run.results
        ],
    }
    if run.passed:
        return WorkflowExecutionResult(status=WorkflowStepStatus.SUCCEEDED, reason="verification passed", output=output)
    return WorkflowExecutionResult(status=WorkflowStepStatus.FAILED, reason="verification failed or no checks were selected", output=output)


def _path_parameter(parameters: dict[str, Any], name: str, *, default: Path) -> Path:
    value = parameters.get(name)
    if value is None:
        return default
    if not isinstance(value, str) or not value.strip():
        raise WorkflowExecutorError("INVALID_VERIFICATION_STEP", f"{name} must be a non-empty string path")
    return Path(value)


def _int_parameter(parameters: dict[str, Any], name: str, *, default: int) -> int:
    value = parameters.get(name, default)
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise WorkflowExecutorError("INVALID_VERIFICATION_STEP", f"{name} must be an integer >= 1")
    return value


def _string_parameter(parameters: dict[str, Any], name: str, *, default: str) -> str:
    value = parameters.get(name, default)
    if not isinstance(value, str) or not value.strip():
        raise WorkflowExecutorError("INVALID_VERIFICATION_STEP", f"{name} must be a non-empty string")
    return value
