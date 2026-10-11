"""Workflow agent-step executor backed by the native agent loop."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from forgeweave.core import NativeAgentLoop
from forgeweave.core.stop import StopReason
from forgeweave.policy import PolicyGateway
from forgeweave.tools import ToolRegistry

from .contracts import WorkflowStepKind, WorkflowStepStatus
from .executors import WorkflowExecutionContext, WorkflowExecutionResult, WorkflowExecutorError, WorkflowExecutorRegistry


@dataclass(frozen=True)
class NativeAgentWorkflowExecutorConfig:
    """Runtime bindings required to run one workflow agent step."""

    provider: Any
    registry: ToolRegistry
    policy: PolicyGateway
    workspace_precondition_hash: str
    task_id: str


def register_native_agent_workflow_executor(executors: WorkflowExecutorRegistry, config: NativeAgentWorkflowExecutorConfig) -> None:
    """Register a native-loop executor for WorkflowStepKind.AGENT."""

    executors.register(WorkflowStepKind.AGENT, lambda context: execute_native_agent_step(context, config))


def execute_native_agent_step(context: WorkflowExecutionContext, config: NativeAgentWorkflowExecutorConfig) -> WorkflowExecutionResult:
    """Run one native agent loop turn for a workflow agent step."""

    prompt = _prompt_for(context)
    loop = NativeAgentLoop(
        provider=config.provider,
        registry=config.registry,
        policy=config.policy,
        task_id=config.task_id,
        attempt_id=f"{context.run_id}:{context.step.step_id}:{context.attempt_number}",
        workspace_precondition_hash=config.workspace_precondition_hash,
    )
    result = loop.run_once(messages=[{"role": "user", "content": prompt}])
    output = {
        "text": result.text,
        "observations": result.observations,
        "stop_reason": result.stop_decision.reason.value,
        "should_stop": result.stop_decision.should_stop,
    }
    if result.stop_decision.reason is StopReason.WAITING_APPROVAL:
        return WorkflowExecutionResult(status=WorkflowStepStatus.WAITING_APPROVAL, reason="native agent loop is waiting for approval", output=output)
    if result.stop_decision.reason in {StopReason.FAILED, StopReason.CANCELLED, StopReason.BUDGET_EXCEEDED}:
        return WorkflowExecutionResult(status=WorkflowStepStatus.FAILED, reason=f"native agent loop stopped: {result.stop_decision.reason.value}", output=output)
    return WorkflowExecutionResult(status=WorkflowStepStatus.SUCCEEDED, reason=f"native agent loop completed with {result.stop_decision.reason.value}", output=output)


def _prompt_for(context: WorkflowExecutionContext) -> str:
    parameters = context.step.parameters or {}
    prompt = parameters.get("prompt") or parameters.get("objective")
    if not isinstance(prompt, str) or not prompt.strip():
        raise WorkflowExecutorError("INVALID_AGENT_STEP", "agent step requires a non-empty prompt or objective parameter")
    return prompt
