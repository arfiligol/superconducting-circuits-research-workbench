---
aliases:
  - Tech Stack
  - 技術堆疊
tags:
  - diataxis/reference
  - audience/contributor
  - sot/true
  - topic/tech-stack
status: stable
owner: docs-team
audience: contributor
scope: current platform 的技術選型、desktop 包裝方向與共享工具規範。
version: v2.5.0
last_updated: 2026-03-25
updated_by: codex
---

# Tech Stack

本 branch 的目標技術棧是 **Next.js + FastAPI + CLI + Electron + RQ/Redis worker runtime + Julia simulation core**。
原則上，UI、API、CLI 必須共用同一套核心定義與驗證規則，不再把舊版 UI 作為主要實作方向。

!!! info "How to use this page"
    這頁用來確認正式 baseline stack，不用來討論可選替代方案。若某個技術還沒被列進來，就不應被當成預設依賴。

## Canonical Top-Level Surfaces

| Surface | Required interpretation |
| --- | --- |
| `backend/` | canonical app/backend service surface |
| `frontend/` | canonical web app surface |
| `core/` | canonical shared scientific/core surface |
| `cli/` | canonical standalone CLI surface |
| `desktop/` | canonical desktop shell surface |
| `legacy/` | archived / migration residue container；不是新功能預設落點 |

!!! warning "Root `src/` is not the future umbrella"
    package-internal `src/` 可以存在於各 top-level surface 內部，
    但 root-level `src/` 不再是未來 canonical topology 的主要容器。
    `src/app/`、`src/worker/` 若仍存在，都應按 migration residue 理解。

## Stack Map

| layer | baseline |
| --- | --- |
| Frontend | Next.js App Router + React 19 + TypeScript |
| Backend | FastAPI + Pydantic + SQLModel/SQLAlchemy + Casbin |
| CLI | Typer |
| Local runtime queue | `rq` + `redis` |
| Local worker lanes | `sc-worker-simulation`, `sc-worker-characterization` |
| Scientific core | JosephsonCircuits.jl via juliacall |
| Desktop shell | Electron |

## Shared Languages

### Python

| 工具 | 用途 |
| --- | --- |
| `uv` | 依賴與虛擬環境管理 |
| `fastapi` | API framework |
| `pydantic` | schema / validation |
| `sqlmodel`, `sqlalchemy` | metadata persistence |
| `casbin` | app backend authorization baseline |
| `typer` | CLI framework |
| `rq`, `redis` | local queue-backed worker runtime |
| `numpy`, `pandas`, `scipy`, `lmfit`, `scikit-rf` | 數值、分析、擬合 |
| `plotly`, `schemdraw` | 視覺化與電路圖生成 |
| `juliacall` | Python ↔ Julia bridge |
| `rich` | logging 與 CLI 輸出 |
| `ruff`, `basedpyright`, `pytest` | lint / type / test |
| `zarr` | numeric trace storage |

### TypeScript / JavaScript

| 工具 | 用途 |
| --- | --- |
| `Next.js` (App Router) | frontend framework |
| `React 19` | UI runtime |
| `TypeScript` | frontend language |
| `Tailwind CSS v4` | styling |
| `Radix UI` + `shadcn/ui` | UI primitives 與 app components |
| `next-themes` | theme switching |
| `SWR` | server-state fetching and cache |
| `react-hook-form` + `zod` | form state and validation |
| `lucide-react` | icons |
| `Playwright`, `Vitest` | frontend test stack |
| `Electron` | desktop shell for local app packaging |

### Julia

| 工具 | 用途 |
| --- | --- |
| `juliaup` | Julia version management |
| `JosephsonCircuits.jl` | 核心電路模擬引擎 |

## Module Direction

### Frontend

- Next.js App Router
- TypeScript strict mode
- component system based on shadcn/ui + Radix
- 不在 component 內直接實作業務流程或硬編碼 API contract

### Desktop

- Electron 可作為 desktop shell
- Electron main/preload 層只處理桌面能力、視窗生命週期、安全 IPC 與 runtime supervisor
- 不可把業務流程塞進 Electron main process
- desktop 包裝不改變 canonical frontend/backend/CLI 邊界
- desktop runtime profile 採：
  - `local_managed`：監管本地 `redis`、`sc-app`、workers sidecars
  - `remote_server`：只連 remote backend target，不啟動本地 heavy runtime

### Backend

- FastAPI + Pydantic
- 服務層與資料存取分離
- API 層只做 I/O、驗證、mapping、授權與回應
- multi-user app authorization baseline 採 `Casbin`
- `JWT` / refresh token 負責 authentication；capabilities 與 allowed actions 由 backend authorization engine materialize

### Local Runtime Backbone

- app process: `uv run sc-app`
- simulation lane worker: `uv run sc-worker-simulation`
- characterization lane worker: `uv run sc-worker-characterization`
- queue backend: `rq` + `redis`
- desktop-managed local runtime 需把 `redis` 視為 app-supervised private sidecar，而不是使用者自行維護的外部必要前提
- Redis URL: `SC_RQ_REDIS_URL`（preferred） / `SC_REDIS_URL`（fallback alias）
- queue names: `SC_SIMULATION_QUEUE_NAME`、`SC_CHARACTERIZATION_QUEUE_NAME`
- lane mapping:
  - `simulation` + `post_processing` -> simulation lane
  - `characterization` -> characterization lane

!!! warning "Independent workers are the active local runtime baseline"
    local heavy execution 不得由 app process 直接 in-process 執行。
    app submit path 的正式角色是建立 persisted task 並 enqueue 到 lane queue，不是用 background thread 直接跑 solver。

!!! warning "Do not bypass the backend authorization path"
    frontend、desktop、CLI 都不應自行重建 app authorization matrix。多使用者 app 權限的 baseline 在 backend，並由 backend materialize `capabilities` 與 `allowed_actions`。

### CLI

- Typer 作為主要命令列框架
- CLI 直接呼叫 CLI-local abstractions、app-facing shared services 或 top-level `core/` concern owner，而非複製 API 或 UI 邏輯
- 所有關鍵工作流都需要可由 CLI 觸發

### Scientific Core

- `JosephsonCircuits.jl` 仍是 simulation source of truth
- circuit definition 應能同時餵給 simulation、schemdraw、analysis
- characterization / analysis 對 trace source 保持 source-agnostic
- canonical folder 是 top-level `core/`

### Migration Residue Notes

- `src/app/` 應視為 archived legacy UI residue，最終目標是 `legacy/legacy_nicegui_archived/`
- `src/worker/` 應視為 transition residue / pending backend worker-runtime redesign area
- 上述 root `src/` 內容都不應被重新合法化成 canonical target topology

## Storage Direction

- metadata DB：
  - current baseline: `SQLite`
  - service target: `PostgreSQL`
  - schema versioning baseline: `Alembic`
  - detailed migration/version authority: [App / Backend / Circuit Definitions](../../app/backend/circuit-definitions.md)
- numeric traces：
  - baseline: `Zarr`
  - backend abstraction required for future extension

??? note "Why alternatives are not listed"
    這頁只記錄正式 baseline，不列出所有曾考慮過的框架。若之後真的更換 stack，應先更新這頁，再讓實作跟上。

## Dependency Management

- Python: `pyproject.toml` + `uv.lock`
- Frontend: `frontend/package.json` + lockfile
- Julia: `Project.toml` / `Manifest.toml`

### Python Workspace Ownership

- canonical core package root 是 top-level `core/`
- `core/pyproject.toml` 提供 shared-core dependency
- `backend/` 的獨立 `uv sync` 必須能靠 `backend/pyproject.toml` 加上目前 core implementation 的 transitive dependencies 完整啟動
- shared-core 使用到的 persistence / analysis / visualization 依賴，不可只宣告在 repo root；否則 `cd backend && uv sync` 會缺 package

## Agent Rule { #agent-rule }

```markdown
## Tech Stack
- **Frontend**:
    - Next.js App Router
    - React 19
    - TypeScript
    - Tailwind CSS v4
    - Radix UI + shadcn/ui
    - next-themes
    - SWR
    - react-hook-form + zod
    - Electron is allowed as the desktop shell around the frontend
- **Backend**:
    - FastAPI
    - Pydantic
    - SQLModel / SQLAlchemy
    - Casbin as the backend authorization baseline for the multi-user app
    - Rich-compatible logging
- **Local runtime backbone**:
    - `rq`
    - `redis`
    - `uv run sc-app`
    - `uv run sc-worker-simulation`
    - `uv run sc-worker-characterization`
    - desktop local-managed profile supervises Redis + app + worker sidecars; remote-server profile does not start local heavy runtime
- **CLI**:
    - Typer
    - must remain first-class, not a second-tier wrapper
- **Scientific core**:
    - JosephsonCircuits.jl via juliacall
    - plotly + schemdraw for visualization output
- **Topology**:
    - canonical architecture boundaries are top-level `backend/`, `frontend/`, `core/`, `cli/`, `desktop/`, `legacy/`
    - root-level `src/` is not the future umbrella
- **Quality tools**:
    - Ruff
    - BasedPyright
    - pytest
    - Vitest / Playwright when frontend exists
- **Storage direction**:
    - metadata DB: SQLite now, PostgreSQL target
    - metadata DB schema versioning: Alembic; detailed rules live in App / Backend / Circuit Definitions
    - numeric trace store: Zarr
- New UI work should target Next.js, not the legacy UI layer.
- Desktop packaging should use Electron around the frontend instead of reviving legacy-UI-native desktop assumptions.
```
