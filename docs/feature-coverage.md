# ForgeWeave feature coverage and implementation evidence

Updated 2026-10-04. This preserves product scope and exposes gaps. **Planned** means no end-to-end runtime proof. **Partial** identifies existing code without claiming the full feature. Canonical work status lives in [todo](../todo.md) and [tracker](../BUILD_TRACKER.md); architecture lives in [SYSTEM_DESIGN](../SYSTEM_DESIGN.md). The native single-agent gate precedes optional engines and delegation. Laya is explicitly deferred.

| ID | Required feature | Owner | Canonical work | Acceptance evidence required | Current status |
|---|---|---|---|---|---|
| F01 | Harness engineering: lifecycle, environment, policy, context, feedback | core/task/context/policy/verify | M0.H1, M1.33, M1.H1-H2 | Reproducible inspectable verified patch | Partial contracts/state/events; runnable harness pending |
| F02 | Loop engineering: tool, repair, workflow, Ralph loops | core/verify/automation/ralph | M1.H2, M4.H1-H2, M5 Ralph tasks | Finite retries, stop reasons, cancellation/recovery | Planned; regression retry helper exists |
| F03 | Durable versioned events, artifacts, migrations | events/contracts | M1.1-5, M1.R3/R7 | Replay, publication/crash/retention fixtures | Partial BT-001 through BT-007; hardening pending |
| F04 | Policy, action-bound approvals, taint, honest isolation | policy/tools/workspace | M1.8-9, M1.R2/R6 | Stale/reused approval and scope denial | Contracts present; gateway next BT-008 |
| F05 | Built-in read/search/edit/shell/test tools | tools | M1.10-19, M1.R6 | Real workspace effects, hash conflict, process cancel | Planned |
| F06 | Provider stream assembly, capabilities, model selection | models/routing/core | M1 model tasks, M1.R4/R5, M2 providers | Malformed/interleaved stream, usage and user pin tests | Planned |
| F07 | Context engineering, instruction provenance, compaction | context/sessions | M1 context tasks, M1.R1 | Protected constraints survive; changed spans invalidate | Contracts present; assembler pending |
| F08 | Memory: working/session/episodic/project/user/procedural | memory/context | M5 memory, M5.R2 | Scope, promotion, expiry, contradiction, forget | Planned; session event foundation exists |
| F09 | Session resume, fork, replay, checkpoints | sessions/task | M2.20, M1.4-5 | New attempts, immutable history, no effect replay | Partial task attempts; full sessions pending |
| F10 | Custom role profiles, built-ins, agent/skill selection | agents/skills | M3.11-13, M2 skills | Validated metadata, permission intersection | Planned |
| F11 | Task delegation, child lifecycle/context, continuation | agents/core | M3.14-19, M3.H1-H2, M3.R1 | One durable child per request; bounded lineage/budgets | Planned |
| F12 | Fan-out/fan-in, fixed membership, joins/reducers | agents/automation | M3.H3-H4, M4.H1 | Deterministic joins, partial failure, late results | Planned |
| F13 | Worker integration, conflict review, provenance | agents/workspace/verify | M3.15-19, M3.H4 | Combined patch verification after reviewed merge | Planned |
| F14 | Programmable workflow DAGs, templates, pause/resume | automation | M4.8-11, M4.H1-H3 | Typed DAG, approval, fencing and crash-safe retry | Planned |
| F15 | Schedules, repository triggers, idempotent automation | automation | M4.1-7, M4.18 | DST, duplicates, caps, recovery | Planned |
| F16 | Git/worktrees/checkpoints/apply/commit/optional PR | workspace/integrations/github | M1 workspace, M3.20-22, M4.12-16 | User changes preserved; visible conflicts; explicit publish | Planned; ambiguous ancestor Git root unresolved |
| F17 | Skills, hooks and isolated plugins | skills/hooks/plugins | M2.7-13, M2.H5 | Lazy loading, lifecycle order, no permission escalation | Planned |
| F18 | MCP tools/resources/prompts and remote auth | mcp/policy | M2.14-19, M2.R1, M5.R1 | Schema/catalog/cancel/credential boundary | Planned |
| F19 | Web search DDGS + optional SearXNG | tools/web/policy | M2.H1-H3 | Approved backend only; query privacy/caps/failures | Newly specified; planned |
| F20 | Guarded source fetch and research evidence/citations | tools/web/context | M2.H2-H3 | Redirect/DNS checks; real source provenance | Newly specified; planned |
| F21 | Native browser interaction and UI verification | browser/verify | M3.1-10 | Stale refs, effect policy, traces, cleanup | Planned |
| F22 | Browser-use agentic automation | browser/models/policy | M3.H5-H6 | Complete mediation and telemetry-off runtime spike | Newly specified; feasibility open |
| F23 | Local structured logs, traces, metrics and CLI inspection | telemetry/cli | M1.H1, M2.24-25, M2.H4 | Redaction, causal links, bounded sinks, no-default-upload | Planned; durable events exist but are not diagnostics |
| F24 | Harness evaluation, fault injection, regression analysis | verify/telemetry | M1.H2, M2.H6, M6.H1 | Corpus/config/fingerprint + measured acceptance | Partial baseline regression helper; eval runner pending |
| F25 | Interactive CLI/TUI, headless JSON, interruption, image input | cli/models | M1 CLI, M2.21, M6 | Windows console/stream/cancel fixtures and capability gates | Planned |
| F26 | Python SDK and equivalent CLI lifecycle/events | sdk | M2.22-23 | Create/stream/cancel/resume/approve/fork/export parity | Planned |
| F27 | Optional DeepSeek/Codex delegated engines | engines | M2 engine tasks, M0.14 runtime spikes | Real runtime, audit linkage, truthful isolation, verifier | Partial adapters/fake tests; runtime proof pending |
| F28 | Supervised long-horizon Ralph | ralph/core/verify | M5 Ralph tasks | Fresh context, no false completion, stalls/limits | Planned |
| F29 | Config inspection, secrets, health/support diagnostics | cli/policy/telemetry | M0 spikes, M1.R6, M6.R1 | Effective config, secret absence, honest capability report | Planned |
| F30 | Laya | routing | ADR-001 | Separate future decision and calibration gates | Deferred at user's direction |
| F31 | Editor completion/web UI/ACP/cloud workers | future integrations | Explicit initial-release exclusion | New integration design before development | Deferred; CLI features above remain in scope |

Source-to-design mapping is in [research](research/harness-source-review-2026-10-04.md). A later milestone is sequencing, not removal from product scope. Completing one row's scaffolding does not close its acceptance gate.

| ID | Additional requirement under ADR-003 | Owner | Canonical work | Acceptance | Status |
|---|---|---|---|---|---|
| F32 | Evidence-preserving output projections and extraction | context/tools/verify/models | M1.P1, M2.P1-P2 | Scoped rehydration, no lost failures or forged receipts | Planned |
| F33 | Authorized edit/check sequences and measured compaction | core/policy/context/telemetry | M2.P3-P4 | Per-action policy/recovery; complete cost accounting | Planned |
| F34 | Worker evidence exchange and isolated harness experiments | agents/automation/verify | M3.P1, M5.P1 | Reproduced claims, frozen candidates, finite budgets | Planned |
| F35 | Frozen release evaluation and rollback | verify/cli/events | M6.P1-P2 | Protected final split, release manifest, rollback rehearsal | Planned |

The [paper review](research/sol-pi-review-2026-10-04.md) separates findings from these original ForgeWeave requirements. F01-F35 now define the coverage index; M6.H1 must reconcile all rows.
