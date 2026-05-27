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
scope: current platform 的 Notebook/Application/Julia Runner 技術選型與工具規範。
version: v3.1.0
last_updated: 2026-05-28
updated_by: codex
---

# Tech Stack

本 branch 的目標技術棧是 **Next.js + FastAPI + Electron + Julia Core + Julia Runner + local filesystem Zarr**。
Python Backend 是 control/data plane；Julia Runner 是 compute plane；Notebook 是 explicit research execution environment。

!!! info "How to use this page"
    這頁用來確認正式 baseline stack，不用來討論可選替代方案。若某個技術還沒被列進來，就不應被當成預設依賴。

## Canonical Top-Level Surfaces

| Surface | Required interpretation |
| --- | --- |
| `app/backend/` | canonical Python Backend control/data plane |
| `app/frontend/` | canonical Next.js application surface |
| `app/desktop/` | canonical Electron shell surface |
| `core/julia/SuperconductingCircuitsCore/` | reusable Julia circuit construction / simulation / analysis library |
| `core/julia/SuperconductingCircuitsRunner/` | async Julia compute runner |
| `core/python/sc_data_contracts/` | optional shared Python schemas/contracts |
| `notebooks/pluto/` | Julia research cockpit |
| `notebooks/python/` | backend/data API inspection, migration, emergency analysis |
| `scripts/` | dev/build/test/maintenance helpers only |

!!! warning "Root `src/` is not the future umbrella"
    package-internal `src/` 可以存在於各 top-level surface 內部，
    但 root-level `src/` 不再是未來 canonical topology 的主要容器。
    root-level runtime or app code must not be recreated there.

## Stack Map

| layer | baseline |
| --- | --- |
| Frontend | Next.js App Router + React 19 + TypeScript |
| Backend | FastAPI + Pydantic + SQLAlchemy/Alembic + NumPy + Zarr |
| Compute runner | Julia + HTTP.jl + JSON3.jl + StructTypes.jl + Zarr.jl |
| Local runtime | frontend + Python Backend + Julia Runner |
| Scientific core | Julia package under `core/julia/SuperconductingCircuitsCore/` |
| Desktop shell | Electron |

## Shared Languages

### Python

| 工具 | 用途 |
| --- | --- |
| `uv` | 依賴與虛擬環境管理 |
| `fastapi` | API framework |
| `pydantic` | schema / validation |
| `sqlalchemy`, `alembic` | metadata persistence and migration |
| `pydantic-settings` | backend settings |
| `numpy`, `zarr`, `fsspec` | TraceStore validation/publication |
| `rich` | developer-facing logging output when useful |
| `ruff`, `basedpyright`, `pytest` | lint / type / test |

Application backend dependencies must stay focused on the control/data plane.
Do not add legacy UI runtimes, queue-service clients, command-line product packages, in-process Julia bridges, or notebook-only analysis/plotting libraries unless a new SoT explicitly reintroduces them for the backend.
Notebook-specific Python dependencies belong in `notebooks/python/pyproject.toml` or a notebook dependency group, not in the application backend.

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
| `JosephsonCircuits.jl` | 核心電路模擬引擎 inside Julia Core/Runner |
| `HTTP.jl` | Runner client for backend task protocol |
| `JSON3.jl`, `StructTypes.jl` | Runner task / manifest contracts |
| `Zarr.jl` | local filesystem Zarr v2 staging writer |
| `DataFrames.jl` | tabular summaries when needed |

## Module Direction

### Frontend

- Next.js App Router
- TypeScript strict mode
- component system based on shadcn/ui + Radix
- 不在 component 內直接實作業務流程或硬編碼 API contract
- primary surfaces are Dashboard, Dataset, Data Ingestion, Raw Data / Trace Browser, and Tasks / Result Browser
- simulation/analysis workbench pages must not remain exposed as primary product navigation

### Desktop

- Electron 可作為 desktop shell
- Electron main/preload 層只處理桌面能力、視窗生命週期、安全 IPC 與 runtime supervisor
- 不可把業務流程塞進 Electron main process
- desktop 包裝不改變 canonical frontend/backend/runner 邊界
- desktop local mode starts frontend, Python Backend, and Julia Runner
- desktop local mode must not start a separate queue worker service

### Backend

- FastAPI + Pydantic
- 服務層與資料存取分離
- API 層只做 I/O、驗證、mapping、授權與回應
- multi-user app authorization baseline 採 `Casbin`
- `JWT` / refresh token 負責 authentication；capabilities 與 allowed actions 由 backend authorization engine materialize

### Local Runtime Backbone

- frontend process: `npm run dev --prefix app/frontend`
- backend process: `cd app/backend && uv run uvicorn src.app.main:app --reload --port 8000`
- runner process: `julia --project=core/julia/SuperconductingCircuitsRunner -e 'using SuperconductingCircuitsRunner; SuperconductingCircuitsRunner.main()'`
- task claiming is DB-backed through the Python Backend runner API
- local staging uses filesystem Zarr under `data/staging/tasks/<task_id>/`
- official numeric authority is Python Backend-managed TraceStore under `data/trace_store/`

!!! warning "Runner is the active local compute baseline"
    local heavy execution must not run in the Python Backend process.
    The app submit path creates persisted tasks and the Julia Runner claims them asynchronously through the backend protocol.

!!! warning "Do not bypass the backend authorization path"
    frontend、desktop、notebooks 都不應自行重建 app authorization matrix。多使用者 app 權限的 baseline 在 backend，並由 backend materialize `capabilities` 與 `allowed_actions`。

### Scripts

- No active command-line product surface.
- `scripts/` may contain dev/build/test/maintenance helpers only.
- Scripts are not user-facing workflow contracts and must not own business logic.

### Scientific Core

- `SuperconductingCircuitsCore` owns reusable circuit construction, delayed lowering, JosephsonCircuits wrappers, sweep helpers, and analysis helpers
- `SuperconductingCircuitsRunner` owns task polling/claiming, execution dispatch, local Zarr staging, manifest writing, progress/heartbeat/complete/fail reporting
- Julia Runner does not write formal metadata DB records
- Python Backend validates Runner manifests and publishes result Zarr into official TraceStore

### Removed Surface Notes

- root `backend/`, `frontend/`, and `desktop/` must not exist as active surfaces after relocation to `app/`
- root command workflow, legacy UI code, and root runtime-worker code are removed from active package discovery
- root `src/` must not be re-legitimized as canonical target topology

## Storage Direction

- metadata DB：
  - current baseline: `SQLite`
  - service target: `PostgreSQL`
  - schema versioning baseline: `Alembic`
  - detailed migration/version authority: [App / Backend / Circuit Definitions](../../app/backend/circuit-definitions.md)
- numeric traces:
  - Runner staging baseline: local filesystem `Zarr v2`
  - official TraceStore baseline: backend-managed local filesystem `Zarr`
  - complex arrays use real/imag arrays, never cross-language complex dtype assumptions
  - S3-compatible storage remains a future Python Backend storage backend concern

??? note "Why alternatives are not listed"
    這頁只記錄正式 baseline，不列出所有曾考慮過的框架。若之後真的更換 stack，應先更新這頁，再讓實作跟上。

## Dependency Management

- Python: `pyproject.toml` + `uv.lock`
- Frontend: `app/frontend/package.json` + lockfile
- Desktop: `app/desktop/package.json` + lockfile
- Julia Core: `core/julia/SuperconductingCircuitsCore/Project.toml`
- Julia Runner: `core/julia/SuperconductingCircuitsRunner/Project.toml`

### Python Workspace Ownership

- Python Backend package root is `app/backend/`
- Python notebook dependencies belong to `notebooks/python/`
- root `pyproject.toml` is a lightweight workspace/dev project or can cease being an installable application package

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
    - Pydantic Settings
    - SQLAlchemy
    - Alembic
    - NumPy
    - Zarr
    - fsspec
- **Julia Core**:
    - `core/julia/SuperconductingCircuitsCore/`
    - reusable circuit construction, simulation, sweep, and analysis library
- **Julia Runner**:
    - `core/julia/SuperconductingCircuitsRunner/`
    - HTTP.jl
    - JSON3.jl
    - StructTypes.jl
    - Zarr.jl
    - DataFrames.jl
- **Local runtime backbone**:
    - frontend
    - Python Backend
    - Julia Runner
    - no separate queue service
- **Scripts**:
    - `scripts/dev/`
    - `scripts/build/`
    - `scripts/test/`
    - `scripts/maintenance/`
    - no active command-line product surface
- **Topology**:
    - canonical architecture boundaries are `app/backend/`, `app/frontend/`, `app/desktop/`, `core/julia/`, `core/python/`, `notebooks/`, `scripts/`, and `docs/`
    - root-level `backend/`, `frontend/`, `desktop/`, `cli/`, and `src/` are not future canonical surfaces
- **Quality tools**:
    - Ruff
    - BasedPyright
    - pytest
    - Vitest / Playwright when frontend exists
- **Storage direction**:
    - metadata DB: SQLite local, PostgreSQL target
    - metadata DB schema versioning: Alembic
    - Runner staging: local filesystem Zarr v2
    - official TraceStore: Python Backend-managed Zarr
- New UI work should target Next.js, not the legacy UI layer.
- Desktop packaging should use Electron around frontend + Python Backend + Julia Runner.
```
