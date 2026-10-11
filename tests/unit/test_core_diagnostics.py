from __future__ import annotations

import unittest

from forgeweave.contracts import BudgetLedger, BudgetReservation, ContextManifest
from forgeweave.core import BudgetLimits, BudgetUsage, LoopDiagnostics


class LoopDiagnosticsTests(unittest.TestCase):
    def test_projects_context_catalog_config_and_budget_without_prompt_text(self) -> None:
        diagnostics = LoopDiagnostics(
            context_manifest=_manifest(),
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
                    BudgetReservation(
                        reservation_id="reserve-2",
                        purpose="model-stream",
                        estimated_tokens=25,
                        estimated_cost=0.05,
                        actual_tokens=20,
                        actual_cost=0.04,
                    ),
                ),
            ),
            root_budget_id="root-budget-1",
        )

        fields = diagnostics.to_telemetry_fields()

        self.assertEqual(fields["context_request_id"], "ctx-1")
        self.assertEqual(fields["context_token_estimate"], 512)
        self.assertEqual(fields["catalog_version"], "tools-v1")
        self.assertEqual(fields["effective_config_hash"], "sha256:config")
        self.assertEqual(fields["budget_usage_tokens"], 250)
        self.assertEqual(fields["budget_limit_tokens"], 1000)
        self.assertEqual(fields["budget_reserved_tokens"], 100)
        self.assertEqual(fields["budget_reserved_cost"], 0.10)
        self.assertEqual(fields["root_budget_id"], "root-budget-1")
        self.assertNotIn("latest_user_request", fields)
        self.assertNotIn("prompt", fields)

    def test_blank_root_budget_id_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            LoopDiagnostics(root_budget_id=" ")


def _manifest() -> ContextManifest:
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
