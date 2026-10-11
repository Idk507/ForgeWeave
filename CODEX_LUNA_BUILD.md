# ForgeWeave build guide for GPT-5.6 Luna in Codex

Date: 2026-10-02. Target coding model: **GPT-5.6 Luna**, selected by the user in Codex. This guide organizes implementation work; it does not claim model context limits, pricing or benchmark performance. It does not change Codex settings or configure ForgeWeave's runtime provider.

## 1. Purpose and authority

SoL-Pi amendment (2026-10-04): consult [paper review](docs/research/sol-pi-review-2026-10-04.md) and SYSTEM_DESIGN section 15 for P-series tasks. Establish baselines before tuning; implement one mechanism behind an explicit option; validate source/effect identity; measure auxiliary spend; update evidence before enabling it. Luna as the build model is not automatic authorization to add runtime auxiliary models. Release validators and final evaluation tasks stay outside the optimizing agent's writable scope.

2026-10-04 research amendment: read [feature coverage](docs/feature-coverage.md), [ADR-002](docs/architecture/adr-002-harness-coverage-and-research-tools.md), and only the relevant SYSTEM_DESIGN section 14 subsection before its slice. The [source review](docs/research/harness-source-review-2026-10-04.md) records upstream commits and package identity; implementation must check the pinned release API rather than assume repository HEAD equals an installed wheel. Include local diagnostics in the M1 loop gate, web search in M2, delegation/fan-out/fan-in and browser-use feasibility in M3, and workflow joins/recovery in M4. No feature may disappear from summaries or the backlog merely because delivery is later.

For each Luna slice load the current objective, relevant contract, source references, affected code/tests and last verified checkpoint. Keep the full feature matrix on disk; use its row IDs in the handoff. Record completed/pending IDs, commands actually run, changed files, source hashes, remaining risks and next dependency-ready task in BUILD_TRACKER.md before a context reset. Never assume an SDK stub or design document means the runtime feature is implemented.

Build the native Python CLI in small, independently verified slices. Complete the single-agent M1 gate before optional engine expansion, routing or delegation. This guide supplements [AGENTS.md](AGENTS.md), [SYSTEM_DESIGN.md](SYSTEM_DESIGN.md), [plan.md](plan.md), [todo.md](todo.md) and [ADR-000](docs/architecture/adr-000.md). It cannot override their security or compatibility requirements. If they conflict, stop the affected change, record a decision and synchronize the documents.

Use the existing source as scaffolding, not proof of a completed harness. Engine adapters and the regression helper already exist; inspect and reuse their owning modules. Do not regenerate the project from scratch.

## 2. Paste this into the first Codex message

```text
Use GPT-5.6 Luna to build ForgeWeave following CODEX_LUNA_BUILD.md.
First read AGENTS.md and this guide, then inspect the current source, tests,
todo.md and the relevant design sections. Do not load every document on every turn.

Work on one small acceptance-defined slice at a time. Record its owner,
requirements, likely files, boundary tests, security impact and compatibility
constraints before editing. Implement the real owning module, run focused
checks, review the diff, and record actual evidence before proceeding.

Start with the preflight and contract work in section 5. The Git repository
currently resolves to the Downloads ancestor; inspect and report that boundary.
Do not initialize Git, commit, or create worktrees against the wrong root.
If repository selection requires my input, ask one precise question and
continue independent documentation or contract inspection.

Keep native Windows 11 and Python 3.11+ supported. No required Docker, WSL,
Redis, hosted service or permanent daemon. Keep all mutating execution behind
the gateway and never claim a worktree or Job Object is a filesystem sandbox.
Do not install optional engines or make live provider calls without scoped
authorization. Use a scripted fake provider first.

Do not silently lower acceptance criteria, mark stubs complete, or stop after
merely writing a plan. Continue through authorized work while preserving the
milestone gates. No subagents or multiple writers unless I explicitly enable them.
```

## 3. Context loading rules

Treat context as a working set. Load this guide at session start and reference it thereafter. Read AGENTS.md and any nearest package instructions before editing. Use heading searches to select the relevant SYSTEM_DESIGN sections, todo task IDs, owning source and boundary tests. Preserve any mandatory full-file read instruction; section selection is an efficiency rule, not permission to omit policy.

| Work | Design to load | Minimum evidence to inspect |
|---|---|---|
| Contracts and persistence | Sections 4, 5, 13.2, 13.4; plan 5–6 | Existing contracts, event requirements, migration tasks |
| Context assembly | Sections 6, 13.1–13.2 | Constraint ledger, provider protocol, context tasks |
| Tool authorization | Sections 9, 13.3–13.4 | Path/approval contracts, execution profiles, workspace state |
| Provider and budget work | Sections 5, 13.5 | Fake stream fixtures, budget and capability contracts |
| Verification | Sections 13.6; plan 7.5 | Existing regression helper, check configuration, acceptance spec |
| CLI and resume | Sections 4–5, 13.4, 13.6 | Task projection, recovery records, Windows CLI spike |

Do not inject the entire feature inventory, full transcripts, huge logs, all tool schemas or all memory into each coding step. Read bounded relevant code spans and expand when dependencies demand it. Retain precise paths, hashes, test evidence and requirement IDs. An omitted fact is unknown, not a reason to invent an interface.

Keep a compact implementation handoff in `docs/build/next-step.md` once implementation starts. It is a navigation aid, never policy or the sole evidence record. Include:

```markdown
# Current build handoff
Updated: <UTC timestamp>
Slice / todo IDs: <identifiers>
Acceptance criteria: <unchanged requirement IDs and validator>
Repository / worktree / base revision: <verified values>
Modified files: <paths and purpose>
Decisions: <ADR or contract references>
Checks actually run: <command, result, evidence location>
Known failures / unknowns: <specific findings>
Next action: <one concrete action>
Context to reload: <design headings, source files, tests>
```

Before resuming, verify this record against current files and tests. Do not carry old passing results across a changed workspace. Update the handoff at verified checkpoints and before a fresh chat. Do not create a second task backlog: todo.md remains the implementation checklist.

## 4. One slice execution protocol

1. **Inspect:** identify the owner, existing interfaces/tests and exact unmet requirement. Check relevant package instructions and workspace changes.
2. **Record:** write a concise slice record in the handoff: requirement IDs, acceptance criteria, expected checks, security impact, compatibility constraints and likely files.
3. **Bound:** aim for one behavior and roughly 2–5 files. This is a sizing guideline, not a hard cap. Split broader work along interfaces without omitting required integration.
4. **Implement:** use type hints/docstrings and explicit boundary errors. Keep contracts/versioning stable. No placeholder runtime behavior, duplicate abstractions or unrelated refactoring.
5. **Verify:** test behavior at actual module boundaries and workspace effects. Use fake models for deterministic tests. Run focused checks first; run affected integration checks when wiring changes.
6. **Review:** inspect the complete diff for policy bypass, secret persistence, cancellation gaps, Windows issues and compatibility. Fix findings within scope.
7. **Checkpoint:** update existing todo IDs only when their full acceptance criteria pass. Record partial completion honestly, with commands/results and open risks. Preserve the original checkout and interrupted worktrees.
8. **Continue:** take the next dependency-ready slice while authorization remains sufficient. Ask only for missing decisions or action authorization that cannot be inferred from the task.

If the same check fails repeatedly without a new hypothesis, stop repeating it. Record the failure, investigate its cause and revise the approach. Never weaken the check, change required criteria or claim a pass to advance the milestone.

## 5. Initial build queue

This is an execution index into todo.md, not a replacement backlog. Each row may require several small slices. Before editing, confirm prerequisites against the current checklist; do not assume all rows are ready.

| Order | Outcome | Existing task references | Acceptance checkpoint |
|---|---|---|---|
| 1 | Establish repository boundary and local capability inventory | M0.R2, M0.13–14 | Intended Git root resolved; Windows cancellation and isolation unknowns recorded separately |
| 2 | Map requirements and define owner/protocol boundaries | M0.28, M0.R1, M0.20–24 | Requirement → owner → schema → fixture mapping; no naming contradictions |
| 3 | Complete minimal tooling and CLI/storage/process spikes | M0.12–18, M0.R3 | Native Windows results and decisions recorded; no unexecuted spike called passed |
| 4 | Version contracts and schema fixtures | M0.20–26 | Valid/invalid boundary cases and round-trips pass; cross-owner transaction contract defined |
| 5 | Persist events and artifacts durably | M1.1–5, M1.R3, M1.R7 | Atomic state/events, publish-before-index, corrupt/missing artifact and busy/disk-full behavior tested |
| 6 | Authorize scoped tools and approvals | M1.8–14, M1.R2 | Schema validation, path confinement checks, changed-argument rejection and atomic grant consumption pass |
| 7 | Create owned workspaces and bounded process execution | M1.15–23, M1.R6 | Original checkout protected; cancellation kills descendants; actual containment level reported |
| 8 | Assemble fake model streams and enforce budgets | M1.6–7, M1.27, M1.R4 | Partial tool JSON never executes; missing usage retains reservation; retry/compaction cost included |
| 9 | Build protected bounded context | M1.28–32, M1.R1 | Ten compactions preserve required constraints; unsatisfiable input fails; stale spans invalidate |
| 10 | Wire the native loop and independent verification | M1.33–39, M1.R5 | Gateway/event ordering enforced; weakened tests cannot alone prove completion; repairs are bounded |
| 11 | Expose CLI and recovery against a fixture repository | M1.40–45 | JSON/stdout separation, interruption, unknown-outcome reconciliation and resume tested |
| 12 | Add one authorized real provider and pass M1 | M1.24–26, M1 gate, M1.R1–7 | Seeded bug fixed/verified; kill/resume has no duplicated side effect; Windows native evidence |

Steps 5–11 must be integrated into one fake-provider task flow before claiming the native slice complete. Step 12 requires current official provider documentation and explicit credential/network setup. Selecting Luna as the **Codex builder** does not select the model ForgeWeave will call at runtime.

Optional engine-specific M0 runtime spikes are deferred to M2 after M1, as clarified in todo.md. Subsequent work follows M2–M6 gates; do not jump to browser orchestration, learned memory, Laya active routing or Ralph while the native spine is incomplete.

## 6. Verification discipline

Use `python -m pytest <affected-test-path>` for focused tests once the environment supports it. Discover the configured lint/type/import checks before running them; do not claim these commands are already configured or passing. Install dependencies only within the task's authorized environment. Do not add meaningless tests for documentation or tests that simply mirror implementation internals.

Use fixtures for malicious content, Windows paths, stale file hashes, stream disconnects, cost exhaustion, cancelled children and crash boundaries. Provider smoke tests remain opt-in and must not leak source or credentials. Native test runs can execute repository code, so apply the execution profile rather than equating a test command with a read-only action.

Each completed slice reports modified files, actual check commands/results, failures, remaining risks and evidence links. A failed or unavailable check is stated explicitly. A passing unit test does not establish OS confinement, provider compatibility or crash recovery unless it actually exercises that boundary.

## 7. Resume prompt for a later Codex chat

```text
Continue ForgeWeave using GPT-5.6 Luna and CODEX_LUNA_BUILD.md.
Read AGENTS.md and docs/build/next-step.md if it exists. Verify the handoff
against the current workspace and todo.md. Load only the relevant design
sections, owning code and tests. Preserve existing changes and acceptance criteria.
Finish the active slice before starting another. Record evidence, update the
handoff, and continue the next dependency-ready authorized slice.
If there is no handoff, inspect the checklist/source/tests and establish one;
do not invent previous progress or restart the project.
```

## 8. Decisions requiring human input

Ask a concise question when the repository root is ambiguous, a required provider/privacy choice is absent, execution needs unconfined permissions, or publication/credentials/network installation lacks authorization. Continue independent work while awaiting the answer. Routine implementation choices within approved contracts do not require repeated confirmation. Keep the requested Luna model; model changes and delegation require user direction.

This guide is ready for implementation use. It provides a disciplined build workflow, not evidence that ForgeWeave is already implemented.
