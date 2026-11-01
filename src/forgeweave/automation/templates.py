"""Built-in workflow templates for safe workflow admission."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .contracts import JoinMode, JoinPolicy, WorkflowDefinition, WorkflowStep, WorkflowStepKind


@dataclass(frozen=True)
class WorkflowTemplate:
    """Named built-in workflow definition with a reviewable description."""

    template_id: str
    title: str
    description: str
    definition: WorkflowDefinition


def _join(step_id: str, depends_on: tuple[str, ...], *, mode: JoinMode = JoinMode.ALL_SUCCESS) -> WorkflowStep:
    return WorkflowStep(step_id=step_id, kind=WorkflowStepKind.JOIN, depends_on=depends_on, join_policy=JoinPolicy(mode=mode))


_BUILTIN_TEMPLATES: tuple[WorkflowTemplate, ...] = (
    WorkflowTemplate(
        template_id="browser-ui-regression",
        title="Browser UI regression",
        description="Reproduce a UI issue through browser-capable steps, patch locally and verify through guarded browser checks.",
        definition=WorkflowDefinition(
            workflow_id="browser-ui-regression",
            version=1,
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            steps=(
                WorkflowStep(step_id="reproduce_ui", kind=WorkflowStepKind.AGENT, capability="browser", parameters={"requires_browser": True}),
                WorkflowStep(step_id="plan_fix", kind=WorkflowStepKind.AGENT, capability="plan", depends_on=("reproduce_ui",)),
                WorkflowStep(step_id="implement_fix", kind=WorkflowStepKind.AGENT, capability="implement", depends_on=("plan_fix",), parameters={"artifacts": ["patch"]}, max_attempts=2),
                WorkflowStep(step_id="verify_browser", kind=WorkflowStepKind.VERIFICATION, capability="browser", depends_on=("implement_fix",), parameters={"artifacts": ["verification"], "requires_browser": True}, max_attempts=2),
                _join("browser_gate", ("reproduce_ui", "plan_fix", "implement_fix", "verify_browser")),
            ),
        ),
    ),
    WorkflowTemplate(
        template_id="dependency-update",
        title="Dependency update",
        description="Assess, update, verify and review dependency changes before any external publication.",
        definition=WorkflowDefinition(
            workflow_id="dependency-update",
            version=1,
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            steps=(
                WorkflowStep(step_id="inspect_dependency", kind=WorkflowStepKind.AGENT, capability="research"),
                WorkflowStep(step_id="plan_update", kind=WorkflowStepKind.AGENT, capability="plan", depends_on=("inspect_dependency",)),
                WorkflowStep(step_id="apply_update", kind=WorkflowStepKind.AGENT, capability="implement", depends_on=("plan_update",), parameters={"artifacts": ["patch"]}, max_attempts=2),
                WorkflowStep(step_id="run_regression_checks", kind=WorkflowStepKind.VERIFICATION, capability="test", depends_on=("apply_update",), parameters={"artifacts": ["verification"]}, max_attempts=2),
                WorkflowStep(step_id="review_update", kind=WorkflowStepKind.AGENT, capability="review", depends_on=("run_regression_checks",)),
                _join("dependency_gate", ("inspect_dependency", "plan_update", "apply_update", "run_regression_checks", "review_update")),
            ),
        ),
    ),
    WorkflowTemplate(
        template_id="docs-sync",
        title="Documentation sync",
        description="Detect code/documentation drift, update docs and verify generated documentation artifacts locally.",
        definition=WorkflowDefinition(
            workflow_id="docs-sync",
            version=1,
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            steps=(
                WorkflowStep(step_id="inspect_drift", kind=WorkflowStepKind.AGENT, capability="research"),
                WorkflowStep(step_id="plan_docs", kind=WorkflowStepKind.AGENT, capability="plan", depends_on=("inspect_drift",)),
                WorkflowStep(step_id="update_docs", kind=WorkflowStepKind.AGENT, capability="implement", depends_on=("plan_docs",), parameters={"artifacts": ["patch"]}, max_attempts=2),
                WorkflowStep(step_id="verify_docs", kind=WorkflowStepKind.VERIFICATION, capability="test", depends_on=("update_docs",), parameters={"artifacts": ["verification"]}),
                _join("docs_gate", ("inspect_drift", "plan_docs", "update_docs", "verify_docs")),
            ),
        ),
    ),
    WorkflowTemplate(
        template_id="independent-patches-integration-verification",
        title="Independent patches, integration and verification",
        description="Independent patch branches fan in to integration and verification without publication side effects.",
        definition=WorkflowDefinition(
            workflow_id="independent-patches-integration-verification",
            version=1,
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            steps=(
                WorkflowStep(step_id="plan", kind=WorkflowStepKind.AGENT, capability="plan"),
                WorkflowStep(step_id="patch_a", kind=WorkflowStepKind.AGENT, capability="implement", depends_on=("plan",), max_attempts=2),
                WorkflowStep(step_id="patch_b", kind=WorkflowStepKind.AGENT, capability="implement", depends_on=("plan",), max_attempts=2),
                _join("patch_join", ("patch_a", "patch_b"), mode=JoinMode.ALL_SETTLED),
                WorkflowStep(step_id="integrate", kind=WorkflowStepKind.AGENT, capability="implement", depends_on=("patch_join",), max_attempts=2),
                WorkflowStep(step_id="verify", kind=WorkflowStepKind.VERIFICATION, capability="test", depends_on=("integrate",), max_attempts=2),
            ),
        ),
    ),
    WorkflowTemplate(
        template_id="issue-to-patch",
        title="Issue to patch",
        description="Turn an admitted issue into a reviewed local patch with explicit verification and approval gates.",
        definition=WorkflowDefinition(
            workflow_id="issue-to-patch",
            version=1,
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            steps=(
                WorkflowStep(step_id="inspect_issue", kind=WorkflowStepKind.AGENT, capability="research"),
                WorkflowStep(step_id="plan_patch", kind=WorkflowStepKind.AGENT, capability="plan", depends_on=("inspect_issue",)),
                WorkflowStep(step_id="implement_patch", kind=WorkflowStepKind.AGENT, capability="implement", depends_on=("plan_patch",), parameters={"artifacts": ["patch"]}, max_attempts=2),
                WorkflowStep(step_id="verify_patch", kind=WorkflowStepKind.VERIFICATION, capability="test", depends_on=("implement_patch",), parameters={"artifacts": ["verification"]}, max_attempts=2),
                WorkflowStep(step_id="approve_patch", kind=WorkflowStepKind.APPROVAL, depends_on=("verify_patch",)),
                _join("completion_gate", ("inspect_issue", "plan_patch", "implement_patch", "verify_patch", "approve_patch")),
            ),
        ),
    ),
    WorkflowTemplate(
        template_id="parallel-investigation-synthesis",
        title="Parallel investigation and synthesis",
        description="Bounded fan-out investigation branches that must settle before a synthesis step.",
        definition=WorkflowDefinition(
            workflow_id="parallel-investigation-synthesis",
            version=1,
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            steps=(
                WorkflowStep(step_id="scope", kind=WorkflowStepKind.AGENT, capability="plan"),
                WorkflowStep(step_id="investigate_code", kind=WorkflowStepKind.AGENT, capability="research", depends_on=("scope",)),
                WorkflowStep(step_id="investigate_tests", kind=WorkflowStepKind.AGENT, capability="research", depends_on=("scope",)),
                WorkflowStep(step_id="investigate_docs", kind=WorkflowStepKind.AGENT, capability="research", depends_on=("scope",)),
                _join("investigation_join", ("investigate_code", "investigate_tests", "investigate_docs"), mode=JoinMode.ALL_SETTLED),
                WorkflowStep(step_id="synthesize", kind=WorkflowStepKind.AGENT, capability="plan", depends_on=("investigation_join",)),
            ),
        ),
    ),
    WorkflowTemplate(
        template_id="pr-review",
        title="Pull request review",
        description="Inspect a pull request, run targeted checks and produce review findings without publication side effects.",
        definition=WorkflowDefinition(
            workflow_id="pr-review",
            version=1,
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            steps=(
                WorkflowStep(step_id="inspect_diff", kind=WorkflowStepKind.AGENT, capability="research"),
                WorkflowStep(step_id="run_targeted_checks", kind=WorkflowStepKind.VERIFICATION, capability="test", depends_on=("inspect_diff",), parameters={"artifacts": ["verification"]}),
                WorkflowStep(step_id="review_code", kind=WorkflowStepKind.AGENT, capability="review", depends_on=("run_targeted_checks",), parameters={"artifacts": ["review"]}),
                WorkflowStep(step_id="approval_to_publish", kind=WorkflowStepKind.APPROVAL, depends_on=("review_code",)),
                _join("review_gate", ("inspect_diff", "run_targeted_checks", "review_code", "approval_to_publish")),
            ),
        ),
    ),
    WorkflowTemplate(
        template_id="research-plan-implement-test-review",
        title="Research, plan, implement, test and review",
        description="Single-agent coding flow with explicit verification and review gates before completion.",
        definition=WorkflowDefinition(
            workflow_id="research-plan-implement-test-review",
            version=1,
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            steps=(
                WorkflowStep(step_id="research", kind=WorkflowStepKind.AGENT, capability="research"),
                WorkflowStep(step_id="plan", kind=WorkflowStepKind.AGENT, capability="plan", depends_on=("research",)),
                WorkflowStep(step_id="implement", kind=WorkflowStepKind.AGENT, capability="implement", depends_on=("plan",), max_attempts=2),
                WorkflowStep(step_id="test", kind=WorkflowStepKind.VERIFICATION, capability="test", depends_on=("implement",), max_attempts=2),
                WorkflowStep(step_id="review", kind=WorkflowStepKind.AGENT, capability="review", depends_on=("test",)),
                _join("completion_gate", ("research", "plan", "implement", "test", "review")),
            ),
        ),
    ),
    WorkflowTemplate(
        template_id="scheduled-test-triage",
        title="Scheduled test triage",
        description="Run scheduled verification, triage failures and require approval before applying a repair patch.",
        definition=WorkflowDefinition(
            workflow_id="scheduled-test-triage",
            version=1,
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            steps=(
                WorkflowStep(step_id="run_scheduled_checks", kind=WorkflowStepKind.VERIFICATION, capability="test", parameters={"artifacts": ["verification"]}),
                WorkflowStep(step_id="triage_failures", kind=WorkflowStepKind.AGENT, capability="research", depends_on=("run_scheduled_checks",)),
                WorkflowStep(step_id="approve_repair", kind=WorkflowStepKind.APPROVAL, depends_on=("triage_failures",)),
                WorkflowStep(step_id="repair", kind=WorkflowStepKind.AGENT, capability="implement", depends_on=("approve_repair",), parameters={"artifacts": ["patch"]}, max_attempts=2),
                WorkflowStep(step_id="verify_repair", kind=WorkflowStepKind.VERIFICATION, capability="test", depends_on=("repair",), parameters={"artifacts": ["verification"]}, max_attempts=2),
                _join("triage_gate", ("run_scheduled_checks", "triage_failures", "approve_repair", "repair", "verify_repair")),
            ),
        ),
    ),
)


def list_workflow_templates() -> tuple[WorkflowTemplate, ...]:
    """Return built-in workflow templates ordered by template id."""

    return tuple(sorted(_BUILTIN_TEMPLATES, key=lambda item: item.template_id))


def get_workflow_template(template_id: str) -> WorkflowTemplate:
    """Return one built-in workflow template by id."""

    for template in _BUILTIN_TEMPLATES:
        if template.template_id == template_id:
            return template
    raise KeyError(template_id)


def workflow_definition_to_mapping(definition: WorkflowDefinition) -> dict[str, Any]:
    """Return a JSON-serializable workflow definition mapping."""

    return {
        "workflow_id": definition.workflow_id,
        "version": definition.version,
        "schema_version": definition.schema_version,
        "failure_policy": definition.failure_policy.value,
        "input_schema": definition.input_schema,
        "output_schema": definition.output_schema,
        "steps": [
            {
                "step_id": step.step_id,
                "kind": step.kind.value,
                "depends_on": list(step.depends_on),
                "capability": step.capability,
                "parameters": step.parameters or {},
                "join_policy": None
                if step.join_policy is None
                else {
                    "mode": step.join_policy.mode.value,
                    "failure_policy": step.join_policy.failure_policy.value,
                    "quorum": step.join_policy.quorum,
                },
                "max_attempts": step.max_attempts,
                "timeout_seconds": step.timeout_seconds,
            }
            for step in definition.steps
        ],
    }
