# Harness implementation review — 2026-10-04

## Scope and evidence standard
Research gate RG-002 addresses the user's request before the next runtime slice. Reviewed repository Markdown, package metadata, GitHub trees and selected raw source files. No external SDK or browser package was installed or executed. Source inspection proves implementation structure, not end-to-end operation or containment on Windows. All ForgeWeave architecture below is a proposed native adaptation, not a claim of vendor parity.

Evidence levels: **source-inspected** for code read at an immutable commit; **vendor-documented** for public documentation; **unverified** for inaccessible material or runtime behavior. Repository HEAD snapshots and PyPI releases are separate evidence: the reviewed HEAD is not assumed to be the code in the published wheel. Before integration inspect the exact wheel/release tag and hashes.

## Package identity and compatibility

PyPI JSON endpoints were read on 2026-10-04. These are observations, not dependency upgrades.

| Package | Observed version | Python requirement | Role |
|---|---|---|---|
| [deepseek-harness-sdk](https://pypi.org/pypi/deepseek-harness-sdk/json) | 0.1.5rc1 | >=3.10 | Official subprocess SDK; pre-release; inspect matching runtime wheel |
| [openai-codex](https://pypi.org/pypi/openai-codex/json) | 0.160.0 | >=3.10 | Official Codex Python SDK; project still pins 0.159.3 |
| [codex-harness](https://pypi.org/pypi/codex-harness/json) | 0.1.1 | >=3.12 | Third-party quality hooks, not OpenAI's agent harness |
| [ddgs](https://pypi.org/pypi/ddgs/json) | 9.16.0 | >=3.10 | Optional metasearch client; MIT metadata |
| [browser-use](https://pypi.org/pypi/browser-use/json) | 0.13.10 | >=3.11,<4.0 | Optional browser agent; license metadata field absent in JSON; official docs identify MIT |

The bare `deepseek-harness` remains excluded: existing research identified a different project sharing the official SDK's import namespace. Do not conflate a model-provider adapter with an external harness. Keep all integrations lazy and separately packaged. Existing exact pins remain unchanged until compatibility tests justify an upgrade.

### Published-wheel inspection

Downloaded the following pure-Python wheel archives into memory without installing, importing or executing their contents. Each archive SHA-256 matched the digest published by its version-specific PyPI JSON endpoint. Read distribution metadata and the named module; its module hash matched the reviewed repository snapshot. This establishes parity for those modules only, not the complete wheel/runtime or transitive dependencies.

| Release / inspected module | Verified wheel SHA-256 | Module SHA-256 |
|---|---|---|
| [DeepSeek SDK 0.1.5rc1](https://pypi.org/pypi/deepseek-harness-sdk/0.1.5rc1/json), `deepseek_harness/api.py` | `8d9897e97e8a95fd738cb2c3e2c563951d824e43847ec6f3b0fb172c0729b4d8` | `9e24adee62987e38e0577c4ba051b15b015f61cd5d5412dc56882094f5e52c2b` |
| [Codex SDK 0.159.3](https://pypi.org/pypi/openai-codex/0.159.3/json), `openai_codex/_message_router.py` | `5148065fb13cfb3f106c6493f3a5dc26457da98f6350e193e85eda8b65263b8f` | `8c1239bae89e3128ea797fd1ed23619bccab5614212908f3cb498f84ea67c396` |
| [DDGS 9.16.0](https://pypi.org/pypi/ddgs/9.16.0/json), `ddgs/ddgs.py` | `175d9198c958a263f51a06a54368ba0b41294942c0cd29f4aa71be03dbcd5f4a` | `1cd33c4c5dd81ab865d6257327c4f079fae0cbe2e37ec8c7a9c575df771f27b1` |
| [Browser-use 0.13.10](https://pypi.org/pypi/browser-use/0.13.10/json), `browser_use/telemetry/service.py` | `66eb20153094f21728bc0110ada17c03a0c475df2374985d6b47e349cbd47705` | `40a5e5506b6083c7d3b07779a2e01ba85a3861ed33b12f871fac54f534035e68` |

Metadata confirms the DeepSeek SDK's exact runtime pin and Codex SDK's exact CLI pin. Browser-use brings a substantially broader dependency surface, including browser-harness, browser-use-sdk and cdp-use; inspect those action/cloud boundaries in M3.H5 rather than treating the top-level package as a small Playwright wrapper. DDGS depends on primp and lxml; native-wheel availability on supported Windows/Python versions needs a packaging check.

## OpenAI Codex: what was inspected

Snapshot: `afb436df8b70bb5bc57b86d9a3e829968988cd21` in [openai/codex](https://github.com/openai/codex/tree/afb436df8b70bb5bc57b86d9a3e829968988cd21).

| Source | Observation | Native adaptation |
|---|---|---|
| [agent/control/spawn.rs](https://github.com/openai/codex/blob/afb436df8b70bb5bc57b86d9a3e829968988cd21/codex-rs/core/src/agent/control/spawn.rs) | Spawn control separates fork inheritance, startup input and descendant restoration; graph-ordered restoration reserves identity | Durable parent/child graph; reserve identity and budgets before launch; record explicit context mode |
| [agent/control/mailbox.rs](https://github.com/openai/codex/blob/afb436df8b70bb5bc57b86d9a3e829968988cd21/codex-rs/core/src/agent/control/mailbox.rs) | Mutex-protected pending messages and watch notifications; mailbox cleanup handles cancelled startup | ForgeWeave durable message receipts plus process-local wake signals; delivery does not itself confer authority |
| [agent/control/budget.rs](https://github.com/openai/codex/blob/afb436df8b70bb5bc57b86d9a3e829968988cd21/codex-rs/core/src/agent/control/budget.rs) | Shared rollout usage can stop execution; reminders acknowledged after entering history | Root budget reservations for descendants; settled actual usage and recorded budget reminders |
| [multi_agents_v2/wait.rs](https://github.com/openai/codex/blob/afb436df8b70bb5bc57b86d9a3e829968988cd21/codex-rs/core/src/tools/handlers/multi_agents_v2/wait.rs) | Wait bounds come from configuration and activity subscription | Event-driven wait with cursors and timeout; avoid repeated model polling |
| [Python _message_router.py](https://github.com/openai/codex/blob/afb436df8b70bb5bc57b86d9a3e829968988cd21/sdk/python/src/openai_codex/_message_router.py) | One reader owns ordered stdio; routes request responses and turn notifications into distinct queues | Separate transport response, notification and turn channels; tolerate unknown notifications |
| [Python async_client.py](https://github.com/openai/codex/blob/afb436df8b70bb5bc57b86d9a3e829968988cd21/sdk/python/src/openai_codex/async_client.py) | Async API wraps a sync transport and handles cancellation cleanup separately | Adapter cancellation must stop runtime activity, not just cancel an asyncio waiter |
| [otel README](https://github.com/openai/codex/blob/afb436df8b70bb5bc57b86d9a3e829968988cd21/codex-rs/otel/README.md) | Session telemetry provides common metadata, metrics and configurable exporters | Local diagnostics from M1; OTel integration and trace export in M2 |

File SHA-256 examples: spawn `65101355eb1346605e3faa9109c5040194410d5847e2f769c865c0ee00e7c595`; message router `8c1239bae89e3128ea797fd1ed23619bccab5614212908f3cb498f84ea67c396`. The study examined selected seams, not the entire Rust runtime. No assertion that Codex automatically gives every child an isolated Git worktree; that is ForgeWeave's own writer policy.

## DeepSeek Harness: what was inspected

Snapshot: `5badb15009ae1756c3afe0ae0cef1faafc290ccc` in [deepseek-ai/deepseek-harness](https://github.com/deepseek-ai/deepseek-harness/tree/5badb15009ae1756c3afe0ae0cef1faafc290ccc).

| Source | Observation | Native adaptation |
|---|---|---|
| [agent-loop/agent.ts](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/core/agent-loop/src/agent.ts) | Turn/step boundaries, inbox admission, context assembly, pre-step interception, cancellation and tool recovery are explicit | Separate turn/step lifecycle from provider streaming; log model-visible packet before inference; deterministic stop reasons |
| [agent-loop/tool-calls.ts](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/core/agent-loop/src/tool-calls.ts) | Calls prepare in order; eligible dispatch bodies overlap; results finalize in model order; cancellation drains started calls | Bounded read concurrency and serial writes; retain actual completion order in audit and canonical order in model context |
| [subagent service](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/subagent/subagent/src/index.ts) and [subsystem contract](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/docs/subsystems/subagent.md) | Provider capability seam and parent lineage; documented one-shot versus continuable background children and activation state | Explicit one-shot child first; continuations reuse durable child identity with a new attempt; unsupported capabilities rejected |
| [workflow service](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/workflow/workflow/src/index.ts) and [workflow contract](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/docs/subsystems/workflow.md) | Optional workflow seam, parent attribution, caps, cancellation and paired lifecycle events; provider runs orchestration scripts | Adopt run/step/member lifecycle and bounded joins; initial ForgeWeave workflows are validated declarative DAGs, not arbitrary scripts |
| [telemetry coordinator](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/session/session-telemetry/src/coordinator.ts) | Capture, redaction and sink shutdown are separate concerns | Redact before all diagnostic outputs; isolate sink failure from authoritative audit commits |
| [Python SDK README](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/python/sdk/README.md) | Lazy bundled runtime with explicit home; run interval begins at inbox admission and ends at whole-agent idle; descendant notifications included | Define admission versus completion, root versus child event attribution, and no hidden global engine home |
| [Python client.py](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/python/sdk/src/deepseek_harness/client.py) | Subprocess transport with reader thread, response/request queues and notification subscriptions | Distinct protocol channels with process cleanup and scoped notification delivery |
| [Python api.py](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/python/sdk/src/deepseek_harness/api.py) | Session run subscribes before submitting and waits for matching inbox receipt then session idle | Subscribe before admission to prevent lost notifications; idle remains separate from verified completion |

File SHA-256 examples: agent loop `9c985dd5ce3612b0a6f1833cb592930e4e390d4249821accea53064d8e42015c`; tool scheduling `5c7e8d8ff0028b436efdd13e5dffa4801d2311c211c3af039e7dab705f87b303`. Whole-agent idle is not independently verified coding completion. Existing plan 4.1 engine restrictions remain applicable. Documented sandbox seams do not prove ForgeWeave mediation or Windows containment.

## Claude Code and Copilot delegation

**Vendor-documented**, not reverse-engineered proprietary internals. [Claude subagents](https://code.claude.com/docs/en/sub-agents) describes specialized prompts, tools, permissions, separate contexts and result summaries; fresh context and conversation forks are distinct. [Claude teams](https://code.claude.com/docs/en/agent-teams) describes a lead, separate teammates, a shared task list and mailboxes, with experimental limitations. ForgeWeave therefore distinguishes role definitions, one-shot subagents, continuable workers and coordinated groups. It uses bounded context packets by default; a fork is explicit and still filtered by policy.

[Copilot SDK custom agents](https://docs.github.com/en/copilot/how-tos/copilot-sdk/features/custom-agents) documents scoped tools/prompts/MCP, isolated delegation and lifecycle events. [Custom agent configuration](https://docs.github.com/en/copilot/reference/custom-agents-configuration) supplies a profile reference. ForgeWeave imports compatible metadata only after validation, without inheriting vendor permissions.

## Grok Build and Muse Code

Grok snapshot `2bdd1d6a6369de0e8c68132ea4539e9abd9e14a8`: inspected [agent.rs](https://github.com/xai-org/grok-build/blob/2bdd1d6a6369de0e8c68132ea4539e9abd9e14a8/crates/codegen/xai-grok-agent/src/agent.rs), [compaction.rs](https://github.com/xai-org/grok-build/blob/2bdd1d6a6369de0e8c68132ea4539e9abd9e14a8/crates/codegen/xai-grok-agent/src/compaction.rs), and [redact_common.rs](https://github.com/xai-org/grok-build/blob/2bdd1d6a6369de0e8c68132ea4539e9abd9e14a8/crates/codegen/xai-grok-otel/src/redact_common.rs). Public source exists; earlier blanket statements that all Grok internals are proprietary would be wrong. Selected files establish tool/prompt composition, compaction and redaction surfaces; broader runtime parity remains unreviewed. [Official overview](https://docs.x.ai/build/overview) documents TUI, headless and ACP surfaces. ForgeWeave keeps CLI/headless and defers ACP.

Meta's [official product page](https://ai.meta.com/llama) search result identifies Muse Code/Muse Spark, but full pages redirected to an inaccessible developer site during this review. Detailed Muse Code harness/delegation internals remain **unverified**. Do not invent those internals or declare parity. Record this research gap and revisit accessible official SDK/source documentation before adopting a Meta-specific behavior.

## Search providers: DDGS and alternatives

DDGS snapshot `70a5635510fb8d5b15d5ba6ceced6a67e212149b`: inspected [ddgs.py](https://github.com/deedy5/ddgs/blob/70a5635510fb8d5b15d5ba6ceced6a67e212149b/ddgs/ddgs.py) (SHA-256 `1cd33c4c5dd81ab865d6257327c4f079fae0cbe2e37ec8c7a9c575df771f27b1`) and packaging. It uses synchronous search and thread-pool backend work. [README](https://github.com/deedy5/ddgs) documents explicit/automatic backend selection and result fields. ForgeWeave should wrap it in a bounded worker, require explicit eligible backends, deduplicate URLs, enforce timeout/result caps and record backend disclosure. Cancelling a coroutine alone does not terminate a blocking library thread; test process isolation or await bounded cleanup. Domain filters must be enforced on returned URLs, not assumed from `site:` text. Source fetching remains a separate guarded tool.

Specific source finding: `_get_engines` can recurse to `auto` when no engine is selected (lines 128-129). Passing an explicit backend string alone is therefore insufficient. Validate the exact available backend inventory and prove invalid/disabled choices fail without network disclosure. This is an adapter acceptance requirement, not an assertion that library configuration already enforces task policy.

[SearXNG](https://github.com/searxng/searxng) is an open-source alternative. Its [search API](https://docs.searxng.org/dev/search_api.html) supports HTTP query parameters and JSON when the instance enables that format; public instances can refuse it. Add an adapter for a user-configured endpoint, not a mandatory local server. Explicitly authorize disclosure to that endpoint and its configured downstream engines. A public instance is not an automatic fallback. A hosted provider API can later implement the same contract, with separate credentials and cost accounting; not evaluated here.

## Browser-use source and integration boundary

Snapshot `7be96ed8bafa8dfe1eef228b59cf5c884b8b2431`: inspected [agent/service.py](https://github.com/browser-use/browser-use/blob/7be96ed8bafa8dfe1eef228b59cf5c884b8b2431/browser_use/agent/service.py), [tools/service.py](https://github.com/browser-use/browser-use/blob/7be96ed8bafa8dfe1eef228b59cf5c884b8b2431/browser_use/tools/service.py), [telemetry/service.py](https://github.com/browser-use/browser-use/blob/7be96ed8bafa8dfe1eef228b59cf5c884b8b2431/browser_use/telemetry/service.py), and packaging. Browser-use provides an agent/action registry and browser session flow, rather than merely a Playwright locator wrapper. Its internal loop and actions must not bypass ForgeWeave model accounting or policy.

[Official telemetry documentation](https://docs.browser-use.com/open-source/development/monitoring/telemetry) says collection can include instructions, URLs, actions and results; `ANONYMIZED_TELEMETRY=false` disables it. Source checks the configuration before creating its PostHog client. Set it before importing in an isolated adapter process, disable any separately configured cloud features, and test outbound traffic. Do not assume a step callback intercepts every effect. Inventory all default/custom actions including navigation, downloads, file access, script execution and skill/cloud calls; mediate or disable each. Native Playwright remains the baseline while this feasibility gate is open.

## Gaps confirmed and resulting changes

| Gap | Resolution |
|---|---|
| Broad feature list presented as full architecture | Coverage matrix links requirement, owner, backlog and acceptance |
| Harness/loop engineering too implicit | SYSTEM_DESIGN 14.1 defines four loops and engineering feedback |
| Delegation only summarized | 14.2 defines durable child lifecycle, context, messages, budgets and failure behavior |
| Fan-out/fan-in unspecified | 14.3 defines join modes, fixed membership, evidence validation and integration |
| Workflow DAG too shallow | 14.4 defines immutable definition, typed step state and recovery |
| No dedicated web-search contract | 14.5 defines search/fetch tools, DDGS/SearXNG seams and evidence |
| Browser-use absent | 14.6 adds optional adapter and mediation gate |
| Telemetry deferred too far | 14.7 adds M1 local diagnostics and M2 OTel/export/evals |

Runtime proof still required: exact SDK/wheel parity; Windows subprocess cancellation and isolation; external engine tool mediation; DDGS backend failure and cancellation; SearXNG JSON-disabled handling; browser-use complete action interception and telemetry-off traffic; multi-agent recovery and join/integration correctness. These are open tasks, not successful research results.
