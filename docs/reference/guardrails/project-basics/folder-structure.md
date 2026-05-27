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
scope: 定義 current platform 的 app/core/notebooks/scripts/docs canonical surfaces 與 migration residue 邊界。
version: v4.1.0
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
├── Plans/                     # active multi-agent planning artifacts; not long-term SoT
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
| Electron main / preload / packaging | `app/desktop/` |
| API router, service, persistence | `app/backend/` |
| Julia circuit construction / simulation / analysis library | `core/julia/SuperconductingCircuitsCore/` |
| Julia async compute runner | `core/julia/SuperconductingCircuitsRunner/` |
| Python data contract schemas if needed | `core/python/sc_data_contracts/` |
| Pluto notebook | `notebooks/pluto/` |
| Python backend/data notebook | `notebooks/python/` |
| dev/build/test/maintenance helper | `scripts/dev/`, `scripts/build/`, `scripts/test/`, `scripts/maintenance/` |
| multi-agent planning, prompt handoff, test backlog | `Plans/`，由 Planning & Reviewing Agent 建立/退休/刪除 |
| archived legacy UI / command workflow / runtime residue | `docs/archive/` as inert text only, or delete if not needed |
| retired root worker runtime residue | 不屬於 target layout；不得新增或恢復 |
| committed OpenAPI contract snapshot | root `openapi.json` |

!!! warning "Do not reintroduce old root package surfaces"
    這次決策不是把 `app/backend/`、`app/frontend/`、`app/desktop/` 再拆回 root `backend/`、`frontend/`、`desktop/`。
    也不要讓 root `cli/` 或 `src/` 重新變成 active entrypoint。

## Removed Root Surfaces

| Removed location | Current rule |
| --- | --- |
| `backend/` | must not exist as an active root surface |
| `frontend/` | must not exist as an active root surface |
| `desktop/` | must not exist as an active root surface |
| `cli/` | must not exist as an active product surface |
| `src/app/` | must not exist as active UI/runtime code |
| root worker runtime folder | must not exist as active runtime code |

## Planning Artifacts

`Plans/` 是協作型 delivery artifacts 的暫存與交接區。
它可以被 commit 以支援多 agents 共享同一份 plan/prompt/test backlog，但它不是長期產品 SoT。

| Concern | Rule |
| --- | --- |
| Owner | Planning & Reviewing Agent |
| Purpose | active plan、lane prompts、test backlog、review/fixup coordination |
| Not for | 產品規格、長期 architecture contract、完成後仍有效的操作手冊 |
| Promotion | 長期決策必須移到 `docs/reference/**` |
| Cleanup | merge/cleanup pass 必須刪除、退休或明確保留 active backlog |

若 `Plans/` 內容與 `docs/reference/**` 衝突，以 `docs/reference/**` 為準；Planning & Reviewing Agent 必須更新 plan 或回交 Documentation Agent。

## Related Blueprints

- backend 的責任分層與模組邊界，參見 [Backend Architecture](./backend-architecture.md)
- shared core 的 canonical contract 與 adopter boundary，參見 [Core Reference](../../core/index.md)

## Dependency Direction

1. `app/frontend/` 依賴 API contract，不直接依賴 backend internals
2. `app/desktop/` 依賴 frontend build、backend/runner process supervision 與受控 IPC，不承載業務規則
3. `app/backend/` API 層依賴 services/domain/infrastructure，不執行 heavy compute
4. `core/julia/SuperconductingCircuitsRunner/` 依賴 backend runner protocol，不擁有正式 metadata DB
5. `core/julia/SuperconductingCircuitsCore/` 不依賴 FastAPI、Next.js、Electron 或 Python Backend internals
6. `scripts/` 不得成為 user-facing command-line product surface
7. root `backend/`、`frontend/`、`desktop/`、`cli/`、`src/` residues 不得被重新解讀成正式 architecture boundary

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
- **No user-facing command-line product surface**; helper automation goes to `scripts/dev/`, `scripts/build/`, `scripts/test/`, or `scripts/maintenance/`.
- **Archived legacy UI / command workflow / old runtime residue** should be deleted from active package discovery or moved to `docs/archive/` as inert text.
- **Root worker runtime folder** must not be recreated as a runtime surface.
- **Docs and guardrails** go to `docs/`; `docs/docs_zhtw/` is generated staging, not a primary edit source.
- **Plans** go to `Plans/` only as active multi-agent coordination artifacts; Planning & Reviewing Agents own creation and cleanup, and long-term decisions must move to `docs/reference/**`.
- **Committed OpenAPI snapshot** stays at repo root as `openapi.json` for contract-sync verification.
- Root-level `backend/`, `frontend/`, `desktop/`, `cli/`, and `src/` are not future canonical surfaces.
- Dependency direction:
    - frontend depends on API contracts, not backend internals
    - desktop depends on frontend outputs, backend/runner process supervision, and secure IPC, not business logic ownership
    - backend API layer depends inward on services/domain/infrastructure and must not run heavy compute
    - Julia Runner owns compute execution and staging result packages, not formal metadata DB records
    - Julia Core must stay framework-agnostic
    - scripts are helpers, not user-facing workflow contracts
```
