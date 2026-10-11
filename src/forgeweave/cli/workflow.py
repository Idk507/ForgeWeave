"""Workflow CLI rendering helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from forgeweave.automation import (
    NativeAgentWorkflowExecutorConfig,
    ToolWorkflowExecutorConfig,
    WorkflowExecutorRegistry,
    JoinMode,
    JoinPolicy,
    WorkflowDefinition,
    WorkflowFailurePolicy,
    WorkflowRun,
    WorkflowRunnerResult,
    WorkflowRunStatus,
    WorkflowStatusView,
    WorkflowStep,
    WorkflowStepKind,
    WorkflowStore,
    register_native_agent_workflow_executor,
    register_tool_workflow_executor,
    WorkflowTemplate,
    get_workflow_template,
    list_workflow_templates,
    run_workflow_once,
    workflow_definition_to_mapping,
    workflow_input_hash,
    workflow_status_view,
)
from forgeweave.cli.run import _registry as _build_cli_tool_registry
from forgeweave.models import FakeModelProvider, ModelChunk
from forgeweave.policy import PolicyGateway, PolicyRule
from forgeweave.contracts import PolicyOutcome


@dataclass(frozen=True)
class WorkflowValidationView:
    """Result of validating a workflow definition file."""

    workflow_id: str
    version: int
    definition_hash: str
    step_count: int
    schema_version: str


@dataclass(frozen=True)
class WorkflowDefinitionSummary:
    """Compact persisted workflow definition summary."""

    workflow_id: str
    version: int
    definition_hash: str
    step_count: int


@dataclass(frozen=True)
class WorkflowRunSummary:
    """Compact persisted workflow run summary."""

    run_id: str
    workflow_id: str
    definition_hash: str
    input_hash: str
    status: str


@dataclass(frozen=True)
class WorkflowListView:
    """Persisted workflow definitions and runs for CLI inspection."""

    definitions: tuple[WorkflowDefinitionSummary, ...]
    runs: tuple[WorkflowRunSummary, ...]


@dataclass(frozen=True)
class WorkflowTemplateSummary:
    """Compact built-in workflow template summary."""

    template_id: str
    title: str
    description: str
    workflow_id: str
    step_count: int


@dataclass(frozen=True)
class WorkflowTemplateListView:
    """Built-in workflow templates available for admission."""

    templates: tuple[WorkflowTemplateSummary, ...]


@dataclass(frozen=True)
class WorkflowTemplateView:
    """Detailed built-in workflow template view."""

    summary: WorkflowTemplateSummary
    definition: dict[str, Any]


@dataclass(frozen=True)
class WorkflowRunAdmissionView:
    """Persisted workflow run admitted by the CLI."""

    run: WorkflowRunSummary
    admitted: bool
    definition: WorkflowDefinitionSummary


def validate_workflow_definition_file(path: Path) -> WorkflowValidationView:
    """Load and validate a JSON workflow definition file."""

    definition = _load_definition_file(path)
    return WorkflowValidationView(
        workflow_id=definition.workflow_id,
        version=definition.version,
        definition_hash=definition.definition_hash,
        step_count=len(definition.steps),
        schema_version=definition.schema_version,
    )


def workflow_template_list_view() -> WorkflowTemplateListView:
    """Return built-in workflow templates for CLI inspection."""

    return WorkflowTemplateListView(templates=tuple(_template_summary(template) for template in list_workflow_templates()))


def workflow_template_view(template_id: str) -> WorkflowTemplateView:
    """Return one built-in workflow template with its definition mapping."""

    template = get_workflow_template(template_id)
    return WorkflowTemplateView(
        summary=_template_summary(template),
        definition=workflow_definition_to_mapping(template.definition),
    )


def render_workflow_template_list(view: WorkflowTemplateListView, *, as_json: bool = False) -> str:
    """Render built-in workflow template summaries."""

    payload = {
        "templates": [
            {
                "template_id": item.template_id,
                "title": item.title,
                "description": item.description,
                "workflow_id": item.workflow_id,
                "step_count": item.step_count,
            }
            for item in view.templates
        ]
    }
    if as_json:
        return json.dumps(payload, indent=2, sort_keys=True)
    lines = ["Workflow templates:"]
    for item in view.templates:
        lines.append(f"  - {item.template_id}: {item.title} ({item.step_count} steps)")
    return "\n".join(lines)


def render_workflow_template(view: WorkflowTemplateView, *, as_json: bool = False) -> str:
    """Render one built-in workflow template."""

    payload = {
        "template_id": view.summary.template_id,
        "title": view.summary.title,
        "description": view.summary.description,
        "workflow_id": view.summary.workflow_id,
        "step_count": view.summary.step_count,
        "definition": view.definition,
    }
    if as_json:
        return json.dumps(payload, indent=2, sort_keys=True)
    return "\n".join(
        (
            f"Template: {view.summary.template_id}",
            f"Title: {view.summary.title}",
            f"Workflow: {view.summary.workflow_id}",
            f"Steps: {view.summary.step_count}",
            f"Description: {view.summary.description}",
        )
    )


def workflow_list_from_store(store_path: Path, *, workflow_id: str | None = None) -> WorkflowListView:
    """Load persisted workflow definitions and runs from a local SQLite store."""

    store = WorkflowStore.open(store_path)
    try:
        definitions = store.list_definitions()
        runs = store.list_runs(workflow_id=workflow_id)
    finally:
        store.close()
    if workflow_id is not None:
        definitions = tuple(definition for definition in definitions if definition.workflow_id == workflow_id)
    return WorkflowListView(
        definitions=tuple(_definition_summary(definition) for definition in definitions),
        runs=tuple(_run_summary(run) for run in runs),
    )


def admit_workflow_run_from_file(
    store_path: Path,
    definition_path: Path,
    *,
    inputs: dict[str, Any] | None = None,
    run_id: str | None = None,
) -> WorkflowRunAdmissionView:
    """Validate and admit a workflow run without executing workflow steps."""

    definition = _load_definition_file(definition_path)
    run_inputs = inputs or {}
    input_hash = workflow_input_hash(run_inputs)
    run = WorkflowRun(
        run_id=run_id or _default_run_id(definition, input_hash),
        workflow_id=definition.workflow_id,
        definition_hash=definition.definition_hash,
        input_hash=input_hash,
    )
    store = WorkflowStore.open(store_path)
    try:
        store.record_definition(definition)
        admitted = store.admit_run(run)
    finally:
        store.close()
    return WorkflowRunAdmissionView(
        run=_run_summary(admitted),
        admitted=True,
        definition=_definition_summary(definition),
    )


def resume_workflow_run_from_store(store_path: Path, *, run_id: str) -> WorkflowRunAdmissionView:
    """Move a persisted paused/failed workflow run back to pending for a future runner."""

    store = WorkflowStore.open(store_path)
    try:
        current = store.get_run(run_id)
        if current.status not in {
            WorkflowRunStatus.FAILED,
            WorkflowRunStatus.CANCELLED,
            WorkflowRunStatus.WAITING_EXTERNAL,
            WorkflowRunStatus.WAITING_APPROVAL,
        }:
            raise ValueError(f"workflow run {run_id} cannot resume from status {current.status.value}")
        resumed = store.update_run_status(run_id, WorkflowRunStatus.PENDING)
        definition = store.get_definition(resumed.definition_hash)
    finally:
        store.close()
    return WorkflowRunAdmissionView(
        run=_run_summary(resumed),
        admitted=False,
        definition=_definition_summary(definition),
    )


def render_workflow_run_admission(view: WorkflowRunAdmissionView, *, as_json: bool = False) -> str:
    """Render workflow run admission or resume state."""

    payload = {
        "run": {
            "run_id": view.run.run_id,
            "workflow_id": view.run.workflow_id,
            "definition_hash": view.run.definition_hash,
            "input_hash": view.run.input_hash,
            "status": view.run.status,
        },
        "definition": {
            "workflow_id": view.definition.workflow_id,
            "version": view.definition.version,
            "definition_hash": view.definition.definition_hash,
            "step_count": view.definition.step_count,
        },
        "admitted": view.admitted,
        "execution_started": False,
    }
    if as_json:
        return json.dumps(payload, indent=2, sort_keys=True)
    action = "Workflow run admitted" if view.admitted else "Workflow run resumed"
    return "\n".join(
        (
            action,
            f"Run: {view.run.run_id}",
            f"Workflow: {view.run.workflow_id}",
            f"Status: {view.run.status}",
            f"Definition hash: {view.run.definition_hash}",
            "Execution started: false",
        )
    )


def workflow_tick_from_store(
    store_path: Path,
    *,
    run_id: str,
    max_ready_steps: int | None = None,
    executors: WorkflowExecutorRegistry | None = None,
) -> WorkflowRunnerResult:
    """Run one workflow scheduler tick over a persisted run."""

    store = WorkflowStore.open(store_path)
    try:
        return run_workflow_once(store, run_id=run_id, max_ready_steps=max_ready_steps, executors=executors)
    finally:
        store.close()


def workflow_executors_for_cli_tick(
    *,
    enable_native_agent: bool = False,
    enable_tool: bool = False,
    fake_response: str | None = None,
    fake_tool_call: str | None = None,
    repo_root: Path | None = None,
    dry_run: bool = False,
) -> WorkflowExecutorRegistry | None:
    """Build opt-in workflow executors for a CLI tick."""

    if not enable_native_agent and not enable_tool:
        return None
    if fake_response is not None and fake_tool_call is not None:
        raise ValueError("use either --fake-response or --fake-tool-call, not both")
    registry = WorkflowExecutorRegistry()
    tool_registry = _build_cli_tool_registry((repo_root or Path.cwd()).resolve(), dry_run=dry_run)
    policy = PolicyGateway(
        policy_revision="policy-v1",
        rules=(PolicyRule(tool_name="write_text", outcome=PolicyOutcome.ALLOW, reason="workflow tick explicit write"),),
    )
    if enable_native_agent:
        register_native_agent_workflow_executor(
            registry,
            NativeAgentWorkflowExecutorConfig(
                provider=FakeModelProvider(_fake_chunks(fake_response=fake_response, fake_tool_call=fake_tool_call)),
                registry=tool_registry,
                policy=policy,
                workspace_precondition_hash="sha256:workflow-cli",
                task_id="workflow-cli",
            ),
        )
    if enable_tool:
        register_tool_workflow_executor(
            registry,
            ToolWorkflowExecutorConfig(
                registry=tool_registry,
                policy=policy,
                workspace_precondition_hash="sha256:workflow-cli",
                task_id="workflow-cli",
            ),
        )
    return registry


def render_workflow_tick(view: WorkflowRunnerResult, *, as_json: bool = False) -> str:
    """Render one workflow scheduler tick."""

    payload = {
        "run_id": view.run_id,
        "run_status": view.run_status.value,
        "ready_before": list(view.ready_before),
        "recorded_steps": [
            {
                "step_id": step.step_id,
                "attempt_id": step.attempt_id,
                "status": step.status.value,
                "reason": step.reason,
            }
            for step in view.recorded_steps
        ],
        "execution_started": view.execution_started,
    }
    if as_json:
        return json.dumps(payload, indent=2, sort_keys=True)
    lines = [
        f"Workflow tick: {view.run_id}",
        f"Run status: {view.run_status.value}",
        f"Ready before: {_join(list(view.ready_before))}",
        f"Execution started: {str(view.execution_started).lower()}",
        "Recorded steps:",
    ]
    if view.recorded_steps:
        for step in view.recorded_steps:
            lines.append(f"  - {step.step_id}: {step.status.value} ({step.reason})")
    else:
        lines.append("  none")
    return "\n".join(lines)


def render_workflow_list(view: WorkflowListView, *, as_json: bool = False) -> str:
    """Render persisted workflow definitions and runs for humans or automation."""

    payload = {
        "definitions": [
            {
                "workflow_id": item.workflow_id,
                "version": item.version,
                "definition_hash": item.definition_hash,
                "step_count": item.step_count,
            }
            for item in view.definitions
        ],
        "runs": [
            {
                "run_id": item.run_id,
                "workflow_id": item.workflow_id,
                "definition_hash": item.definition_hash,
                "input_hash": item.input_hash,
                "status": item.status,
            }
            for item in view.runs
        ],
    }
    if as_json:
        return json.dumps(payload, indent=2, sort_keys=True)
    lines = ["Workflow definitions:"]
    if view.definitions:
        for item in view.definitions:
            lines.append(f"  - {item.workflow_id} v{item.version}: {item.definition_hash} ({item.step_count} steps)")
    else:
        lines.append("  none")
    lines.append("Workflow runs:")
    if view.runs:
        for item in view.runs:
            lines.append(f"  - {item.run_id}: {item.workflow_id} {item.status} {item.input_hash}")
    else:
        lines.append("  none")
    return "\n".join(lines)


def render_workflow_validation(view: WorkflowValidationView, *, as_json: bool = False) -> str:
    """Render workflow validation success for humans or automation."""

    payload = {
        "valid": True,
        "workflow_id": view.workflow_id,
        "version": view.version,
        "definition_hash": view.definition_hash,
        "step_count": view.step_count,
        "schema_version": view.schema_version,
    }
    if as_json:
        return json.dumps(payload, indent=2, sort_keys=True)
    return "\n".join(
        (
            "Workflow definition valid",
            f"Workflow: {view.workflow_id}",
            f"Version: {view.version}",
            f"Steps: {view.step_count}",
            f"Definition hash: {view.definition_hash}",
        )
    )


def workflow_status_from_store(store_path: Path, *, run_id: str) -> WorkflowStatusView:
    """Load an inspectable workflow status projection from a local SQLite store."""

    store = WorkflowStore.open(store_path)
    try:
        return workflow_status_view(store, run_id=run_id)
    finally:
        store.close()


def render_workflow_status(view: WorkflowStatusView, *, as_json: bool = False) -> str:
    """Render workflow run state for humans or automation."""

    payload = _workflow_status_payload(view)
    if as_json:
        return json.dumps(payload, indent=2, sort_keys=True)
    return _render_text(payload)


def _workflow_status_payload(view: WorkflowStatusView) -> dict[str, Any]:
    return {
        "run": {
            "run_id": view.run.run_id,
            "workflow_id": view.run.workflow_id,
            "definition_hash": view.run.definition_hash,
            "input_hash": view.run.input_hash,
            "status": view.run.status.value,
        },
        "ready": list(view.ready),
        "waiting": list(view.waiting),
        "active": list(view.active),
        "completed": list(view.completed),
        "failed": list(view.failed),
        "done": view.done,
        "steps": [
            {
                "step_id": step.step_id,
                "status": step.status.value,
                "latest_attempt_id": step.latest_attempt_id,
                "attempt_count": step.attempt_count,
            }
            for step in view.steps
        ],
    }


def _render_text(payload: dict[str, Any]) -> str:
    run = payload["run"]
    lines = [
        f"Workflow run: {run['run_id']}",
        f"Workflow: {run['workflow_id']}",
        f"Status: {run['status']}",
        f"Done: {str(payload['done']).lower()}",
        f"Ready: {_join(payload['ready'])}",
        f"Waiting: {_join(payload['waiting'])}",
        f"Active: {_join(payload['active'])}",
        f"Completed: {_join(payload['completed'])}",
        f"Failed: {_join(payload['failed'])}",
        "Steps:",
    ]
    for step in payload["steps"]:
        latest = step["latest_attempt_id"] or "none"
        lines.append(
            f"  - {step['step_id']}: {step['status']} "
            f"(attempts={step['attempt_count']}, latest={latest})"
        )
    return "\n".join(lines)


def _join(values: list[str]) -> str:
    return ", ".join(values) if values else "none"





def _fake_chunks(*, fake_response: str | None, fake_tool_call: str | None) -> tuple[ModelChunk, ...]:
    if fake_tool_call is not None:
        return (ModelChunk(kind="tool_call", call_id="workflow-call-1", content=fake_tool_call), ModelChunk(kind="done"))
    return (ModelChunk(kind="text", content=fake_response or ""), ModelChunk(kind="done"))


def _template_summary(template: WorkflowTemplate) -> WorkflowTemplateSummary:
    return WorkflowTemplateSummary(
        template_id=template.template_id,
        title=template.title,
        description=template.description,
        workflow_id=template.definition.workflow_id,
        step_count=len(template.definition.steps),
    )


def workflow_inputs_from_json(value: str | None, file_path: Path | None) -> dict[str, Any]:
    """Load workflow input JSON from a CLI string or file path."""

    if value is not None and file_path is not None:
        raise ValueError("use either --input-json or --input-file, not both")
    if file_path is not None:
        raw = file_path.read_text(encoding="utf-8")
    elif value is not None:
        raw = value
    else:
        return {}
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("workflow inputs must be a JSON object")
    return payload


def _load_definition_file(path: Path) -> WorkflowDefinition:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("workflow definition must be a JSON object")
    return _definition_from_mapping(payload)


def _default_run_id(definition: WorkflowDefinition, input_hash: str) -> str:
    seed = f"{definition.workflow_id}:{definition.definition_hash}:{input_hash}"
    digest = sha256(seed.encode("utf-8")).hexdigest()[:12]
    return f"run-{definition.workflow_id}-{digest}"


def _definition_summary(definition: WorkflowDefinition) -> WorkflowDefinitionSummary:
    return WorkflowDefinitionSummary(
        workflow_id=definition.workflow_id,
        version=definition.version,
        definition_hash=definition.definition_hash,
        step_count=len(definition.steps),
    )


def _run_summary(run: WorkflowRun) -> WorkflowRunSummary:
    return WorkflowRunSummary(
        run_id=run.run_id,
        workflow_id=run.workflow_id,
        definition_hash=run.definition_hash,
        input_hash=run.input_hash,
        status=run.status.value,
    )


def _definition_from_mapping(payload: dict[str, Any]) -> WorkflowDefinition:
    steps = payload.get("steps")
    if not isinstance(steps, list):
        raise ValueError("workflow definition steps must be a list")
    return WorkflowDefinition(
        workflow_id=str(payload["workflow_id"]),
        version=int(payload["version"]),
        input_schema=_dict_field(payload, "input_schema"),
        output_schema=_dict_field(payload, "output_schema"),
        failure_policy=WorkflowFailurePolicy(payload.get("failure_policy", WorkflowFailurePolicy.FAIL_FAST.value)),
        schema_version=str(payload.get("schema_version", "workflow-definition.v1")),
        steps=tuple(_step_from_mapping(item) for item in steps),
    )


def _step_from_mapping(payload: Any) -> WorkflowStep:
    if not isinstance(payload, dict):
        raise ValueError("workflow step must be a JSON object")
    join_payload = payload.get("join_policy")
    return WorkflowStep(
        step_id=str(payload["step_id"]),
        kind=WorkflowStepKind(payload["kind"]),
        depends_on=tuple(str(item) for item in payload.get("depends_on", ())),
        capability=None if payload.get("capability") is None else str(payload["capability"]),
        parameters=payload.get("parameters") or None,
        join_policy=None if join_payload is None else _join_policy_from_mapping(join_payload),
        max_attempts=int(payload.get("max_attempts", 1)),
        timeout_seconds=None if payload.get("timeout_seconds") is None else int(payload["timeout_seconds"]),
    )


def _join_policy_from_mapping(payload: Any) -> JoinPolicy:
    if not isinstance(payload, dict):
        raise ValueError("join_policy must be a JSON object")
    return JoinPolicy(
        mode=JoinMode(payload["mode"]),
        failure_policy=WorkflowFailurePolicy(payload.get("failure_policy", WorkflowFailurePolicy.FAIL_FAST.value)),
        quorum=None if payload.get("quorum") is None else int(payload["quorum"]),
    )


def _dict_field(payload: dict[str, Any], name: str) -> dict[str, Any]:
    value = payload[name]
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a JSON object")
    return value
