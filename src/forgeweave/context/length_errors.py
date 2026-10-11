"""Provider context-length failure detection and retry planning."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ContextLengthError:
    """Sanitized provider signal that the assembled prompt exceeded context limits."""

    provider: str
    model: str
    current_input_tokens: int
    message: str


@dataclass(frozen=True)
class ContextLengthRetryPlan:
    """Instruction to rebuild context under a smaller input budget."""

    target_input_budget: int
    reason: str = "PROVIDER_CONTEXT_LENGTH_EXCEEDED"


@dataclass(frozen=True)
class ContextLengthRecovery:
    """Plan retries after a provider rejects context length."""

    reduction_ratio: float = 0.75
    minimum_input_budget: int = 1024

    def __post_init__(self) -> None:
        if not 0 < self.reduction_ratio < 1:
            raise ValueError("reduction_ratio must be between 0 and 1")
        if self.minimum_input_budget < 1:
            raise ValueError("minimum_input_budget must be positive")

    def plan_retry(self, error: ContextLengthError) -> ContextLengthRetryPlan:
        """Return the next target input budget for context reassembly."""

        reduced = int(error.current_input_tokens * self.reduction_ratio)
        return ContextLengthRetryPlan(target_input_budget=max(self.minimum_input_budget, reduced))


def detect_context_length_error(
    exc: Exception,
    *,
    provider: str,
    model: str,
    current_input_tokens: int,
) -> ContextLengthError | None:
    """Classify known provider length failures without leaking raw provider payloads."""

    status_code = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    message = _sanitized_message(str(exc))
    normalized = message.lower()
    length_markers = (
        "context length",
        "maximum context",
        "context too long",
        "prompt too long",
        "token limit",
        "too many tokens",
    )
    status_allows_length = status_code in {400, 413, 422} or status_code is None
    if status_allows_length and any(marker in normalized for marker in length_markers):
        return ContextLengthError(
            provider=provider,
            model=model,
            current_input_tokens=current_input_tokens,
            message=message,
        )
    return None


def _sanitized_message(message: str) -> str:
    """Bound provider error text and avoid echoing long payloads into logs/context."""

    cleaned = " ".join(message.split())
    if len(cleaned) > 240:
        return cleaned[:237] + "..."
    return cleaned
