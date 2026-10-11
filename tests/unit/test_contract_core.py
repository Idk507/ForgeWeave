from __future__ import annotations

import unittest
from datetime import UTC, datetime

from pydantic import ValidationError

from forgeweave.contracts import (
    ActorKind,
    Artifact,
    ArtifactKind,
    Attempt,
    AttemptStatus,
    EffectSet,
    Event,
    EventKind,
    PolicyDecision,
    PolicyOutcome,
    Session,
    Step,
    StepStatus,
    Task,
    TaskStatus,
    ToolCall,
    ToolFailure,
    ToolResult,
    ToolSpec,
    Turn,
    TurnRole,
    Worktree,
    WorktreeState,
)


class CoreContractTests(unittest.TestCase):
    def test_task_and_attempt_lifecycle_values_are_validated(self) -> None:
        task = Task(task_id="task-1", title="Fix failing test", status=TaskStatus.CREATED)
        attempt = Attempt(attempt_id="attempt-1", task_id=task.task_id, status=AttemptStatus.PREPARING)

        self.assertEqual(task.schema_version, "task.v1")
        self.assertEqual(attempt.task_id, "task-1")

        with self.assertRaises(ValidationError):
            Task(task_id="task-2", title=" ", status=TaskStatus.CREATED)

    def test_event_requires_canonical_identity_fields(self) -> None:
        event = Event(
            event_id="evt-1",
            task_id="task-1",
            attempt_id="attempt-1",
            sequence=1,
            actor=ActorKind.SYSTEM,
            kind=EventKind.TASK_CREATED,
            correlation_id="corr-1",
            payload_ref="artifact://payload",
        )

        self.assertEqual(event.schema_version, "event.v1")
        self.assertEqual(event.occurred_at.tzinfo, UTC)

        with self.assertRaises(ValidationError):
            Event(
                event_id="evt-2",
                task_id="task-1",
                attempt_id="attempt-1",
                sequence=0,
                actor=ActorKind.SYSTEM,
                kind=EventKind.TASK_CREATED,
                correlation_id="corr-1",
                payload_ref="artifact://payload",
            )

    def test_tool_contracts_bind_arguments_effects_and_outcomes(self) -> None:
        spec = ToolSpec(
            name="read_file",
            schema_version="read-file.v1",
            description="Read one file.",
            input_schema={"type": "object"},
            effects=EffectSet(reads=frozenset({"workspace"})),
        )
        call = ToolCall(
            call_id="call-1",
            tool_name=spec.name,
            tool_schema_version=spec.schema_version,
            arguments={"path": "README.md"},
            argument_hash="sha256:args",
            effects=spec.effects,
        )
        result = ToolResult(call_id=call.call_id, output_ref="artifact://out", output_hash="sha256:out")
        failure = ToolFailure(call_id=call.call_id, error_type="NotFound", message="missing")

        self.assertTrue(spec.effects.is_read_only)
        self.assertEqual(call.effect_hash, spec.effects.fingerprint)
        self.assertEqual(result.call_id, "call-1")
        self.assertEqual(failure.error_type, "NotFound")

    def test_policy_decision_records_allow_deny_or_ask(self) -> None:
        decision = PolicyDecision(
            decision_id="decision-1",
            task_id="task-1",
            attempt_id="attempt-1",
            tool_call_id="call-1",
            outcome=PolicyOutcome.ALLOW,
            reason="read-only tool",
            policy_revision="policy-1",
        )

        self.assertEqual(decision.outcome, PolicyOutcome.ALLOW)

        with self.assertRaises(ValidationError):
            PolicyDecision(
                decision_id="decision-2",
                task_id="task-1",
                attempt_id="attempt-1",
                tool_call_id="call-1",
                outcome=PolicyOutcome.DENY,
                reason="",
                policy_revision="policy-1",
            )

    def test_session_turn_step_artifact_and_worktree_contracts(self) -> None:
        session = Session(session_id="session-1", task_id="task-1")
        turn = Turn(
            turn_id="turn-1",
            task_id="task-1",
            attempt_id="attempt-1",
            role=TurnRole.USER,
            content_ref="artifact://prompt",
            context_manifest_id="manifest-1",
        )
        step = Step(step_id="step-1", task_id="task-1", attempt_id="attempt-1", status=StepStatus.PENDING)
        artifact = Artifact(
            artifact_id="artifact-1",
            task_id="task-1",
            kind=ArtifactKind.TEXT,
            uri="artifact://artifact-1",
            sha256="abc123",
            size_bytes=10,
        )
        worktree = Worktree(
            worktree_id="wt-1",
            task_id="task-1",
            repository_path="C:/repo",
            worktree_path="C:/repo-wt",
            base_commit="abc123",
            branch="fw/task-1-fix",
            state=WorktreeState.ACTIVE,
        )

        self.assertEqual(session.task_id, "task-1")
        self.assertEqual(turn.role, TurnRole.USER)
        self.assertEqual(step.status, StepStatus.PENDING)
        self.assertFalse(artifact.redacted)
        self.assertEqual(worktree.branch, "fw/task-1-fix")

    def test_models_are_immutable(self) -> None:
        task = Task(task_id="task-1", title="Immutable", status=TaskStatus.CREATED)

        with self.assertRaises(ValidationError):
            task.status = TaskStatus.RUNNING  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
