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


_BUILTIN_TEMPLATES: tuple[WorkflowTemplate, ...] = (
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
                WorkflowStep(
                    step_id="completion_gate",
                    kind=WorkflowStepKind.JOIN,
                    depends_on=("research", "plan", "implement", "test", "review"),
                    join_policy=JoinPolicy(mode=JoinMode.ALL_SUCCESS),
                ),
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
                WorkflowStep(
                    step_id="investigation_join",
                    kind=WorkflowStepKind.JOIN,
                    depends_on=("investigate_code", "investigate_tests", "investigate_docs"),
                    join_policy=JoinPolicy(mode=JoinMode.ALL_SETTLED),
                ),
                WorkflowStep(step_id="synthesize", kind=WorkflowStepKind.AGENT, capability="plan", depends_on=("investigation_join",)),
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
                WorkflowStep(
                    step_id="patch_join",
                    kind=WorkflowStepKind.JOIN,
                    depends_on=("patch_a", "patch_b"),
                    join_policy=JoinPolicy(mode=JoinMode.ALL_SETTLED),
                ),
                WorkflowStep(step_id="integrate", kind=WorkflowStepKind.AGENT, capability="implement", depends_on=("patch_join",), max_attempts=2),
                WorkflowStep(step_id="verify", kind=WorkflowStepKind.VERIFICATION, capability="test", depends_on=("integrate",), max_attempts=2),
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
