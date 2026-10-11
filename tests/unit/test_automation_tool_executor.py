from __future__ import annotations

import unittest

from forgeweave.automation import (
    ToolWorkflowExecutorConfig,
    WorkflowDefinition,
    WorkflowExecutionContext,
    WorkflowExecutorRegistry,
    WorkflowRun,
    WorkflowStep,
    WorkflowStepKind,
    WorkflowStepStatus,
    WorkflowStore,
    execute_tool_step,
    register_tool_workflow_executor,
    run_workflow_once,
    workflow_input_hash,
)
from forgeweave.contracts import EffectSet, PolicyOutcome, ToolSpec
from forgeweave.policy import PolicyGateway, PolicyRule
from forgeweave.tools import ToolRegistry


class ToolWorkflowExecutorTests(unittest.TestCase):
    def test_allowed_tool_step_dispatches_through_registry(self) -> None:
        calls: list[dict[str, object]] = []
        registry = ToolRegistry(catalog_version="tools-test")
        registry.register(
            ToolSpec(
                id="echo",
                name="echo",
                description="Echo text",
                input_schema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
                effects=EffectSet(),
                schema_version="echo.v1",
            ),
            lambda arguments: calls.append(arguments) or {"echo": arguments["text"]},
        )
        config = ToolWorkflowExecutorConfig(
            registry=registry,
            policy=PolicyGateway(policy_revision="policy-v1"),
            workspace_precondition_hash="sha256:workspace",
            task_id="task-1",
        )
        context = WorkflowExecutionContext(run_id="run-1", workflow_id="wf", step=_tool_step(), attempt_number=1)

        result = execute_tool_step(context, config)

        self.assertEqual(result.status, WorkflowStepStatus.SUCCEEDED)
        self.assertEqual(calls, [{"text": "hello"}])
        self.assertEqual(result.output["output"], {"echo": "hello"})  # type: ignore[index]

    def test_ask_policy_waits_for_approval_without_dispatch(self) -> None:
        dispatched = False
        registry = ToolRegistry(catalog_version="tools-test")
        registry.register(
            ToolSpec(
                id="write",
                name="write",
                description="Write text",
                input_schema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
                effects=EffectSet(writes=frozenset({"workspace"})),
                schema_version="write.v1",
            ),
            lambda _arguments: nonlocal_set_true(),
        )
        config = ToolWorkflowExecutorConfig(
            registry=registry,
            policy=PolicyGateway(policy_revision="policy-v1"),
            workspace_precondition_hash="sha256:workspace",
            task_id="task-1",
        )
        step = WorkflowStep(
            step_id="write",
            kind=WorkflowStepKind.TOOL,
            parameters={"tool_name": "write", "tool_schema_version": "write.v1", "arguments": {"text": "hello"}},
        )

        def nonlocal_set_true() -> dict[str, str]:
            nonlocal dispatched
            dispatched = True
            return {"unexpected": "dispatch"}

        result = execute_tool_step(WorkflowExecutionContext(run_id="run-1", workflow_id="wf", step=step, attempt_number=1), config)

        self.assertEqual(result.status, WorkflowStepStatus.WAITING_APPROVAL)
        self.assertFalse(dispatched)
        self.assertIn("approval required", result.reason)

    def test_deny_policy_fails_without_dispatch(self) -> None:
        dispatched = False
        registry = ToolRegistry(catalog_version="tools-test")
        registry.register(
            ToolSpec(
                id="echo",
                name="echo",
                description="Echo text",
                input_schema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
                effects=EffectSet(),
                schema_version="echo.v1",
            ),
            lambda _arguments: nonlocal_set_true(),
        )
        config = ToolWorkflowExecutorConfig(
            registry=registry,
            policy=PolicyGateway(policy_revision="policy-v1", rules=(PolicyRule(tool_name="echo", outcome=PolicyOutcome.DENY, reason="blocked"),)),
            workspace_precondition_hash="sha256:workspace",
            task_id="task-1",
        )

        def nonlocal_set_true() -> dict[str, str]:
            nonlocal dispatched
            dispatched = True
            return {"unexpected": "dispatch"}

        result = execute_tool_step(WorkflowExecutionContext(run_id="run-1", workflow_id="wf", step=_tool_step(), attempt_number=1), config)

        self.assertEqual(result.status, WorkflowStepStatus.FAILED)
        self.assertFalse(dispatched)
        self.assertIn("policy denied", result.reason)

    def test_registered_tool_executor_integrates_with_runner(self) -> None:
        registry = ToolRegistry(catalog_version="tools-test")
        registry.register(
            ToolSpec(
                id="echo",
                name="echo",
                description="Echo text",
                input_schema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
                effects=EffectSet(),
                schema_version="echo.v1",
            ),
            lambda arguments: {"echo": arguments["text"]},
        )
        executors = WorkflowExecutorRegistry()
        register_tool_workflow_executor(
            executors,
            ToolWorkflowExecutorConfig(
                registry=registry,
                policy=PolicyGateway(policy_revision="policy-v1"),
                workspace_precondition_hash="sha256:workspace",
                task_id="task-1",
            ),
        )
        with _workflow_store() as store:
            definition = WorkflowDefinition(workflow_id="wf", version=1, input_schema={}, output_schema={}, steps=(_tool_step(),))
            store.record_definition(definition)
            run = store.admit_run(WorkflowRun(run_id="run-1", workflow_id="wf", definition_hash=definition.definition_hash, input_hash=workflow_input_hash({})))

            result = run_workflow_once(store, run_id=run.run_id, executors=executors)

            self.assertEqual(result.recorded_steps[0].status, WorkflowStepStatus.SUCCEEDED)
            self.assertEqual(store.list_attempts(run.run_id)[0].status, WorkflowStepStatus.SUCCEEDED)


def _tool_step() -> WorkflowStep:
    return WorkflowStep(
        step_id="echo",
        kind=WorkflowStepKind.TOOL,
        parameters={"tool_name": "echo", "tool_schema_version": "echo.v1", "arguments": {"text": "hello"}},
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
