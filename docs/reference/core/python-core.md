---
aliases:
  - Python Core Reference
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/core-reference
status: stable
owner: docs-team
audience: team
scope: Python core 能力、共享 contract 與 backend-facing reference surface。
version: v0.6.0
last_updated: 2026-05-28
updated_by: codex
---

# Python Core

本頁記錄 Python-owned core surface：`sc_core` 的 canonical contracts，以及 Python Backend 如何在 persistence、task lifecycle、storage reference 中消費這些 contracts。

!!! info "Owned Surface"
    Python core 的 canonical owner 是 installable `sc_core` package。
    canonical folder 是 top-level `core/`。
    `core/shared/` 與 `core/sc_core/` 是目前的 implementation location；
    app/backend adapters 是 adopter，不是 contract owner。

!!! warning "Do Not Move Ownership"
    HTTP schema、ORM / repository implementation、Electron runtime concerns 不得寫成 `Python Core` 的 owner 範圍。
    這些屬於 adapter 或 app layer。

## Exported Families

=== "Circuit Definitions"

    | Surface | Focus | Primary exports |
    |---|---|---|
    | `sc_core.circuit_definitions` | canonical source inspection、validation、preview artifact naming | `inspect_circuit_definition_source`, `CircuitDefinitionInspection`, `ValidationNotice`, `ValidationLevel`, `DEFAULT_PREVIEW_ARTIFACTS` |

=== "Tasking"

    | Surface | Focus | Primary exports |
    |---|---|---|
    | `sc_core.tasking` | task submission kind、lane naming、dispatch routing metadata | `TaskSubmissionKind`, `LaneName`, `WorkerDispatchPlan`, `resolve_worker_task_route`, `build_worker_dispatch_plan`, `build_worker_enqueue_kwargs` |

=== "Execution"

    | Surface | Focus | Primary exports |
    |---|---|---|
    | `sc_core.execution` | task creation、lifecycle mutation、execution operation、history / audit payload | `TaskCreationSpec`, `TaskExecutionOperation`, `TaskExecutionTransition`, `TaskLifecycleMutation`, `TaskResultHandle`, lifecycle builder helpers |

=== "Storage"

    | Surface | Focus | Primary exports |
    |---|---|---|
    | `sc_core.storage` | trace / result handles、trace-store locator、payload lifecycle、version markers | `StorageRecordHandle`, `TraceBatchHandle`, `TraceStoreLocator`, `TraceStorePayloadLifecycle`, `TraceStoreVersionMarkers`, `TraceResultLinkage` |

## Python Adopters

| Adopter Surface | Role | Why it is not the owner |
|---|---|---|
| `core/shared/persistence/repositories/` | persisted rows 映射到 canonical objects | repository 實作是 adapter；canonical shape 由 `sc_core` 決定；不得反向定義 `core/` topology |
| `core/shared/persistence/trace_store.py` | TraceStore backend binding | backend binding 與 runtime config 不等於 storage contract owner |
| `app/backend/src/app/infrastructure/persistence/` | app backend persistence adapter | backend adapter consumes contracts; it does not redefine them |
| `app/backend/src/app/services/` | task lifecycle and publication services | service layer orchestrates contracts; compute remains in Julia Runner |

## Consumer Pairing

| Consumer | 主要依賴的 Python core family |
|---|---|
| Backend task / dataset / definition adapters | `circuit_definitions`, `execution`, `storage` |
| Backend runner API / publisher | `tasking`, `execution`, `storage` |

## Ownership Boundary

| Concern | SoT |
|---|---|
| ownership boundary | [Core Reference](index.md) |
| canonical contract ownership | [Canonical Contract Registry](../architecture/canonical-contract-registry.md) |
| task lifecycle semantics | [App / Backend / Tasks & Execution](../app/backend/tasks-execution.md) |

## Related

- [Core Reference](index.md)
- [Julia Wrapper](julia-wrapper.md)
