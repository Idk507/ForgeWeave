# ForgeWeave — Build Plan

Execution guide derived from [AGENTS.md](./AGENTS.md) (implementation contract) and [SYSTEM_DESIGN.md](./SYSTEM_DESIGN.md) (architecture). Task-level checklist lives in [todo.md](./todo.md). If this plan disagrees with either source, the sources win; record an ADR and update all documents.

## 1. Product in one paragraph

Current authority: [ADR-004](docs/architecture/adr-004-independent-native-cli.md), [source review](docs/research/native-cli-source-review-2026-11-01.md) and SYSTEM_DESIGN section 16. Implement an independent native coding CLI; other agents are references. N1–N3 in todo.md close CLI composition, continuing feedback and protected verification/recovery before extension work. Existing M-series acceptance requirements remain; external-engine delivery is retired. Do not use file-by-file progress as a substitute for a working user flow.

ForgeWeave is a model-independent, local-first **Python CLI coding agent**. Invariant: every authorized action, its originating context, the resulting change and its verification result stay inspectable and resumable from the CLI. The model proposes structured requests; the harness validates, authorizes and executes them. Editor, web UI, ACP, hosted service and cloud workers are out of scope for the first release.

## 2. Non-negotiable rules (apply to every task)

1. The model never executes tools. Flow: schema validation -> `PolicyGateway.authorize` -> execute -> observation.
2. Model output, retrieved code, README text, issues, web pages, MCP responses and plugin output are **untrusted data**, never policy. Instruction precedence: platform policy > org policy > task/user requirements > repo AGENTS.md/rules > skills > retrieved content.
3. Persist `ToolCallRequested` and `PolicyDecision` **before** execution, then `ToolResult`/`ToolFailure`. Recovery reconciles in-flight calls; it never blindly replays side effects.
4. Windows 11 native must work with no Docker, WSL, Redis, FastAPI, Postgres, daemon or telemetry service.
5. No network, deploy, billing, publish, credential or destructive action without explicit task authorization. Never log secrets or full sensitive prompts by default.
6. Python 3.11+, type hints and docstrings everywhere; Pydantic versioned contracts; asyncio orchestration; SQLite WAL.
7. Modify the owning module; do not add duplicate abstractions. Small, independently reviewable patches. Tests assert behavior at module boundaries and on real workspace changes.
8. Completion = verified acceptance criteria, never a model saying "done".
9. Permissions are always **intersected** (user/task/agent/skill/MCP/plugin), never unioned. Children get subsets of parent authority.
10. Do not copy proprietary source, prompts, branding or private APIs. Label proprietary internals "unknown".

## 3. Source-document reconciliation

ADR-003 incorporates the [SoL-Pi review](docs/research/sol-pi-review-2026-10-04.md): M1.P1 establishes evidence baselines; M2.P1-P4 evaluates bounded observation projections, validated extraction, edit/check orchestration and compaction economics; M3.P1 adds worker evidence exchange; M5.P1 adds isolated development experiments; M6.P1-P2 adds frozen release evaluation and rollout/rollback evidence. All extend existing owners and gates; no optimization enables itself or lowers capability requirements.

The 2026-10-04 amendment in [ADR-002](docs/architecture/adr-002-harness-coverage-and-research-tools.md) and SYSTEM_DESIGN section 14 supplies missing execution contracts. [Source review](docs/research/harness-source-review-2026-10-04.md) records pinned implementation studies; [coverage](docs/feature-coverage.md) maps them to backlog and gates. Preserve earlier feature requirements. Local diagnostic instrumentation now starts in M1; web search lands in M2; browser-use feasibility and explicit fan-out/fan-in land in M3; durable workflow joins land in M4. Full OTel/export remains M2. Runtime integrations require release-specific and Windows checks.

AGENTS.md milestones (M0-M6) and SYSTEM_DESIGN.md stages (0-6) differ in grouping. Plan adopts AGENTS milestones as the delivery order, with these explicit decisions recorded in [ADR-000](docs/architecture/adr-000.md):

| Topic | AGENTS.md | SYSTEM_DESIGN.md | Decision |
|---|---|---|---|
| Context assembler / session memory | M5 (memory) | Stage 2 | Context assembler, token budget, trim/rehydrate and session snapshots land in **M1/M2**; scoped long-term/episodic memory stays **M5**. |
| Skills, MCP, browser, subagents | M2-M3 | Stage 3 | Follow AGENTS (skills/MCP in M2, browser/subagents in M3). |
| Ralph + automation | Ralph M5, automation M4 | Stage 5 together | Follow AGENTS: automation **M4**, Ralph **M5**. |
| Long AGENTS.md | Feature inventory | "Keep as concise index" | After M0, shrink AGENTS.md into an index linking to SYSTEM_DESIGN.md and ADRs. |

## 4. Technology decisions

| Concern | Choice | Notes |
|---|---|---|
| Language/runtime | Python 3.11+ | Verify on 3.11, 3.12, 3.13. |
| Contracts | Pydantic v2 | Versioned; JSON Schema exported to `schemas/`. |
| Concurrency | asyncio | Cancellation tokens propagate to subprocesses and model streams. |
| Persistence | SQLite WAL + content-addressed artifact dir | Per-task artifact directory; hashes in SQLite. |
| CLI | `typer` (non-interactive), `prompt_toolkit` or `textual` (interactive) | **Spike first**: verify Windows console behavior (ANSI, Ctrl+C, resize). |
| Browser | Playwright Python async | One non-persistent context per task. |
| Web search | Optional DDGS, then user-configured SearXNG HTTP adapter | Typed search tool; explicit backends, query disclosure policy, separate guarded source fetch; no required search server. |
| Agentic browser automation | Optional browser-use adapter | M3 feasibility gate: mediate every action or label unmediated and restrict scope; telemetry disabled before import. |
| MCP | Official MCP Python SDK | stdio first, then Streamable HTTP. |
| Telemetry | OpenTelemetry API + local JSON exporter | No external service. |
| Secrets | OS keyring; encrypted file or env fallback | Explicit opt-in for fallback. |
| Packaging | `pyproject.toml`, `uv` or `pip`, `pytest`, `ruff`, `mypy`/`pyright`, `import-linter` | Pin after implementation-time checks. |
| Optional verifier: Codex Harness | `codex-harness` (optional extra `forgeweave[quality-codex-harness]`) | See section 4.1. Third-party; native implementation is the default. |

Dependency pinning rule: check current versions and licenses at implementation time; record in `docs/architecture/dependencies.md`.

Research on 2026-10-04 observed `openai-codex` 0.160.0, `ddgs` 9.16.0 and `browser-use` 0.13.10. These are observations, not upgraded pins. The repository still pins Codex 0.159.3. Reviewed upstream HEAD commits are not evidence that the current wheels contain identical implementations. See the source review for exact commits and package identity.

### 4.1 Reference harnesses and inactive engine experiments

[ADR-004](docs/architecture/adr-004-independent-native-cli.md) supersedes the earlier vendor-engine delivery proposal. ForgeWeave implements its own Python runtime. The [current source review](docs/research/native-cli-source-review-2026-11-01.md) records Codex, DeepSeek Harness, Claude Code, OpenCode and Reason findings and pinned revisions. The [2026-10-04 study](docs/research/harness-source-review-2026-10-04.md) retains historical package evidence.

Existing `engines` modules/extras are inactive experiments; do not expand, install or expose them as part of the native CLI. Native provider adapters call model APIs directly. Reuse baseline-vs-after verification ideas in the existing `verify` owner, scoped registrations in `plugins`, and event-derived history in `sessions`. Third-party `codex-harness` is distinct from OpenAI's runtime. No vendor code, SDK or CLI is required to run ForgeWeave.
## 5. Repository layout (target)

```
forgeweave/
  pyproject.toml
  AGENTS.md  SYSTEM_DESIGN.md  plan.md  todo.md
  docs/
    research/capability-matrix.md
    architecture/adr-*.md  threat-model.md  dependencies.md
    runbooks/
  schemas/                      # exported JSON Schema (generated)
  src/forgeweave/
    contracts/   events/   task/   core/       # core = agent loop, budgets, cancellation
    models/      routing/  context/ memory/
    engines/                       # inactive legacy experiments; outside product delivery
    tools/       policy/   workspace/ sessions/
    browser/     mcp/      skills/  agents/
    automation/  ralph/    verify/  telemetry/
    integrations/github/
    plugins/     hooks/
    cli/         sdk/
    app.py                      # composition root (only place wiring concrete adapters)
  tests/
    unit/ integration/ e2e/ adversarial/ fixtures/ evals/
  evals/                        # evaluation corpus + runners
```

Package boundary rules (enforced by `import-linter` contracts):
- `contracts` depends on nothing but Pydantic/stdlib.
- `core` never imports concrete `models`, `browser`, `mcp`, `routing`, `engines` implementations; depends on protocols in `contracts`.
- `engines` may import vendor SDKs only inside its adapters; the vendor SDK is an optional extra and import failure degrades to "engine unavailable".
- No module mutates another module's persistent state; writes go through the owner (e.g. only `events` writes the event log, only `workspace` touches worktree tables).
- Every tool/browser/MCP/plugin/subagent effect goes through `policy`.

## 6. Core contracts (define first, version everything)

- Entities: `EngineRun`, `EngineEvent` (untrusted imported observation), `Finding`, `FindingDelta` (regression result), `Task`, `Attempt`, `Session`, `Turn`, `Step`, `ToolSpec`, `ToolCall`, `EffectSet`, `PolicyDecision`, `Approval`, `Artifact`, `Event`, `Budget`, `ContextPacket`, `ToolCatalog`, `RoutingState`, `RoutingDecision`, `DecisionEvidence`, `MemoryEntry`, `Iteration`, `Automation`, `Lease`, `Worktree`.
- `Event` fields: `event_id, task_id, attempt_id, parent_id, sequence (monotonic per task), timestamp_utc, schema_version, actor, correlation_id, payload_ref`.
- Task states: `CREATED -> PREPARING -> RUNNING -> {WAITING_APPROVAL | WAITING_EXTERNAL} -> VERIFYING -> {COMPLETED | FAILED | CANCELLED}`; resume re-enters `RUNNING` via a **new attempt**; prior events immutable. Transitions are atomic with event append.
- Ralph iteration states: `QUEUED, SETTING_UP, EXECUTING, CHECKING, CONTINUING, BLOCKED, STOPPED`.
- `EffectSet`: read/write paths, network destinations, browser state mutation, external API operation, secret usage.
- Tool protocol: `describe() -> ToolSpec`, `validate(args) -> ParsedArgs`, `effects(args) -> EffectSet`, async `execute(args, ctx) -> ToolResult`.
- Provider protocol: `ModelProvider.stream(messages, tools, options, cancellation)` + capability descriptor (tool calling, vision, context limit, parallel calls, prompt caching, reasoning controls, output schema, usage).
- Memory entry: `id, scope, type, text, source_event_ids, source_paths_and_hashes, confidence, verification_status, created_at, last_verified_at, expires_at, sensitivity, owner, revision`.
- Idempotency: tool-call tokens; automation key = `(trigger source, event id, automation id, revision)`.
- Retry classes: safe/idempotent, conditionally reconcilable, non-retryable.

Gate for contracts: schema round-trips; event log rebuilds identical task state; migrations tested up/down where feasible.

## 7. Cross-cutting subsystems

### 7.1 Policy gateway
`PolicyGateway.authorize(task, agent, tool, arguments, effects) -> allow | deny | ask`. Intersects permissions; revalidates URL, path, command and side effects at dispatch time (TOCTOU). Handles unknown tool, stale catalog version, invalid args as structured errors with bounded retry. Taint tracking: lower-trust content flowing to sensitive sinks requires explicit authorization. Reports effective isolation level honestly (worktree != sandbox). Approval records persist and are auditable.

### 7.2 Context engineering
Budget `B = W - O - T - S`. Prompt order: platform/task policy -> repo instruction map -> user objective + acceptance criteria -> worktree/branch/test state -> recent turns -> code spans with provenance -> verified memories -> tool schemas -> bounded tool results. Operations: trim, summarize (cited, claims verified against events), rehydrate, reset. Compact before overflow. Retrieval ledger per turn. Invalidation: file hash change, commit change, stale test results, browser snapshots on DOM change, MCP resources on TTL. Event log stays lossless; summaries are disposable projections. Never truncate the latest user request or policy.

### 7.3 Security
Threat model: prompt injection (code/issues/web/MCP), malicious plugins/skills, shell output, SSRF, path traversal and symlink escape, credential leakage, concurrent worktree writes, automation replay, memory poisoning, supply chain, artifact tampering. Redaction before persistence. Adversarial fixture suite maintained from M1 onward.

### 7.4 Observability
OTel-compatible spans: task, iteration, context build, retrieval, model, policy, tool, verification, memory. Correlate by `task_id` + `trace_id`. Separate context, model and tool latency. Track estimated vs billed tokens separately; enforce spend ceilings.

### 7.5 Verification
Select checks from repo config and change impact (format, lint, type, tests, build, security scan, smoke). Capture command, env fingerprint, exit status, timing, truncated output + artifact ref. Agent-run tests are separate from independent acceptance checks. Repeated identical failure stops the repair loop.

Quality-regression layer (adopted design from codex-harness, native implementation): snapshot affected files before a mutating step (Git-based so shell edits are covered), run enabled analyzers on BEFORE and AFTER, normalize to `Finding`, and block only on new or worsened findings. Numeric metrics (complexity, length, statements, branches, nesting) are compared by file+analyzer+rule+qualified symbol; ordinary diagnostics by occurrence count. Analyzer or config failures fail closed as infrastructure failures and do not consume the repair budget. Retry budget is scoped per task attempt; a relevant PASS resets it. Default analyzers: Ruff, mypy/pyright; optional Flake8, Pylint, Black (check-only).

## 8. Milestone plan

Milestones are dependencies, not calendar promises. A milestone is done only when its gate passes with recorded evidence.

### M0 — Research and contracts
**Deliverables:** `docs/research/capability-matrix.md` (row per product/feature, source URL, retrieval date, evidence level: source-verified / vendor-documented / inferred, target milestone); ADRs (event protocol, worktree isolation, provider boundary, persistence, CLI framework choice, ADR-000 doc reconciliation); versioned JSON Schemas; threat model; evaluation task set outline; project skeleton (`pyproject.toml`, lint/type/test config, import-linter contracts, CI on Windows + Linux).
**Gate:** every feature in AGENTS.md maps to a requirement and owner; unknown proprietary internals marked unknown; schema round-trip tests pass.

### M1 — Local vertical slice

ADR-002 gate additions: M1.H1 introduces local redacted JSONL diagnostics and operation correlation with the loop; M1.H2 proves ordered tool observation, bounded effect-aware concurrency, cancellation/steering and finite repair. Harness engineering covers executable owner/acceptance checks and recorded context/config provenance, not only prompting. See SYSTEM_DESIGN 14.1/14.7.
**Deliverables:**
- Contracts, SQLite event store (WAL, migrations, monotonic sequence), artifact store.
- Task controller + state machine, cancellation tokens, budgets.
- One model adapter (pick one provider with official docs, e.g. OpenAI or Anthropic) behind `ModelProvider`; rate-limit backoff with jitter and capped retries.
- Instruction loader (AGENTS.md etc. with provenance, size limit, contradiction detection).
- Deterministic tools: list, glob, read, regex search (`rg`), precise patch with expected file hash, shell (argv, timeout, output cap, cancellation), test runner, git status/diff/commit. Path normalization with traversal/symlink protection.
- `WorkspaceManager`: worktree + branch `fw/<task-id>-<slug>`, SQLite records, per-repo and per-worktree locks, dirty-checkout detection, safe cleanup.
- Policy gateway v1 (read-only / workspace-write; approvals via CLI prompt).
- Context assembler v1 (token budget, provenance, trim, tool-result caps, artifact rehydration).
- Verification runner + repair loop with identical-failure stop.
- `verify/regression` baseline-vs-after policy with Ruff analyzer adapter (design from codex-harness, section 4.1); fail-closed infrastructure errors.
- CLI: `fw run`, `fw task status|resume|cancel|diff`, `fw config show`, `--json` events, slash commands, Ctrl+C.
- Resume with in-flight reconciliation.
**Gate:** a seeded bug is fixed on a branch, verified, and resumed after killing the process **without duplicating a side effect**; original checkout untouched; runs natively on Windows.

### M2 — Extensible harness

ADR-002 additions (M2.H1-H6): first-class `web_search` and separate `web_fetch` with DDGS then configured SearXNG, query disclosure controls, citations and failure fixtures; complete local/OTel log-span-metric/export surfaces; explicit hook failure/ordering semantics; measured harness evaluation. Search adapters live under `tools/web`, using the existing registry and gateway. DDGS is optional and automatic backend disclosure is prohibited. See SYSTEM_DESIGN 14.5/14.7.
**Deliverables:** native runtime extensions: provider capability negotiation, hooks, progressive skills, isolated plugins, stdio MCP, guarded search/fetch, session fork/replay, Python SDK, stable headless events and local traces. Reuse analyzer adapters and effective-config inspection. Follow N5 and existing M2 requirements; external-engine integration is inactive under ADR-004.

**Gate:** extensions cannot exceed permissions; failures settle or recover clearly; SDK and CLI share native events; provider selection cannot alter authority; enabled search, diagnostics and hook acceptance fixtures pass.
### M3 — Browser and agent orchestration

ADR-002 additions (M3.H1-H6): explicit delegation lifecycle and durable messages/continuations; fixed-membership fan-out/fan-in with join policies, aggregate budgets, reviewed patches and merged verification; browser-use source/runtime mediation and telemetry-off spike before an optional adapter. Default child context is selected references, not an unbounded transcript. See SYSTEM_DESIGN 14.2/14.3/14.6.
**Deliverables:** `BrowserManager` (isolated context per task, tab registry, teardown guarantee, typed browser tools, snapshot with stable refs and stale-ref rejection, SSRF/DNS/redirect validation, domain/download allowlists, size limits, traces, no `page.evaluate` without high-risk permission, redaction); custom agent definitions (`.forgeweave/agents/*.yaml|md`, intersected permissions, checksum logged) + built-ins (`explore, plan, implement, review, test, browser`); `AgentScheduler` (parent-child records, delegation requests, per-child budgets, depth/fanout limits, read-only concurrency on pinned commit, isolated worktree per writer, integrator workflow, provenance); `fw agent|worktree|branch` commands; `task apply|commit|pr` groundwork (three-way merge, conflict workflow).
**Gate:** browser obeys domain and side-effect permissions; concurrent agents never write the same worktree; conflict, timeout, cancellation and recovery integration tests pass.

### M4 — Automation and Git workflow

ADR-002 additions (M4.H1-H3): immutable typed DAGs, bounded map/join, leased/fenced step attempts, artifact bindings, declared partial-failure policies, approval recovery and explicit compensation. Manual workflow invocation remains available without schedules. Arbitrary model-written Python/JavaScript is excluded from the initial declarative runner. See SYSTEM_DESIGN 14.4.
**Deliverables:** cron scheduler with IANA timezone and DST handling; `fw automation serve|add|list|pause|resume|history|remove`; OS scheduler export (Task Scheduler / cron); headless runner; workflow DAG (`.forgeweave/workflows/*.yaml`, constrained expression language, per-step budgets/retries, approval gates) with example workflows (issue-to-patch, PR review, dependency update, browser UI regression, scheduled test triage, docs sync); idempotency keys, leases, per-repo concurrency caps, bounded retries; optional signed webhook receiver; GitHub integration via `gh`/API (issue/PR/CI polling, review-comment intake mapped to current lines, opt-in PR creation); conflict-aware branch integration.
**Gate:** duplicate events create one task; retries never duplicate external actions or PRs; every run links to an auditable event history.

### M5 — Advanced local intelligence
**Deliverables:** `memory/` (working, session, episodic, project, user, procedural stores; candidate -> verified -> accepted promotion; contradiction/supersession; expiry; redaction; `fw memory list|show|search|add|approve|edit|forget|export`); optional semantic index (scoped, hash+commit tied, compared to lexical baseline before default-on); cost controls and model-tier escalation; remote MCP (Streamable HTTP + auth); `ralph/` controller (immutable goal, versioned spec, plan.json, progress.jsonl, one unit per iteration, fresh context, independent verifier, stall detection, checkpoints, `fw ralph start|status|pause|resume|stop|explain`, no recursive Ralph); richer browser UI tests; workflow templates.

**Gate:** memory is inspectable/correctable/deletable and deleted entries never reappear in prompts; Ralph rejects false completion and stops stalled loops; multi-agent integration preserves verification evidence.

### M6 — CLI hardening and release
**Deliverables:** fault injection suite, security review, supply-chain + license review, migration/backup/restore drills (SQLite + artifacts), Windows/macOS/Linux package validation, CLI accessibility, docs, support runbooks, release pipeline, SBOM.
**Gate:** critical threat cases tested; local mode usable offline except model calls; editor/web/ACP/hosted recorded as separate future proposals.

## 9. Dependency order (critical path)

```
M0 contracts -> event store -> task controller -> tool protocol + policy -> workspace
   -> model adapter -> core loop -> context assembler -> verify -> CLI -> resume (M1 gate)
M1 -> providers/hooks/skills/MCP/plugins/SDK/telemetry -> deterministic routing policy (M2)
M2 -> browser + agents/scheduler (M3) -> automation/workflows/GitHub (M4)
M4 + M2 -> memory/Ralph (M5) -> hardening (M6)
```

Parallelizable after M1 core: skills, MCP client, telemetry, SDK, capability matrix, eval corpus.## 10. Testing strategy

- **Unit:** contracts, state machine transitions, path guard, patch hash conflict, budget math, cron/DST, expression parser.
- **Integration:** real temp Git repos, real worktrees, real subprocess cancellation, fake model provider (scripted tool calls), local Playwright fixture server, stdio MCP fixture server.
- **Crash/resume:** kill the process at each boundary (before dispatch, after policy decision, mid-tool, after result before append) and assert no duplicate side effect.
- **Adversarial:** prompt-injection fixtures (README, issue, web page, MCP output, tool output), path traversal/symlink, SSRF (loopback, private IP, metadata, DNS rebinding, redirects), secret leakage, memory poisoning, false completion claim, malicious skill/plugin.
- **Eval corpus (`evals/`):** one-file bug, cross-package change, flaky test, large monorepo, ambiguous request, interrupt/restart, prompt injection, forbidden action, Windows-native. Metrics: pass@1, accepted-change rate, regressions, cost per accepted change, latency, retrieval precision, approvals, policy violations, recovery success. Compare harness changes with same-model/same-task runs only.
- **Architecture tests:** import-linter package boundaries; no module bypasses policy.
- **Final end-to-end scenario** (SYSTEM_DESIGN section 11): scheduled GitHub issue -> worktree -> deterministic capability selection -> custom agent + skill + scoped memory -> read-only subagent -> edit + Playwright check -> MCP context -> failing test -> bounded Ralph iteration -> verified -> reviewer sees diff/evidence/trace -> authorized draft PR. Run again interrupting at three boundaries.

## 11. Definition of done per task (checklist for implementing agents)

1. Record affected module, acceptance criteria, expected tests, security impact, compatibility constraints.
2. Read AGENTS.md, nearest package AGENTS.md, and the relevant SYSTEM_DESIGN section only (do not inject both full documents).
3. Inspect existing code/tests; modify the owner module.
4. Implement with types/docstrings; explicit boundary error handling.
5. Add behavior-level tests; run lint, type check, tests on Windows.
6. Verify no policy bypass, no secret logging, no network side effects without authorization.
7. Update docs/ADR if a contract or decision changed.

## 12. Key risks and mitigations

| Risk | Mitigation |
|---|---|
| Memory contaminates prompts | Scoped retrieval, citations, expiry, review, no policy elevation |
| Long AGENTS.md crowds context | Convert to concise index after M0 |
| Ralph amplifies errors/cost | Finite budgets, one unit/iteration, independent verifier, stall detector |
| Worktree != sandbox | Honest isolation reporting, approvals, least-privilege subprocess env |
| Stale browser/MCP state | Revalidate on every execution; expire refs/catalogs |
| Windows console quirks | CLI framework spike in M0 |
| Provider API drift | Capability descriptors, adapter compatibility tests, pinned versions |
| Confusing `codex-harness` (third-party hooks) with OpenAI Codex | Dependency table in plan.md 4.1; ADR-010 |
| Bare `deepseek-harness` is an unrelated package with the same import name as the official SDK | Pin official `deepseek-harness-sdk`; declare conflict; runtime signature check; never install both |
| `codex-harness` needs Python 3.12 and writes to `~/.codex` | Native implementation by default; optional isolated-HOME subprocess verifier |
| Proprietary behavior assumptions | Evidence-level column in research matrix |

## 13. Open questions to resolve early (ADR candidates)

1. First model provider for M1 and credential setup flow.
2. Interactive UI: `prompt_toolkit` vs `textual` (decide after Windows spike).
3. Token estimator per provider and fallback heuristic.
4. Subprocess isolation options on Windows (Job Objects, restricted tokens) and what level to claim.
5. Plugin process protocol (JSON-RPC over stdio assumed) and signing/trust source.
6. Where Ralph/plan artifacts live when users want them checked in.
8. Branch naming/slug collisions and cleanup retention defaults.
9. Redaction rules and consented evaluation trace collection.
10. License policy for dependencies, and optional engines (MIT for DeepSeek packages, Apache-2.0 for openai-codex and codex-harness; preserve notices).

## 14. Immediate next actions

For implementation using GPT-5.6 Luna in Codex, follow [CODEX_LUNA_BUILD.md](CODEX_LUNA_BUILD.md). It supplies the start/resume prompts, bounded context workflow and dependency-ready slice index without replacing this plan or todo.md.

1. Apply the completed [ADR-000](docs/architecture/adr-000.md) and review [the gap assessment](docs/research/architecture-review-2026-10-02.md); resolve Git-root ownership and containment unknowns before mutating execution.
2. Complete M0 contract definitions and Windows CLI/process/storage spikes; record measured native dependency/isolation decisions. Existing engine scaffolding is not a passed native-harness gate.
3. Implement one native M1 vertical slice with protected context, all budget ceilings, action-bound approval, event/artifact persistence and crash reconciliation together.
4. Verify the seeded-bug/crash/resume scenario before extension and delegation expansion. Preserve the existing M0–M6 task IDs and evidence.

## 15. Pre-development review and implementation amendments (2026-10-02)

Behavioral details are normative in SYSTEM_DESIGN.md section 13; this section defines delivery sequencing. The research does not justify a larger first release. Close these contracts before proceeding to development. No implementation was added by this review.

| Slice / owner | Acceptance and boundary tests | Dependencies / milestone |
|---|---|---|
| Contract reconciliation / docs | Canonical package/event names agree; requirement map retains inventory; ADR-000 linked | Completed reconciliation; requirement mapping remains M0 |
| Capability preflight / CLI, workspace, policy | Resolve ancestor Git roots; measure Windows process termination and containment separately; diagnostics never expose keys | M0 spikes, then M1 doctor |
| Context / contracts, context, models | Manifest and immutable requirement ledger; ten compactions lose zero protected constraints; oversized requirements fail explicitly; validate protocol pairs and secret exclusion | M0 schemas; M1 before sustained loop |
| Audit retention / events, sessions | Exact/redacted/reference-only fidelity; sensitive prompts absent by default; forget excludes content from subsequent retrieval; expired sources reported | M1 persistence; M5 memory deletion integration |
| Approval / policy, CLI | Argument/policy/workspace change invalidates grant; one-action consumption is atomic; headless approval-needed exits | M0 schema; M1 dispatch |
| Recovery / events, task, workspace | Kill at each boundary; unknown side effects reconciled or parked; stale lease cannot mutate; disk-full prevents dispatch | M1 before resume gate |
| Streams and budgets / models, core | No partial call dispatch; malformed streams bounded; missing usage reserves cost; retries/compaction/children share ceilings | M1; children integration M3 |
| Verification / verify, task | Criterion IDs and whole-input fingerprint; weakened test cannot alone prove completion; inconclusive failures stop boundedly | M1 required checks |
| Egress / policy, MCP, browser | Provider connection does not grant tool network; auth-discovery/redirect destinations checked; local MCP launch needs executable authorization | M2 stdio, M3 browser, M5 remote MCP |

Security and compatibility constraints apply to every slice: native Windows 11/Python 3.11+, no required daemon/service, no raw secret persistence, original checkout preserved, capability grants intersected. Test commands belong to each future implementation task after tooling exists; this documentation review claims no runtime checks.

### 15.1 Clarifications superseding ambiguous earlier wording

- Section 3 reconciliation is now recorded by ADR-000. Conceptual stages in SYSTEM_DESIGN do not reorder milestones. Keep AGENTS as an inventory until migration preserves every normative requirement.
- Section 7.2 context includes M1 basic summary validation and requirement retention, not just trimming. Long-term memory stays M5. “Model-visible means logged” means a reconstructable ordered manifest with declared retention fidelity; exact sensitive payload retention is opt-in.
- Section 7.4 and M5 cost controls do not postpone spend ceilings: reservations and conservative unknown-usage accounting are M1. M5 adds price/quality optimization.
- SQLite transactions and artifact files cannot be committed as one filesystem/DB operation; use publish-before-index and reconciliation. Approval, task transition and event writes use owner repositories within one transaction unit of work.
- Do not infer package-conflict enforcement from optional extras metadata; pip extras cannot generically prevent a conflicting distribution. Detect the wrong SDK at startup and document supported clean environments.

### 15.2 Release evidence

Keep a requirement → owner → milestone → acceptance fixture → result/artifact matrix. M0 gate additionally requires section 13 schemas and documented unknowns. M1 gate additionally requires context retention, single-use approval, unknown-outcome recovery, stream/budget and verification-fingerprint fixtures. M2+ gates add the same contracts for each new trust surface. Release thresholds beyond deterministic safety assertions remain provisional until measurements are recorded; an unexecuted spike is never a passed gate.
