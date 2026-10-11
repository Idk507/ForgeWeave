# ForgeWeave — TODO

Ordered checklist. Companion to [plan.md](./plan.md). Mark an item done only with acceptance evidence (test, artifact or doc link). Items in a milestone depend on the previous milestone's gate unless tagged `[parallel]`.

Legend: `[ ]` open, `[x]` done. Tags: `[sec]` security-relevant, `[win]` Windows verification required, `[parallel]` can run alongside other work.

---

## M0 — Research and contracts

### Docs and decisions

- [x] M0.P1 RG-003: review arXiv 2609.20519 methods/results/limitations; record ADR-003 and section 15 with phased native requirements. Documentation scope only; paper experiments not reproduced.

- [x] M0.H1 RG-002: source-based harness/delegation/search/browser/observability review, ADR-002, section 14 and feature coverage matrix (2026-10-04). Documentation acceptance only; runtime proofs remain open.
- [ ] M0.H2 Resolve documented source gaps before affected integration: exact wheel/tag vs HEAD parity, accessible Muse Code primary implementation docs, Windows runtime/containment evidence. Do not block unrelated native slices on unavailable vendor internals.
- [ ] M0.1 Create `docs/research/capability-matrix.md` (columns: product, feature, source URL, retrieval date, evidence level, source availability, proposed ForgeWeave implementation, target milestone, owner)
- [ ] M0.2 Cover all products: GitHub Copilot, Codex, Claude Code, Cursor, Meta Muse, Kimi Code, Pi, OpenCode, Grok Build, DeepSeek Harness; mark proprietary internals "unknown"
- [x] M0.3 ADR-000: reconcile naming, ownership and delivery order; [decision](docs/architecture/adr-000.md), SYSTEM_DESIGN sections 3/4/13 and plan section 15 (2026-10-02)
- [ ] M0.4 ADR: event protocol and append-before-dispatch rules
- [ ] M0.5 ADR: worktree isolation model
- [ ] M0.6 ADR: provider boundary and capability negotiation
- [x] M0.7 ADR: defer Laya (System 1) integration from the active native-core sequence. Evidence: `docs/architecture/adr-001-defer-laya-integration.md` (2026-10-04).
- [ ] M0.8 ADR: persistence (SQLite WAL + artifact store, backup/restore)
- [ ] M0.8a ADR-010: engines and reuse of harness packages (native core; optional `engines`; mediated vs delegated; `codex-harness` is design-reference + optional verifier only; see plan.md 4.1)
- [ ] M0.9 ADR: CLI framework (after spike M0.12)
- [ ] M0.10 `docs/architecture/threat-model.md` (supply chain, malicious repo files, compromised MCP, leaked Git tokens, artifact tampering, prompt injection, SSRF, memory poisoning)
- [ ] M0.11 `docs/architecture/dependencies.md` (pinned versions and licenses for active dependencies; Laya review remains deferred with ADR-001)
- [ ] M0.11a Dependencies doc: add `deepseek-harness-sdk`/`deepseek-harness-runtime-bin` (MIT, >=3.10, pre-release), `openai-codex` (Apache-2.0), `codex-harness` (Apache-2.0, >=3.12) as optional extras with exact pins and notice requirements
- [ ] M0.11b Add DeepSeek Harness (Cordis plugins, session log, seams, profiles/bundles) and Codex Harness (hook-based regression policy) rows to the capability matrix with evidence level "vendor-documented", retrieval date 2026-10-01

### Spikes
- [ ] M0.12 [win] CLI spike: `typer` + `prompt_toolkit`/`textual` on Windows 11 (streaming, Ctrl+C, resize, ANSI, piping)
- [ ] M0.13 [win] Subprocess spike: cancellation propagation, process-tree kill (Job Objects), output capping
- [ ] M0.14 [win] SQLite WAL concurrency spike (multiple processes, locks)
- [ ] M0.14a [win] Engine spike: after native M1 gate, install the reviewed pinned SDK in a clean venv on Windows x64; inspect `sdk` dump-config and disable uploads before any authorized run; use a disposable workspace + isolated `DSH_HOME`; record startup, memory, events and measured confinement. Never default to `sdk-minimal`.
- [ ] M0.14b Engine spike: install `openai-codex` (0.159.3 requires `openai-codex-cli-bin==0.159.3`, pydantic>=2.12); run a thread against a disposable workspace; record auth requirements, event stream shape, sandbox/approval options
- [ ] M0.14c Mediated-mode feasibility: can `dsh` (profile patch removing native shell/fs) and Codex app-server be limited to a ForgeWeave-served MCP tool endpoint? Record result; decides whether `delegated` mode ships
- [x] M0.14d Verify the bare PyPI name `deepseek-harness`: done 2026-10-01 via PyPI JSON API. It is an unrelated third-party client (0.3.1) sharing the `deepseek_harness` import name with the official SDK; never depend on it or co-install
- [ ] M0.14d2 [sec] Engine adapter startup check: refuse to run unless `deepseek_harness.DeepSeekHarness` accepts `dsh_home` and `deepseek-harness-runtime-bin` is importable; extras metadata declares conflict with bare `deepseek-harness`
- [ ] M0.14f Run spikes M0.14a/b/e manually in a disposable venv (installation was blocked as high-risk during planning, so these are NOT yet executed); record results in `docs/research/engine-spikes.md`
- [ ] M0.14e Spike `codex-harness` in an isolated HOME on Python 3.12: run `codex-harness-check` on a fixture file; confirm no writes outside the isolated HOME; record findings format

### Skeleton
- [ ] M0.15 `pyproject.toml`, `src/forgeweave/*` package skeleton per plan.md section 5 (started: `pyproject.toml`, `forgeweave/engines`, `tests/unit/test_engines.py`; remaining packages not yet created)
- [ ] M0.16 Tooling: `ruff`, `mypy` or `pyright`, `pytest` (+ asyncio), `import-linter` contracts for package boundaries
- [ ] M0.17 CI (Windows + Linux matrix): lint, type check, tests, import-linter
- [ ] M0.18 Package-level `AGENTS.md` stubs for major packages
- [ ] M0.19 Shrink root AGENTS.md into a concise index linking SYSTEM_DESIGN.md/ADRs only after requirement mapping preserves all normative constraints (ADR-000)

### Contracts
- [x] M0.20 `contracts`: Task, Attempt, Session, Turn, Step, Event, Budget, Artifact, Worktree. Evidence: `src/forgeweave/contracts/core.py`, `src/forgeweave/contracts/operational.py`, `tests/unit/test_contract_core.py`, `tests/unit/test_contracts.py`; `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 41 tests on 2026-10-02.
- [x] M0.21 `contracts`: ToolSpec, ToolCall, ToolResult/ToolFailure, EffectSet, PolicyDecision, Approval. Evidence: `src/forgeweave/contracts/core.py`, `src/forgeweave/contracts/operational.py`, `tests/unit/test_contract_core.py`, `tests/unit/test_contracts.py`; `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 41 tests on 2026-10-02.
- [ ] M0.22 `contracts`: ModelProvider protocol, capability descriptor, usage record
- [ ] M0.23 `contracts`: ContextPacket, ToolCatalog, RoutingState, RoutingDecision, DecisionEvidence
- [ ] M0.24 `contracts`: MemoryEntry, Iteration, Automation, Lease
- [x] M0.25 Schema versioning + migration framework; exported JSON Schema to `schemas/`. Evidence: `src/forgeweave/contracts/schema.py`, `schemas/*.schema.json`, `src/forgeweave/events/migrations.py`; `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 52 tests on 2026-10-02.
- [x] M0.26 (partial) Test: schema round-trips; event log rebuilds identical task state. Evidence: `tests/unit/test_contract_schema.py`; event-log rebuild test remains BT-004/BT-006.
- [ ] M0.27 Evaluation task-set outline in `evals/` (categories from plan.md section 10)
- [ ] M0.28 Requirement -> owner map for every AGENTS.md feature (project board or `docs/requirements.md`)
- [ ] **M0 GATE:** every feature maps to requirement + owner; unknowns marked; round-trip tests green

---

## M1 — Local vertical slice

### Persistence and task core
- [x] M1.1 `events`: SQLite WAL store, per-task monotonic sequence, immutable append, idempotent duplicate delivery. Evidence: `src/forgeweave/events/store.py`, `tests/unit/test_events_store.py`; `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 49 tests on 2026-10-02.
- [x] M1.2 `events`: artifact store (content-hash addressed, task-scoped dir, mime, redaction status, retention). Evidence: `src/forgeweave/events/store.py`, `tests/unit/test_events_store.py`; `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 49 tests on 2026-10-02.
- [x] M1.3 `events`: explicit migrations + migration tests. Evidence: `src/forgeweave/events/migrations.py`, `tests/unit/test_events_migrations.py`; `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 52 tests on 2026-10-02.
- [x] M1.4 `task`: state machine with atomic transition + event append; illegal transition tests. Evidence: `src/forgeweave/task/state.py`, `tests/unit/test_task_state.py`; `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 56 tests on 2026-10-02.
- [x] M1.5 `task`: attempts; resume creates new attempt; prior events immutable. Evidence: `src/forgeweave/task/state.py`, `tests/unit/test_task_state.py`; `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 56 tests on 2026-10-02.
- [ ] M1.6 `core`: cancellation token propagating to subprocesses and model streams. Partial evidence: BT-014 adds `CancellationToken` and checks cancellation before/during model stream accumulation and before tool dispatch in the native loop; BT-082 propagates cancellation into an already-running shell subprocess and returns structured cancelled evidence. Full Windows process-tree cancellation remains M1.15/M0.13 work.
- [ ] M1.7 `core`: budgets (turns, wall time, tokens, tool calls, delegation depth, context size). Partial evidence: BT-014 adds `BudgetLimits`, `BudgetUsage`, `BudgetGuard` and structured `BudgetExceeded` reasons for all listed dimensions; full native-loop accounting and persisted budget reconciliation remain open.

### Policy and tools
- [x] M1.8 [sec] `policy`: gateway allow/deny/ask; permission intersection; approval persistence. Evidence: `src/forgeweave/policy/gateway.py`, `tests/unit/test_policy_gateway.py`; `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 67 tests on 2026-10-04.
- [ ] M1.9 [sec] `policy`: dispatch-time revalidation of path/command/URL/effects. Partial evidence: BT-008 revalidates tool name, schema version, argument hash, effect hash, workspace precondition hash and policy revision before dispatch. Full path/command/URL semantic revalidation remains BT-009 and M1.R6.
- [x] M1.10 [sec] `tools`: registry, schema validation, structured errors for unknown tool/stale catalog/invalid args. Evidence: `src/forgeweave/tools/registry.py`, `tests/unit/test_tools_registry.py`; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 74 tests on 2026-10-04.
- [x] M1.11 [sec] `tools`: path normalization, traversal and symlink escape protection. Evidence: `src/forgeweave/tools/files.py`, `tests/unit/test_tools_files.py`; path guard rejects absolute paths, traversal and symlink escape.
- [x] M1.12 `tools`: list, glob, read. Evidence: `src/forgeweave/tools/files.py`, `tests/unit/test_tools_files.py`; tools also register through `register_file_tools`.
- [x] M1.13 `tools`: regex search (`rg` with Windows fallback). Evidence: `FileTools.search` prefers `rg` via argv and falls back to Python regex scanning; covered by `tests/unit/test_tools_files.py`.
- [x] M1.14 `tools`: patch/replace with expected file hash + structured conflict. Evidence: `FileTools.replace_text`, `PatchConflictError`, `tests/unit/test_tools_files.py`.
- [ ] M1.15 [sec][win] `tools`: shell (argv, cwd in worktree, timeout, output cap, env allowlist, cancellation, process-tree kill). Partial evidence: BT-015 adds `ShellTools` and `run_shell` registry support with argv-only execution, workspace cwd guard, timeout, output cap, environment allowlist and pre-dispatch cancellation; BT-082 adds in-flight subprocess cancellation with a structured `cancelled` result flag; Windows process-tree kill, terminal-control filtering and deeper shell authorization fixtures remain open.
- [ ] M1.16 `tools`: git status/diff/commit. Partial evidence: BT-016 adds `GitTools` and registry tools for explicit repositories with their own `.git`, covering status, bounded diff and guarded local commit with `allow_mutation=True`; current ForgeWeave workspace root ambiguity still blocks exercising Git mutation against this project checkout. BT-068 exposes bounded read-only Git diff through `fw task diff --repo-root`; focused CLI/Git tests passed 31 tests and full unit suite passed 270 tests on 2026-10-10.
- [ ] M1.17 `tools`: test runner with captured evidence. Partial evidence: BT-017 adds `TestRunnerTools` and a `run_tests` registry tool backed by `VerificationRunner`, returning `VerificationRun` evidence, stdout/stderr and output artifacts for explicit argv commands; BT-071 adds repository-config based check selection that returns VerificationCommand objects for pytest/unittest and Ruff without executing them; focused verify-selection tests passed 5 tests and full unit suite passed 281 tests on 2026-10-10. BT-072 exposes selected checks through `fw verify select` without executing them; focused CLI/verify-selection tests passed 34 tests and full unit suite passed 283 tests on 2026-10-10. BT-073 adds `run_selected_verification` to execute selected commands through VerificationRunner and capture output artifacts; focused selected-runner/selection tests passed 9 tests and full unit suite passed 287 tests on 2026-10-10. BT-074 adds `fw verify run-selected` to execute selected checks and write output artifacts to an explicit directory; focused CLI/selected-runner tests passed 35 tests and full unit suite passed 289 tests on 2026-10-10.
- [x] M1.18 Effective isolation level reporting in CLI/config show. Evidence: BT-018 adds `IsolationView`, honest default host-user isolation claims and `fw config show --json` isolation output; focused CLI tests passed 6 tests and full unit suite passed 126 tests on 2026-10-05.

### Workspace
- [x] M1.19 [win] `workspace`: worktree create via Git commands; branch `fw/<task-id>-<slug>`; sanitized names/paths. Evidence: BT-019 adds `WorkspaceManager.create_worktree`, branch/path sanitization and isolated temp-repo tests; focused workspace tests passed 5 tests and full suite passed 131 tests on 2026-10-05.
- [x] M1.20 `workspace`: SQLite records (repo path, base commit, branch, worktree path, owner, dirty, cleanup state). Evidence: BT-020 adds `WorkspaceStore` using the `Worktree` contract with SQLite WAL persistence, state/dirty updates and task listing; focused store tests passed 4 tests and full suite passed 135 tests on 2026-10-05.
- [x] M1.21 `workspace`: per-repo and per-worktree locks. Evidence: BT-021 adds `WorkspaceLockStore` with SQLite WAL fenced repo/worktree leases, TTL replacement, token-checked release/refresh and focused lock tests; full unit suite passed 140 tests on 2026-10-06.
- [x] M1.22 `workspace`: detect dirty original checkout; never discard user changes. Evidence: `WorkspaceManager` checks source porcelain status before `git worktree add`, rejects dirty checkouts with `DIRTY_SOURCE_CHECKOUT`, and preserves this behavior under BT-022 lock integration; full unit suite passed 142 tests on 2026-10-06.
- [x] M1.23 `workspace`: preserve failed/interrupted worktrees; cleanup only via `git worktree remove` after clean check; prune. Evidence: BT-023 adds `WorkspaceLifecycle` with preserve, dirty detection, clean-only `git worktree remove`, prune and store state updates; focused lifecycle tests passed 3 tests and full unit suite passed 145 tests on 2026-10-06.

### Model and context
- [ ] M1.24 `models`: pick first provider (ADR) and implement adapter with streaming + tool calls + usage. Partial evidence: OpenAI-compatible/Azure Responses adapter implemented in `src/forgeweave/models/openai_compatible.py`; unit tests in `tests/unit/test_openai_compatible_provider.py`; live Azure smoke against `gpt-4o` returned `forgeweave-azure-ok` on 2026-10-05. BT-024 adds non-streaming Responses API function-call normalization into ForgeWeave `tool_call` chunks and passes tool catalogs to the client; focused provider tests passed 4 tests and full unit suite passed 146 tests on 2026-10-06. True streaming chunks, retry behavior and ADR remain open.
- [x] M1.25 `models`: jittered backoff, capped retries, rate-limit handling. Evidence: BT-025 adds `RetryPolicy`, `RetryableModelError` and `call_with_retries`, wires retry handling into the OpenAI-compatible adapter for 408/409/425/429/5xx and timeout/connection/rate-limit style exceptions; focused retry/provider tests passed 10 tests and full unit suite passed 152 tests on 2026-10-06.
- [x] M1.26 `models`: credential storage via OS keyring; explicit fallback. Evidence: BT-026 adds `CredentialResolver` with optional OS keyring lookup, explicit environment fallback and sanitized missing-secret errors; `OpenAICompatibleProvider.from_env` now resolves the API key through it. Focused credential/provider tests passed 10 tests and full unit suite passed 156 tests on 2026-10-06.
- [x] M1.27 `models`: scripted fake provider for tests. Evidence: `src/forgeweave/models/fake.py`, `tests/unit/test_model_stream.py`; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 80 tests on 2026-10-04.
- [x] M1.28 `context`: instruction resolver with provenance, size limits, contradiction detection, precedence order. Evidence: `src/forgeweave/context/instructions.py`, `tests/unit/test_context_instructions.py`; full `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 91 tests on 2026-10-05.
- [x] M1.29 `context`: assembler with `B = W - O - T - S`, per-section allocation, provenance on every span. Evidence: `src/forgeweave/context/assembler.py`, `tests/unit/test_context_assembler.py`; manifests use `ContextSpan` source hashes and reserve output/tool/safety headroom.
- [x] M1.30 `context`: trim, tool-result caps with artifact pointers, rehydration. Evidence: BT-011 trims lower-priority optional context and records omitted span IDs; BT-028 adds `ToolResultProjector` to cap large tool outputs, persist full output through `ArtifactStore`, include artifact URI/hash pointers in model context and rehydrate text artifacts by URI. Focused tool-result context tests passed 3 tests and full unit suite passed 163 tests on 2026-10-06.
- [x] M1.31 `context`: never truncate latest user request/policy; handle provider length errors. Evidence: BT-011 treats latest user request, active acceptance criteria and protected instructions as protected spans and raises `CONTEXT_UNSATISFIABLE` when they cannot fit; BT-029 adds provider context-length error detection and retry-budget planning for context reassembly. Focused length-error tests passed 4 tests and full unit suite passed 167 tests on 2026-10-06.
- [x] M1.32 `context`: retrieval ledger; invalidate on file hash change. Evidence: BT-027 adds `RetrievalLedger` and `RetrievalLedgerEntry` for file-backed context spans with workspace path guarding, full-file SHA-256 evidence and stale-entry detection; focused retrieval-ledger tests passed 4 tests and full unit suite passed 160 tests on 2026-10-06.

### Loop, verification, CLI

- [ ] M1.P1 `context`/`events`/`verify`: baseline observation/evidence fixtures before optimization: artifact identity, scoped rehydration, critical failure retention, disclosure/retention handling and measured loop usage. Required native behavior, not an auxiliary-model integration.

- [x] M1.H1 `telemetry`/`core`: local structured JSONL logs and causal spans during loop integration; redaction before sinks, bounded queues/rotation, exporter failure handling, audit references and no external upload. Evidence: BT-035 adds a local-only `JsonlTelemetrySink` and `TelemetryEvent` with stable event names, correlation IDs and recursive secret-field redaction before writing JSONL; focused telemetry tests passed 3 tests and full unit suite passed 186 tests on 2026-10-06. BT-036 adds `TelemetrySpan` plus `span.started`/`span.ended` JSONL records with span IDs, parent span IDs, deterministic duration fields and redacted span attributes; focused telemetry tests passed 5 tests and full unit suite passed 188 tests on 2026-10-06. BT-037 adds `BoundedTelemetryWriter` with bounded pending events, oldest-event drop accounting, sink failure accounting and retry-preserving flush behavior; focused telemetry-buffer tests passed 4 tests and full unit suite passed 192 tests on 2026-10-06. BT-038 adds optional local JSONL file rotation with byte limits and retained backup counts; focused telemetry JSONL tests passed 8 tests and full unit suite passed 195 tests on 2026-10-06. BT-039 wires stable local audit events into `NativeAgentLoop` for loop, model stream, policy and dispatch boundaries without recording full prompts, tool arguments or tool outputs; focused core-loop tests passed 4 tests and full unit suite passed 196 tests on 2026-10-06. Richer duration spans and persisted event-log linkage remain follow-up hardening.
- [ ] M1.H2 `core`/`verify`: harness/loop fixtures from section 14.1: stream settlement, deterministic observation order, effect-aware concurrency, steering, cancellation/drain, global repair cap and explicit stop reasons. Partial evidence: BT-030 adds `StopEvaluator`, `StopDecision` and canonical `StopReason` values for final answer, approval wait, cancellation and budget exhaustion; BT-031 adds deterministic dispatch observation ordering; BT-032 adds effect-aware dispatch planning; BT-033 adds staged dispatch execution with injectable parallel executor; BT-034 wires staged dispatch into `NativeAgentLoop`. BT-040 adds `LoopResult.stop_decision` and drains cancellation at the post-model safe boundary without starting new policy/tool work; focused core-loop/control/stop tests passed 16 tests and full unit suite passed 197 tests on 2026-10-06. BT-041 adds `RepairLoopController` to map verification outcomes and `RepairGuard` state into explicit stop decisions for pass, retryable failure, repeated identical failure and repair-budget exhaustion; focused core-repair/verify/stop tests passed 14 tests and full unit suite passed 201 tests on 2026-10-06. BT-042 adds prompt-free `LoopDiagnostics` for context/catalog/config/root-budget telemetry and wires it into loop start/end audit events; focused diagnostics/core-loop/telemetry tests passed 17 tests and full unit suite passed 205 tests on 2026-10-10. Broader steering/drain and dynamic task-runner repair orchestration remain open.
- [ ] M1.33 `core`: agent loop (context -> model -> validate -> policy -> dispatch -> observe -> stop check). Partial evidence: BT-010 implements a one-turn fake-provider loop that validates complete model tool-call JSON, authorizes through `PolicyGateway`, revalidates before dispatch and records observations. BT-030 adds structured stop-check primitives. BT-034 wires staged dispatch planning/execution into the loop while preserving policy revalidation and model-order observations. BT-039 adds local loop audit events. BT-040 adds structured `LoopResult.stop_decision` and post-model cancellation drain. BT-042 adds prompt-free context/catalog/config/root-budget diagnostics in loop telemetry. BT-043 adds `LoopEventRecorder` for append-only loop start/end audit references with diagnostics refs and canonical stop reasons. BT-044 wires optional loop event recording into `NativeAgentLoop`. BT-045 adds `ContextModelInput` to carry assembled context into provider-ready messages plus prompt-free loop diagnostics. BT-046 adds `NativeLoopContextBuilder` to assemble context from request metadata, constraints, instructions, optional spans and provider budget into loop-ready model input; focused context/core tests passed 18 tests and full unit suite passed 215 tests on 2026-10-10. BT-047 adds `RepairOrchestrator` so retryable verification failures call a repair step and terminal pass/repeated-failure/budget decisions preserve ordered verification evidence; focused core-repair/verify/stop tests passed 17 tests and full unit suite passed 218 tests on 2026-10-10. BT-048 adds `NativeAgentLoop.run_context_repair`, which verifies first, runs one prepared context turn per retryable repair decision, and skips model/tool execution when the repair guard stops; focused core-loop/core-repair/verify tests passed 22 tests and full unit suite passed 220 tests on 2026-10-10. BT-053 adds the task-runner-facing verified mutating-tool execution boundary. BT-054 wires optional verified dispatch into `NativeAgentLoop`, adds verification evidence to observations and fails the loop when the regression gate blocks; focused core-loop/verified-tool tests passed 15 tests and full unit suite passed 239 tests on 2026-10-10. BT-055 adds `VerifiedExecutorFactory`/`build_verified_executor` for CLI/task setup to construct snapshot, Ruff and regression-gate dependencies; focused factory/verified-tool/core-loop tests passed 18 tests and full unit suite passed 242 tests on 2026-10-10. `fw verify config` validates and renders verified-dispatch construction from explicit CLI inputs without running analyzers or mutating Git (BT-056). BT-057 adds a minimal deterministic `fw run` path that executes one native loop turn with fake text/tool-call streams, optional verified-dispatch construction and rooted write_text tool output; focused CLI tests passed 11 tests and full unit suite passed 247 tests on 2026-10-10. BT-058 adds prompt-file input for scripted/CI runs; focused CLI tests passed 13 tests and full unit suite passed 249 tests on 2026-10-10. BT-059 adds fake-tool-call-file input for deterministic scripted native runs; focused CLI tests passed 15 tests and full unit suite passed 251 tests on 2026-10-10. BT-060 adds run output-file writing for scripted/CI result capture; focused CLI tests passed 16 tests and full unit suite passed 252 tests on 2026-10-10. BT-061 adds dry-run tool observation without workspace writes; focused CLI tests passed 17 tests and full unit suite passed 253 tests on 2026-10-10. Live provider/task projection remains later M1 work.
- [x] M1.34 `core`: persist ToolCallRequested + PolicyDecision before dispatch; ToolResult/Failure after. Evidence: `src/forgeweave/events/execution.py`, `src/forgeweave/events/store.py`, `tests/unit/test_tool_execution_events.py`; `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 60 tests on 2026-10-04.
- [x] M1.35 `core`: parallel read-only dispatch, serialized edits. Evidence: BT-031 adds deterministic observation ordering; BT-032 groups read-only jobs into parallel-ready stages and serializes write/process/network/external effects; BT-033 executes planned stages through serial and injectable parallel executors while preserving model-visible order. Focused dispatch tests passed 10 tests and full unit suite passed 182 tests on 2026-10-06.
- [ ] M1.36 `core`: crash recovery reconciling in-flight calls. Partial evidence: BT-062 adds `ToolExecutionRecovery` to cancel REQUESTED/AUTHORIZED tool executions after restart and mark DISPATCHING executions as OUTCOME_UNKNOWN with required evidence while leaving terminal executions unchanged; focused recovery/event tests passed 7 tests and full unit suite passed 256 tests on 2026-10-10. BT-063 adds `TaskRecoveryCoordinator` so resume first reconciles the failed attempt, cancels not-dispatched calls and blocks automatic resume on OUTCOME_UNKNOWN dispatched calls; focused task/recovery tests passed 10 tests and full unit suite passed 259 tests on 2026-10-10. BT-064 adds `TaskProjectionBuilder` to rebuild current task/attempt state from persisted lifecycle events with bounded status metadata; focused task projection/state/recovery tests passed 10 tests and full unit suite passed 262 tests on 2026-10-10. BT-065 wires `fw task status --event-store ... --task-id ...` to that durable projection while preserving `--task-file`; focused CLI/projection tests passed 22 tests and full unit suite passed 264 tests on 2026-10-10. BT-066 adds `fw task resume` backed by durable projection hydration and task recovery coordination, reporting cancelled/unknown tool executions and blocking ambiguous dispatched side effects; focused CLI tests passed 21 tests and full unit suite passed 266 tests on 2026-10-10. Crash-boundary fixtures remain open.
- [ ] M1.37 `verify`: check selection from repo config; evidence capture (command, env fingerprint, exit, timing, output artifact). Partial evidence: BT-012 adds `VerificationRunner` command execution with argv, cwd, environment/config/workspace fingerprints, exit code, timeout, capped output artifact and `VerificationRun` evidence; BT-071 adds repo-config check selection with config/workspace fingerprints; focused verify-selection tests passed 5 tests and full unit suite passed 281 tests on 2026-10-10. BT-072 exposes selected commands through `fw verify select` with config/workspace fingerprints; focused CLI/verify-selection tests passed 34 tests and full unit suite passed 283 tests on 2026-10-10. BT-073 adds selected-command execution with VerificationRun evidence and output artifacts; focused selected-runner/selection tests passed 9 tests and full unit suite passed 287 tests on 2026-10-10. BT-074 exposes selected-check execution through `fw verify run-selected`; focused CLI/selected-runner tests passed 35 tests and full unit suite passed 289 tests on 2026-10-10. BT-075 adds `VerificationRun.duration_ms`, measures it in `VerificationRunner`, and surfaces it through selected-run CLI output and final reports; focused verification/report/CLI tests passed 44 tests and full unit suite passed 289 tests on 2026-10-10. BT-076 adds `complete_from_selected_verification` to turn selected verification results into the structured final report and mark empty selected-check runs as an explicit risk; focused completion/final-report/selected-runner tests passed 12 tests and full unit suite passed 293 tests on 2026-10-10. BT-077 adds `complete_repository_task` as a native-loop-facing orchestration helper that selects and runs repository verification before producing the final report; focused task-completion/completion/selected-runner tests passed 12 tests and full unit suite passed 297 tests on 2026-10-10. Native loop still needs to invoke this boundary automatically after real implementation attempts.
- [ ] M1.38 `verify`: repair loop with identical-failure stop. Partial evidence: BT-012 adds `RepairGuard` and stable repeated-failure fingerprints with a harness-wide repair cap. BT-041 adds `RepairLoopController` that converts passed, failed and inconclusive `VerificationResult` values into canonical stop decisions while preserving repair fingerprints and output artifact references; focused core-repair tests passed 4 tests and full unit suite passed 201 tests on 2026-10-06. BT-047 adds `RepairOrchestrator` for verify/repair retries that stops on pass, repeated identical failure or repair-cap exhaustion; focused core-repair/verify/stop tests passed 17 tests and full unit suite passed 218 tests on 2026-10-10. BT-048 wires that controller into `NativeAgentLoop.run_context_repair` with tests proving model repair turns only run for retryable verification failures; focused core-loop/core-repair/verify tests passed 22 tests and full unit suite passed 220 tests on 2026-10-10. BT-053 adds task-runner-facing analyzer execution around mutating tools. BT-054 wires that executor into `NativeAgentLoop` dispatch and maps blocked regression-gate decisions to failed loop stops; focused core-loop/verified-tool tests passed 15 tests and full unit suite passed 239 tests on 2026-10-10. BT-055 adds verified executor factory construction; `fw verify config` exposes construction validation; live `fw run` integration remains open.
- [x] M1.38a `verify`: `Finding` contract + analyzer adapter protocol. Evidence: BT-049 adds `AnalyzerInvocation`, `AnalyzerResult` and `AnalyzerAdapter` so analyzer adapters own process invocation/parsing and return normalized `Finding` values or fail-closed infrastructure evidence; focused analyzer/regression/verify tests passed 20 tests and full unit suite passed 224 tests on 2026-10-10.
- [x] M1.38b `verify`: Ruff adapter for diagnostics + numeric metrics C901, PLR0912, PLR0915 and PLR1702 with isolated config pass. Evidence: BT-050 adds `RuffAnalyzerAdapter` with isolated JSON command construction, normalized diagnostic parsing, numeric `Finding.value`/`Finding.limit` extraction and fail-closed invalid-output handling; focused Ruff/analyzer/regression tests passed 19 tests and full unit suite passed 228 tests on 2026-10-10.
- [x] M1.38c `verify/regression`: implemented in `src/forgeweave/verify/regression.py` (`Finding`, `regressions`), tested: per file+analyzer+rule+symbol; numeric metrics worsen-only; diagnostics by occurrence count; cross-file debt cannot offset; moved functions are not regressions
- [x] M1.38d `verify`: Git-based snapshot before every mutating step so shell edits are covered; atomic claim of snapshot for idempotent duplicate delivery. Evidence: BT-051 adds `GitSnapshotStore` with Git patch capture, base commit/changed path/hash metadata and duplicate-claim preservation; focused snapshot/regression/Ruff tests passed 17 tests and full unit suite passed 230 tests on 2026-10-10.
- [x] M1.38e `verify`: `RetryBudget` is wired to analyzer fail-closed handling. Evidence: BT-052 adds `RegressionGate` and `RegressionGateDecision`; code regressions consume budget, passes reset it, and analyzer infrastructure failures block without consuming repair budget; focused regression-gate/regression/analyzer tests passed 19 tests and full unit suite passed 234 tests on 2026-10-10.
- [x] M1.38f (partial) Tests cover legacy debt, 63->70 blocks, 82->81 allowed, moved function, extra occurrence; invalid-syntax baseline repair still to do
- [ ] M1.39 Final answer: modified files, checks run, failed checks, risks, artifact links. Partial evidence: BT-069 adds `FinalReport`, `CheckSummary`, `build_final_report` and `render_final_report` for structured JSON/text task handoff from modified files, verification evidence, risks and artifact links; focused final-report tests passed 4 tests and full unit suite passed 274 tests on 2026-10-10. BT-070 adds `fw task report` to build/render that structured report from explicit modified files, VerificationRun JSON files, risks and artifact links; focused CLI/final-report tests passed 31 tests and full unit suite passed 276 tests on 2026-10-10. BT-076 adds the runner-facing completion helper that builds final reports from selected verification evidence; focused completion/final-report/selected-runner tests passed 12 tests and full unit suite passed 293 tests on 2026-10-10. BT-077 adds `complete_repository_task` to run selected repository verification and build the final report through one core completion boundary; focused task-completion/completion/selected-runner tests passed 12 tests and full unit suite passed 297 tests on 2026-10-10. BT-078 wires that boundary into `fw run --complete-report` after a stopping native-loop result and returns the structured report in JSON/text; focused CLI/task-completion tests passed 38 tests and full unit suite passed 300 tests on 2026-10-11. Live provider run integration remains open.
- [ ] M1.40 [win] `cli`: `fw run`, `fw task status|resume|cancel|diff`, `fw config show`, `--json`, slash commands, Ctrl+C. Partial evidence: BT-013 adds dependency-light `fw config show --json` and `fw task status --task-file ... --json`, with clean stdout/stderr capture and a `pyproject.toml` script entry. BT-056 adds `fw verify config` to validate verified-dispatch construction from explicit repo/snapshot/target/config inputs without running analyzers; focused CLI/factory tests passed 11 tests and full unit suite passed 244 tests on 2026-10-10. BT-057 adds the first deterministic `fw run` path with JSON/text output and rooted write_text tool execution. BT-058 adds `fw run --prompt-file` as a mutually exclusive prompt source; focused CLI tests passed 13 tests and full unit suite passed 249 tests on 2026-10-10. BT-059 adds `fw run --fake-tool-call-file` as a mutually exclusive deterministic tool-call source; focused CLI tests passed 15 tests and full unit suite passed 251 tests on 2026-10-10. BT-060 adds `fw run --output-file` for JSON/text result capture without stdout; focused CLI tests passed 16 tests and full unit suite passed 252 tests on 2026-10-10. BT-061 adds `fw run --dry-run` for validated tool observation without workspace writes; focused CLI tests passed 17 tests and full unit suite passed 253 tests on 2026-10-10. `fw task status --event-store` now exposes live event-store task projection (BT-065), and `fw task resume` performs recovery-backed event-store resume (BT-066). `fw task cancel` now appends durable lifecycle cancellation from the event store (BT-067). `fw task diff` now exposes bounded read-only Git patches for explicit repository roots (BT-068). BT-078 adds `fw run --complete-report` with task id, verification output, modified-file, risk and artifact options, preserving `final_report: null` until the loop stops; focused CLI/task-completion tests passed 38 tests and full unit suite passed 300 tests on 2026-10-11. BT-079 catches keyboard interruption at the CLI boundary and returns exit code 130 without a traceback; focused CLI tests passed 35 tests and full unit suite passed 301 tests on 2026-10-11. BT-080 adds a local slash-command parser for `/help`, `/config` and `/status`, wires it into `fw run` before model invocation, and fails closed on unknown slash commands; focused CLI/slash tests passed 42 tests and full unit suite passed 308 tests on 2026-10-11. BT-081 adds explicit `fw run --provider openai-compatible`, reusing the existing OpenAI-compatible adapter from environment configuration and rejecting fake response/tool-call inputs on the live provider; focused CLI/provider tests passed 46 tests and full unit suite passed 310 tests on 2026-10-11. BT-083 exports the registry-owned tool catalog and passes it into model-provider calls so live providers can select available tools; focused registry/core/CLI/provider tests passed 62 tests and full unit suite passed 313 tests on 2026-10-11. Deeper subprocess cancellation propagation remains open.
- [ ] M1.41 Seeded-bug fixture repository + end-to-end test
- [ ] M1.42 Crash tests at each boundary (pre-dispatch, post-policy, mid-tool, post-result/pre-append). Partial evidence: BT-084 covers post-result/pre-append artifact publication reconciliation for present/missing/corrupt artifact files without replaying tools; broader crash fixtures remain open
- [ ] M1.43 [sec] Initial adversarial fixtures (injection in README/tool output, traversal, symlink)
- [ ] M1.44 Every model request has an ordered context manifest and declared exact/redacted/reference-only replay fidelity; exact sensitive payloads retained only by consent (SYSTEM_DESIGN 13.2). Partial evidence: BT-011 context packets emit ordered `ContextManifest` records with default redacted fidelity; core-loop integration for every model request remains open.
- [x] M1.45 Event-log migration rule: committed generations are never rewritten; successor published beside source; adjacent `vN -> vN+1` migration steps. Evidence: `src/forgeweave/events/migrations.py`, `src/forgeweave/events/store.py`, `tests/unit/test_events_migrations.py`; `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 52 tests on 2026-10-02.
- [ ] **M1 GATE:** seeded bug fixed + verified + resumed after kill with no duplicate side effect; original checkout untouched; Windows native pass

---

## M2 — Extensible harness

### Providers
- [ ] M2.1 Adapters: Anthropic, Moonshot/Kimi, DeepSeek, Meta Model API, xAI (only with official docs/access)
- [ ] M2.2 OpenAI-compatible adapter + explicit compatibility tests; local endpoint support. Partial evidence: BT-010A adds an OpenAI-compatible Responses adapter with injectable client tests and `.env`-loaded Azure smoke; BT-081 wires that adapter into `fw run --provider openai-compatible` with mocked CLI coverage; BT-083 passes registry tool specs into provider calls. Provider-specific live tool-call schema compatibility remains open.
- [ ] M2.3 Capability negotiation and graceful limits for small models
- [ ] M2.4 Provider failover, circuit breakers, per-model concurrency gates
- [ ] M2.5 [sec] Repository policy blocking disallowed providers

### Engines (optional delegated backends)
- [x] M2.5a `contracts`: `EngineRun`, `EngineEvent` (untrusted observation), isolation-level enum (`mediated`, `delegated-unmediated`) (done in `src/forgeweave/engines/contracts.py`; `EngineRun` persistence still to do with event store)
- [x] M2.5b `engines`: `DelegatedEngine` protocol (`run` with `on_event` and `CancelToken`); registry `get_engine`; CLI flag `--engine native|jsonrpc|appserver` still to do
- [ ] M2.5c [sec] Import-linter: `core` never imports `engines`; vendor SDK imports only inside adapters; missing extra yields "engine unavailable"
- [x] M2.5d `engines/general.JsonRpcEngine`: JSON-RPC stdio adapter over `deepseek-harness-sdk` implemented with fakes (default profile `sdk`, not `sdk-minimal`); still to do: real-runtime run after spike M0.14a
- [ ] M2.5e [sec] DeepSeek upload patch derived from `dsh --profile sdk --dump-config` (whole-row replacement semantics); adapter already refuses to run unless `upload_disabled_attested=True`; also set OTel session upload `DISABLED`; test asserts no upload plugin active against the real runtime
- [x] M2.5f `engines/general.AppServerEngine`: app-server adapter over `openai-codex` implemented with fakes; requires explicit `approval_mode`; still to do: determine `ApprovalMode` members and run against the real runtime after spike M0.14b
- [ ] M2.5g [sec] Mediated mode (if M0.14c passes): engine native shell/fs disabled; tools served via ForgeWeave MCP endpoint; every call authorized by `PolicyGateway`; test that an engine cannot write outside its worktree
- [x] M2.5h (partial) [sec] Delegated-mode pre-flight `validate_request` implemented and tested (opt-in, forbidden effects, worktree-only, engine home isolation, provider allow-list); still to do: repository-policy loader and OS-level confinement evidence
- [ ] M2.5i Import engine events as `EngineEvent`, linked to task event log; engine "done" never completes a task; ForgeWeave verifier and regression policy run on the resulting worktree diff
- [ ] M2.5j Crash/resume: reconcile engine session id with ForgeWeave attempt id; engine crash mid-run leaves worktree preserved
- [ ] M2.5k [win] Cancellation propagates to the engine subprocess tree (Job Object); test no orphan `dsh`/Codex processes
- [ ] M2.5l Pin exact versions in extras (`engine-deepseek`, `engine-codex`); Windows x64 CI smoke; protocol conformance tests with a fake engine
- [ ] M2.5m Optional verifier plugin: `codex-harness-check` subprocess with isolated HOME, Python 3.12+ only, findings mapped into `Finding`; never writes to the user's `~/.codex`
- [ ] M2.5n Extra analyzer adapters (Flake8, Pylint, Black check-only, MyPy) reusing the M1 adapter contract
- [ ] M2.5o Plugin registry with scoped registrations that unwind on unload (Cordis-style); test teardown leaves no tools/hooks registered
- [ ] M2.5p Hook event names and ordering aligned with plan.md 4.1 (pre-step, request, pre-execute, execute, post-execute, turn-stopping); hooks may deny or add checks only
- [ ] M2.5q `fw config show --effective` prints layered composition (defaults, project, user, CLI overlay) with provenance

### Hooks, skills, plugins
- [ ] M2.6 `hooks`: before/after turn, model call, tool, edit, test, approval, completion; deny/add-checks only
- [ ] M2.7 [sec] Test: hooks cannot bypass policy gateway
- [ ] M2.8 `skills`: discovery (`.forgeweave/skills`, user dir, `.agents/skills`, `.claude/skills`), metadata-first, on-demand body/resources
- [ ] M2.9 `skills`: frontmatter/reference/cycle/size validation; checksum + invocation logging
- [ ] M2.10 [sec] Test: skills cannot expand permissions; scripts go through shell policy
- [ ] M2.11 `plugins`: manifest (API version, permissions, entry point, signature/trusted source, deps, limits)
- [ ] M2.12 [sec] `plugins`: out-of-process runner, resource limits, typed tool/context/verifier registration
- [ ] M2.13 CLI: `fw skill list|show|validate|run`, `fw plugin ...`

### MCP
- [ ] M2.14 `mcp`: stdio client via official SDK; capability negotiation; tools/resources/prompts handled separately
- [ ] M2.15 [sec] `mcp`: namespaced permissions, trust level, allowlisted ops, timeouts, response byte caps, schema validation at invocation
- [ ] M2.16 `mcp`: catalog cache within advertised limits; catalog-change handling
- [ ] M2.17 [sec] `mcp`: audit record (server identity, schema version, redacted args, authorization, outcome); sampling/server-initiated requests disabled
- [ ] M2.18 CLI: `fw mcp add|list|inspect|test|remove` with effective-permission explanation
- [ ] M2.19 Stdio MCP fixture server + tests

### Sessions, SDK, telemetry

- [ ] M2.P1 `context`/`tools`: optional ObservationProjection with bounded first exposure, exact page rehydration, failure pinning, stale/missing/private-artifact tests; preserve lossless permitted artifacts and context-manifest references. Depends on M1.P1 and context/tool gateway.
- [ ] M2.P2 `verify`/`context`/`models`: optional EvidenceReceipt extraction for registered build/test outputs; validate hash/status/spans/size and structured failure completeness; account auxiliary model/root budget; fall back safely. Test forged/incomplete receipts and incompatible provider/retention state.
- [ ] M2.P3 `core`/`tools`/`policy`: optional edit/check ActionSequence using existing tools; separate permissions/events, post-edit fingerprint, approval pause, conflict/skip behavior and per-action crash reconciliation. Never inherit patch approval for shell execution.
- [ ] M2.P4 `context`/`telemetry`: optional CompactionEstimate at verified plan boundaries; include summarizer spend, cache rewrite/read costs and uncertainty; pressure-based hard limit remains; feature-alone/combined eval before enabling.

- [ ] M2.H1 `tools/web`: versioned SearchProvider/SearchRequest/SearchResult contracts and lazy DDGS adapter; inspect exact release, approved backend restriction (including invalid-backend auto-fallback), enforced deadline/cancellation and no startup network. Depends on native registry/policy/budgets.
- [ ] M2.H2 `tools/web`/`policy`/`context`: `web_search` and separate `web_fetch`; query disclosure/redaction, network authorization, URL/DNS/redirect/post-filter controls, bounded extracted artifacts, citations, TTL/cache scoping and tainted-content handling.
- [ ] M2.H3 `tools/web`: optional configured SearXNG HTTP adapter; JSON-disabled/rate-limit/fallback behavior; fixture-driven fake-model search -> fetch -> cited implementation evidence. Live checks separately authorized; native offline tools work without extras.
- [ ] M2.H4 `telemetry`/`cli`/`sdk`: expand M1 diagnostics with OTel adapters, linked worker/workflow spans, bounded redacted trace export and `fw task logs`, `fw trace show|export`, `fw metrics show`; CLI/SDK equivalence, sink failure and no-default-upload tests. Supplements M2.24-25.
- [ ] M2.H5 `hooks`/`plugins`: deterministic interception order, required-check vs optional-observer failures, recursion limits, scoped registration/unload and no policy bypass; reuse existing owners.
- [ ] M2.H6 `verify`/`telemetry`: pinned harness eval corpus/config and fault-injection runner; record verified acceptance, regressions, usage, latency, stalls and interventions; distinguish fake fixtures from opt-in live model trials.
- [ ] M2.20 `sessions`: projection from events, snapshots, replay (never executes tools), branch/fork, resume checks. Partial evidence: BT-064 adds task lifecycle projection from committed events without executing tools; BT-065 exposes that projection through `fw task status --event-store` while preserving the file-based status path; BT-066 uses the projection to hydrate task state for recovery-backed resume; BT-067 uses the same projection path for durable task cancellation. Broader session snapshots, replay, branch/fork and resume checks remain open.
- [ ] M2.21 JSON/headless output stable event schema
- [ ] M2.22 `sdk`: create task, stream events, cancel, resume, approvals, branch, artifacts, trace export
- [ ] M2.23 Test: SDK and CLI emit equivalent events
- [ ] M2.24 `telemetry`: OTel spans + local JSON exporter; redaction; correlation ids
- [ ] M2.25 Token estimate vs billed usage tracking; spend ceilings

### Routing (deferred)
- [ ] Deferred by ADR-001: retain M2.26-M2.33 as a future Laya proposal; do not implement, install, benchmark, or expose routing commands in the active native-core sequence.
- [ ] **M2 GATE:** skills/plugins cannot exceed permissions; failures recover or fail clearly; SDK == CLI events; deterministic routing cannot alter permissions; engine run recorded as one task with untrusted events, true isolation label, original checkout untouched, and engine absence/failure never affects `--engine native`

Expanded M2 gate: M2.H1-H6 checks pass for enabled features; research tools never disclose to ineligible providers, fetched sources have provenance, required hooks fail closed, diagnostic exports redact and require opt-in for network sinks.

---

## M3 — Browser and agent orchestration

### Browser
- [ ] M3.1 `browser`: BrowserManager (async Playwright, isolated non-persistent context per task, tab registry, teardown guarantee)
- [ ] M3.2 Typed tools: open, snapshot, click, fill, select, type, press, scroll, wait, screenshot, download, upload, tabs, console, close
- [ ] M3.3 Snapshot with stable element refs; reject stale refs; role/label/test-id locators; ambiguity errors; bounded waits
- [ ] M3.4 [sec] URL policy: block file://, loopback, private ranges, metadata; validate redirects + DNS resolution; domain allowlist
- [ ] M3.5 [sec] Effect classification (read-only navigation vs state-changing click/upload/submit); policy on effect
- [ ] M3.6 [sec] No arbitrary `page.evaluate` without high-risk permission; no cookie/storage persistence by default; no credential echo
- [ ] M3.7 Size limits (screenshots, DOM excerpts, downloads, traces); download dir allowlist; vision gating by policy
- [ ] M3.8 Playwright trace on failure, redacted, task-local artifact
- [ ] M3.9 Resume revalidates page state (no click replay); headed/headless modes; `--browser` opt-in
- [ ] M3.10 Local fixture server tests: navigation, popups, downloads, forms, stale locators, blocked hosts, timeouts, crash, cleanup

### Agents and subagents

- [ ] M3.P1 `agents`/`verify`: group-scoped EvidenceBoard from existing artifacts/events; immutable candidate snapshot, independent reproduction and verified best-candidate update; stale/unverified claims cannot satisfy fan-in. Depends on M3.H1-H4.

- [ ] M3.H1 `agents`/`contracts`: DelegationRequest/ChildRun/ChildResult/JoinGroup/message schemas with idempotency, lineage, role hash, context refs, workspace base, output criteria and aggregate budget reservation. Supplements M3.11-16 and M3.R1.
- [ ] M3.H2 `agents`: admitted vs idle vs verified completion, one-shot then continuable child attempts; durable mailbox receipts/cursors, event-driven wait, policy-controlled spawn/message/list/interrupt/continue; restart reconciliation and bounded parent cancellation. Test duplicate spawn/message, root cap race, stale context, permission escalation and startup failure.
- [ ] M3.H3 `agents`: explicit fan-out membership and fan-in `all_success`, `all_settled`, `quorum(k)`, `first_verified`; bounded map inputs, stable ordering, fail-fast/collect-errors and cancel/drain policy. Test duplicate/late/malformed/stale results, worker crash and deterministic joins.
- [ ] M3.H4 `agents`/`workspace`/`verify`: fan-in integration reviews worker scope/base/patches; detect overlap and conflicts; three-way merge in integrator workspace; verify combined fingerprint and preserve provenance/rejected artifacts. Supplements M3.17-19.
- [ ] M3.H5 `browser`: browser-use exact-release/source feasibility spike: enumerate every default/custom browser/file/script/skill/cloud action and nested model call; prove policy interception before effects and accounted budgets; disable telemetry before import in isolated subprocess and capture outbound traffic on Windows. No mediation claim from a callback alone.
- [ ] M3.H6 `browser`/`models`/`policy`: optional browser-use adapter only after M3.H5 succeeds; isolated state, action-by-action canonical events, cancellation, no old-click replay, denial/hidden-action/download/JS/telemetry tests. If mediation fails, retain restricted delegated-unmediated experiments; native Playwright remains baseline.
- [ ] M3.11 `agents`: definition loader/validator (`.forgeweave/agents/*.yaml|md`); permission intersection; checksum + effective permissions logged
- [ ] M3.12 Built-in agents: explore, plan, implement, review, test, browser
- [ ] M3.13 CLI: `fw agent list|show|validate|run`, `--agent`, task-scoped handoff
- [ ] M3.14 `agents`: `AgentScheduler` (parent-child records, typed delegation, output contract, per-child budget, depth/fanout/time/spend limits)
- [ ] M3.15 Read-only concurrent exploration on pinned commit; isolated worktree + branch per writer
- [ ] M3.16 Child context: selected instructions + references only (no transcript dump); children return summary/evidence/patch ref/open questions
- [ ] M3.17 Integrator workflow: review diffs, reconcile conflicts, verify merged result, provenance report
- [ ] M3.18 Cancellation/approval propagation; sibling failure isolation
- [ ] M3.19 Tests: deterministic scheduling, timeout, partial failure, overlapping edits, conflicts, stale base commit, merged verification

### Git CLI
- [ ] M3.20 CLI: `fw worktree list|create|inspect|switch|lock|unlock|cleanup`
- [ ] M3.21 CLI: `fw branch create|compare|checkpoint|merge`; `fw task apply|commit`
- [ ] M3.22 Checkpoints (commit or patch + base hash); three-way merge apply; abort on conflict; ancestry checks
- [ ] **M3 GATE:** browser obeys domain/effect permissions; no shared-worktree writers; conflict/timeout/cancel/recovery tests pass

Expanded M3 gate: enabled delegation passes M3.H1-H4 lifecycle/join/budget fixtures; browser-use availability is reported honestly against M3.H5-H6. Never claim parity or complete mediation from mocked adapters.

---

## M4 — Automation and Git workflow

- [ ] M4.H1 `automation`: immutable WorkflowDefinition/Run/Step/Attempt contracts; typed bounded map/join/condition/approval/agent/tool/verification nodes; cycles/types/dependency/capability validation before dispatch; JoinGroup references reuse `agents` contracts. Partial evidence: BT-086 adds immutable WorkflowDefinition, WorkflowRun, WorkflowStep, StepAttempt, typed step kinds, JoinPolicy, stable definition/input hashes, and validation for duplicate IDs, unknown dependencies, cycles and invalid quorum joins. Capability authorization, artifact bindings and agents JoinGroup reuse remain open.
- [ ] M4.H2 `automation`/`events`: step leases/fencing/idempotency, validated artifact bindings, declared fail-fast/collect-errors, bounded cancellation, approval pause/resume and changed-definition/input handling. Test crash-after-submit, stale lease, resumed join and retry budget persistence. Explicit compensation requires its own policy decision. Partial evidence: BT-087 adds SQLite persistence for immutable workflow definitions, admitted runs bound to definition/input hashes, idempotent step attempts and status updates preserving lease/idempotency evidence. BT-088 adds a read-only workflow planner that computes ready/waiting/active/completed/failed steps from persisted state without dispatching effects. BT-095 adds a safe runner tick that records ready steps as idempotent attempts without executing side effects and deterministically completes join steps. BT-096 adds retry-aware runner projection for failed/cancelled steps with remaining `max_attempts`. BT-097 adds an explicit mediated executor registry and runner bridge for registered step executors. BT-098 adds a concrete policy-mediated tool-step executor. BT-099 adds a native-agent workflow executor backed by NativeAgentLoop. BT-100 wires executor-enabled workflow ticks into the CLI behind explicit flags. BT-101 adds a verification-step executor backed by selected verification evidence. Step lease enforcement, approval pause/resume and artifact bindings remain open.
- [ ] M4.H3 `automation`/`cli`: inspect tree/joins/active workers/budgets/evidence; templates for research-plan-implement-test-review, parallel investigation-synthesis and independent patches-integration-verification. No arbitrary model-authored code evaluation; publication stays separately authorized. Partial evidence: BT-088 adds the read-only scheduling projection that CLI status/tree views can use; BT-089 adds a workflow status projection combining persisted run, definition, attempts and planner output into inspectable step/run state; BT-090 adds `fw workflow status` JSON/text rendering over the persisted workflow store; BT-091 adds JSON workflow definition validation; BT-092 adds persisted workflow definition/run listing; BT-093 completes the initial workflow CLI with safe run admission and resume; BT-094 adds built-in static templates for research-plan-implement-test-review, parallel investigation-synthesis and independent patches-integration-verification with CLI inspection.

- [ ] M4.1 `automation`: definitions, next/last run, status, task link in SQLite. Partial evidence: BT-087 stores workflow definitions, runs and step attempts in SQLite; BT-092 exposes persisted definitions and runs through read-only store listing and `fw workflow list`; scheduler next/last run, task links and actual runner execution remain open.
- [ ] M4.2 Cron in IANA timezone incl. DST transitions (tests for skipped/repeated hours)
- [ ] M4.3 `fw automation serve|add|list|pause|resume|history|remove`; clearly show serve-process dependency
- [ ] M4.4 OS scheduler export (Windows Task Scheduler, cron)
- [ ] M4.5 Idempotency keys, leases, per-repo concurrency caps, bounded retries; no replay of non-idempotent calls
- [ ] M4.6 One-shot `fw run --prompt-file ... --json`; CI/GitHub Actions invocation. Partial evidence: BT-058 adds `--prompt-file` for scripted JSON runs, BT-059 adds `--fake-tool-call-file` for deterministic scripted tool-call runs, BT-060 adds `--output-file` for CI artifact capture and BT-061 adds `--dry-run` for non-mutating scripted validation; CI/GitHub Actions invocation remains open.
- [ ] M4.7 Filesystem/Git event triggers
- [ ] M4.8 Workflow YAML schema + validator; constrained expression language (no arbitrary Python eval)
- [ ] M4.9 Workflow runner: DAG, per-step budget/retry per idempotency, approval gates, artifacts, verification gates. Partial evidence: BT-095 adds the safe persisted runner tick and `fw workflow tick`; BT-097 adds the mediated executor registry and runner bridge; BT-099 adds the native-agent executor bridge; BT-100 wires native-agent/tool executors into `fw workflow tick`; artifact bindings and approval gates remain open; BT-101 adds a verification-step executor backed by selected verification evidence; BT-098 adds the policy-mediated tool-step executor; BT-096 adds retry-aware projection for persisted failed/cancelled attempts.
- [ ] M4.10 CLI: `fw workflow validate|list|run|status|resume`. Partial evidence: BT-090 implements `fw workflow status` for persisted run inspection; BT-091 implements `fw workflow validate` for JSON definition files; BT-092 implements `fw workflow list`; BT-093 implements safe `fw workflow run` admission and `fw workflow resume`; BT-095 adds `fw workflow tick` for one safe persisted scheduler tick; BT-100 adds explicit executor-enabled tick flags.
- [ ] M4.11 Example workflows: issue-to-patch, PR review, dependency update, browser UI regression, scheduled test triage, docs sync. Partial evidence: BT-094 adds the first static built-in workflow templates for core coding-agent flows; integration-specific examples remain open.
- [ ] M4.12 `integrations/github`: `gh`/API wrapper; issue/PR/CI polling; commit-pinned checkout
- [ ] M4.13 [sec] Optional signed webhook receiver (HMAC verification, replay window)
- [ ] M4.14 Review-comment intake mapped to current lines; plan update; rerun affected checks
- [ ] M4.15 [sec] Opt-in PR creation, branch push, external message, deployment (explicit task policy + approval; never implicit from green tests)
- [ ] M4.16 Optional signed commit policy; conflict-aware branch integration; `fw task pr`
- [ ] M4.17 Failure reporting: inspectable result + local notification/reporting adapter
- [ ] M4.18 Tests: duplicate event -> one task; crash retry -> no duplicate PR/external action; DST; concurrency cap
- [ ] **M4 GATE:** duplicates collapse; no duplicated external effects; each run links to auditable history

---

## M5 — Advanced local intelligence

- [ ] M5.P1 `automation`/`verify`: optional isolated harness-development experiment workflow with immutable hypothesis/candidate lineage, development-only feedback, review, finite budgets and no installed-harness/policy/evaluator mutation. Depends on workflow/eval foundations; not production self-modification.

### Memory
- [ ] M5.1 `memory`: stores for working, session, episodic, project, user, procedural (separate storage and retrieval)
- [ ] M5.2 Promotion pipeline candidate -> source-verified -> accepted; evidence/user acceptance required
- [ ] M5.3 Duplicate/contradiction/supersession with lineage; expiry and reverification triggers
- [ ] M5.4 [sec] Secret redaction, encryption for opted-in sensitive records, retention, no cross-repo leakage
- [ ] M5.5 Scoped, ranked, token-limited retrieval with source + verification date
- [ ] M5.6 CLI: `fw memory list|show|search|add|approve|edit|forget|export`; edit audit log
- [ ] M5.7 Tests: stale memory, contradiction, cross-repo leakage, forget semantics, usefulness vs no-memory baseline

### Semantic index (optional)
- [ ] M5.8 Incremental index of allowed files only; hash+commit tied; exclude secrets/generated; syntax-boundary chunking
- [ ] M5.9 Compare precision against lexical search; enable by default only if better

### Laya active mode (deferred)
- [ ] Deferred by ADR-001: retain M5.10-M5.15 as a future proposal. Reintroduce only through a new ADR after the native M1 gate and a demonstrated deterministic-routing limitation.

### Remote MCP, cost, UI tests
- [ ] M5.16 [sec] MCP Streamable HTTP + authentication
- [ ] M5.17 Cost controls: pre-run estimates, ceilings, circuit breakers
- [ ] M5.18 Richer browser-assisted UI tests; workflow templates

### Ralph
- [ ] M5.19 `ralph`: goal/spec versioning, `plan.json` schema, `progress.jsonl`; controller-owned status transitions
- [ ] M5.20 Iteration state machine; one unit per iteration; fresh bounded context; worktree reconciliation after crash
- [ ] M5.21 Independent acceptance verifier (completion phrase never sufficient)
- [ ] M5.22 Stop conditions: verified completion, cancel, budget, repeated identical failure, no progress in N, policy block, outage, unsafe workspace
- [ ] M5.23 Pause for approval/resume without repeating external side effects; checkpoint verified vs labeled unverified patches
- [ ] M5.24 CLI: `fw ralph start|status|pause|resume|stop|explain`; no recursive Ralph; single-agent default
- [ ] M5.25 Plan-update validation (cannot delete required acceptance criteria)
- [ ] M5.26 Adversarial tests: false success, same-line churn, oscillation, flaky verifier, changed criteria, summary losing requirement, crash between patch and append, subagent conflict
- [ ] M5.27 Compaction tests: critical constraints survive; lost-constraint detection
- [ ] **M5 GATE:** memory inspectable/erasable; Ralph rejects false completion + stops stalls; multi-agent keeps verification evidence. Laya is excluded from this gate by ADR-001.

---

## M6 — Hardening and release

- [ ] M6.P1 `verify`: frozen EvaluationProfile/ReleaseCandidate and protected held-out split; predeclared capability/efficiency thresholds, auxiliary-cost accounting, repeated feature-alone/combined checks, failure rejection and no feedback leakage. Unknown thresholds/data cannot pass.
- [ ] M6.P2 `cli`/`verify`/`events`: release manifest with dependency/config hashes, full feature evidence, Windows recovery checks, known limitations and optional defaults; rehearse rollback to verified compatible build/config without destructive database downgrade. Publication remains separately authorized.

- [ ] M6.H1 Reconcile every F01-F35 coverage row with implemented evidence, unresolved limitations or explicit deferral; publish measured eval/support results. Include per-loop cancellation, fan-in recovery, search privacy, optimization/rollback and browser-use mediation/telemetry evidence for enabled capabilities.

- [ ] M6.1 Fault injection: provider outage, disk full, DB lock, killed subprocess, corrupt event, partial artifact
- [ ] M6.2 [sec] Security review against threat model; adversarial suite for all critical cases
- [ ] M6.3 [sec] Supply-chain and license review; SBOM; pin dependencies
- [ ] M6.4 Migration, backup and restore drills (SQLite + artifacts together)
- [ ] M6.5 [win] Package validation on Windows, macOS, Linux; offline mode check
- [ ] M6.6 CLI accessibility review (no color-only signals, screen-reader friendly output)
- [ ] M6.7 Performance targets measured: CLI startup, scheduled-job start, event persistence, cancellation latency, resume success
- [ ] M6.8 Full evaluation run: pass@1, accepted-change rate, regressions, cost, latency, retrieval precision, approvals, policy violations, recovery
- [ ] M6.9 Final end-to-end scenario (issue -> draft PR) run with interruption at three boundaries
- [ ] M6.10 Docs, examples, support runbooks, release pipeline
- [ ] M6.11 Record editor/web/ACP/hosted as separate future proposals
- [ ] **M6 GATE:** critical threat cases tested; offline-usable except model calls

---

## Ongoing (every milestone)
- [ ] Keep [BUILD_TRACKER.md](BUILD_TRACKER.md) current with the active slice, planned files, checks and evidence before proceeding to each next phase
- [ ] Keep adversarial fixtures growing with each new input surface
- [ ] Keep capability matrix and ADRs current
- [ ] Keep import-linter contracts green
- [ ] Re-verify external SDK/API docs at implementation time
- [ ] Track requirement status, owner, evidence link for each item

## Pre-development review additions — ordered with the existing milestones

Documentation review completed 2026-10-02: [research evidence](docs/research/architecture-review-2026-10-02.md), [operational contracts](SYSTEM_DESIGN.md#13-pre-development-operational-contracts-2026-10-02), plan section 15. These tasks extend existing items; they do not mark runtime capabilities complete.

- [x] M0.R1 Define ConstraintLedger, ContextManifest, SummaryRecord, ApprovalGrant, ToolExecution, ExecutionProfile, BudgetLedger, AcceptanceSpec and VerificationRun schemas (owners: contracts plus subsystem protocols; depends M0.20–24). Evidence: `src/forgeweave/contracts/operational.py`, `tests/unit/test_contracts.py`; `PYTHONPATH=src python -m unittest discover -s tests/unit` passed 35 tests on 2026-10-02.
- [ ] M0.R2 Resolve intended repository root before worktree use; record Windows filesystem/network isolation backend evidence separately from Job Object cancellation (workspace/policy; depends M0.13)
- [ ] M0.R3 Define replay/retention modes, local SQLite durability/backup policy and shared transaction unit of work (events/sessions; depends M0.8)
- [ ] M1.R1 Protected requirement ledger and context manifest; provider-aware fit checks, ten-compaction fixture, unsupported-summary/injection/overflow tests; CLI context inspect/explain (context/models/CLI; depends M0.R1). Partial evidence: BT-011 preserves active `ConstraintLedger` criteria in context and raises unsatisfiable fit errors instead of dropping protected spans; BT-045 adds `ContextModelInput` so manifest-backed context can be handed to the native loop with diagnostics refs; BT-046 adds `NativeLoopContextBuilder` for provider-budgeted native-loop context assembly; ten-compaction, unsupported-summary/injection fixtures and CLI inspect/explain remain open.
- [ ] M1.R2 Action-bound approval expiry/revocation/single-use atomic consumption; headless approval-needed behavior (policy/CLI; depends M1.8). Partial evidence: BT-008 implements action-bound approval matching, expiry/revocation checks via `ApprovalGrant.matches`, and single-use SQLite consumption in `SQLiteApprovalStore`; headless CLI approval-needed behavior remains M1.40.
- [ ] M1.R3 Dispatch-intent/OUTCOME_UNKNOWN reconciliation, artifact publication recovery, lease fencing and crash/disk-full/busy tests (events/task/workspace; depends M0.R3, M1.1–5). Partial evidence: BT-062 adds restart reconciliation for in-flight tool executions, preserving ambiguous dispatched side effects as OUTCOME_UNKNOWN with evidence; BT-063 wires that recovery into task resume coordination, blocking new attempts while ambiguous dispatched calls require attention; BT-084 adds a restart-safe artifact publication ledger for the post-result/pre-append boundary, reconciling staged artifacts as published, missing or corrupt by hash evidence; BT-085 adds mutation-boundary lease fencing over WorkspaceLockStore to reject expired or replaced lock tokens; crash/disk-full/busy tests remain open. Partial evidence: dispatch intent and OUTCOME_UNKNOWN reconciliation are implemented in `src/forgeweave/events/execution.py` and covered by `tests/unit/test_tool_execution_events.py`; BT-043 adds loop lifecycle event references through `LoopEventRecorder`; BT-044 wires those loop lifecycle references into `NativeAgentLoop`; artifact publication recovery now has BT-084 ledger coverage; BT-085 adds workspace lease fencing; crash/disk-full/busy fixtures remain open.
- [ ] M1.R4 Bounded model stream accumulator; partial JSON never dispatched; conservative missing-usage accounting and reservations for retries/compaction (models/core; depends M0.R1). Partial evidence: BT-010 implements bounded tool-call JSON assembly, rejects incomplete/malformed tool calls before registry dispatch, and creates a conservative missing-usage reservation; retry/compaction reservation wiring remains open.
- [ ] M1.R5 Whole-input verification fingerprint, protected acceptance validators, inconclusive/flaky handling and harness-wide repair bound (verify/task; depends verification adapter tasks). Partial evidence: BT-012 emits `VerificationRun.whole_input_fingerprint`, marks timeouts inconclusive and adds `RepairGuard` stop reasons; protected validator weakening detection and flaky retry classification remain open.
- [ ] M1.R6 Windows path/reparse/device/ADS fixtures, terminal control filtering, Git-hook/test-command authorization and read-only doctor --json (tools/policy/workspace/CLI; depends M0.R2). Partial evidence: BT-009 path guard rejects absolute paths, traversal, symlink escape and colon-bearing relative components; device/reparse/ADS fixtures, terminal filtering, Git-hook/test-command authorization and doctor CLI remain open.
- [ ] M1.R7 Redacted default audit and exact-retention opt-in; task-scoped artifact lookup, retention tombstones and consistent backup restore fixture (events/sessions; depends M0.R3)
- [ ] M2.R1 MCP protocol/version reconnect negotiation, local server executable authorization and catalog invalidation (mcp/policy; depends M2.14–19)
- [ ] M3.R1 Aggregate child reservations and continuation of context/approval/recovery contracts across handoffs (agents/core; depends M3.14)
- [ ] M5.R1 Shared egress checks on remote MCP auth discovery, credential audience separation and no token passthrough (mcp/policy; depends M5.16)
- [ ] M5.R2 Forget invalidates summaries, indices and caches; report backup/export/provider deletion limits (memory/context/events; depends M5.4–7)
- [ ] M6.R1 Publish measured support matrix and requirement/evidence coverage; restricted execution claims require confinement fixtures on supported hosts

M0.R1–R3 are prerequisites for their M1 slices. M1.R1–R7 must pass before the expanded M1 gate; optional engine expansion waits for this gate. Engine-specific M0.14a/b/c/e/f runtime spikes are deferred research items for M2 and do not block the native M0/M1 gate. Network smoke tests and installs remain explicitly scoped future tasks, not actions performed in the documentation review.













