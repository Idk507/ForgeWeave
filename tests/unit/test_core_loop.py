from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from forgeweave.context import ContextModelInput
from forgeweave.context.assembler import ContextPacket
from forgeweave.contracts import BudgetLedger, BudgetReservation, ContextManifest, ContextSpan, EffectSet, EventKind, ToolSpec, VerificationRun
from forgeweave.core import BudgetLimits, BudgetUsage, CancellationToken, LoopDiagnostics, NativeAgentLoop, StopReason
from forgeweave.events import EventStore, LoopEventRecorder
from forgeweave.models import FakeModelProvider, ModelChunk
from forgeweave.policy import PolicyGateway, PolicyRule
from forgeweave.telemetry import BoundedTelemetryWriter, JsonlTelemetrySink
from forgeweave.tools import ToolRegistry
from forgeweave.verify import RepairGuard, VerificationResult
from forgeweave.contracts import PolicyOutcome



class FakeVerifiedExecutor:
    def __init__(self, *, outcome: str, should_block: bool) -> None:
        self.outcome = outcome
        self.should_block = should_block
        self.calls: list[str] = []

    def run(self, *, call, dispatch):
        self.calls.append(call.tool_name)
        output = dispatch()
        decision = FakeGateDecision(outcome=self.outcome, should_block=self.should_block)
        return FakeVerifiedResult(output=output, gate_decision=decision)


class FakeVerifiedResult:
    def __init__(self, *, output, gate_decision) -> None:
        self.output = output
        self.gate_decision = gate_decision


class FakeGateDecision:
    def __init__(self, *, outcome: str, should_block: bool) -> None:
        self.outcome = outcome
        self.should_block = should_block
        self.retry_exhausted = False
        self.regressions = ()
        self.infrastructure_errors = ()
        self.before_snapshot_id = "before"
        self.after_snapshot_id = "after"


class RecordingProvider(FakeModelProvider):
    def __init__(self, chunks: list[ModelChunk]) -> None:
        super().__init__(chunks)
        self.messages: list[dict[str, object]] | None = None
        self.tools: list[dict[str, object]] | None = None

    def stream(self, *, messages: list[dict[str, object]], tools: list[dict[str, object]], options: dict[str, object]):
        self.messages = messages
        self.tools = tools
        return super().stream(messages=messages, tools=tools, options=options)


class CoreLoopTests(unittest.TestCase):

    def test_loop_passes_registered_tool_catalog_to_provider(self) -> None:
        provider = RecordingProvider([ModelChunk(kind="text", content="done"), ModelChunk(kind="done")])
        registry = ToolRegistry(catalog_version="tools-v1")
        registry.register(
            ToolSpec(
                name="write_text",
                description="Write a file.",
                input_schema={
                    "type": "object",
                    "required": ["path", "content"],
                    "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                },
                effects=EffectSet(writes=frozenset({"workspace"})),
                schema_version="write-text.v1",
            ),
            lambda arguments: "ok",
        )
        loop = NativeAgentLoop(
            provider=provider,
            registry=registry,
            policy=PolicyGateway(policy_revision="policy-v1"),
            task_id="task-1",
            attempt_id="attempt-1",
            workspace_precondition_hash="sha256:workspace",
        )

        result = loop.run_once(messages=[{"role": "user", "content": "finish"}])

        self.assertEqual(result.text, "done")
        self.assertEqual(provider.tools, list(registry.model_catalog()))
        assert provider.tools is not None
        self.assertEqual(provider.tools[0]["name"], "write_text")
        self.assertEqual(provider.tools[0]["schema_version"], "write-text.v1")

    def test_loop_runs_model_policy_registry_observation_cycle(self) -> None:
        provider = FakeModelProvider(
            [
                ModelChunk(kind="tool_call", call_id="model-call-1", content='{"tool_name":"read_file"'),
                ModelChunk(
                    kind="tool_call",
                    call_id="model-call-1",
                    content=',"tool_schema_version":"read-file.v1","arguments":{"path":"README.md"}}',
                ),
                ModelChunk(kind="done"),
            ]
        )
        registry = ToolRegistry(catalog_version="tools-v1")
        registry.register(
            ToolSpec(
                name="read_file",
                description="Read a file.",
                input_schema={
                    "type": "object",
                    "required": ["path"],
                    "properties": {"path": {"type": "string"}},
                },
                effects=EffectSet(reads=frozenset({"workspace"})),
                schema_version="read-file.v1",
            ),
            lambda arguments: "contents:" + arguments["path"],
        )
        loop = NativeAgentLoop(
            provider=provider,
            registry=registry,
            policy=PolicyGateway(policy_revision="policy-v1"),
            task_id="task-1",
            attempt_id="attempt-1",
            workspace_precondition_hash="sha256:workspace",
        )

        result = loop.run_once(messages=[{"role": "user", "content": "read README"}])

        self.assertEqual(result.observations, [{"tool_name": "read_file", "output": "contents:README.md"}])
        self.assertEqual(result.policy_decisions[0].outcome, PolicyOutcome.ALLOW)


    def test_loop_uses_dispatch_planner_for_ordered_observations(self) -> None:
        provider = FakeModelProvider(
            [
                ModelChunk(
                    kind="tool_call",
                    call_id="model-call-1",
                    content='{"tool_name":"read_file","tool_schema_version":"read-file.v1","arguments":{"path":"a.txt"}}',
                ),
                ModelChunk(
                    kind="tool_call",
                    call_id="model-call-2",
                    content='{"tool_name":"read_file","tool_schema_version":"read-file.v1","arguments":{"path":"b.txt"}}',
                ),
                ModelChunk(kind="done"),
            ]
        )
        registry = ToolRegistry(catalog_version="tools-v1")
        registry.register(
            ToolSpec(
                name="read_file",
                description="Read a file.",
                input_schema={
                    "type": "object",
                    "required": ["path"],
                    "properties": {"path": {"type": "string"}},
                },
                effects=EffectSet(reads=frozenset({"workspace"})),
                schema_version="read-file.v1",
            ),
            lambda arguments: "contents:" + arguments["path"],
        )

        loop = NativeAgentLoop(
            provider=provider,
            registry=registry,
            policy=PolicyGateway(policy_revision="policy-v1"),
            task_id="task-1",
            attempt_id="attempt-1",
            workspace_precondition_hash="sha256:workspace",
            parallel_dispatch=lambda batch: [
                (job.index, {"tool_name": job.tool_name, "output": registry.dispatch(job.payload["call"])})
                for job in reversed(batch)
            ],
        )

        result = loop.run_once(messages=[{"role": "user", "content": "read two files"}])

        self.assertEqual(
            result.observations,
            [
                {"tool_name": "read_file", "output": "contents:a.txt"},
                {"tool_name": "read_file", "output": "contents:b.txt"},
            ],
        )

    def test_loop_drains_cancellation_after_model_turn_into_structured_result(self) -> None:
        token = CancellationToken()
        provider = FakeModelProvider(
            [
                ModelChunk(
                    kind="tool_call",
                    call_id="model-call-1",
                    content='{"tool_name":"read_file","tool_schema_version":"read-file.v1","arguments":{"path":"README.md"}}',
                ),
                ModelChunk(kind="done"),
            ]
        )
        registry = ToolRegistry(catalog_version="tools-v1")
        registry.register(
            ToolSpec(
                name="read_file",
                description="Read a file.",
                input_schema={
                    "type": "object",
                    "required": ["path"],
                    "properties": {"path": {"type": "string"}},
                },
                effects=EffectSet(reads=frozenset({"workspace"})),
                schema_version="read-file.v1",
            ),
            lambda arguments: "contents:" + arguments["path"],
        )
        loop = NativeAgentLoop(
            provider=provider,
            registry=registry,
            policy=PolicyGateway(policy_revision="policy-v1"),
            task_id="task-1",
            attempt_id="attempt-1",
            workspace_precondition_hash="sha256:workspace",
            on_model_turn_complete=lambda: token.cancel("stop after model"),
        )

        result = loop.run_once(messages=[{"role": "user", "content": "read README"}], cancellation=token)

        self.assertEqual(result.observations, [])
        self.assertEqual(result.stop_decision.reason, StopReason.CANCELLED)
        self.assertEqual(result.stop_decision.details["message"], "stop after model")

    def test_loop_records_local_telemetry_audit_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            telemetry_path = Path(tmp) / "telemetry.jsonl"
            writer = BoundedTelemetryWriter(sink=JsonlTelemetrySink(telemetry_path), capacity=20)
            provider = FakeModelProvider(
                [
                    ModelChunk(
                        kind="tool_call",
                        call_id="model-call-1",
                        content='{"tool_name":"read_file","tool_schema_version":"read-file.v1","arguments":{"path":"README.md"}}',
                    ),
                    ModelChunk(kind="done"),
                ]
            )
            registry = ToolRegistry(catalog_version="tools-v1")
            registry.register(
                ToolSpec(
                    name="read_file",
                    description="Read a file.",
                    input_schema={
                        "type": "object",
                        "required": ["path"],
                        "properties": {"path": {"type": "string"}},
                    },
                    effects=EffectSet(reads=frozenset({"workspace"})),
                    schema_version="read-file.v1",
                ),
                lambda arguments: "contents:" + arguments["path"],
            )
            loop = NativeAgentLoop(
                provider=provider,
                registry=registry,
                policy=PolicyGateway(policy_revision="policy-v1"),
                task_id="task-1",
                attempt_id="attempt-1",
                workspace_precondition_hash="sha256:workspace",
                telemetry=writer,
                correlation_id="corr-loop-1",
            )

            result = loop.run_once(messages=[{"role": "user", "content": "read README"}])
            flush = writer.flush()

            self.assertEqual(result.observations, [{"tool_name": "read_file", "output": "contents:README.md"}])
            self.assertEqual(flush.failed, 0)
            events = [json.loads(line) for line in telemetry_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(
                [event["event"] for event in events],
                [
                    "loop.started",
                    "model.stream.started",
                    "model.stream.ended",
                    "tool.policy.decided",
                    "tool.dispatch.started",
                    "tool.dispatch.ended",
                    "loop.ended",
                ],
            )
            self.assertTrue(all(event["correlation_id"] == "corr-loop-1" for event in events))
            self.assertEqual(events[2]["fields"]["tool_request_count"], 1)
            self.assertEqual(events[3]["fields"]["policy_outcome"], "allow")
            self.assertEqual(events[5]["fields"]["status"], "ok")
            self.assertEqual(events[-1]["fields"]["observation_count"], 1)

    def test_loop_records_prompt_free_diagnostics_in_local_telemetry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            telemetry_path = Path(tmp) / "telemetry.jsonl"
            writer = BoundedTelemetryWriter(sink=JsonlTelemetrySink(telemetry_path), capacity=20)
            provider = FakeModelProvider([ModelChunk(kind="text", content="done"), ModelChunk(kind="done")])
            registry = ToolRegistry(catalog_version="tools-v1")
            diagnostics = LoopDiagnostics(
                context_manifest=_context_manifest(),
                budget_limits=BudgetLimits(max_turns=3, max_tokens=1000, max_tool_calls=5, max_context_tokens=600),
                budget_usage=BudgetUsage(turns=1, tokens=250, tool_calls=2, context_tokens=400),
                budget_ledger=BudgetLedger(
                    task_id="task-1",
                    currency="USD",
                    price_source_version="prices-v1",
                    reservations=(
                        BudgetReservation(
                            reservation_id="reserve-1",
                            purpose="model-stream",
                            estimated_tokens=100,
                            estimated_cost=0.10,
                        ),
                    ),
                ),
                root_budget_id="root-budget-1",
            )
            loop = NativeAgentLoop(
                provider=provider,
                registry=registry,
                policy=PolicyGateway(policy_revision="policy-v1"),
                task_id="task-1",
                attempt_id="attempt-1",
                workspace_precondition_hash="sha256:workspace",
                telemetry=writer,
                correlation_id="corr-loop-1",
                diagnostics=diagnostics,
            )

            result = loop.run_once(messages=[{"role": "user", "content": "secret prompt text"}])
            writer.flush()

            self.assertEqual(result.stop_decision.reason, StopReason.FINAL_ANSWER)
            events = [json.loads(line) for line in telemetry_path.read_text(encoding="utf-8").splitlines()]
            started = events[0]["fields"]
            ended = events[-1]["fields"]
            self.assertEqual(started["context_request_id"], "ctx-1")
            self.assertEqual(started["effective_config_hash"], "sha256:config")
            self.assertEqual(started["catalog_version"], "tools-v1")
            self.assertEqual(started["budget_usage_tokens"], 250)
            self.assertEqual(started["budget_limit_tokens"], 1000)
            self.assertEqual(started["budget_reserved_tokens"], 100)
            self.assertEqual(started["root_budget_id"], "root-budget-1")
            self.assertEqual(ended["context_request_id"], "ctx-1")
            serialized_fields = json.dumps([event["fields"] for event in events], sort_keys=True)
            self.assertNotIn("secret prompt text", serialized_fields)
            self.assertNotIn("latest_user_request", serialized_fields)

    def test_loop_persists_start_and_end_events_with_diagnostics_refs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = EventStore.open(root / "events.db")
            try:
                provider = FakeModelProvider([ModelChunk(kind="text", content="done"), ModelChunk(kind="done")])
                registry = ToolRegistry(catalog_version="tools-v1")
                loop = NativeAgentLoop(
                    provider=provider,
                    registry=registry,
                    policy=PolicyGateway(policy_revision="policy-v1"),
                    task_id="task-1",
                    attempt_id="attempt-1",
                    workspace_precondition_hash="sha256:workspace",
                    correlation_id="corr-loop-1",
                    event_recorder=LoopEventRecorder(store),
                    diagnostics_ref="diagnostics://task-1/attempt-1/loop",
                )

                result = loop.run_once(messages=[{"role": "user", "content": "secret prompt text"}])

                self.assertEqual(result.stop_decision.reason, StopReason.FINAL_ANSWER)
                events = store.list_events("task-1")
                self.assertEqual([event.sequence for event in events], [1, 2])
                self.assertEqual([event.kind for event in events], [EventKind.STEP_RECORDED, EventKind.STEP_RECORDED])
                self.assertEqual(events[0].payload_ref, "loop-started://diagnostics://task-1/attempt-1/loop")
                self.assertEqual(events[1].payload_ref, "loop-ended://final_answer/diagnostics://task-1/attempt-1/loop")
                self.assertNotIn("secret prompt text", store.raw_event_json(events[0].event_id))
            finally:
                store.close()

    def test_loop_accepts_prepared_context_model_input(self) -> None:
        provider = RecordingProvider([ModelChunk(kind="text", content="done"), ModelChunk(kind="done")])
        registry = ToolRegistry(catalog_version="tools-v1")
        prepared = ContextModelInput.from_packet(_context_packet(), user_message="Implement the next slice.")
        loop = NativeAgentLoop(
            provider=provider,
            registry=registry,
            policy=PolicyGateway(policy_revision="policy-v1"),
            task_id="task-1",
            attempt_id="attempt-1",
            workspace_precondition_hash="sha256:workspace",
        )

        result = loop.run_context_once(context_input=prepared)

        self.assertEqual(result.stop_decision.reason, StopReason.FINAL_ANSWER)
        self.assertEqual(provider.messages, prepared.messages)

    def test_loop_reports_denied_tool_without_dispatching(self) -> None:
        dispatched: list[str] = []
        provider = FakeModelProvider(
            [
                ModelChunk(
                    kind="tool_call",
                    call_id="model-call-1",
                    content='{"tool_name":"write_file","tool_schema_version":"write-file.v1","arguments":{"path":"a.txt"}}',
                ),
                ModelChunk(kind="done"),
            ]
        )
        registry = ToolRegistry(catalog_version="tools-v1")
        registry.register(
            ToolSpec(
                name="write_file",
                description="Write a file.",
                input_schema={
                    "type": "object",
                    "required": ["path"],
                    "properties": {"path": {"type": "string"}},
                },
                effects=EffectSet(writes=frozenset({"workspace"})),
                schema_version="write-file.v1",
            ),
            lambda arguments: dispatched.append(arguments["path"]),
        )
        loop = NativeAgentLoop(
            provider=provider,
            registry=registry,
            policy=PolicyGateway(
                policy_revision="policy-v1",
                rules=(PolicyRule(tool_name="write_file", outcome=PolicyOutcome.DENY, reason="writes disabled"),),
            ),
            task_id="task-1",
            attempt_id="attempt-1",
            workspace_precondition_hash="sha256:workspace",
        )

        result = loop.run_once(messages=[{"role": "user", "content": "write"}])

        self.assertEqual(dispatched, [])
        self.assertEqual(result.observations[0]["error"], "writes disabled")

    def test_loop_runs_context_repair_until_verification_passes(self) -> None:
        provider = RecordingProvider([ModelChunk(kind="text", content="repair applied"), ModelChunk(kind="done")])
        registry = ToolRegistry(catalog_version="tools-v1")
        prepared = ContextModelInput.from_packet(_context_packet(), user_message="Repair the failure.")
        loop = NativeAgentLoop(
            provider=provider,
            registry=registry,
            policy=PolicyGateway(policy_revision="policy-v1"),
            task_id="task-1",
            attempt_id="attempt-1",
            workspace_precondition_hash="sha256:workspace",
        )
        verification_results = iter([
            _verification_result(outcome="failed", exit_code=1, run_id="verify-1"),
            _verification_result(outcome="passed", exit_code=0, run_id="verify-2"),
        ])

        result = loop.run_context_repair(
            context_input=prepared,
            verify=lambda: next(verification_results),
            guard=RepairGuard(max_repairs=2),
        )

        self.assertEqual(result.stop_decision.reason, StopReason.FINAL_ANSWER)
        self.assertEqual(result.repair_attempts, 1)
        self.assertEqual([item.run.run_id for item in result.verification_results], ["verify-1", "verify-2"])
        self.assertEqual(provider.messages, prepared.messages)

    def test_loop_context_repair_does_not_run_model_when_guard_stops(self) -> None:
        provider = RecordingProvider([ModelChunk(kind="text", content="unused"), ModelChunk(kind="done")])
        registry = ToolRegistry(catalog_version="tools-v1")
        prepared = ContextModelInput.from_packet(_context_packet(), user_message="Repair the failure.")
        loop = NativeAgentLoop(
            provider=provider,
            registry=registry,
            policy=PolicyGateway(policy_revision="policy-v1"),
            task_id="task-1",
            attempt_id="attempt-1",
            workspace_precondition_hash="sha256:workspace",
        )

        result = loop.run_context_repair(
            context_input=prepared,
            verify=lambda: _verification_result(outcome="failed", exit_code=1),
            guard=RepairGuard(max_repairs=1),
        )

        self.assertEqual(result.stop_decision.reason, StopReason.FAILED)
        self.assertEqual(result.stop_decision.details["repair_stop_reason"], "repair-budget-exhausted")
        self.assertEqual(result.repair_attempts, 0)
        self.assertIsNone(provider.messages)

    def test_loop_uses_verified_executor_for_mutating_tool_pass(self) -> None:
        provider = FakeModelProvider(
            [
                ModelChunk(
                    kind="tool_call",
                    call_id="model-call-1",
                    content='{"tool_name":"write_file","tool_schema_version":"write-file.v1","arguments":{"path":"a.txt"}}',
                ),
                ModelChunk(kind="done"),
            ]
        )
        registry = ToolRegistry(catalog_version="tools-v1")
        registry.register(
            ToolSpec(
                name="write_file",
                description="Write a file.",
                input_schema={
                    "type": "object",
                    "required": ["path"],
                    "properties": {"path": {"type": "string"}},
                },
                effects=EffectSet(writes=frozenset({"workspace"})),
                schema_version="write-file.v1",
            ),
            lambda arguments: "wrote:" + arguments["path"],
        )
        verified_executor = FakeVerifiedExecutor(outcome="passed", should_block=False)
        loop = NativeAgentLoop(
            provider=provider,
            registry=registry,
            policy=PolicyGateway(
                policy_revision="policy-v1",
                rules=(PolicyRule(tool_name="write_file", outcome=PolicyOutcome.ALLOW, reason="test allow"),),
            ),
            task_id="task-1",
            attempt_id="attempt-1",
            workspace_precondition_hash="sha256:workspace",
            verified_executor=verified_executor,
        )

        result = loop.run_once(messages=[{"role": "user", "content": "write"}])

        self.assertEqual(verified_executor.calls, ["write_file"])
        self.assertEqual(result.observations[0]["output"], "wrote:a.txt")
        self.assertEqual(result.observations[0]["verification_outcome"], "passed")
        self.assertFalse(result.observations[0]["verification_blocked"])
        self.assertEqual(result.stop_decision.reason, StopReason.CONTINUE)

    def test_loop_fails_when_verified_executor_blocks_mutating_tool(self) -> None:
        provider = FakeModelProvider(
            [
                ModelChunk(
                    kind="tool_call",
                    call_id="model-call-1",
                    content='{"tool_name":"write_file","tool_schema_version":"write-file.v1","arguments":{"path":"a.txt"}}',
                ),
                ModelChunk(kind="done"),
            ]
        )
        registry = ToolRegistry(catalog_version="tools-v1")
        registry.register(
            ToolSpec(
                name="write_file",
                description="Write a file.",
                input_schema={
                    "type": "object",
                    "required": ["path"],
                    "properties": {"path": {"type": "string"}},
                },
                effects=EffectSet(writes=frozenset({"workspace"})),
                schema_version="write-file.v1",
            ),
            lambda arguments: "wrote:" + arguments["path"],
        )
        loop = NativeAgentLoop(
            provider=provider,
            registry=registry,
            policy=PolicyGateway(
                policy_revision="policy-v1",
                rules=(PolicyRule(tool_name="write_file", outcome=PolicyOutcome.ALLOW, reason="test allow"),),
            ),
            task_id="task-1",
            attempt_id="attempt-1",
            workspace_precondition_hash="sha256:workspace",
            verified_executor=FakeVerifiedExecutor(outcome="code-regression", should_block=True),
        )

        result = loop.run_once(messages=[{"role": "user", "content": "write"}])

        self.assertEqual(result.observations[0]["verification_outcome"], "code-regression")
        self.assertTrue(result.observations[0]["verification_blocked"])
        self.assertEqual(result.stop_decision.reason, StopReason.FAILED)
        self.assertEqual(result.stop_decision.details["verification_outcome"], "code-regression")


def _context_packet() -> ContextPacket:
    return ContextPacket(
        manifest=ContextManifest(
            request_id="ctx-1",
            task_id="task-1",
            attempt_id="attempt-1",
            provider="fake",
            model="fake-model",
            adapter_version="adapter-v1",
            effective_policy_hash="sha256:policy",
            effective_config_hash="sha256:config",
            workspace_revision="sha256:workspace",
            catalog_version="tools-v1",
            spans=(
                ContextSpan(
                    span_id="latest-user-request",
                    source="user:latest-request",
                    source_hash="sha256:latest",
                    authority="task",
                    sensitivity="normal",
                    token_estimate=4,
                ),
            ),
            token_estimate=4,
        ),
        text_by_span_id={"latest-user-request": "Build the feature."},
    )


def _verification_result(
    *,
    outcome: str,
    exit_code: int | None,
    run_id: str = "verify-1",
) -> VerificationResult:
    run = VerificationRun(
        run_id=run_id,
        task_id="task-1",
        criterion_ids=("unit",),
        command_argv=("python", "-m", "unittest"),
        cwd="C:/workspace",
        environment_profile_hash="sha256:env",
        verifier_version="unit",
        config_hash="sha256:config",
        workspace_fingerprint="sha256:workspace",
        untracked_input_hashes={},
        timeout_seconds=5,
        exit_code=exit_code,
        output_artifact_id="artifact-1",
        outcome=outcome,  # type: ignore[arg-type]
        whole_input_fingerprint="sha256:input",
    )
    return VerificationResult(run=run, stdout="", stderr="", timed_out=outcome == "inconclusive")

def _context_manifest() -> ContextManifest:
    return ContextManifest(
        request_id="ctx-1",
        task_id="task-1",
        attempt_id="attempt-1",
        provider="fake",
        model="fake-model",
        adapter_version="adapter-v1",
        effective_policy_hash="sha256:policy",
        effective_config_hash="sha256:config",
        workspace_revision="sha256:workspace",
        catalog_version="tools-v1",
        spans=(),
        omitted_spans=("omitted-1",),
        summary_lineage=("summary-1",),
        token_estimate=512,
    )


if __name__ == "__main__":
    unittest.main()
