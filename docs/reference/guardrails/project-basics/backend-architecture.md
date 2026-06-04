---
aliases:
  - Backend Architecture
  - 後端架構藍圖
tags:
  - diataxis/reference
  - audience/contributor
  - sot/true
  - topic/project-basics
status: stable
owner: docs-team
audience: contributor
scope: 定義 Python Backend control/data plane、Runner protocol 與 TraceStore publication 邊界。
version: v2.0.1
last_updated: 2026-05-28
updated_by: codex
---

# Backend Architecture

Python Backend 的目標不是單純 CRUD API，也不是 heavy simulation runtime。
它是 control plane + data plane：負責 auth/session/workspace、metadata、task lifecycle、Runner protocol、TraceStore publication、provenance 與 frontend/notebook data APIs。

!!! info "Use this page for boundary decisions"
    當問題在問「這段 backend code 應該放哪一層、誰可以依賴誰、哪裡才是 owner」時，先回到本頁。
    這頁不是 API endpoint 清單，而是 backend 內部責任分層的藍圖。

## Responsibilities

=== "Backend must own"

    - auth / session / workspace context
    - dataset / design / trace / task / result metadata
    - task submission / status / cancellation / result access
    - Runner claim / heartbeat / progress / complete / fail protocol
    - TraceStore-facing contracts, publication, and payload locators
    - manifest validation, provenance, and TraceBatchRecord / TraceRecord creation

=== "Backend must not own"

    - UI state
    - Electron-specific behavior
    - heavy simulation / sweep / fitting execution
    - Runner staging output generation
    - formal acceptance of Runner output without validation
    - frontend-only display state

!!! warning "Common failure mode"
    最常見的 backend drift 不是少一層 abstraction，而是把 UI state、transport detail、heavy compute 或 unchecked Runner output 偷塞進 services。
    一旦出現這種情況，先回來檢查 layer boundary，而不是只補 helper。

## Target Internal Structure

```text
app/backend/app_backend/
├── api/
│   ├── router.py
│   ├── routers/
│   ├── schemas/
│   └── presenters/
├── services/
├── domain/
└── infrastructure/
    ├── runtime.py
    ├── repositories/
    ├── persistence/
    ├── tracestore/
    └── runner/
```

## Layer Boundaries

| Layer | Owns | Must not own |
| --- | --- | --- |
| API | request parsing、auth gate、service invocation、response mapping、transport error translation | business workflow、persistence details、heavy compute |
| Services | use case orchestration、repository coordination、task submission、Runner state transitions、publication flow、framework-agnostic application errors | FastAPI transport exceptions、web concerns |
| Domain | backend-owned models for auth/session/task/storage adapters and publication records | HTTP schema concerns、framework bootstrapping |
| Infrastructure | persistence / TraceStore / Runner protocol adapters、composition root wiring | heavy simulation execution、frontend state |

??? info "Why the table is enough here"
    本頁要先讓讀者快速判斷 owner boundary。
    若需要更細的 transport / request-response 規格，應去看 `App / Backend` 的對應 reference，而不是在這頁重複 endpoint-level 細節。

## Dependency Direction

1. API 依賴 inward services/domain
2. services 依賴 abstractions 與 infrastructure 注入物
3. infrastructure 依賴外部系統與 runtime
4. backend 可依賴 framework-neutral Python contract packages only when needed
5. Julia Core and Julia Runner do not depend on backend internals; they communicate through HTTP/JSON task protocol and local filesystem staging

## Runner Protocol

Backend exposes these Runner protocol endpoints:

- `POST /runner/v1/tasks/claim`
- `POST /runner/v1/tasks/{task_id}/heartbeat`
- `POST /runner/v1/tasks/{task_id}/progress`
- `GET /runner/v1/tasks/{task_id}/cancellation`
- `POST /runner/v1/tasks/{task_id}/complete`
- `POST /runner/v1/tasks/{task_id}/fail`

Application-triggered simulation and analysis must always be asynchronous.
Notebook direct execution is allowed only because the notebook kernel is an explicit research execution environment.

## Publication Boundary

When Runner completes, Backend must:

1. mark the task as `staging_result`
2. validate manifest path, schema, `task_id`, and manifest checksum
3. open local staging `result.zarr`
4. verify every declared array exists
5. verify shape, chunk shape, dtype, and axis lengths
6. reject absolute paths and path traversal
7. move/copy/adopt the result into canonical TraceStore
8. create TraceBatchRecord / TraceRecord metadata
9. move manifest/log artifacts into `data/artifacts/tasks/<task_id>/`
10. mark the task completed

## TraceStore Boundary

- `data/staging/` is temporary and not authoritative.
- `data/trace_store/` is the official numeric authority.
- `data/artifacts/` keeps manifests, logs, summaries, and reports.
- Runner writes local filesystem Zarr v2 staging packages.
- Backend publishes validated staging packages into official TraceStore.
- Complex arrays must use explicit `real` and `imag` arrays.

## Agent Rule { #agent-rule }

```markdown
## Backend Architecture
- Treat backend as a headless application backend, not just a thin CRUD API.
- Keep API handlers limited to parsing, auth, service invocation, response mapping, and transport error translation.
- Keep service errors framework-agnostic; FastAPI-specific exceptions belong in the API layer.
- Keep persistence, TraceStore, Runner protocol, and publication adapters in infrastructure/services.
- Python Backend is the control plane + data plane; it must not execute heavy Julia simulation or analysis in process.
- Julia Runner is the compute plane; it writes local staging Zarr packages and reports manifest locators.
- Backend owns official TraceStore publication and must validate Runner output before creating TraceBatchRecord / TraceRecord metadata.
- No large ND arrays over HTTP/JSON; use Zarr for numeric trace payloads and HTTP only for control/status/manifest/summaries/slices.
- Do not let frontend state, Electron concerns, or transport-only display state leak into backend services or domain.
```
