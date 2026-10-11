"""Safe loop diagnostics projections for local telemetry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from forgeweave.contracts import BudgetLedger, ContextManifest
from forgeweave.core.control import BudgetLimits, BudgetUsage


@dataclass(frozen=True)
class LoopDiagnostics:
    """Prompt-free diagnostic metadata for one loop turn."""

    context_manifest: ContextManifest | None = None
    budget_limits: BudgetLimits | None = None
    budget_usage: BudgetUsage | None = None
    budget_ledger: BudgetLedger | None = None
    root_budget_id: str | None = None

    def __post_init__(self) -> None:
        if self.root_budget_id is not None and not self.root_budget_id.strip():
            raise ValueError("root_budget_id must not be blank when provided")

    def to_telemetry_fields(self) -> dict[str, Any]:
        """Return a structured telemetry projection without prompt or schema bodies."""

        fields: dict[str, Any] = {}
        if self.context_manifest is not None:
            manifest = self.context_manifest
            fields.update(
                {
                    "context_request_id": manifest.request_id,
                    "context_token_estimate": manifest.token_estimate,
                    "context_span_count": len(manifest.spans),
                    "context_omitted_span_count": len(manifest.omitted_spans),
                    "context_summary_count": len(manifest.summary_lineage),
                    "context_fidelity": manifest.fidelity.value,
                    "effective_policy_hash": manifest.effective_policy_hash,
                    "effective_config_hash": manifest.effective_config_hash,
                    "workspace_revision": manifest.workspace_revision,
                    "catalog_version": manifest.catalog_version,
                    "provider": manifest.provider,
                    "model": manifest.model,
                    "adapter_version": manifest.adapter_version,
                }
            )
        if self.budget_limits is not None:
            fields.update(_budget_limit_fields(self.budget_limits))
        if self.budget_usage is not None:
            fields.update(_budget_usage_fields(self.budget_usage))
        if self.budget_ledger is not None:
            fields.update(_budget_ledger_fields(self.budget_ledger))
        if self.root_budget_id is not None:
            fields["root_budget_id"] = self.root_budget_id
        return fields


def _budget_limit_fields(limits: BudgetLimits) -> dict[str, int | float | None]:
    return {
        "budget_limit_turns": limits.max_turns,
        "budget_limit_tokens": limits.max_tokens,
        "budget_limit_tool_calls": limits.max_tool_calls,
        "budget_limit_delegation_depth": limits.max_delegation_depth,
        "budget_limit_context_tokens": limits.max_context_tokens,
        "budget_limit_wall_seconds": limits.max_wall_seconds,
    }


def _budget_usage_fields(usage: BudgetUsage) -> dict[str, int]:
    return {
        "budget_usage_turns": usage.turns,
        "budget_usage_tokens": usage.tokens,
        "budget_usage_tool_calls": usage.tool_calls,
        "budget_usage_delegation_depth": usage.delegation_depth,
        "budget_usage_context_tokens": usage.context_tokens,
    }


def _budget_ledger_fields(ledger: BudgetLedger) -> dict[str, int | float | str]:
    pending = [item for item in ledger.reservations if not item.is_reconciled]
    return {
        "budget_currency": ledger.currency,
        "budget_price_source_version": ledger.price_source_version,
        "budget_reservation_count": len(ledger.reservations),
        "budget_pending_reservation_count": len(pending),
        "budget_reserved_tokens": sum(item.estimated_tokens for item in pending),
        "budget_reserved_cost": ledger.remaining_reserved_cost,
    }
