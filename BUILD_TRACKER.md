# ForgeWeave build tracker

Date started: 2026-10-02

This file tracks the concrete implementation slices I am going to build next. It is a working ledger, not a replacement for [todo.md](todo.md), [plan.md](plan.md), [AGENTS.md](AGENTS.md), or [SYSTEM_DESIGN.md](SYSTEM_DESIGN.md). The source checklist IDs stay canonical; this file records the active build order, acceptance evidence, and current status.

## Rules for this tracker

- Work one small slice at a time.
- Before editing, record the owning module, acceptance criteria, expected checks, security impact, and compatibility constraints.
- Mark a slice done only after code, tests, and evidence exist.
- Keep optional engines, browser, automation, subagents, and long-term memory out of scope until the native M0/M1 prerequisites are done. Laya integration is deferred by ADR-001 and remains out of scope for this tracker.
- Do not create commits, branches, or worktrees until the repository-root boundary is resolved.

## Current repository boundary

Git currently resolves the repository root to `C:/Users/dhanu/Downloads`, while the project workspace is `C:/Users/dhanu/Downloads/ForgeWeave`. Until this is resolved, implementation may continue in files, but Git worktree, branch, commit, and cleanup features must not be exercised against the ancestor repository.

## Build queue

RG-003 (2026-10-04): Documentation review completed; validation below. Scope: reviewed arXiv 2609.20519 methods/results/limitations and mapped findings into context/tools/agents/verify/telemetry contracts and shipping gates. Evidence: `docs/research/sol-pi-review-2026-10-04.md`, ADR-003, SYSTEM_DESIGN section 15, coverage F32-F35, 10 canonical P-series tasks and synchronized Luna guide. Security: individual policy decisions and source evidence survive batching/reduction; no automatic production harness self-modification. Compatibility: native Windows/Python 3.11 and user-selected Luna; no inferred savings/capability guarantee. Runtime optimizations remain pending, conditional and measured; BT-008 remains next native slice.

Research gate RG-002 (2026-10-04): Done for documentation scope before BT-008. Owners: architecture/research docs, `core`, `agents`, `automation`, `tools`, `browser`, `telemetry`. Acceptance: inspected pinned upstream source, package identity and four published Python wheels (archive hashes verified; selected modules match reviewed source); mapped harness/loop engineering, custom agents, delegation, fan-out/fan-in, workflows, web search, browser-use and observability to owners, milestones and behavioral checks; synchronized authoritative docs and Luna guide. Checks: nine Markdown files have no missing local links; 20 added canonical task IDs each defined once; 31 coverage rows; `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 60 tests. Security: query disclosure, external browser effects, delegated authority and trace redaction specified. Compatibility: native Windows/Python 3.11; optional packages are not core startup requirements. Limitations: no package installed/executed, no runtime mediation/containment proof, Muse Code implementation pages inaccessible; these remain tracked open work. Laya stays deferred.

| Order | Tracker ID | Canonical IDs | Status | Build target | Acceptance evidence |
|---:|---|---|---|---|---|
| 1 | BT-001 | M0.R1 | Done | Operational contracts for context, approvals, execution, budgets, isolation, and verification | `src/forgeweave/contracts/operational.py`; `tests/unit/test_contracts.py`; `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 35 tests |
| 2 | BT-002 | M0.20, M0.21 | Done | Core versioned contracts for task/session/attempt/events/tools/policy/artifacts/worktrees | `src/forgeweave/contracts/core.py`; `tests/unit/test_contract_core.py`; `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 41 tests |
| 3 | BT-003 | M0.25, M0.26 | Done | Schema export and contract round-trip tests | `src/forgeweave/contracts/schema.py`; `schemas/*.schema.json`; `tests/unit/test_contract_schema.py`; `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 44 tests |
| 4 | BT-004 | M0.R3, M1.1, M1.2 | Done | SQLite WAL event store and content-addressed artifact store contracts | `src/forgeweave/events/store.py`; `tests/unit/test_events_store.py`; `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 49 tests |
| 5 | BT-005 | M1.3, M1.45 | Done | Event-store migration framework that publishes successor migrations without rewriting committed generations | `src/forgeweave/events/migrations.py`; `tests/unit/test_events_migrations.py`; `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 52 tests |
| 6 | BT-006 | M1.4, M1.5 | Done | Task state machine and attempts, with immutable prior attempts on resume | `src/forgeweave/task/state.py`; `tests/unit/test_task_state.py`; `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 56 tests |
| 7 | BT-007 | M1.34, M1.R3 | Done | Append-before-dispatch tool execution records and `OUTCOME_UNKNOWN` crash reconciliation | `src/forgeweave/events/execution.py`; `tests/unit/test_tool_execution_events.py`; `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 60 tests |
| 8 | BT-008 | M1.8, M1.9, M1.R2 | Done | Policy gateway v1 with action-bound approvals and dispatch-time revalidation | `src/forgeweave/policy/gateway.py`; `tests/unit/test_policy_gateway.py`; focused policy tests passed 7 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 67 tests |
| 9 | BT-009 | M1.10-M1.14, M1.R6 | Done | Tool registry, path guard, read/list/glob/search, and hash-conditional patch | `src/forgeweave/tools/registry.py`; `src/forgeweave/tools/files.py`; `tests/unit/test_tools_registry.py`; `tests/unit/test_tools_files.py`; focused tests passed 7 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 74 tests |
| 10 | BT-010 | M1.27, M1.33, M1.R4 | Done | Scripted fake model provider and bounded stream accumulator for the native loop | `src/forgeweave/models/fake.py`; `src/forgeweave/core/loop.py`; `tests/unit/test_model_stream.py`; `tests/unit/test_core_loop.py`; focused tests passed 6 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 80 tests |
| 10A | BT-010A | M1.24, M2.2 | Done | OpenAI-compatible/Azure Responses API adapter text-output slice | `src/forgeweave/models/openai_compatible.py`; `tests/unit/test_openai_compatible_provider.py`; optional extra `model-openai`; focused tests passed 3 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 83 tests; live Azure smoke returned `forgeweave-azure-ok` without logging secrets |
| 11 | BT-011 | M1.28-M1.32, M1.R1, M1.44 | Done | Instruction resolver and context assembler with manifests, protected constraints, and fit checks | `src/forgeweave/context`; focused context tests passed 8 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 91 tests |
| 12 | BT-012 | M1.37, M1.38, M1.R5 | Done | Verification runner, evidence capture, and bounded repair-stop fingerprints | `src/forgeweave/verify/runner.py`; focused verification tests passed 5 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 96 tests |
| 13 | BT-013 | M1.40 | Done | Minimal CLI surface for config inspection and task status | `src/forgeweave/cli`; focused CLI tests passed 5 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 101 tests |
| 14 | BT-014 | M1.6, M1.7 | Done | Core cancellation token and budget guard primitives | `src/forgeweave/core/control.py`; focused core-control tests passed 6 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 107 tests |
| 15 | BT-015 | M1.15, M1.R6 | Done | Workspace-scoped shell tool foundation | `src/forgeweave/tools/shell.py`; focused shell tests passed 8 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 115 tests |
| 16 | BT-016 | M1.16 | Done | Explicit-root Git status, diff and guarded commit tools | `src/forgeweave/tools/git.py`; focused Git tests passed 6 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 121 tests |
| 17 | BT-017 | M1.17, M1.37 | Done | Test-runner tool backed by verification evidence | `src/forgeweave/tools/test_runner.py`; focused test-runner tests passed 4 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 125 tests |
| 18 | BT-018 | M1.18 | Done | Effective isolation reporting in config show | `src/forgeweave/cli/isolation.py`; focused CLI tests passed 6 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 126 tests |
| 19 | BT-019 | M1.19, M1.22 | Done | Explicit-root Git worktree creation with sanitized task branches | `src/forgeweave/workspace/manager.py`; focused workspace tests passed 5 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 131 tests |
| 20 | BT-020 | M1.20 | Done | SQLite worktree record store | `src/forgeweave/workspace/store.py`; focused workspace-store tests passed 4 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 135 tests |
| 21 | BT-021 | M1.21 | Done | Fenced per-repo and per-worktree lock store | `src/forgeweave/workspace/locks.py`; focused workspace-lock tests passed 5 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 140 tests |
| 22 | BT-022 | M1.21, M1.22 | Done | Wire workspace locks into Git worktree creation | `src/forgeweave/workspace/manager.py`; focused workspace-manager tests passed 7 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 142 tests |
| 23 | BT-023 | M1.23 | Done | Safe worktree preserve and cleanup lifecycle | `src/forgeweave/workspace/lifecycle.py`; focused workspace-lifecycle tests passed 3 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 145 tests |
| 24 | BT-024 | M1.24 | Done | OpenAI-compatible Responses tool-call normalization | `src/forgeweave/models/openai_compatible.py`; focused provider tests passed 4 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 146 tests |
| 25 | BT-025 | M1.25 | Done | Model retry policy and OpenAI-compatible retry wiring | `src/forgeweave/models/retry.py`; focused retry/provider tests passed 10 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 152 tests |
| 26 | BT-026 | M1.26 | Done | Model credential resolver with keyring/env fallback | `src/forgeweave/models/credentials.py`; focused credential/provider tests passed 10 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 156 tests |
| 27 | BT-027 | M1.32 | Done | Context retrieval ledger and stale file detection | `src/forgeweave/context/retrieval.py`; focused retrieval-ledger tests passed 4 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 160 tests |
| 28 | BT-028 | M1.30 | Done | Tool-result projection with artifact pointers and rehydration | `src/forgeweave/context/tool_results.py`; focused tool-result context tests passed 3 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 163 tests |
| 29 | BT-029 | M1.31 | Done | Provider context-length error detection and retry planning | `src/forgeweave/context/length_errors.py`; focused length-error tests passed 4 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 167 tests |
| 30 | BT-030 | M1.H2, M1.33 | Done | Core structured stop decisions | `src/forgeweave/core/stop.py`; focused stop tests passed 5 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 172 tests |
| 31 | BT-031 | M1.H2, M1.35 | Done | Deterministic dispatch observation ordering | `src/forgeweave/core/dispatch.py`; focused dispatch tests passed 3 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 175 tests |
| 32 | BT-032 | M1.H2, M1.35 | Done | Effect-aware dispatch stage planning | `src/forgeweave/core/dispatch.py`; focused dispatch scheduling tests passed 7 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 179 tests |
| 33 | BT-033 | M1.H2, M1.35 | Done | Staged dispatch execution with ordered observations | `src/forgeweave/core/dispatch.py`; focused dispatch execution tests passed 10 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 182 tests |
| 34 | BT-034 | M1.H2, M1.33 | Done | Native loop staged dispatch integration | `src/forgeweave/core/loop.py`; focused core-loop tests passed 3 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 183 tests |
| 35 | BT-035 | M1.H1 | Done | Local JSONL telemetry sink with redaction | `src/forgeweave/telemetry/jsonl.py`; focused telemetry tests passed 3 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 186 tests |
| 36 | BT-036 | M1.H1 | Done | Local causal telemetry spans | `src/forgeweave/telemetry/jsonl.py`; focused telemetry tests passed 5 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 188 tests |
| 37 | BT-037 | M1.H1 | Done | Bounded local telemetry writer with sink failure accounting | `src/forgeweave/telemetry/buffer.py`; focused telemetry-buffer tests passed 4 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 192 tests |
| 38 | BT-038 | M1.H1 | Done | Local JSONL telemetry file rotation | `src/forgeweave/telemetry/jsonl.py`; focused telemetry JSONL tests passed 8 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 195 tests |
| 39 | BT-039 | M1.H1, M1.33 | Done | Native loop telemetry audit references | `src/forgeweave/core/loop.py`; focused core-loop tests passed 4 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 196 tests |
| 40 | BT-040 | M1.H2, M1.33 | Done | Native loop cancellation drain stop result | `src/forgeweave/core/loop.py`; focused core-loop/control/stop tests passed 16 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 197 tests |
| 41 | BT-041 | M1.H2, M1.38 | Done | Repair-loop stop controller | `src/forgeweave/core/repair.py`; focused core-repair/verify/stop tests passed 14 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 201 tests |
| 42 | BT-042 | M1.H2, M1.33 | Done | Prompt-free loop diagnostics telemetry | `src/forgeweave/core/diagnostics.py`; focused diagnostics/core-loop/telemetry tests passed 17 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 205 tests |
| 43 | BT-043 | M1.33, M1.R3 | Done | Loop lifecycle event recorder | `src/forgeweave/events/loop.py`; focused loop/event/core tests passed 17 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 207 tests |
| 44 | BT-044 | M1.33, M1.R3 | Done | Native loop event-recorder integration | `src/forgeweave/core/loop.py`; focused core/event/telemetry tests passed 23 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 208 tests |
| 45 | BT-045 | M1.33, M1.R1 | Done | Context packet to model-input bridge | `src/forgeweave/context/model_input.py`; focused context/core diagnostics tests passed 17 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 212 tests |
| 46 | BT-046 | M1.33, M1.R1 | Done | Native loop context builder | `src/forgeweave/core/context.py`; focused context/core tests passed 18 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 215 tests |
| 47 | BT-047 | M1.33, M1.38 | Done | Repair orchestration runner | `src/forgeweave/core/repair.py`; focused core-repair/verify/stop tests passed 17 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 218 tests |
| 48 | BT-048 | M1.33, M1.38 | Done | Native loop context repair entrypoint | `src/forgeweave/core/loop.py`; focused core-loop/core-repair/verify tests passed 22 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 220 tests |
| 49 | BT-049 | M1.38a | Done | Analyzer adapter result contract | `src/forgeweave/verify/analyzers.py`; focused analyzer/regression/verify tests passed 20 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 224 tests |
| 50 | BT-050 | M1.38b | Done | Ruff analyzer adapter | `src/forgeweave/verify/ruff.py`; focused ruff/analyzer/regression tests passed 19 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 228 tests |
| 51 | BT-051 | M1.38d | Done | Git patch snapshot store | `src/forgeweave/verify/snapshots.py`; focused snapshot/regression/Ruff tests passed 17 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 230 tests |
| 52 | BT-052 | M1.38e | Done | Analyzer regression gate | `src/forgeweave/verify/gate.py`; focused regression-gate/regression/analyzer tests passed 19 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 234 tests |
| 53 | BT-053 | M1.33, M1.38 | Done | Verified mutating tool execution boundary | `src/forgeweave/verify/execution.py`; focused verified-tool/gate/snapshot tests passed 9 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 237 tests |
| 54 | BT-054 | M1.33, M1.38 | Done | Native loop verified dispatch wiring | `src/forgeweave/core/loop.py`; focused core-loop/verified-tool tests passed 15 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 239 tests |
| 55 | BT-055 | M1.33, M1.38, M1.40 | Done | Verified executor factory | `src/forgeweave/verify/factory.py`; focused factory/verified-tool/core-loop tests passed 18 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 242 tests |
| 56 | BT-056 | M1.33, M1.38, M1.40 | Done | CLI verified-dispatch config validation | `src/forgeweave/cli/verify.py`; focused CLI/factory tests passed 11 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 244 tests |
| 57 | BT-057 | M1.33, M1.40 | Done | Minimal deterministic `fw run` | `src/forgeweave/cli/run.py`; focused CLI run tests passed 11 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 247 tests |
| 58 | BT-058 | M1.40, M4.6 | Done | `fw run --prompt-file` | `src/forgeweave/cli/app.py`; focused CLI tests passed 13 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 249 tests |
| 59 | BT-059 | M1.40, M4.6 | Done | `fw run --fake-tool-call-file` | `src/forgeweave/cli/app.py`; focused CLI tests passed 15 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 251 tests |
| 60 | BT-060 | M1.40, M4.6 | Done | `fw run --output-file` | `src/forgeweave/cli/app.py`; focused CLI tests passed 16 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 252 tests |
| 61 | BT-061 | M1.40, M4.6 | Done | `fw run --dry-run` | `src/forgeweave/cli/run.py`, `src/forgeweave/cli/app.py`; focused CLI tests passed 17 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 253 tests |
| 62 | BT-062 | M1.36, M1.R3 | Done | Tool execution restart reconciliation | `src/forgeweave/events/recovery.py`; focused recovery/event tests passed 7 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 256 tests |
| 63 | BT-063 | M1.36, M1.R3 | Done | Task resume recovery coordinator | `src/forgeweave/task/recovery.py`; focused task/recovery tests passed 10 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 259 tests |
| 64 | BT-064 | M1.36, M2.20 | Done | Durable task projection from lifecycle events | `src/forgeweave/task/projection.py`, `src/forgeweave/task/state.py`; focused task projection/state/recovery tests passed 10 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 262 tests |
| 65 | BT-065 | M1.40, M2.20 | Done | `fw task status` from event store | `src/forgeweave/cli/status.py`, `src/forgeweave/cli/app.py`; focused CLI/projection tests passed 22 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 264 tests |
| 66 | BT-066 | M1.36, M1.40, M2.20 | Done | `fw task resume` with recovery reconciliation | `src/forgeweave/cli/task.py`, `src/forgeweave/task/state.py`, `src/forgeweave/cli/app.py`; focused CLI tests passed 21 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 266 tests |
| 67 | BT-067 | M1.40, M2.20 | Done | `fw task cancel` from event store | `src/forgeweave/cli/task.py`, `src/forgeweave/cli/app.py`; focused CLI/projection tests passed 26 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 268 tests |
| 68 | BT-068 | M1.16, M1.40 | Done | `fw task diff` bounded Git patch | `src/forgeweave/cli/task.py`, `src/forgeweave/cli/app.py`; focused CLI/Git tests passed 31 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 270 tests |
| 69 | BT-069 | M1.39 | Done | Structured final report contract | `src/forgeweave/core/final_report.py`; focused final-report tests passed 4 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 274 tests |
| 70 | BT-070 | M1.39, M1.40 | Done | `fw task report` structured final report | `src/forgeweave/cli/report.py`, `src/forgeweave/cli/app.py`; focused CLI/final-report tests passed 31 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 276 tests |
| 71 | BT-071 | M1.17, M1.37 | Done | Verification check selection from repo config | `src/forgeweave/verify/selection.py`; focused verify-selection tests passed 5 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 281 tests |
| 72 | BT-072 | M1.37, M1.40 | Done | `fw verify select` command projection | `src/forgeweave/cli/verify.py`, `src/forgeweave/cli/app.py`; focused CLI/verify-selection tests passed 34 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 283 tests |
| 73 | BT-073 | M1.17, M1.37 | Done | Selected verification runner | `src/forgeweave/verify/selected_runner.py`; focused selected-runner/selection tests passed 9 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 287 tests |
| 74 | BT-074 | M1.17, M1.37, M1.40 | Done | `fw verify run-selected` command | `src/forgeweave/cli/verify.py`, `src/forgeweave/cli/app.py`; focused CLI/selected-runner tests passed 35 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 289 tests |
| 75 | BT-075 | M1.37, M1.39 | Done | Verification run duration evidence | `src/forgeweave/contracts/operational.py`, `src/forgeweave/verify/runner.py`; focused verification/report/CLI tests passed 44 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 289 tests |
| 76 | BT-076 | M1.37, M1.39 | Done | Completion report from selected verification | `src/forgeweave/core/completion.py`; focused completion/final-report/selected-runner tests passed 12 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 293 tests |
| 77 | BT-077 | M1.37, M1.39 | Done | Repository task completion orchestration | `src/forgeweave/core/task_completion.py`; focused task-completion/completion/selected-runner tests passed 12 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 297 tests |
| 78 | BT-078 | M1.39, M1.40 | Done | w run --complete-report completion boundary | `src/forgeweave/cli/run.py`, `src/forgeweave/cli/app.py`; focused CLI/task-completion tests passed 38 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 300 tests |
| 84 | BT-084 | M1.R3, M1.42 | Done | Artifact publication recovery ledger | `src/forgeweave/events/artifact_recovery.py`; focused artifact-publication recovery tests passed 5 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 318 tests |
| 85 | BT-085 | M1.R3, M1.21 | Done | Workspace lease fencing checks | `src/forgeweave/workspace/leases.py`; focused workspace lease/lock tests passed 9 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 322 tests |
| 86 | BT-086 | M4.H1 | Done | Automation workflow contracts and DAG validation | `src/forgeweave/automation/contracts.py`; focused automation contract tests passed 6 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 328 tests |
| 87 | BT-087 | M4.H2, M4.1 | Done | Workflow SQLite persistence for definitions/runs/attempts | `src/forgeweave/automation/store.py`; focused automation store/contract tests passed 12 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 334 tests |
| 88 | BT-088 | M4.H2, M4.H3 | Done | Read-only workflow scheduling planner | `src/forgeweave/automation/planner.py`; focused automation planner/store/contract tests passed 17 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 339 tests |
| 89 | BT-089 | M4.H3 | Done | Workflow status projection | `src/forgeweave/automation/status.py`; focused automation status/planner/store/contract tests passed 20 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 342 tests |
| 90 | BT-090 | M4.H3, M4.10 | Done | Workflow CLI status command | `src/forgeweave/cli/workflow.py`, `src/forgeweave/cli/app.py`; focused CLI/workflow-status tests passed 44 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 344 tests |
| 91 | BT-091 | M4.10 | Done | Workflow CLI validate command | `src/forgeweave/cli/workflow.py`, `src/forgeweave/cli/app.py`; focused CLI tests passed 43 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 346 tests |
| 92 | BT-092 | M4.1, M4.10 | Done | Workflow store/list CLI inspection | `src/forgeweave/automation/store.py`, `src/forgeweave/cli/workflow.py`, `src/forgeweave/cli/app.py`; focused store/CLI tests passed 52 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 349 tests |
| 93 | BT-093 | M4.1, M4.10 | Done | Complete workflow CLI admission/resume module | `src/forgeweave/cli/workflow.py`, `src/forgeweave/cli/app.py`; focused CLI tests passed 48 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 352 tests |
| 94 | BT-094 | M4.H3, M4.11 | Done | Built-in workflow templates catalog and CLI | `src/forgeweave/automation/templates.py`, `src/forgeweave/cli/workflow.py`, `src/forgeweave/cli/app.py`; focused template/CLI tests passed 53 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 357 tests |

## Active slice template

Copy this block before starting a slice and update it as work proceeds.

```text
Tracker ID:
Canonical IDs:
Owning module:
Acceptance criteria:
Expected checks:
Security impact:
Compatibility constraints:
Files planned:
Status:
Evidence:
Open risks:
```

## Active slice

RG-003 validation: checked nine affected Markdown files with no missing local links; all 10 P-series task IDs are defined exactly once; coverage has 35 rows. Documentation only; no runtime code or dependencies changed and no paper experiments were executed. The previous 60-test baseline remains the latest runtime test evidence.

RG-002 documentation/research gate is validated; BT-008 remains the next runtime slice. Revised later queue: M1.H1-H2 diagnostics/loop fixtures with native loop integration -> M2.H1-H6 research tools, observability, hooks and evals -> M3.H1-H4 custom agents/delegation/joins -> M3.H5-H6 browser-use feasibility/adapter -> M4.H1-H3 durable workflows. Each is split into a small tested slice before implementation; existing BT-001 through BT-007 evidence is preserved. Full requirements are indexed by F01-F31 in `docs/feature-coverage.md`.

Tracker ID: BT-094
Canonical IDs: M4.H3, M4.11
Owning module: `src/forgeweave/automation`, `src/forgeweave/cli`
Acceptance criteria: Add built-in reusable workflow templates for research-plan-implement-test-review, parallel investigation-synthesis and independent patches-integration-verification, with CLI list/show inspection and JSON export.
Expected checks: focused template and CLI tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit`.
Security impact: Templates are static WorkflowDefinition objects validated by contract constructors; they do not evaluate arbitrary model-authored code, execute workflow steps, dispatch tools, perform network calls, request approvals or publish artifacts.
Compatibility constraints: Additive template catalog and CLI inspection commands; no persistence schema, workflow admission or runner behavior changes.
Files planned: `src/forgeweave/automation/templates.py`, `src/forgeweave/automation/__init__.py`, `src/forgeweave/cli/workflow.py`, `src/forgeweave/cli/app.py`, `tests/unit/test_automation_templates.py`, `tests/unit/test_cli_app.py`, `todo.md`, `BUILD_TRACKER.md`.
Status: Done.
Evidence: Focused `PYTHONPATH=src python -m unittest tests.unit.test_automation_templates tests.unit.test_cli_app` passed 53 tests; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 357 tests on 2026-10-11.
Open risks: Workflow execution runner remains open; future templates can be added through the same static catalog contract.













