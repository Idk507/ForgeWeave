# ADR-001: Defer Laya integration until native core reliability is demonstrated

Status: Accepted
Date: 2026-10-04

## Context

ForgeWeave has not yet completed its native M1 single-agent flow. The current work establishes durable events, task lifecycle, action-bound policy, tool execution recovery, context protection, verification, and a minimal CLI. Laya would add a model dependency, checkpoint lifecycle, Windows memory and startup costs, calibration data requirements, routing telemetry, and a second decision path before the core can demonstrate reliable recovery and verification.

The existing design documented Laya as optional, but still scheduled shadow-mode work in M2 and active-routing work in M5. That ordering would divide implementation attention before the native core is proven.

## Decision

Defer all Laya implementation. Do not install the package, download checkpoints, create routing commands, collect routing datasets, benchmark Laya, or expose active or shadow routing during the active delivery plan.

Native development uses deterministic eligibility constraints and explicit user model choice. The existing Laya design notes remain a future proposal, not an implementation requirement. Reintroduction requires a new ADR after the native M1 gate has passed and evidence shows a deterministic-routing limitation worth solving.

## Consequences

The active build queue remains focused on the M1 reliability spine, beginning with BT-007 tool-execution recovery. The `routing` package name remains reserved for future deterministic policy interfaces, so a later integration does not require a package rename. Laya-specific tasks are preserved as deferred feature inventory in `todo.md`, without an active milestone or release gate.

This supersedes the M2/M5 Laya sequencing portions of ADR-000 while retaining ADR-000's native-first principle.
