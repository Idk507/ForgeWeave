# ADR-004: Independent native coding CLI and evidence-based delivery

Status: Accepted
Date: 2026-11-01

## Context

The user wants an independently implemented coding CLI comparable in practical use to Codex, Claude Code and OpenCode. A sequence of isolated helper modules and optional vendor-engine adapters has obscured the missing native end-to-end path. The current research is recorded in [source review](../research/native-cli-source-review-2026-11-01.md).

## Decision

ForgeWeave implements and owns the complete Python runtime: task/session lifecycle, conversation, model/tool loop, context, permissions, process control, workspaces, independent verification, recovery and diagnostics. Reference harnesses supply public design evidence; they are neither combined nor required to perform tasks. Comparable workflows are a target; identical proprietary behavior and superior performance are not asserted.

Existing `engines` scaffolding and optional extras are experimental legacy work, outside the active product and release gates. Preserve it without expanding or wiring it into native commands. A future request to ship delegated engines requires a separate decision. Provider adapters still call user-selected model APIs; a provider is not an agent runtime.

SYSTEM_DESIGN section 16 defines the composition root and execution contracts. Todo N-series orders complete user outcomes, using existing M-series owners and requirements. No file count or arbitrary patch-size target may split an acceptance scenario into endless unconnected helpers. Each checkpoint must show reachable CLI behavior and real workspace evidence.

## Consequences

M1 reliability closes before extensions; interactive usability follows the same runtime rather than a second implementation. External engine tasks are historical research only and cannot block native release. Hooks and plugin registrations remain scoped, while policy, root budgets, execution identity and release validators remain authoritative. Cache stability, deferred discovery and batching require controlled quality/cost experiments before default enablement.

This supersedes engine-delivery recommendations in plan section 4.1 and its M2 gate. Existing security, context, memory, browser/search, delegation, workflow, Ralph and release-evidence requirements remain. Old source-review dates and passed test evidence are not rewritten as new proof.
