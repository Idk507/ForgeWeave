# ADR-003: Evidence-preserving harness optimization and release evaluation

## Status
Accepted for design and evaluation scope; optimizations remain gated until tested.

## Date
2026-10-04

## Context
The user requested review of arXiv 2609.20519. Existing contracts protect context and auditability, but do not explicitly define optimization experiments, output projections, auxiliary evidence validation or a frozen release-candidate evaluation boundary. See [paper review](../research/sol-pi-review-2026-10-04.md).

## Decision
Add SYSTEM_DESIGN section 15 and canonical P-series tasks. Preserve original evidence, protected constraints, action-level authorization and native Windows reliability. Introduce optional output projections and validated auxiliary extraction; separately authorized edit/check sequences; provider-aware compaction accounting; and immutable candidate/evaluation profiles. Test each optimization independently and together. Required capability gates precede efficiency acceptance. Production tasks cannot rewrite the harness, policies, evaluator or release criteria.

## Alternatives considered
Automatically enabling all paper mechanisms would import unvalidated quality tradeoffs and model assumptions. Unchecked summaries would undermine evidence. Combined tools with inherited permission would weaken the gateway. Selecting by token reduction alone would ignore correctness and auxiliary cost. Reusing final evaluation feedback for tuning would weaken claims of generalization.

## Consequences
Baseline evidence fixtures join M1. Optional optimizations follow in M2; worker evidence exchange follows in M3; isolated auto-research workflows remain later development tooling. M6 adds explicit freeze, release evaluation and rollback artifacts. No vendor package is installed and no reported benchmark gain becomes a ForgeWeave guarantee. User choice of Luna as the build model is preserved without changing runtime model configuration. ADR-001 and ADR-002 remain in force.

## Evidence
[Paper](https://arxiv.org/pdf/2609.20519), [review](../research/sol-pi-review-2026-10-04.md), [architecture](../../SYSTEM_DESIGN.md#15-evidence-preserving-optimization-and-shipping-contracts), [todo](../../todo.md).
