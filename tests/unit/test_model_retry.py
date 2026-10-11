from __future__ import annotations

import unittest

from forgeweave.models.retry import RetryPolicy, RetryableModelError, call_with_retries


class RetryPolicyTests(unittest.TestCase):
    def test_retries_retryable_errors_with_capped_jittered_delays(self) -> None:
        calls: list[int] = []
        delays: list[float] = []

        def operation() -> str:
            calls.append(1)
            if len(calls) < 3:
                raise RetryableModelError("rate limit")
            return "ok"

        result = call_with_retries(
            operation,
            policy=RetryPolicy(max_attempts=4, initial_delay_seconds=1.0, max_delay_seconds=3.0, jitter_ratio=0.5),
            sleep=delays.append,
            jitter=lambda attempt: 1.0,
        )

        self.assertEqual(result, "ok")
        self.assertEqual(len(calls), 3)
        self.assertEqual(delays, [1.5, 3.0])

    def test_stops_after_max_attempts(self) -> None:
        calls: list[int] = []

        def operation() -> str:
            calls.append(1)
            raise RetryableModelError("temporary outage")

        with self.assertRaises(RetryableModelError):
            call_with_retries(
                operation,
                policy=RetryPolicy(max_attempts=2, initial_delay_seconds=0.1, max_delay_seconds=1.0, jitter_ratio=0.0),
                sleep=lambda delay: None,
                jitter=lambda attempt: 0.0,
            )

        self.assertEqual(len(calls), 2)

    def test_non_retryable_errors_are_not_retried(self) -> None:
        calls: list[int] = []

        def operation() -> str:
            calls.append(1)
            raise ValueError("bad request")

        with self.assertRaises(ValueError):
            call_with_retries(operation, policy=RetryPolicy(max_attempts=4), sleep=lambda delay: None)

        self.assertEqual(len(calls), 1)

    def test_policy_rejects_invalid_attempt_count(self) -> None:
        with self.assertRaises(ValueError):
            RetryPolicy(max_attempts=0)


if __name__ == "__main__":
    unittest.main()
