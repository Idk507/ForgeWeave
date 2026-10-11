"""Tool execution event recording and restart reconciliation helpers."""

from __future__ import annotations

from uuid import uuid4

from forgeweave.contracts import (
    ActorKind,
    Event,
    EventKind,
    PolicyDecision,
    PolicyOutcome,
    ToolCall,
    ToolExecution,
    ToolExecutionState,
    ToolFailure,
    ToolResult,
)

from .store import EventStore


class ToolExecutionRecorder:
    """Record tool-call intent and outcomes without dispatching tools."""

    def __init__(self, store: EventStore) -> None:
        self._store = store

    def record_requested(self, *, task_id: str, attempt_id: str, call: ToolCall) -> ToolExecution:
        """Append ToolCallRequested before any caller dispatches the tool."""

        execution = ToolExecution(
            execution_id=call.call_id,
            task_id=task_id,
            attempt_id=attempt_id,
            tool_name=call.tool_name,
            state=ToolExecutionState.REQUESTED,
            effect_hash=call.effect_hash,
            idempotency_key=_idempotency_key(task_id=task_id, attempt_id=attempt_id, call=call),
        )
        self._store.append(
            _event(
                task_id=task_id,
                attempt_id=attempt_id,
                actor=ActorKind.MODEL,
                kind=EventKind.TOOL_CALL_REQUESTED,
                correlation_id=call.call_id,
                payload_ref=f"tool-call://{call.call_id}",
            )
        )
        return self._store.record_tool_execution(execution)

    def record_policy_decision(self, decision: PolicyDecision) -> ToolExecution:
        """Append a policy decision before an allowed call can dispatch."""

        execution = self._store.get_tool_execution(decision.tool_call_id)
        if execution.task_id != decision.task_id or execution.attempt_id != decision.attempt_id:
            raise ValueError("policy decision does not match requested execution")

        self._store.append(
            _event(
                task_id=decision.task_id,
                attempt_id=decision.attempt_id,
                actor=ActorKind.POLICY,
                kind=EventKind.POLICY_DECISION,
                correlation_id=decision.tool_call_id,
                payload_ref=f"policy-decision://{decision.decision_id}",
            )
        )
        next_state = ToolExecutionState.AUTHORIZED if decision.outcome is PolicyOutcome.ALLOW else ToolExecutionState.CANCELLED
        return self._store.record_tool_execution(execution.model_copy(update={"state": next_state}))

    def mark_dispatching(self, execution_id: str) -> ToolExecution:
        """Mark an authorized execution as being handed to a tool implementation."""

        execution = self._store.get_tool_execution(execution_id)
        if execution.state is not ToolExecutionState.AUTHORIZED:
            raise ValueError("only authorized tool executions can dispatch")
        return self._store.record_tool_execution(execution.model_copy(update={"state": ToolExecutionState.DISPATCHING}))

    def record_result(self, result: ToolResult) -> ToolExecution:
        """Append ToolResult after the tool reports a successful outcome."""

        execution = self._store.get_tool_execution(result.call_id)
        self._require_dispatched(execution)
        self._store.append(
            _event(
                task_id=execution.task_id,
                attempt_id=execution.attempt_id,
                actor=ActorKind.TOOL,
                kind=EventKind.TOOL_RESULT,
                correlation_id=result.call_id,
                payload_ref=f"tool-result://{result.call_id}",
            )
        )
        return self._store.record_tool_execution(execution.model_copy(update={"state": ToolExecutionState.SUCCEEDED}))

    def record_failure(self, failure: ToolFailure) -> ToolExecution:
        """Append ToolFailure after the tool reports a bounded failure."""

        execution = self._store.get_tool_execution(failure.call_id)
        self._require_dispatched(execution)
        self._store.append(
            _event(
                task_id=execution.task_id,
                attempt_id=execution.attempt_id,
                actor=ActorKind.TOOL,
                kind=EventKind.TOOL_FAILURE,
                correlation_id=failure.call_id,
                payload_ref=f"tool-failure://{failure.call_id}",
            )
        )
        return self._store.record_tool_execution(execution.model_copy(update={"state": ToolExecutionState.FAILED}))

    def mark_outcome_unknown(self, execution_id: str, *, reconciliation_evidence: str) -> ToolExecution:
        """Park an ambiguous dispatched call for human or subsystem reconciliation."""

        if not reconciliation_evidence.strip():
            raise ValueError("OUTCOME_UNKNOWN requires reconciliation evidence")
        execution = self._store.get_tool_execution(execution_id)
        self._require_dispatched(execution)
        return self._store.record_tool_execution(
            execution.model_copy(
                update={
                    "state": ToolExecutionState.OUTCOME_UNKNOWN,
                    "reconciliation_evidence": reconciliation_evidence,
                }
            )
        )

    def reconciliation_required(self) -> list[ToolExecution]:
        """Return executions that must be resolved before retrying side effects."""

        return self._store.list_tool_executions(state=ToolExecutionState.OUTCOME_UNKNOWN)

    @staticmethod
    def _require_dispatched(execution: ToolExecution) -> None:
        if execution.state is not ToolExecutionState.DISPATCHING:
            raise ValueError("tool outcome can only be recorded after dispatch starts")


def _event(
    *,
    task_id: str,
    attempt_id: str,
    actor: ActorKind,
    kind: EventKind,
    correlation_id: str,
    payload_ref: str,
) -> Event:
    return Event(
        event_id=f"evt-{uuid4()}",
        task_id=task_id,
        attempt_id=attempt_id,
        sequence=1,
        actor=actor,
        kind=kind,
        correlation_id=correlation_id,
        payload_ref=payload_ref,
    )


def _idempotency_key(*, task_id: str, attempt_id: str, call: ToolCall) -> str:
    return f"{task_id}:{attempt_id}:{call.call_id}:{call.argument_hash}:{call.effect_hash}"
