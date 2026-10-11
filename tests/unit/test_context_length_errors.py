from __future__ import annotations

import unittest

from forgeweave.context import ContextLengthError, ContextLengthRecovery, detect_context_length_error


class ContextLengthRecoveryTests(unittest.TestCase):
    def test_detects_provider_length_error_from_status_and_message(self) -> None:
        error = _ProviderError("maximum context length exceeded", status_code=400)

        detected = detect_context_length_error(error, provider="openai-compatible", model="gpt-4o", current_input_tokens=120_000)

        self.assertIsInstance(detected, ContextLengthError)
        self.assertEqual(detected.provider, "openai-compatible")
        self.assertEqual(detected.model, "gpt-4o")
        self.assertEqual(detected.current_input_tokens, 120_000)
        self.assertNotIn("secret", detected.message.lower())

    def test_ignores_unrelated_provider_error(self) -> None:
        error = _ProviderError("invalid api key", status_code=401)

        self.assertIsNone(detect_context_length_error(error, provider="openai-compatible", model="gpt-4o", current_input_tokens=100))

    def test_recovery_reduces_budget_by_ratio_and_floor(self) -> None:
        error = ContextLengthError(
            provider="provider",
            model="model",
            current_input_tokens=10_000,
            message="context too long",
        )

        recovery = ContextLengthRecovery(reduction_ratio=0.5, minimum_input_budget=2048).plan_retry(error)

        self.assertEqual(recovery.target_input_budget, 5000)
        self.assertEqual(recovery.reason, "PROVIDER_CONTEXT_LENGTH_EXCEEDED")

    def test_recovery_respects_minimum_budget_floor(self) -> None:
        error = ContextLengthError(provider="provider", model="model", current_input_tokens=1000, message="too long")

        recovery = ContextLengthRecovery(reduction_ratio=0.5, minimum_input_budget=2048).plan_retry(error)

        self.assertEqual(recovery.target_input_budget, 2048)


class _ProviderError(Exception):
    def __init__(self, message: str, *, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


if __name__ == "__main__":
    unittest.main()
