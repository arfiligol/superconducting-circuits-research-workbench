---
aliases:
  - App Observability Model
  - Workflow Observability Model
  - 可觀測性模型
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/app-reference
status: draft
owner: docs-team
audience: team
scope: audit logging、workflow observability 與 product telemetry 的 shared taxonomy、責任邊界與 correlation vocabulary。
version: v0.1.0
last_updated: 2026-03-25
updated_by: codex
---

# Observability Model

本頁定義 app-level observability 的正式分層與 shared vocabulary。

!!! info "Three layers, not one log stream"
    本頁處理的是 observability taxonomy。
    若你要的是 actor-centric governance trail，請看 [Audit Logging](audit-logging.md)。
    若你要的是開發層 `logging` module 用法，請看 [Logging Standards](../../guardrails/code-quality/logging.md)。

!!! warning "Do not collapse audit, workflow, and telemetry"
    audit logging、workflow observability 與 product telemetry 可以共享少量 correlation fields，
    但不得收斂成同一個 authority、同一個 query surface 或同一個 retention policy。

## Coverage

| Layer | This page defines |
|---|---|
| Audit logging | governance-facing action taxonomy boundary |
| Workflow observability | request / task / queue / worker / result timeline boundary |
| Product telemetry | aggregate usage / performance measurement boundary |
| Shared vocabulary | correlation / debug / actor / session linkage fields |

## Observability Taxonomy

| Layer | Primary question | Canonical owner | Primary consumers | Must not be confused with |
|---|---|---|---|---|
| Audit Logging | 誰做了什麼治理意義的動作 | app/shared + backend audit surface | admin、workspace governance、support | workflow timeline、page analytics |
| Workflow Observability | 一個 action / request / task 經過哪些 runtime stage | backend runtime + desktop shell adapter + task surfaces | operator、developer、support | actor governance trail |
| Product Telemetry | 哪種 flow 常用、哪裡慢、哪種 path 值得優化 | app telemetry pipeline | product engineering、performance analysis | audit trail、single-task debug record |

## Shared Correlation Vocabulary

| Field | Meaning |
|---|---|
| `correlation_id` | 將同一串 request / task / result / audit action 關聯起來 |
| `debug_ref` | support-safe debug lookup reference |
| `task_id` | task / queue / worker / result handoff 的 public execution identity |
| `session_id` | mode-aware session linkage |
| `workspace_id` | workspace-scoped governance / visibility boundary |
| `actor_user_id` | remote governance 與 actor-centric lookup |
| `runtime_mode` | `local` 或 `online`；不可被 desktop profile 術語取代 |

## Mode Applicability

| Layer | Local mode | Online mode |
|---|---|---|
| Audit logging | reduced / optional；只有當 local governance surface 被明確啟用時才成立 | required for multi-user governance |
| Workflow observability | required | required |
| Product telemetry | allowed，受 local privacy / developer settings 控制 | allowed，受 product telemetry policy 控制 |

## Desktop Shell Responsibilities

| Concern | Contract |
|---|---|
| Local-managed sidecars | desktop shell 可聚合 `redis`、`sc-app`、workers 的 runtime health 與 logs |
| Remote-server profile | desktop shell 不得為了 observability 順手啟動本地 heavy runtime |
| Authority boundary | desktop shell 可做 log aggregation / health display，但不得取代 backend persisted task truth |
| Correlation propagation | local-managed profile 下，desktop shell 應協助把 user action / runtime context 傳給 app/backend 與 sidecars |

## Storage And Access Separation

| Layer | Storage / access baseline |
|---|---|
| Audit logging | separate audit store + governance query surface |
| Workflow observability | runtime/event timeline store 或等價 query surface；可從 persisted task + dispatch metadata + runtime events 重建 |
| Product telemetry | aggregate telemetry pipeline；不得把 raw governance payload 直接當 telemetry store |

## Minimum Consumer Surfaces

| Consumer surface | Reads from |
|---|---|
| Audit Logs page | audit logging surface |
| Task / runtime developer tooling | workflow observability surface |
| Product performance analysis | telemetry aggregates |

!!! tip "Shared identifiers are allowed"
    例如 `correlation_id` 可以同時出現在 audit row、request log 與 task timeline 中。
    但這不表示三者是同一份 authority。

## Related

- [Runtime Modes](runtime-modes.md)
- [Task Runtime & Processors](task-runtime-and-processors.md)
- [Audit Logging](audit-logging.md)
- [Backend / Audit Logs](../backend/audit-logs.md)
- [Backend / Tasks & Execution](../backend/tasks-execution.md)
- [Logging Standards](../../guardrails/code-quality/logging.md)
