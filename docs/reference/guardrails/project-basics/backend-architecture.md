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
scope: 定義 backend 的責任邊界、模組分層與對 sc_core 的依賴方向。
version: v1.3.0
last_updated: 2026-03-21
updated_by: codex
---

# Backend Architecture

backend 的目標不是單純 CRUD API，而是可獨立運作的 headless application backend。
即使 frontend 尚未完成，backend 也應能提供穩定的 auth、CRUD、TraceStore、task、result 與 execution contracts。

!!! info "Use this page for boundary decisions"
    當問題在問「這段 backend code 應該放哪一層、誰可以依賴誰、哪裡才是 owner」時，先回到本頁。
    這頁不是 API endpoint 清單，而是 backend 內部責任分層的藍圖。

## Responsibilities

=== "Backend must own"

    - auth / session / workspace context
    - metadata CRUD
    - TraceStore-facing contracts 與 payload locator
    - task submission / status / result access
    - execution orchestration 與 service composition
    - 對 `sc_core` canonical contracts 的 adapter 與 transport mapping

=== "Backend must not own"

    - UI state
    - Electron-specific behavior
    - duplicated scientific invariants
    - frontend-only display state

!!! warning "Common failure mode"
    最常見的 backend drift 不是少一層 abstraction，而是把 UI state、transport detail 或 duplicated scientific rules 偷塞進 services。
    一旦出現這種情況，先回來檢查 layer boundary，而不是只補 helper。

## Target Internal Structure

```text
backend/src/app/
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
    └── execution/
```

## Layer Boundaries

| Layer | Owns | Must not own |
| --- | --- | --- |
| API | request parsing、auth gate、service invocation、response mapping、transport error translation | business workflow、persistence details |
| Services | use case orchestration、repository coordination、task submission flow、framework-agnostic application errors | FastAPI transport exceptions、web concerns |
| Domain | backend-owned models for auth/session/task/storage adapters | HTTP schema concerns、framework bootstrapping |
| Infrastructure | persistence / TraceStore / execution adapters、composition root wiring | canonical scientific contracts、frontend state |

??? info "Why the table is enough here"
    本頁要先讓讀者快速判斷 owner boundary。
    若需要更細的 transport / request-response 規格，應去看 `App / Backend` 的對應 reference，而不是在這頁重複 endpoint-level 細節。

## Dependency Direction

1. API 依賴 inward services/domain
2. services 依賴 abstractions、`sc_core` 與 infrastructure 注入物
3. infrastructure 依賴外部系統與 runtime
4. backend 可依賴 `sc_core`
5. `sc_core` 不得依賴 backend

## Integration With sc_core

=== "Prefer `sc_core` as owner for"

    - circuit definition invariants
    - task routing / execution contracts
    - storage / provenance canonical handles
    - shared scientific compute orchestration

=== "Backend still owns"

    - API contract exposure
    - persistence / auth / task / workspace semantics
    - adapter state mapping to `sc_core` canonical surfaces

## Agent Rule { #agent-rule }

```markdown
## Backend Architecture
- Treat backend as a headless application backend, not just a thin CRUD API.
- Keep API handlers limited to parsing, auth, service invocation, response mapping, and transport error translation.
- Keep service errors framework-agnostic; FastAPI-specific exceptions belong in the API layer.
- Keep persistence, TraceStore, and execution adapters in infrastructure.
- Reuse `sc_core` for canonical scientific contracts instead of duplicating them in backend adapters.
- Do not let frontend state, Electron concerns, or transport-only display state leak into backend services or domain.
```
