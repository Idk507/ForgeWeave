# Native coding CLI source review — 2026-11-01

## Purpose and evidence limits

Build ForgeWeave's own Python coding CLI with comparable user-facing workflows to Codex, Claude Code and OpenCode. Study mechanisms; do not compose their runtimes into the product. Better quality or efficiency is a hypothesis requiring matched evaluations, not a guarantee. This review supersedes older engine-delivery recommendations, while retaining their dated evidence as historical research.

Retrieval date: 2026-11-01. GitHub API returned these revisions: Codex `4b4a5cf25aa5b064c866218b405c848745fd280f`; DeepSeek Harness `ce7073d51254c26cd63b22a60835b8f948deb447`; OpenCode `97a71f0cc624f128906224ca73d9e4016b43fde0`. Source inspection is static, limited to the linked files and relevant symbols; upstream code was not executed, installed or benchmarked. Branch documents can differ from packaged releases. Claude Code observations below come from official documentation, not private or leaked source. Reason findings are vendor statements, not an independent reproduction.

## Codex: runtime and protocol separation

The official [platform explanation](https://developers.openai.com/blog/codex-as-a-platform) describes an open harness exposed through exec, SDK and app-server surfaces. The [app-server protocol](https://developers.openai.com/codex/app-server) models threads, turns, streamed items and approval interactions. These are useful interface boundaries; ForgeWeave initially needs an in-process application service, not a network server.

At the pinned revision, [session/session.rs](https://github.com/openai/codex/blob/4b4a5cf25aa5b064c866218b405c848745fd280f/codex-rs/core/src/session/session.rs) wires input queues, instruction management, retained context, agent control and session startup/teardown. Root/child trace lineage and startup failure cleanup are explicit. [tools/router.rs](https://github.com/openai/codex/blob/4b4a5cf25aa5b064c866218b405c848745fd280f/codex-rs/core/src/tools/router.rs) separates executable registry entries from model-visible schemas, supports direct/deferred exposure and checks parallel support. Its ToolCall debug representation deliberately excludes sensitive payload fields.

ForgeWeave decisions: one native application service; stable event identity; scoped cancellation; a registry whose advertised catalog matches executable capability; deferred discovery without a permission grant; redaction before diagnostic sinks. Do not copy Codex's Rust organization or require its app-server process. Evidence: source-verified in these files, vendor-documented for public interfaces.

## DeepSeek Harness: composition, settlement and history

The [architecture](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/docs/architecture.md) describes Cordis services, ordered profiles/bundles and registrations that unwind on unload. The [core map](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/packages/core/README.md) distinguishes the Agent interface from its default driver. [agent.ts](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/packages/core/agent-loop/src/agent.ts) implements queued input, a running phase with cancellation, repeated turns, step events and tool-call recovery observation; `whenIdle()` awaits the current activity rather than merely acknowledging admission.

The [session subsystem](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/docs/subsystems/session.md) derives model history from an append-only event log and distinguishes in-memory log semantics from durable persistence. The [tool subsystem](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/docs/subsystems/tools.md) specifies canonical JSON outputs, separate presentation, host-only metadata, cancellation propagation and settling owned work before return.

ForgeWeave decisions: typed canonical observations, independently bounded model/UI projections, explicit admission versus idle versus verified completion, and scoped extension cleanup. Unlike the upstream everything-is-replaceable architecture, ForgeWeave retains an authoritative policy and persistence spine. Evidence: source-verified driver; vendor-documented subsystem contracts.

## Claude Code: documented interaction model

[How it works](https://code.claude.com/docs/en/how-claude-code-works) describes context gathering, action and verification with interruption and steering. Adopt a continuing conversational task loop, not a single response or fixed research/plan/edit pipeline. [Subagents](https://code.claude.com/docs/en/sub-agents) have separate contexts, tool access and permissions; this supports bounded delegation with compact results. Exact internal implementation remains unknown here.

[Hooks](https://code.claude.com/docs/en/hooks) document lifecycle interception. ForgeWeave hooks may deny or require checks but cannot override central policy. [Memory](https://code.claude.com/docs/en/memory) distinguishes project instruction files from automatic memory; retain provenance and user-visible control. [Checkpointing](https://code.claude.com/docs/en/checkpointing) documents edit/conversation rewind and its limitations; ForgeWeave must explicitly distinguish conversation branching, tracked file restoration and irreversible external effects. A checkpoint does not undo arbitrary shell or remote actions. Evidence: vendor-documented, not source-verified.

## OpenCode: explicit agents, permissions and context services

At the pinned revision, [session/prompt.ts](https://github.com/anomalyco/opencode/blob/97a71f0cc624f128906224ca73d9e4016b43fde0/packages/core/src/session/prompt.ts) processes prompt attachments through session storage, skill and plugin services. [permission.ts](https://github.com/anomalyco/opencode/blob/97a71f0cc624f128906224ca73d9e4016b43fde0/packages/core/src/permission.ts) keeps pending approval requests with deferred completion, rejects pending work on close, and reevaluates eligible requests after saved permission updates. [session/compaction.ts](https://github.com/anomalyco/opencode/blob/97a71f0cc624f128906224ca73d9e4016b43fde0/packages/core/src/session/compaction.ts) is a separate context service, not a substitute for original history.

Official [agent docs](https://opencode.ai/docs/agents/) distinguish primary agents and subagents, including plan/build workflows. [Permissions](https://opencode.ai/docs/permissions/) expose allow/ask/deny. ForgeWeave adopts these understandable user controls but keeps stricter action-bound grants and permission intersection. Reimplement concepts in Python, without requiring Bun, TypeScript or OpenCode itself. Evidence: source-verified named services; vendor-documented UX.

## Reason Machines and newer efficiency ideas

The [Reason Agent 1.1 announcement](https://reasonmachines.com/blog/introducing-reason-agent-1-1) describes parallel tool programs, a small direct tool surface with deferred tools, and stable prompt/tool prefixes for cache eligibility. It says the agent builds on Pi and acknowledges that savings from individual design choices have not been isolated. Treat the published scores and savings as vendor-reported; benchmark editions, model/effort, pricing and refusal grading affect comparisons. Do not promise the same gains.

[Reason Network](https://reasonmachines.com/network) concerns communication among existing agent sessions. It is separate from the independent coding harness requested here. Its public messaging UX informs durable mailbox/receipts and session status; installing or joining that network is not part of ForgeWeave's plan. Hosted computers, network federation and cross-vendor orchestration remain outside the local release. No install commands on these pages were executed.

## Search, browser and package identity

[DDGS](https://pypi.org/project/ddgs/) is an optional search dependency: review exact-release backend selection and fallback behavior before use. A configured backend cannot silently disclose queries to an unapproved provider. [SearXNG's API](https://docs.searxng.org/dev/search_api.html) supports configured output formats; a chosen instance must allow JSON and may refuse requests. Search snippets are discovery evidence; separate guarded fetch obtains citable source content. Browser automation remains native Playwright first; [browser-use](https://docs.browser-use.com/open-source/supported-models) documents its own model layer, so nested model calls and browser actions require separate accounting and mediation before an optional adapter.

The official OpenAI Codex harness is the `openai/codex` runtime, distinct from the third-party [codex-harness package](https://pypi.org/project/codex-harness/), which advertises local change control. Official [DeepSeek SDK metadata](https://pypi.org/pypi/deepseek-harness-sdk/json) is distinct from similarly named clients. Earlier pinned package versions remain historical observations, not current recommendations or approval to install. This review changes no dependency pins.

## Repository findings and priorities

Static inspection of `cli/run.py` shows a one-turn entry point, direct root writes, a coarse allow rule and no owned-worktree/task composition. `core/loop.py` now accepts an optional execution recorder, but the CLI does not wire it. Existing records commonly contain URI references without durable retrievable payloads. A hash alone does not establish replay fidelity.

BT-124's broad exception path can classify a result-publication failure after a successful side effect as tool failure. The next implementation must distinguish pre-dispatch rejection, known tool failure, unknown outcome and persistence failure. Shared event/execution updates need transaction ownership. Existing injected parallel dispatch must also use the same authorization, fencing and recording boundary as serial dispatch.

These are inspection findings, not fresh fault-test results. They explain the priority: complete native task composition, structured multi-step feedback, durable payloads/recovery and protected verification before adding more orchestration. Architecture requirements and measurable tasks are in SYSTEM_DESIGN section 16 and todo N-series. The existing M-series inventory remains in scope except retired external-engine delivery requirements.
