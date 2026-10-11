from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
import tempfile
import unittest

from forgeweave.contracts import ApprovalGrant, EffectSet, PolicyOutcome, ToolCall
from forgeweave.policy import (
    ApprovalRequired,
    InMemoryApprovalStore,
    PolicyGateway,
    PolicyRule,
    RevalidationError,
    SQLiteApprovalStore,
)


class PolicyGatewayTests(unittest.TestCase):
    def test_read_only_call_is_allowed_without_approval(self) -> None:
        gateway = PolicyGateway(policy_revision="policy-v1")
        call = ToolCall(
            call_id="call-1",
            tool_name="read_file",
            tool_schema_version="read-file.v1",
            arguments={"path": "README.md"},
            argument_hash="sha256:readme",
            effects=EffectSet(reads=frozenset({"README.md"})),
        )

        decision = gateway.authorize(
            task_id="task-1",
            attempt_id="attempt-1",
            call=call,
            workspace_precondition_hash="sha256:workspace",
        )

        self.assertEqual(decision.outcome, PolicyOutcome.ALLOW)
        self.assertEqual(decision.reason, "read-only tool call allowed")
        self.assertIsNone(decision.approval_grant_id)

    def test_deny_rule_wins_before_approval(self) -> None:
        gateway = PolicyGateway(
            policy_revision="policy-v1",
            rules=(PolicyRule(tool_name="delete_file", outcome=PolicyOutcome.DENY, reason="destructive tool disabled"),),
        )
        call = ToolCall(
            call_id="call-1",
            tool_name="delete_file",
            tool_schema_version="delete-file.v1",
            arguments={"path": "src/app.py"},
            argument_hash="sha256:delete",
            effects=EffectSet(writes=frozenset({"src/app.py"})),
        )

        decision = gateway.authorize(
            task_id="task-1",
            attempt_id="attempt-1",
            call=call,
            workspace_precondition_hash="sha256:workspace",
        )

        self.assertEqual(decision.outcome, PolicyOutcome.DENY)
        self.assertEqual(decision.reason, "destructive tool disabled")

    def test_state_changing_call_asks_when_no_matching_grant_exists(self) -> None:
        gateway = PolicyGateway(policy_revision="policy-v1")
        call = ToolCall(
            call_id="call-1",
            tool_name="patch_file",
            tool_schema_version="patch-file.v1",
            arguments={"path": "src/app.py"},
            argument_hash="sha256:patch",
            effects=EffectSet(writes=frozenset({"src/app.py"})),
        )

        decision = gateway.authorize(
            task_id="task-1",
            attempt_id="attempt-1",
            call=call,
            workspace_precondition_hash="sha256:workspace",
        )

        self.assertEqual(decision.outcome, PolicyOutcome.ASK)
        self.assertEqual(decision.reason, "approval required for state-changing tool call")

    def test_matching_approval_is_consumed_once_and_bound_to_action_shape(self) -> None:
        store = InMemoryApprovalStore()
        gateway = PolicyGateway(policy_revision="policy-v1", approvals=store)
        call = ToolCall(
            call_id="call-1",
            tool_name="patch_file",
            tool_schema_version="patch-file.v1",
            arguments={"path": "src/app.py"},
            argument_hash="sha256:patch",
            effects=EffectSet(writes=frozenset({"src/app.py"})),
        )
        store.put(
            ApprovalGrant(
                grant_id="grant-1",
                task_id="task-1",
                attempt_id="attempt-1",
                tool_name=call.tool_name,
                tool_schema_version=call.tool_schema_version,
                catalog_version="tools-v1",
                argument_hash=call.argument_hash,
                effect_hash=call.effect_hash,
                workspace_precondition_hash="sha256:workspace",
                policy_revision="policy-v1",
                human_actor="user",
                expires_at=datetime.now(UTC) + timedelta(minutes=5),
            )
        )

        allowed = gateway.authorize(
            task_id="task-1",
            attempt_id="attempt-1",
            call=call,
            workspace_precondition_hash="sha256:workspace",
            catalog_version="tools-v1",
        )
        repeated = gateway.authorize(
            task_id="task-1",
            attempt_id="attempt-1",
            call=call,
            workspace_precondition_hash="sha256:workspace",
            catalog_version="tools-v1",
        )

        self.assertEqual(allowed.outcome, PolicyOutcome.ALLOW)
        self.assertEqual(allowed.approval_grant_id, "grant-1")
        self.assertEqual(repeated.outcome, PolicyOutcome.ASK)

    def test_sqlite_approval_store_persists_and_consumes_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            db_path = Path(root) / "approvals.db"
            call = ToolCall(
                call_id="call-1",
                tool_name="patch_file",
                tool_schema_version="patch-file.v1",
                arguments={"path": "src/app.py"},
                argument_hash="sha256:patch",
                effects=EffectSet(writes=frozenset({"src/app.py"})),
            )
            stored = SQLiteApprovalStore.open(db_path)
            stored.put(
                ApprovalGrant(
                    grant_id="grant-1",
                    task_id="task-1",
                    attempt_id="attempt-1",
                    tool_name=call.tool_name,
                    tool_schema_version=call.tool_schema_version,
                    catalog_version="tools-v1",
                    argument_hash=call.argument_hash,
                    effect_hash=call.effect_hash,
                    workspace_precondition_hash="sha256:workspace",
                    policy_revision="policy-v1",
                    human_actor="user",
                    expires_at=datetime.now(UTC) + timedelta(minutes=5),
                )
            )
            stored.close()

            reopened = SQLiteApprovalStore.open(db_path)
            try:
                gateway = PolicyGateway(policy_revision="policy-v1", approvals=reopened)

                allowed = gateway.authorize(
                    task_id="task-1",
                    attempt_id="attempt-1",
                    call=call,
                    workspace_precondition_hash="sha256:workspace",
                    catalog_version="tools-v1",
                )
                repeated = gateway.authorize(
                    task_id="task-1",
                    attempt_id="attempt-1",
                    call=call,
                    workspace_precondition_hash="sha256:workspace",
                    catalog_version="tools-v1",
                )

                self.assertEqual(allowed.outcome, PolicyOutcome.ALLOW)
                self.assertEqual(repeated.outcome, PolicyOutcome.ASK)
            finally:
                reopened.close()

    def test_dispatch_revalidation_rejects_changed_workspace_policy_or_call(self) -> None:
        gateway = PolicyGateway(policy_revision="policy-v1")
        call = ToolCall(
            call_id="call-1",
            tool_name="read_file",
            tool_schema_version="read-file.v1",
            arguments={"path": "README.md"},
            argument_hash="sha256:readme",
            effects=EffectSet(reads=frozenset({"README.md"})),
        )
        decision = gateway.authorize(
            task_id="task-1",
            attempt_id="attempt-1",
            call=call,
            workspace_precondition_hash="sha256:workspace",
        )
        changed_call = call.model_copy(update={"argument_hash": "sha256:changed"})

        gateway.revalidate_for_dispatch(
            decision=decision,
            call=call,
            workspace_precondition_hash="sha256:workspace",
        )

        with self.assertRaises(RevalidationError):
            gateway.revalidate_for_dispatch(
                decision=decision,
                call=changed_call,
                workspace_precondition_hash="sha256:workspace",
            )

        with self.assertRaises(RevalidationError):
            gateway.revalidate_for_dispatch(
                decision=decision,
                call=call,
                workspace_precondition_hash="sha256:changed",
            )

        newer_gateway = PolicyGateway(policy_revision="policy-v2")
        with self.assertRaises(RevalidationError):
            newer_gateway.revalidate_for_dispatch(
                decision=decision,
                call=call,
                workspace_precondition_hash="sha256:workspace",
            )

    def test_dispatch_revalidation_requires_allow_decision(self) -> None:
        gateway = PolicyGateway(policy_revision="policy-v1")
        call = ToolCall(
            call_id="call-1",
            tool_name="patch_file",
            tool_schema_version="patch-file.v1",
            arguments={"path": "src/app.py"},
            argument_hash="sha256:patch",
            effects=EffectSet(writes=frozenset({"src/app.py"})),
        )
        decision = gateway.authorize(
            task_id="task-1",
            attempt_id="attempt-1",
            call=call,
            workspace_precondition_hash="sha256:workspace",
        )

        with self.assertRaises(ApprovalRequired):
            gateway.revalidate_for_dispatch(
                decision=decision,
                call=call,
                workspace_precondition_hash="sha256:workspace",
            )


if __name__ == "__main__":
    unittest.main()
