"""Bounded fake-provider stream assembly and a minimal native loop."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import TYPE_CHECKING, Any, Callable, Iterable, Protocol

from forgeweave.contracts import BudgetReservation, PolicyDecision, PolicyOutcome
from forgeweave.core.control import CancellationToken
from forgeweave.core.diagnostics import LoopDiagnostics
from forgeweave.core.repair import RepairLoopController, RepairOrchestrator, RepairRunResult
from forgeweave.core.stop import StopDecision, StopEvaluator, StopReason
from forgeweave.core.dispatch import DispatchJob, DispatchPlanKind, DispatchPlanner
from forgeweave.models import ModelChunk
from forgeweave.policy import ApprovalRequired, PolicyGateway
from forgeweave.telemetry import TelemetryEvent
from forgeweave.tools import ToolRegistry, ToolRegistryError

if TYPE_CHECKING:
    from collections.abc import Callable

    from forgeweave.context.model_input import ContextModelInput
    from forgeweave.verify import RepairGuard, VerificationResult


class TelemetryRecorder(Protocol):
    """Minimal local telemetry recorder used by the native loop."""

    def record(self, event: TelemetryEvent) -> None:
        """Record one telemetry event."""


class LoopEventRecorderProtocol(Protocol):
    """Minimal event-log recorder used by the native loop."""

    def record_loop_started(
        self,
        *,
        task_id: str,
        attempt_id: str,
        correlation_id: str,
        diagnostics_ref: str,
    ) -> object:
        """Persist a loop-start event."""

    def record_loop_ended(
        self,
        *,
        task_id: str,
        attempt_id: str,
        correlation_id: str,
        stop_decision: StopDecision,
        diagnostics_ref: str,
    ) -> object:
        """Persist a loop-end event."""


class StreamProtocolError(ValueError):
    """Structured stream assembly error."""

    def __init__(self, code: str, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


@dataclass(frozen=True)
class ToolRequest:
    """Complete model-requested tool call data before registry validation."""

    tool_name: str
    tool_schema_version: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class StreamResult:
    """Accepted model stream projection."""

    text: str
    tool_requests: tuple[ToolRequest, ...]
    usage_missing: bool
    usage_reservation: BudgetReservation


@dataclass(frozen=True)
class LoopResult:
    """One native loop turn result."""

    text: str
    observations: list[dict[str, Any]]
    policy_decisions: list[PolicyDecision]
    usage_missing: bool
    stop_decision: StopDecision = StopDecision(StopReason.CONTINUE, False, {})


class ModelStreamAccumulator:
    """Assemble complete provider chunks before any tool validation/dispatch."""

    def __init__(self, *, max_tool_bytes: int = 65_536, default_usage_reservation_tokens: int = 4096) -> None:
        self._max_tool_bytes = max_tool_bytes
        self._default_usage_reservation_tokens = default_usage_reservation_tokens

    def consume(self, chunks: Iterable[ModelChunk], *, cancellation: CancellationToken | None = None) -> StreamResult:
        text_parts: list[str] = []
        tool_parts: dict[str, list[str]] = {}
        usage: dict[str, int] | None = None
        saw_done = False
        for chunk in chunks:
            if cancellation is not None:
                cancellation.raise_if_cancelled()
            if chunk.kind == "text":
                text_parts.append(chunk.content)
                continue
            if chunk.kind == "tool_call":
                if not chunk.call_id:
                    raise StreamProtocolError("MISSING_TOOL_CALL_ID", "tool call chunk is missing call_id")
                parts = tool_parts.setdefault(chunk.call_id, [])
                parts.append(chunk.content)
                if sum(len(part.encode("utf-8")) for part in parts) > self._max_tool_bytes:
                    raise StreamProtocolError("TOOL_CALL_TOO_LARGE", "tool call exceeded stream byte limit")
                continue
            if chunk.kind == "done":
                usage = chunk.usage
                saw_done = True
                continue
            raise StreamProtocolError("UNKNOWN_CHUNK_KIND", f"unknown model chunk kind: {chunk.kind}")

        if tool_parts and not saw_done:
            raise StreamProtocolError("INCOMPLETE_TOOL_CALL", "stream ended before model turn completed")

        requests: list[ToolRequest] = []
        for call_id, parts in tool_parts.items():
            payload = "".join(parts)
            try:
                data = json.loads(payload)
            except json.JSONDecodeError as exc:
                raise StreamProtocolError(
                    "MALFORMED_TOOL_CALL",
                    "tool call JSON is malformed",
                    details={"call_id": call_id},
                ) from exc
            requests.append(_tool_request(data=data, call_id=call_id))

        usage_missing = usage is None
        reservation = BudgetReservation(
            reservation_id="model-stream-usage",
            purpose="model-stream",
            estimated_tokens=0 if usage is not None else self._default_usage_reservation_tokens,
            estimated_cost=0.0,
            actual_tokens=_usage_tokens(usage),
            actual_cost=0.0 if usage is not None else None,
        )
        return StreamResult(
            text="".join(text_parts),
            tool_requests=tuple(requests),
            usage_missing=usage_missing,
            usage_reservation=reservation,
        )


class NativeAgentLoop:
    """Minimal one-turn native loop for fake-provider vertical tests."""

    def __init__(
        self,
        *,
        provider: Any,
        registry: ToolRegistry,
        policy: PolicyGateway,
        task_id: str,
        attempt_id: str,
        workspace_precondition_hash: str,
        accumulator: ModelStreamAccumulator | None = None,
        parallel_dispatch: Callable[[tuple[DispatchJob, ...]], list[tuple[int, dict[str, Any]]]] | None = None,
        telemetry: TelemetryRecorder | None = None,
        correlation_id: str | None = None,
        on_model_turn_complete: Callable[[], None] | None = None,
        diagnostics: LoopDiagnostics | None = None,
        event_recorder: LoopEventRecorderProtocol | None = None,
        diagnostics_ref: str | None = None,
        verified_executor: Any | None = None,
    ) -> None:
        self._provider = provider
        self._registry = registry
        self._policy = policy
        self._task_id = task_id
        self._attempt_id = attempt_id
        self._workspace_precondition_hash = workspace_precondition_hash
        self._accumulator = accumulator or ModelStreamAccumulator()
        self._dispatch_planner = DispatchPlanner()
        self._parallel_dispatch = parallel_dispatch
        self._telemetry = telemetry
        self._correlation_id = correlation_id or task_id
        self._on_model_turn_complete = on_model_turn_complete
        self._diagnostics = diagnostics
        self._event_recorder = event_recorder
        self._diagnostics_ref = diagnostics_ref
        self._verified_executor = verified_executor
        if self._event_recorder is not None and (self._diagnostics_ref is None or not self._diagnostics_ref.strip()):
            raise ValueError("diagnostics_ref must be provided when event_recorder is configured")
        self._stop_evaluator = StopEvaluator()

    def run_context_once(
        self,
        *,
        context_input: "ContextModelInput",
        cancellation: CancellationToken | None = None,
    ) -> LoopResult:
        previous_diagnostics = self._diagnostics
        previous_diagnostics_ref = self._diagnostics_ref
        self._diagnostics = context_input.diagnostics
        self._diagnostics_ref = context_input.diagnostics_ref
        try:
            return self.run_once(messages=context_input.messages, cancellation=cancellation)
        finally:
            self._diagnostics = previous_diagnostics
            self._diagnostics_ref = previous_diagnostics_ref

    def run_context_repair(
        self,
        *,
        context_input: "ContextModelInput",
        verify: "Callable[[], VerificationResult]",
        guard: "RepairGuard",
        cancellation: CancellationToken | None = None,
    ) -> RepairRunResult:
        """Run verification and use one prepared native-loop turn for each repair attempt."""

        orchestrator = RepairOrchestrator(controller=RepairLoopController(guard=guard))

        def repair(_verification: "VerificationResult", _decision: StopDecision) -> None:
            self.run_context_once(context_input=context_input, cancellation=cancellation)

        return orchestrator.run(verify=verify, repair=repair)

    def run_once(self, *, messages: list[dict[str, Any]], cancellation: CancellationToken | None = None) -> LoopResult:
        self._record(
            "loop.started",
            self._with_diagnostics({"message_count": len(messages), "catalog_version": self._registry.catalog_version}),
        )
        self._record_loop_started_event()
        if cancellation is not None:
            cancellation.raise_if_cancelled()
        self._record("model.stream.started", {"message_count": len(messages)})
        stream = self._provider.stream(messages=messages, tools=list(self._registry.model_catalog()), options={})
        result = self._accumulator.consume(stream, cancellation=cancellation)
        self._record(
            "model.stream.ended",
            {
                "text_length": len(result.text),
                "tool_request_count": len(result.tool_requests),
                "usage_missing": result.usage_missing,
            },
        )
        if self._on_model_turn_complete is not None:
            self._on_model_turn_complete()
        if cancellation is not None and cancellation.cancelled:
            stop_decision = self._stop_evaluator.from_cancellation(cancellation)
            self._record_stop(stop_decision, observation_count=0, policy_decision_count=0, usage_missing=result.usage_missing)
            return LoopResult(
                text=result.text,
                observations=[],
                policy_decisions=[],
                usage_missing=result.usage_missing,
                stop_decision=stop_decision,
            )
        observations: list[dict[str, Any]] = []
        decisions: list[PolicyDecision] = []
        jobs: list[DispatchJob] = []

        for index, request in enumerate(result.tool_requests):
            if cancellation is not None:
                cancellation.raise_if_cancelled()
            try:
                call = self._registry.build_call(
                    tool_name=request.tool_name,
                    tool_schema_version=request.tool_schema_version,
                    arguments=request.arguments,
                )
                decision = self._policy.authorize(
                    task_id=self._task_id,
                    attempt_id=self._attempt_id,
                    call=call,
                    workspace_precondition_hash=self._workspace_precondition_hash,
                    catalog_version=self._registry.catalog_version,
                )
                decisions.append(decision)
                self._record(
                    "tool.policy.decided",
                    {
                        "tool_name": request.tool_name,
                        "tool_index": index,
                        "policy_outcome": decision.outcome.value,
                        "policy_revision": decision.policy_revision,
                    },
                )
                if decision.outcome is not PolicyOutcome.ALLOW:
                    observations.append({"tool_name": request.tool_name, "error": decision.reason, "index": index})
                    continue
                self._policy.revalidate_for_dispatch(
                    decision=decision,
                    call=call,
                    workspace_precondition_hash=self._workspace_precondition_hash,
                )
                jobs.append(DispatchJob(index=index, tool_name=request.tool_name, payload={"call": call}, effects=call.effects))
            except (ToolRegistryError, ApprovalRequired) as exc:
                observations.append({"tool_name": request.tool_name, "error": str(exc), "index": index})

        all_observations = [*observations, *self._dispatch_jobs(jobs)]
        ordered_observations = [
            {key: value for key, value in observation.items() if key != "index"}
            for observation in sorted(all_observations, key=lambda item: int(item.get("index", 0)))
        ]

        blocked_verification = next(
            (observation for observation in ordered_observations if observation.get("verification_blocked")),
            None,
        )
        if blocked_verification is not None:
            stop_decision = StopDecision(
                StopReason.FAILED,
                True,
                {
                    "message": "verification gate blocked tool result",
                    "tool_name": blocked_verification.get("tool_name"),
                    "verification_outcome": blocked_verification.get("verification_outcome"),
                },
            )
        else:
            stop_decision = self._stop_evaluator.after_model_turn(
                text=result.text,
                tool_request_count=len(result.tool_requests),
                pending_approval=any(decision.outcome is PolicyOutcome.ASK for decision in decisions),
            )
        self._record_stop(
            stop_decision,
            observation_count=len(ordered_observations),
            policy_decision_count=len(decisions),
            usage_missing=result.usage_missing,
        )
        return LoopResult(
            text=result.text,
            observations=ordered_observations,
            policy_decisions=decisions,
            usage_missing=result.usage_missing,
            stop_decision=stop_decision,
        )

    def _record_stop(
        self,
        stop_decision: StopDecision,
        *,
        observation_count: int,
        policy_decision_count: int,
        usage_missing: bool,
    ) -> None:
        self._record(
            "loop.ended",
            self._with_diagnostics(
                {
                    "observation_count": observation_count,
                    "policy_decision_count": policy_decision_count,
                    "usage_missing": usage_missing,
                    "stop_reason": stop_decision.reason.value,
                }
            ),
        )
        self._record_loop_ended_event(stop_decision)

    def _record_loop_started_event(self) -> None:
        if self._event_recorder is None:
            return
        self._event_recorder.record_loop_started(
            task_id=self._task_id,
            attempt_id=self._attempt_id,
            correlation_id=self._correlation_id,
            diagnostics_ref=self._diagnostics_ref or "",
        )

    def _record_loop_ended_event(self, stop_decision: StopDecision) -> None:
        if self._event_recorder is None:
            return
        self._event_recorder.record_loop_ended(
            task_id=self._task_id,
            attempt_id=self._attempt_id,
            correlation_id=self._correlation_id,
            stop_decision=stop_decision,
            diagnostics_ref=self._diagnostics_ref or "",
        )

    def _with_diagnostics(self, fields: dict[str, Any]) -> dict[str, Any]:
        if self._diagnostics is None:
            return fields
        merged = self._diagnostics.to_telemetry_fields()
        merged.update(fields)
        return merged

    def _record(self, event: str, fields: dict[str, Any]) -> None:
        if self._telemetry is None:
            return
        self._telemetry.record(
            TelemetryEvent(
                event=event,
                task_id=self._task_id,
                attempt_id=self._attempt_id,
                correlation_id=self._correlation_id,
                fields=fields,
            )
        )

    def _dispatch_jobs(self, jobs: list[DispatchJob]) -> list[dict[str, Any]]:
        indexed_observations: list[tuple[int, dict[str, Any]]] = []
        for stage in self._dispatch_planner.plan(jobs):
            if self._parallel_dispatch is not None and stage.kind is DispatchPlanKind.PARALLEL_READS:
                try:
                    indexed_observations.extend(self._parallel_dispatch(stage.jobs))
                except Exception as exc:
                    indexed_observations.extend((job.index, {"tool_name": job.tool_name, "error": str(exc)}) for job in stage.jobs)
                continue
            for job in stage.jobs:
                indexed_observations.append((job.index, self._dispatch_job(job)))
        return [{**observation, "index": index} for index, observation in indexed_observations]

    def _dispatch_job(self, job: DispatchJob) -> dict[str, Any]:
        self._record("tool.dispatch.started", {"tool_name": job.tool_name, "tool_index": job.index})
        call = job.payload["call"]
        try:
            if self._verified_executor is None:
                output = self._registry.dispatch(call)
                observation = {"tool_name": job.tool_name, "output": output}
            else:
                verified = self._verified_executor.run(call=call, dispatch=lambda: self._registry.dispatch(call))
                observation = _verified_observation(tool_name=job.tool_name, output=verified.output, decision=verified.gate_decision)
        except Exception as exc:
            self._record(
                "tool.dispatch.ended",
                {"tool_name": job.tool_name, "tool_index": job.index, "status": "error", "error_type": type(exc).__name__},
            )
            raise
        status = "blocked" if observation.get("verification_blocked") else "ok"
        self._record("tool.dispatch.ended", {"tool_name": job.tool_name, "tool_index": job.index, "status": status})
        return observation


def _verified_observation(*, tool_name: str, output: Any, decision: Any | None) -> dict[str, Any]:
    observation = {"tool_name": tool_name, "output": output}
    if decision is None:
        return observation
    observation.update(
        {
            "verification_outcome": decision.outcome,
            "verification_blocked": decision.should_block,
            "verification_retry_exhausted": decision.retry_exhausted,
            "verification_regression_count": len(decision.regressions),
            "verification_infrastructure_errors": list(decision.infrastructure_errors),
            "before_snapshot_id": decision.before_snapshot_id,
            "after_snapshot_id": decision.after_snapshot_id,
        }
    )
    return observation


def _tool_request(*, data: Any, call_id: str) -> ToolRequest:
    if not isinstance(data, dict):
        raise StreamProtocolError("MALFORMED_TOOL_CALL", "tool call JSON must be an object", details={"call_id": call_id})
    tool_name = data.get("tool_name")
    schema_version = data.get("tool_schema_version")
    arguments = data.get("arguments")
    if not isinstance(tool_name, str) or not isinstance(schema_version, str) or not isinstance(arguments, dict):
        raise StreamProtocolError(
            "MALFORMED_TOOL_CALL",
            "tool call JSON is missing required fields",
            details={"call_id": call_id},
        )
    return ToolRequest(tool_name=tool_name, tool_schema_version=schema_version, arguments=arguments)


def _usage_tokens(usage: dict[str, int] | None) -> int | None:
    if usage is None:
        return None
    return sum(value for value in usage.values() if isinstance(value, int))
