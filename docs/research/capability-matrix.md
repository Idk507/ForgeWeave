# Capability-to-implementation index

Updated 2026-11-01. Current review covers the five references requested for this architecture refresh. It is not a claim that every vendor feature has been inventoried. Older broad-product source gaps remain M0.H2/M0.2 work. Pinned revisions, exact source links and evidence limitations are in [the source register](native-cli-source-review-2026-11-01.md). All ForgeWeave outcomes below are planned until their native acceptance tests pass.

| Reference / mechanism | Evidence | Native owner | Delivery / acceptance |
|---|---|---|---|
| Codex session startup/input/cleanup | Pinned session source | core/task/sessions | N1–N3; failed startup preserves evidence and releases resources |
| Codex thread/turn/item protocol | Official app-server docs | contracts/cli/sdk | N4; ordered streaming and SDK/CLI lifecycle parity |
| Codex direct/deferred tool catalogs | Pinned router source | tools/context/policy | N5; exact advertised schema and reauthorization at invocation |
| DeepSeek queued turns and whenIdle | Pinned agent driver | core | N2; admission differs from settlement; no leaked active work |
| DeepSeek event-derived context | Official session subsystem | sessions/events/context | N2–N3; history projection and declared replay fidelity |
| DeepSeek canonical output/presentation | Official tools subsystem | tools/events | N2; validated JSON and bounded projections with evidence refs |
| DeepSeek reversible registrations | Official architecture | plugins/hooks | N5; unload removes registrations without policy bypass |
| Claude Code context/action/verify | Official product docs | core/verify | N1–N3; model sees tool feedback and protected checks decide completion |
| Claude Code steering/checkpoint UX | Official product docs | cli/sessions/workspace | N4; safe-boundary input, scoped rewind and no effect replay |
| Claude Code subagent contexts | Official product docs | agents/context | N6; scoped contexts/permissions and verified results |
| Claude Code hooks/memory distinction | Official product docs | hooks/memory | N5/N7; interception cannot grant authority; durable facts require evidence |
| OpenCode permission request settlement | Pinned permission service | policy/core | N3–N4; cancel/close settles waits; approvals bind to exact actions |
| OpenCode prompt/compaction services | Pinned source | sessions/context | N2/N4; preserve attachments/provenance and protected constraints |
| OpenCode primary/plan/build agents | Official agent docs | agents/cli | N4/N6; mode-specific effective tool permissions |
| Reason stable prefixes/deferred tools | Vendor announcement; gains unreplicated | context/tools/telemetry | N8; matched quality/cost experiments before defaults |
| Reason parallel tool programs | Vendor announcement; internals unknown | core/tools | N8; typed batches first; every nested effect mediated |
| Reason Network session messaging | Vendor network docs; separate product | agents | N6 local durable mailboxes only; no external federation delivery |
| DDGS and configured SearXNG | Package/API documentation | tools/web/policy | N5; no unapproved backend fallback; guarded fetch and citations |
| Native browser / optional browser-use | Existing section 14.6 plus current provider docs | browser/policy | N6; all actions mediated, telemetry verified off, cancellation/cleanup |

Public implementation is available for the pinned Codex, DeepSeek and OpenCode files. The Claude Code runtime and complete Reason harness internals were not established by this review. Do not infer private architecture or copy proprietary material. Other products remain reference research, not additional runtime dependencies.
