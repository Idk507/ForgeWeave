# ADR-002: Complete harness coverage and add research tools

## Status
Accepted for architecture and delivery scope; integration feasibility remains subject to the listed spikes.

## Date
2026-10-04

## Context
The feature inventory already named agents, workflows, loops and telemetry, but implementation contracts did not adequately define delegation lifecycle, fan-out/fan-in, workflow joins or research tools. Summaries also omitted important product requirements. A feature mention does not establish implementation readiness. The user requests source-based reference studies before further development, including DeepSeek Harness, OpenAI Codex, DDGS and browser-use.

## Decision
1. Preserve the full CLI feature inventory. Add a traceability matrix and SYSTEM_DESIGN section 14 with concrete ownership, contracts and acceptance gates. Distinguish planned, partial and verified behavior.
2. Treat harness engineering as lifecycle, policy, context, environment, tool, verification and feedback engineering. Specify separate inference/tool, repair, orchestration/workflow and Ralph loops. All inherit finite budgets and deterministic stop conditions.
3. Keep native Python ownership of execution and audit. Study upstream implementations at recorded commits; adopt architectural patterns through native interfaces. Optional SDK delegation does not replace native capabilities or establish mediated execution.
4. Make web search and source fetching first-class typed tools. Start with an optional DDGS adapter restricted to explicit approved backends, then an adapter to a user-configured SearXNG endpoint. No server deployment is required. Search and URL fetching have separate effects, permissions and artifacts.
5. Retain Playwright as the native browser baseline. Add an optional browser-use automation adapter only after a source/runtime spike proves every action crosses ForgeWeave policy. Otherwise report delegated-unmediated behavior and exclude unrestricted automation from the release. Disable its product telemetry before import in a dedicated subprocess and verify with a network-capture test.
6. Add local structured logs, metrics and trace correlation during M1 loop integration; expand to OTel/export/evaluation in M2. Durable audit events remain independent of diagnostic exporters.
7. Explicitly specify custom agent definitions, isolated child context, durable delegation, messages, bounded concurrency, aggregate budgets, deterministic joins and reviewed integration. Multi-agent execution remains opt-in after native M1 reliability.

## Alternatives considered
Embedding DeepSeek or Codex as the core would divide state and authority between harnesses. Running browser-use as an unrestricted nested agent would conceal browser actions from policy. DDGS automatic backend selection would make query disclosure difficult to explain. Listing broad features without requirements and tests repeats the original gap.

## Consequences
M0 gains a research/coverage gate; M1 gains diagnostic instrumentation; M2 gains search; M3 gains explicit delegation and browser-use investigation; M4 gains workflow join/recovery contracts. Existing completed slices remain completed only to their recorded scope. Package versions observed during research are not new dependency pins; compatible wheels and Windows behavior must be tested before integration. ADR-001 continues to defer Laya.

Resolve a pre-existing scope contradiction: SYSTEM_DESIGN 13.6 described M1 as first-release acceptance while AGENTS.md's first-release scenario includes later CLI capabilities. M1 is the native vertical-slice gate, not the complete first CLI release. Preserve the broader feature inventory and validate its required enabled capabilities before claiming full release completion.

## Evidence
See [source review](../research/harness-source-review-2026-10-04.md), [coverage matrix](../feature-coverage.md), [SYSTEM_DESIGN section 14](../../SYSTEM_DESIGN.md#14-harness-loop-orchestration-and-research-contracts-2026-10-04), and [todo](../../todo.md). This ADR supplements ADR-000 and supersedes earlier vague scheduling/search/telemetry scope, without changing canonical package ownership or tool event names.
