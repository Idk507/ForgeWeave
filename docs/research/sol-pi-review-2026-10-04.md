# SoL-Pi review and ForgeWeave application

Reviewed 2026-10-04: [arXiv 2609.20519v1](https://arxiv.org/pdf/2609.20519), *SoL-Pi: Recursively Scaling Auto-Research Loops for Efficient Agent Harness*. Read methods, mechanism descriptions, evaluation tables and limitations (sections 2–3 and 5.1). This is paper evidence; its implementation repository and experiments have not been reproduced here.

## Paper findings

The study explores harness changes through isolated development loops, independent review and frozen held-out evaluation. It retains Action Fusion, Online Context Compact, ObservationPack and Evidence-Preserving Reducer. These address adjacent edit/command steps, compaction timing, repeated large outputs and verified log extraction. The compaction estimate does not separately price the summarization call. The efficiency configuration reduces EdgeBench traffic substantially, but retains about 94% of Pi's score; Terminal-Bench results solve 15 tasks versus Pi's 18. Swarm evidence uses one run per configuration. Luna serves as a reducer and swarm worker, not the main backend in the EdgeBench comparison. These results support experimentation, not guaranteed ForgeWeave quality or savings. Sections 2.1, 2.4–2.5, 3.1–3.3 and 5.1 are the relevant references.

## ForgeWeave decisions — original requirements

The following requirements extend our existing security, context and verification contracts. They are ForgeWeave design choices, not a reproduction of the paper's algorithm or thresholds. [ADR-003](../architecture/adr-003-evidence-preserving-harness-optimization.md) records the decision; SYSTEM_DESIGN section 15 specifies behavior.

- Keep lossless retained evidence separate from model-visible projections. A smaller context representation must carry a scope-bound artifact reference and rehydration path, and preserve critical constraints/failures.
- Optimize only when enabled, budgeted and locally measured. Auxiliary inference needs task permission, provider eligibility and aggregate spend accounting; using Luna to build this project does not automatically configure a runtime reducer model.
- An edit/check sequence is orchestration over two ordinary authorized actions. It is not a shell-command suffix that inherits patch approval, nor an atomic transaction promising rollback.
- Protect release evaluation from optimizer access. Freeze code, config, criteria and corpus revision; failed final evaluation rejects that candidate. Subsequent development uses a new candidate and fresh held-out evidence instead of tuning to the same final tests.
- Retain diagnostic artifacts, per-feature toggles, candidate lineage and rollback to a known verified harness configuration. Shipping depends on required behavior and Windows checks, then measured efficiency, not minimum tokens alone.

## Scope and evidence to collect

M1 establishes baseline observation/evidence identity. M2 evaluates observation projections, optional validated extraction, separately authorized action sequences and cache-aware compaction. M3 evaluates worker evidence exchange using existing fan-in contracts. M6 freezes a release candidate and evaluates representative repository tasks, supported hosts, fault recovery, privacy and cost. Optional harness auto-research is a development workflow after these foundations, not a self-modifying production loop.

Record uncompressed baseline, feature-alone runs and combined runs against the same task revisions and model settings. Include acceptance/regression outcomes, context omissions, source rehydrations, billed and estimated tokens, all auxiliary calls, cache effects, elapsed time and interruptions. Unknown usage or pricing remains unknown/conservatively reserved. Runtime improvement thresholds require a written evaluation profile before experiments; no unmeasured threshold is described as passed.
