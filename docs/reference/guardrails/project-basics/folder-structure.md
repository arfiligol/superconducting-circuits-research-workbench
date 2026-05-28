---
aliases:
  - Folder Structure
  - 目錄結構
tags:
  - diataxis/reference
  - audience/contributor
  - sot/true
  - topic/project-basics
status: stable
owner: docs-team
audience: contributor
scope: 定義 current platform 的 app/core/notebooks/scripts/docs canonical surfaces、direct-develop iteration 與 migration residue 邊界。
version: v4.4.0
last_updated: 2026-05-28
updated_by: codex
---

# Folder Structure

本 branch 的 canonical target layout 以 `app/`、`core/`、`notebooks/`、`scripts/`、`docs/` 作為正式架構邊界。
`app/backend/`、`app/frontend/`、`app/desktop/`、`core/julia/`、`core/python/` 是目前應被人類與 AI Agent 直接辨識的主要開發對象。

root-level `backend/`、`frontend/`、`desktop/`、`cli/` 與 `src/` 不再是 active surfaces。
若未來又看到這些 root-level 位置出現可執行 code，應先視為 architecture regression。

!!! info "How to use this page"
    當你不確定新檔案該放哪裡時，先看 placement rules，而不是先照習慣找最近的資料夾塞進去。這頁的重點是 owner boundary，不是完整檔案樹教學。

See [Simulation Interface Boundaries](../../architecture/simulation-interface-boundaries.md) before changing notebook, Application Simulation Workbench, Backend task, or Runner ownership.

## Target Layout

```text
superconducting-circuits-tutorial/
├── app/
│   ├── backend/               # Python Backend control/data plane
│   ├── frontend/              # Next.js data workbench
│   └── desktop/               # Electron shell
├── core/
│   ├── julia/
│   │   ├── SuperconductingCircuitsCore/
│   │   └── SuperconductingCircuitsRunner/
│   └── python/
│       └── sc_data_contracts/
├── notebooks/
│   ├── pluto/
│   └── python/
├── docs/                      # zh-TW docs, guardrails, and docs staging tree
├── data/                      # raw / processed / trace-store / local DB
├── openapi.json               # committed OpenAPI snapshot for contract sync
└── scripts/
    ├── dev/
    ├── build/
    ├── test/
    └── maintenance/
```

!!! important "Top-level folders are the architecture boundaries"
    這份 target layout 故意不把 root `backend/`、`frontend/`、`desktop/`、`cli/` 或 `src/` 畫成 canonical surfaces。
    package-internal `src/` 可以存在於 `app/backend/`、`app/frontend/`、`app/desktop/` 之內，
    但 root-level package surfaces 不再是未來架構的正式收納模型。

## Placement Rules

| 如果要改 | 應放位置 |
| --- | --- |
| Next.js page, layout, component | `app/frontend/` |
| Application Simulation Workbench UI | `app/frontend/` |
| Electron main / preload / packaging | `app/desktop/` |
| API router, service, persistence | `app/backend/` |
| Simulation request / result view API | `app/backend/` |
| Julia circuit construction / simulation / analysis library | `core/julia/SuperconductingCircuitsCore/` |
| Julia async compute runner | `core/julia/SuperconductingCircuitsRunner/` |
| Julia Runner task execution | `core/julia/SuperconductingCircuitsRunner/` |
| Python data contract schemas if needed | `core/python/sc_data_contracts/` |
| Pluto notebook | `notebooks/pluto/` |
| Direct research notebook | `notebooks/pluto/` |
| Python backend/data notebook | `notebooks/python/` |
| Backend/API notebook client | `notebooks/python/` |
| dev/build/test/maintenance helper | `scripts/dev/`, `scripts/build/`, `scripts/test/`, `scripts/maintenance/` |
| archived legacy UI / command workflow / runtime residue | `docs/archive/` as inert text only, or delete if not needed |
| retired root worker runtime residue | 不屬於 target layout；不得新增或恢復 |
| committed OpenAPI contract snapshot | root `openapi.json` |

!!! warning "Do not reintroduce old root package surfaces"
    這次決策不是把 `app/backend/`、`app/frontend/`、`app/desktop/` 再拆回 root `backend/`、`frontend/`、`desktop/`。
    也不要讓 root `cli/` 或 `src/` 重新變成 active entrypoint。

!!! important "Notebook boundary"
    Pluto notebooks are allowed to directly use Julia Core. Python notebooks are not.

    Python notebooks should be treated as programmable clients of the Application Backend, not as a second scientific compute surface.

## Removed Root Surfaces

| Removed location | Current rule |
| --- | --- |
| `backend/` | must not exist as an active root surface |
| `frontend/` | must not exist as an active root surface |
| `desktop/` | must not exist as an active root surface |
| `cli/` | must not exist as an active product surface |
| `src/app/` | must not exist as active UI/runtime code |
| root worker runtime folder | must not exist as active runtime code |

## Architecture Regression Search Gate

Use stale-wording searches when architecture docs, guardrails, runtime layout, or app surfaces change. Check for:

- grouped Electron / Pluto / Python notebook task-flow wording;
- Pluto wording that makes it a Backend workflow participant;
- Python Notebook wording that makes it a Julia compute path;
- Simulation Workbench removal or Pluto replacement wording;
- active CLI, retired Python UI runtime, retired queue-service runtime, or root worker references.

The expected result is no active architecture text that reintroduces old surfaces or confuses notebook/application responsibilities. Hits are acceptable only when they are explicitly forbidden-regression or retired/inert wording.

## Retired Planning Artifacts

`Plans/` is retired as an active repo surface.
Do not create new committed plan prompts, lane handoffs, or temporary coordination artifacts there.

| Concern | Rule |
| --- | --- |
| Durable product / architecture decisions | write them under `docs/reference/**` |
| Ephemeral planning | keep it in the conversation, issue, PR body, or final report |
| Existing `Plans/` files | delete unless the user explicitly asks to preserve one as archive |
| New task slicing | use Codex subagents internally; do not commit lane prompts |

If a deleted plan contains a durable decision, promote that decision to `docs/reference/**` before relying on it.

## Related Blueprints

- backend 的責任分層與模組邊界，參見 [Backend Architecture](./backend-architecture.md)
- shared core 的 canonical contract 與 adopter boundary，參見 [Core Reference](../../core/index.md)

## Dependency Direction

1. `app/frontend/` 依賴 API contract，不直接依賴 backend internals
2. `app/desktop/` 依賴 frontend build、backend/runner process supervision 與受控 IPC，不承載業務規則
3. `app/backend/` API 層依賴 services/domain/infrastructure，不執行 heavy compute
4. Pluto Notebook may depend directly on `SuperconductingCircuitsCore`
5. `notebooks/python/` depends on Backend API contracts, not the Julia scientific core
6. Application Simulation Workbench depends on Backend task/result APIs, not Julia Core
7. `core/julia/SuperconductingCircuitsRunner/` depends on Julia Core and Backend Runner protocol, and does not own formal metadata DB
8. `core/julia/SuperconductingCircuitsCore/` does not depend on FastAPI, Next.js, Electron, or Python Backend internals
9. `scripts/` 不得成為 user-facing command-line product surface
10. root `backend/`、`frontend/`、`desktop/`、`cli/`、`src/` residues 不得被重新解讀成正式 architecture boundary

??? note "Why the full tree is still shown"
    這頁保留完整 target layout，是因為 folder boundary 本身就是 reference contract。其餘 guardrails 不需要都像這樣展開。

## Agent Rule { #agent-rule }

```markdown
## Folder Structure
- **Frontend** work goes to `app/frontend/`.
- **Desktop shell** work goes to `app/desktop/`.
- **Backend** work goes to `app/backend/`.
- **Julia Core** work goes to `core/julia/SuperconductingCircuitsCore/`.
- **Julia Runner** work goes to `core/julia/SuperconductingCircuitsRunner/`.
- **Python contracts** go to `core/python/sc_data_contracts/` only if needed.
- **Notebooks** go to `notebooks/pluto/` or `notebooks/python/`.
- **Pluto notebooks** may directly use `SuperconductingCircuitsCore`.
- **Python notebooks** are programmable Backend API clients and are not a second scientific compute surface.
- **Application Simulation Workbench** work goes to `app/frontend/` and depends on Backend task/result APIs.
- **No user-facing command-line product surface**; helper automation goes to `scripts/dev/`, `scripts/build/`, `scripts/test/`, or `scripts/maintenance/`.
- **Archived legacy UI / command workflow / old runtime residue** should be deleted from active package discovery or moved to `docs/archive/` as inert text.
- **Root worker runtime folder** must not be recreated as a runtime surface.
- **Docs and guardrails** go to `docs/`; `docs/docs_zhtw/` is generated staging, not a primary edit source.
- **Plans** is retired as an active repo surface; do not create new committed plan prompts or lane handoffs.
- **Committed OpenAPI snapshot** stays at repo root as `openapi.json` for contract-sync verification.
- Root-level `backend/`, `frontend/`, `desktop/`, `cli/`, and `src/` are not future canonical surfaces.
- Dependency direction:
    - frontend depends on API contracts, not backend internals
    - desktop depends on frontend outputs, backend/runner process supervision, and secure IPC, not business logic ownership
    - backend API layer depends inward on services/domain/infrastructure and must not run heavy compute
    - Pluto Notebook may depend directly on `SuperconductingCircuitsCore`
    - Python notebook clients depend on Backend API contracts, not the Julia scientific core
    - Application Simulation Workbench depends on Backend task/result APIs, not Julia Core
    - Julia Runner owns compute execution and staging result packages, not formal metadata DB records
    - Julia Core must stay framework-agnostic
    - scripts are helpers, not user-facing workflow contracts
```
