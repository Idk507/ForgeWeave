"""Provider-aware context assembly with protected span preservation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from forgeweave.context.instructions import ResolvedInstruction, content_hash, estimate_tokens
from forgeweave.contracts import ConstraintLedger, ContextManifest, ContextSpan, FidelityMode


class ContextFitError(ValueError):
    """Raised when protected context cannot fit a provider request budget."""

    def __init__(self, code: str, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


@dataclass(frozen=True)
class ContextBudget:
    """Provider context window minus reserves needed for safe execution."""

    provider_context_window: int
    output_reserve: int
    tool_result_reserve: int
    safety_margin: int

    @property
    def input_budget(self) -> int:
        return self.provider_context_window - self.output_reserve - self.tool_result_reserve - self.safety_margin


@dataclass(frozen=True)
class ContextItem:
    """Candidate item for model context assembly."""

    item_id: str
    source: str
    authority: str
    text: str
    token_estimate: int | None = None
    sensitivity: str = "normal"
    priority: int = 0
    protected: bool = False
    redacted: bool = False


@dataclass(frozen=True)
class ContextPacket:
    """Selected text plus the replay manifest for one model request."""

    manifest: ContextManifest
    text_by_span_id: dict[str, str]


class ContextAssembler:
    """Build a bounded context packet without dropping protected requirements."""

    def assemble(
        self,
        *,
        request_id: str,
        task_id: str,
        attempt_id: str,
        provider: str,
        model: str,
        adapter_version: str,
        effective_policy_hash: str,
        effective_config_hash: str,
        workspace_revision: str,
        catalog_version: str,
        latest_user_request: str,
        constraint_ledger: ConstraintLedger,
        instructions: tuple[ResolvedInstruction, ...] | list[ResolvedInstruction],
        optional_items: tuple[ContextItem, ...] | list[ContextItem],
        budget: ContextBudget,
        fidelity: FidelityMode = FidelityMode.REDACTED,
        summary_lineage: tuple[str, ...] = (),
    ) -> ContextPacket:
        """Assemble protected and optional spans under the provider input budget."""

        input_budget = budget.input_budget
        if input_budget <= 0:
            raise ContextFitError(
                "CONTEXT_UNSATISFIABLE",
                "provider context window is exhausted by output, tool-result and safety reserves",
                details={
                    "provider_context_window": budget.provider_context_window,
                    "output_reserve": budget.output_reserve,
                    "tool_result_reserve": budget.tool_result_reserve,
                    "safety_margin": budget.safety_margin,
                    "input_budget": input_budget,
                },
            )

        protected_items = [
            self._latest_request_item(latest_user_request),
            *self._constraint_items(constraint_ledger),
            *(self._instruction_item(instruction) for instruction in instructions if instruction.protected),
        ]
        selectable_items = [
            *(self._instruction_item(instruction) for instruction in instructions if not instruction.protected),
            *optional_items,
        ]

        protected_total = sum(self._tokens(item) for item in protected_items)
        if protected_total > input_budget:
            raise ContextFitError(
                "CONTEXT_UNSATISFIABLE",
                "protected context cannot fit within the provider input budget",
                details={"input_budget": input_budget, "protected_tokens": protected_total},
            )

        selected: list[ContextItem] = list(protected_items)
        omitted: list[str] = []
        used = protected_total
        for item in sorted(selectable_items, key=lambda candidate: (-candidate.priority, candidate.item_id)):
            item_tokens = self._tokens(item)
            if used + item_tokens <= input_budget:
                selected.append(item)
                used += item_tokens
            else:
                omitted.append(item.item_id)

        spans = tuple(self._span(item) for item in selected)
        manifest = ContextManifest(
            request_id=request_id,
            task_id=task_id,
            attempt_id=attempt_id,
            provider=provider,
            model=model,
            adapter_version=adapter_version,
            effective_policy_hash=effective_policy_hash,
            effective_config_hash=effective_config_hash,
            workspace_revision=workspace_revision,
            catalog_version=catalog_version,
            spans=spans,
            omitted_spans=tuple(omitted),
            summary_lineage=summary_lineage,
            token_estimate=sum(span.token_estimate for span in spans),
            fidelity=fidelity,
        )
        return ContextPacket(manifest=manifest, text_by_span_id={item.item_id: item.text for item in selected})

    @staticmethod
    def _latest_request_item(text: str) -> ContextItem:
        cleaned = text.strip()
        if not cleaned:
            raise ValueError("latest_user_request must not be blank")
        return ContextItem(
            item_id="latest-user-request",
            source="user:latest-request",
            authority="task",
            text=cleaned,
            protected=True,
            priority=10_000,
        )

    @staticmethod
    def _constraint_items(ledger: ConstraintLedger) -> tuple[ContextItem, ...]:
        return tuple(
            ContextItem(
                item_id=f"constraint:{criterion.criterion_id}",
                source=criterion.origin,
                authority=criterion.authority,
                text=criterion.text,
                protected=True,
                priority=9_000,
            )
            for criterion in ledger.constraints
            if criterion.criterion_id in ledger.active_ids
        )

    @staticmethod
    def _instruction_item(instruction: ResolvedInstruction) -> ContextItem:
        return ContextItem(
            item_id=instruction.span_id,
            source=instruction.source,
            authority=instruction.authority,
            text=instruction.text,
            token_estimate=instruction.token_estimate,
            sensitivity=instruction.sensitivity,
            priority=8_000 - instruction.precedence,
            protected=instruction.protected,
        )

    @staticmethod
    def _tokens(item: ContextItem) -> int:
        token_estimate = item.token_estimate if item.token_estimate is not None else estimate_tokens(item.text)
        if token_estimate <= 0:
            raise ValueError(f"context item token estimate must be positive: {item.item_id}")
        return token_estimate

    def _span(self, item: ContextItem) -> ContextSpan:
        return ContextSpan(
            span_id=item.item_id,
            source=item.source,
            source_hash=content_hash(item.text),
            authority=item.authority,
            sensitivity=item.sensitivity,
            token_estimate=self._tokens(item),
            redacted=item.redacted,
        )
