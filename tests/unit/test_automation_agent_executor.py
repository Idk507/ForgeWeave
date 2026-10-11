from __future__ import annotations

import json
import unittest

from forgeweave.automation import (
    NativeAgentWorkflowExecutorConfig,
    WorkflowDefinition,
    WorkflowExecutionContext,
    WorkflowExecutorError,
    WorkflowExecutorRegistry,
    WorkflowRun,
    WorkflowStep,
    WorkflowStepKind,
    WorkflowStepStatus,
    WorkflowStore,
    execute_native_agent_step,
    register_native_agent_workflow_executor,
    run_workflow_once,
    workflow_input_hash,
)
from forgeweave.contracts import EffectSet, ToolSpec
from forgeweave.models import FakeModelProvider, ModelChunk
from forgeweave.policy import PolicyGateway
from forgeweave.tools import ToolRegistry


class NativeAgentWorkflowExecutorTests(unittest.TestCase):
    def test_final_answer_marks_agent_step_succeeded(self) -> None:
        result = execute_native_agent_step(
            WorkflowExecutionContext(run_id="run-1", workflow_id="wf", step=_agent_step(), attempt_number=1),
            _config(provider=FakeModelProvider((ModelChunk(kind="text", content="done"), ModelChunk(kind="done")))),
        )

        self.assertEqual(result.status, WorkflowStepStatus.SUCCEEDED)
        self.assertIn("final_answer", result.reason)
        self.assertEqual(result.output["text"], "done")  # type: ignore[index]

    def test_pending_tool_approval_marks_agent_step_waiting_approval(self) -> None:
        tool_call = json.dumps({"tool_name": "write", "tool_schema_version": "write.v1", "arguments": {"text": "hello"}})
        provider = FakeModelProvider((ModelChunk(kind="tool_call", call_id="call-1", content=tool_call), ModelChunk(kind="done")))
        result = execute_native_agent_step(
            WorkflowExecutionContext(run_id="run-1", workflow_id="wf", step=_agent_step(), attempt_number=1),
            _config(provider=provider, include_write_tool=True),
        )

        self.assertEqual(result.status, WorkflowStepStatus.WAITING_APPROVAL)
        self.assertIn("waiting for approval", result.reason)
        self.assertEqual(result.output["stop_reason"], "waiting_approval")  # type: ignore[index]

    def test_agent_step_requires_prompt_or_objective(self) -> None:
        with self.assertRaises(WorkflowExecutorError) as raised:
            execute_native_agent_step(
                WorkflowExecutionContext(
                    run_id="run-1",
                    workflow_id="wf",
                    step=WorkflowStep(step_id="agent", kind=WorkflowStepKind.AGENT),
                    attempt_number=1,
                ),
                _config(provider=FakeModelProvider((ModelChunk(kind="text", content="done"), ModelChunk(kind="done")))),
            )

        self.assertEqual(raised.exception.code, "INVALID_AGENT_STEP")

    def test_registered_native_agent_executor_integrates_with_runner(self) -> None:
        executors = WorkflowExecutorRegistry()
        register_native_agent_workflow_executor(
            executors,
            _config(provider=FakeModelProvider((ModelChunk(kind="text", content="done"), ModelChunk(kind="done")))),
        )
        with _workflow_store() as store:
            definition = WorkflowDefinition(workflow_id="wf", version=1, input_schema={}, output_schema={}, steps=(_agent_step(),))
            store.record_definition(definition)
            run = store.admit_run(WorkflowRun(run_id="run-1", workflow_id="wf", definition_hash=definition.definition_hash, input_hash=workflow_input_hash({})))

            result = run_workflow_once(store, run_id=run.run_id, executors=executors)

            self.assertEqual(result.recorded_steps[0].status, WorkflowStepStatus.SUCCEEDED)
            self.assertEqual(store.list_attempts(run.run_id)[0].status, WorkflowStepStatus.SUCCEEDED)


def _agent_step() -> WorkflowStep:
    return WorkflowStep(step_id="agent", kind=WorkflowStepKind.AGENT, parameters={"prompt": "finish the task"})


def _config(*, provider: FakeModelProvider, include_write_tool: bool = False) -> NativeAgentWorkflowExecutorConfig:
    registry = ToolRegistry(catalog_version="tools-test")
    if include_write_tool:
        registry.register(
            ToolSpec(
                id="write",
                name="write",
                description="Write text",
                input_schema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
                effects=EffectSet(writes=frozenset({"workspace"})),
                schema_version="write.v1",
            ),
            lambda _arguments: {"unexpected": "dispatch"},
        )
    return NativeAgentWorkflowExecutorConfig(
        provider=provider,
        registry=registry,
        policy=PolicyGateway(policy_revision="policy-v1"),
        workspace_precondition_hash="sha256:workspace",
        task_id="task-1",
    )


class _workflow_store:
    def __enter__(self) -> WorkflowStore:
        from pathlib import Path
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self._store = WorkflowStore.open(Path(self._tmp.name) / "workflows.db")
        return self._store

    def __exit__(self, *_exc: object) -> None:
        self._store.close()
        self._tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
