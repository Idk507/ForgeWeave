"""Workflow step executors backed by ForgeWeave tools and policy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from forgeweave.contracts import PolicyOutcome
from forgeweave.policy import PolicyGateway
from forgeweave.tools import ToolRegistry

from .contracts import WorkflowStepKind, WorkflowStepStatus
from .executors import WorkflowExecutionContext, WorkflowExecutionResult, WorkflowExecutorError, WorkflowExecutorRegistry


@dataclass(frozen=True)
class ToolWorkflowExecutorConfig:
    """Runtime bindings required to mediate workflow tool steps."""

    registry: ToolRegistry
    policy: PolicyGateway
    workspace_precondition_hash: str
    task_id: str


def register_tool_workflow_executor(executors: WorkflowExecutorRegistry, config: ToolWorkflowExecutorConfig) -> None:
    """Register a policy-mediated executor for WorkflowStepKind.TOOL."""

    executors.register(WorkflowStepKind.TOOL, lambda context: execute_tool_step(context, config))


def execute_tool_step(context: WorkflowExecutionContext, config: ToolWorkflowExecutorConfig) -> WorkflowExecutionResult:
    """Execute one workflow tool step through registry validation and policy mediation."""

    parameters = context.step.parameters or {}
    tool_name = _required_string(parameters, "tool_name")
    schema_version = _required_string(parameters, "tool_schema_version")
    arguments = parameters.get("arguments", {})
    if not isinstance(arguments, dict):
        raise WorkflowExecutorError("INVALID_TOOL_ARGUMENTS", "tool step arguments must be an object")

    call = config.registry.build_call(tool_name=tool_name, tool_schema_version=schema_version, arguments=arguments)
    attempt_id = f"{context.run_id}:{context.step.step_id}:{context.attempt_number}"
    decision = config.policy.authorize(
        task_id=config.task_id,
        attempt_id=attempt_id,
        call=call,
        workspace_precondition_hash=config.workspace_precondition_hash,
        catalog_version=config.registry.catalog_version,
    )
    if decision.outcome is PolicyOutcome.ASK:
        return WorkflowExecutionResult(
            status=WorkflowStepStatus.WAITING_APPROVAL,
            reason=f"approval required for tool {tool_name}: {decision.reason}",
            output={"policy_decision_id": decision.decision_id, "tool_call_id": call.call_id},
        )
    if decision.outcome is PolicyOutcome.DENY:
        return WorkflowExecutionResult(
            status=WorkflowStepStatus.FAILED,
            reason=f"policy denied tool {tool_name}: {decision.reason}",
            output={"policy_decision_id": decision.decision_id, "tool_call_id": call.call_id},
        )

    config.policy.revalidate_for_dispatch(
        decision=decision,
        call=call,
        workspace_precondition_hash=config.workspace_precondition_hash,
    )
    output = config.registry.dispatch(call)
    return WorkflowExecutionResult(
        status=WorkflowStepStatus.SUCCEEDED,
        reason=f"tool {tool_name} completed through policy gateway",
        output={"policy_decision_id": decision.decision_id, "tool_call_id": call.call_id, "output": output},
    )


def _required_string(parameters: dict[str, Any], name: str) -> str:
    value = parameters.get(name)
    if not isinstance(value, str) or not value.strip():
        raise WorkflowExecutorError("INVALID_TOOL_STEP", f"tool step parameter {name} must be a non-empty string")
    return value
