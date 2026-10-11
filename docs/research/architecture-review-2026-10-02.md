# Pre-development architecture review

Reviewed: 2026-10-02. Scope: planning documents, current source/test inventory and primary technical documentation. No provider calls, dependency installations or engine-runtime spikes performed.

## Task record

Affected owners: architecture documentation, context, events, task, policy, tools, models, verify and CLI planning. Acceptance: reconcile conflicting contracts, identify concrete gaps, define acceptance fixtures and sequence them before implementation. Verification: local Markdown links, cross-document names, source-file hashes and checklist consistency. Security: documentation only; no credentials or publication. Compatibility: Python 3.11+, native Windows 11, no required service. Existing unchecked tasks remain open.

## Current evidence

`src/forgeweave/engines` contains contracts, adapters, registry and pre-flight validation; `verify/regression.py` contains baseline comparison and a retry budget. Only two unit-test modules exist. No native CLI, event store, context assembler, gateway or workspace manager is present. Fake-SDK tests do not establish OS confinement. The Git root resolves above ForgeWeave, so do not assume this folder is already an independent repository.

## Primary research and implications

| Source | Evidence | ForgeWeave decision / acceptance |
|---|---|---|
| [Anthropic context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) | Vendor engineering guidance: selective retrieval, compaction and structured notes | Record selected sources; protect requirements outside summaries; evaluate retention across compactions. Exact budgets below are proposals, not vendor guarantees. |
| [SQLite WAL](https://www.sqlite.org/wal.html) | Specification: one writer, same-host shared memory, FULL/NORMAL durability tradeoff, WAL is persistent state | Local state directory, short serialized transactions, bounded busy handling, FULL for action authorization, SQLite-aware backup plus artifact manifest. Test power-loss/crash boundaries. |
| [Windows Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects) | OS documentation: process grouping, limits and termination, with breakaway considerations | Test descendant termination and report capabilities separately; do not claim filesystem/network containment from process grouping. |
| [MCP security practices](https://modelcontextprotocol.io/docs/2025-11-25/tutorials/security/security_best_practices) | Protocol guidance: token audience, consent, SSRF and local-server risks | Scope credentials to connections, reject token passthrough, validate auth-discovery destinations and explicitly authorize local server launch. |
| [MCP lifecycle](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle) | Version and capability negotiation precede normal operation | Pin supported protocol versions, reject unsupported capabilities and rebuild catalogs after reconnect. |

These references support the identified failure modes. The proposed contracts and thresholds are ForgeWeave design decisions and require implementation-time tests. Existing provider/package claims in plan.md section 4.1 were not independently revalidated here and remain subject to the listed spikes.

## Gap assessment

| Gap | Priority | Owning contract |
|---|---|---|
| Naming/delivery contradictions | Before coding | ADR-000 |
| Summary loses a requirement or promotes untrusted text | M1 blocker | ContextManifest, ConstraintLedger, SummaryRecord |
| Exact prompt reconstruction conflicts with sensitive-data minimization | M1 blocker | Replay fidelity and retention policy |
| Crash after side effect but before result append | M1 blocker | ToolExecution reconciliation state |
| Approval reused after arguments/workspace change | M1 blocker | ApprovalGrant binding/expiry |
| Shell/test/Git hook effects exceed predicted effects | M1 blocker | ExecutionProfile and OS containment evidence |
| Partial stream, missing usage and retry overspend | M1 blocker | ModelTurn accumulator and BudgetLedger |
| SQLite/artifact consistency and lease split-brain | M1 blocker | Transaction unit of work and fencing |
| MCP auth discovery bypasses browser egress checks | M2/M5 blocker | Shared egress policy |
| Verification checks acceptance while model changes tests | M1 blocker | AcceptanceSpec and verification fingerprint |
| Windows paths, terminal escape output, nested Git roots | M0/M1 blocker | Native-platform fixtures |

## Additions worth prioritizing

Add CLI context inspection, structured recovery, doctor/preflight diagnostics, bounded evaluation fixtures and a release support matrix. Defer semantic indexing, dynamic model optimization, additional engines and more UI breadth until the native slice has recovery evidence. A separate hosted service or editor would add scope without resolving these gaps.

## Remaining uncertainties

Windows containment backend, runtime/library compatibility, first provider credential flow, token estimator accuracy and real-engine mediation need spikes. Do not convert a documented mechanism into a passing security claim. Active routing thresholds require a consented held-out dataset; they cannot be chosen from vendor confidence alone.
