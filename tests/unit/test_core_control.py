from __future__ import annotations

import unittest

from forgeweave.core import (
    BudgetExceeded,
    BudgetGuard,
    BudgetLimits,
    BudgetUsage,
    CancellationToken,
    ModelStreamAccumulator,
)
from forgeweave.models import ModelChunk


class CancellationTokenTests(unittest.TestCase):
    def test_cancellation_token_records_reason_and_raises(self) -> None:
        token = CancellationToken()

        token.cancel("user interrupted")

        self.assertTrue(token.cancelled)
        self.assertEqual(token.reason, "user interrupted")
        with self.assertRaises(InterruptedError):
            token.raise_if_cancelled()

    def test_stream_accumulator_stops_when_cancelled_before_tool_parse(self) -> None:
        token = CancellationToken()
        accumulator = ModelStreamAccumulator()

        def chunks() -> list[ModelChunk]:
            token.cancel("stop before dispatch")
            return [
                ModelChunk(
                    kind="tool_call",
                    call_id="call-1",
                    content='{"tool_name":"read_file","tool_schema_version":"read.v1","arguments":{}}',
                ),
                ModelChunk(kind="done"),
            ]

        with self.assertRaises(InterruptedError):
            accumulator.consume(chunks(), cancellation=token)


class BudgetGuardTests(unittest.TestCase):
    def test_allows_usage_inside_limits(self) -> None:
        guard = BudgetGuard(
            BudgetLimits(
                max_turns=2,
                max_tokens=100,
                max_tool_calls=3,
                max_delegation_depth=1,
                max_context_tokens=50,
                max_wall_seconds=10,
            ),
            now=lambda: 100.0,
        )

        usage = BudgetUsage(turns=1, tokens=30, tool_calls=2, delegation_depth=1, context_tokens=40)

        guard.check(usage, now=105.0)

    def test_blocks_each_discrete_limit_with_structured_code(self) -> None:
        limits = BudgetLimits(max_turns=1, max_tokens=10, max_tool_calls=1, max_delegation_depth=0, max_context_tokens=20)
        cases = [
            (BudgetUsage(turns=2), "TURN_BUDGET_EXCEEDED"),
            (BudgetUsage(tokens=11), "TOKEN_BUDGET_EXCEEDED"),
            (BudgetUsage(tool_calls=2), "TOOL_CALL_BUDGET_EXCEEDED"),
            (BudgetUsage(delegation_depth=1), "DELEGATION_DEPTH_EXCEEDED"),
            (BudgetUsage(context_tokens=21), "CONTEXT_BUDGET_EXCEEDED"),
        ]

        for usage, code in cases:
            with self.subTest(code=code), self.assertRaises(BudgetExceeded) as raised:
                BudgetGuard(limits).check(usage)
            self.assertEqual(raised.exception.code, code)

    def test_blocks_wall_clock_limit(self) -> None:
        guard = BudgetGuard(BudgetLimits(max_wall_seconds=5), now=lambda: 10.0)

        with self.assertRaises(BudgetExceeded) as raised:
            guard.check(BudgetUsage(), now=16.0)

        self.assertEqual(raised.exception.code, "WALL_TIME_BUDGET_EXCEEDED")

    def test_usage_adds_model_and_tool_costs_without_mutation(self) -> None:
        usage = BudgetUsage().record_model_usage(tokens=7).record_tool_call()

        self.assertEqual(usage.tokens, 7)
        self.assertEqual(usage.tool_calls, 1)
        self.assertEqual(BudgetUsage().tokens, 0)


if __name__ == "__main__":
    unittest.main()
