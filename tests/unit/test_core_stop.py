from __future__ import annotations

import unittest

from forgeweave.contracts import PolicyOutcome
from forgeweave.core import BudgetExceeded, CancellationToken, StopEvaluator, StopReason


class StopEvaluatorTests(unittest.TestCase):
    def test_stops_for_final_answer_without_tool_requests(self) -> None:
        decision = StopEvaluator().after_model_turn(text="done", tool_request_count=0, pending_approval=False)

        self.assertEqual(decision.reason, StopReason.FINAL_ANSWER)
        self.assertTrue(decision.should_stop)

    def test_continues_when_tool_requests_exist(self) -> None:
        decision = StopEvaluator().after_model_turn(text="", tool_request_count=1, pending_approval=False)

        self.assertEqual(decision.reason, StopReason.CONTINUE)
        self.assertFalse(decision.should_stop)

    def test_waits_for_approval(self) -> None:
        decision = StopEvaluator().after_policy_decisions([PolicyOutcome.ASK])

        self.assertEqual(decision.reason, StopReason.WAITING_APPROVAL)
        self.assertTrue(decision.should_stop)

    def test_cancellation_maps_to_cancelled_stop(self) -> None:
        token = CancellationToken()
        token.cancel("user requested stop")

        decision = StopEvaluator().from_cancellation(token)

        self.assertEqual(decision.reason, StopReason.CANCELLED)
        self.assertEqual(decision.details["message"], "user requested stop")

    def test_budget_error_maps_to_budget_stop(self) -> None:
        error = BudgetExceeded("TOKEN_BUDGET_EXCEEDED", "token budget exceeded", limit=100, actual=101)

        decision = StopEvaluator().from_budget_error(error)

        self.assertEqual(decision.reason, StopReason.BUDGET_EXCEEDED)
        self.assertEqual(decision.details["code"], "TOKEN_BUDGET_EXCEEDED")
        self.assertEqual(decision.details["limit"], 100)
        self.assertEqual(decision.details["actual"], 101)


if __name__ == "__main__":
    unittest.main()
