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
version: v3.4.0
last_updated: 2026-05-28
updated_by: codex
---

# Tech Stack

本 branch 的目標技術棧是 **Next.js + FastAPI + Electron + Julia Core + Julia Runner + local filesystem Zarr**。
Python Backend 是 control/data plane；Julia Runner 是 compute plane；Notebook 是 explicit research execution environment。

!!! info "How to use this page"
    這頁用來確認正式 baseline stack，不用來討論可選替代方案。若某個技術還沒被列進來，就不應被當成預設依賴。

See [Simulation Interface Boundaries](../../architecture/simulation-interface-boundaries.md) for the canonical Pluto / Python Notebook / Application Simulation Workbench split.

## Canonical Top-Level Surfaces

| Surface | Required interpretation |
| --- | --- |
| `app/backend/` | canonical Python Backend control/data plane |
| `app/frontend/` | canonical Next.js application surface |
| `app/desktop/` | canonical Electron shell surface |
| `core/julia/SuperconductingCircuitsCore/` | docs-defined Julia Core Authoring model, simulation helpers, and analysis helpers |
| `core/julia/SuperconductingCircuitsRunner/` | async Julia compute runner |
| `core/python/sc_data_contracts/` | optional shared Python schemas/contracts |
| `notebooks/pluto/` | Julia research cockpit |
| `notebooks/python/` | programmable data analysis, file inspection, Backend API inspection, migration, emergency analysis |
| `scripts/` | dev/build/test/maintenance helpers only |

!!! warning "Root `src/` is not the canonical umbrella"
    package-internal `src/` 可以存在於各 top-level surface 內部，
    但 root-level `src/` 不是 canonical topology 的主要容器。
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

## Interface Boundary Rules

| Surface | Role | May use the Julia scientific core directly? | May read local/exported/canonical data files directly? | May submit Backend tasks? |
| --- | --- | ---: | ---: | ---: |
| Pluto Notebook | Research-grade simulation cockpit | Yes | Yes | No |
| Python Notebook | Programmable data-analysis and inspection surface | No | Yes | Yes |
| Electron Application / Simulation Workbench | Productized workflow UI | No | Through Backend APIs | Yes |
| Python Backend | Control/data plane | No | Owns storage adapters | Owns task lifecycle |
| Julia Runner | Compute plane | Uses Julia Core through task execution | Writes staging packages | Claims tasks |

### Pluto Notebook

Pluto Notebook is the direct Julia Core research interface. It may directly use `SuperconductingCircuitsCore` through the docs-defined Julia Core Authoring model, compiler path, simulation helpers, sweep helpers, and Julia analysis helpers.

It is not a Backend task submitter in the platform architecture. If a Pluto result should become official platform data, it must go through an explicit import/publication path defined separately.

### Python Notebook

Python Notebook is a programmable data-analysis and inspection surface. It may call Python Backend APIs for datasets, tasks, traces, result views, migration, debugging, and emergency analysis.

It may directly read local Zarr, exported data, CSV/raw files, and canonical TraceStore files for ad hoc analysis. It must use Backend contracts for platform state changes, including task creation, metadata mutation, TraceStore publication, result registration, provenance, and indexing.

It must not directly call `SuperconductingCircuitsCore` or use JuliaCall as a normal simulation compute path. Scientific simulation compute belongs to Pluto direct execution or Julia Runner async execution.

### Application Simulation Workbench

Application Simulation Workbench is a first-class product surface. It is not replaced by Pluto.

All Application-triggered simulation must be submitted as persisted Backend tasks and executed asynchronously by Julia Runner.

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
- primary surfaces include Dashboard, Dataset, Simulation Workbench, Analysis Workbench, Task / Execution Center, Data Ingestion, Raw Data / Trace Browser, and Design Assets
- Application Simulation Workbench is a first-class product surface, but it must submit async tasks rather than owning compute logic
- Application Analysis Workbench is a first-class product surface, but it must submit async tasks rather than owning compute logic

### Desktop

- Electron 可作為 desktop shell
- Electron main/preload 層只處理桌面能力、視窗生命週期、安全 IPC 與 runtime supervisor
- 不可把業務流程塞進 Electron main process
- desktop 包裝不改變 canonical frontend/backend/runner 邊界
- desktop local mode starts frontend, Python Backend, and Julia Runner
- desktop local mode must not start a separate queue service

### Backend

- FastAPI + Pydantic
- 服務層與資料存取分離
- API 層只做 I/O、驗證、mapping、授權與回應
- multi-user app authorization baseline 採 `Casbin`
- `JWT` / refresh token 負責 authentication；capabilities 與 allowed actions 由 backend authorization engine materialize

### Local Runtime Backbone

- frontend process: `npm run dev --prefix app/frontend`
- backend process: `cd app/backend && uv run uvicorn src.app.main:app --reload --port 8000`
- runner process: `julia --project=core/julia/SuperconductingCircuitsRunner -e 'using SuperconductingCircuitsRunner; run_polling_runner(backend_url="http://127.0.0.1:8000")'`
- task claiming is DB-backed through the Python Backend runner API
- local staging uses filesystem Zarr under `data/staging/tasks/<task_id>/`
- official numeric authority is Python Backend-managed TraceStore under `data/trace_store/`
- Local Mode is not a shell-only product mode. A usable Local Mode means the frontend can reach the Python Backend and the Python Backend can coordinate Julia Runner execution. UI-only shell previews are developer tools, not product runtime modes.

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

- `SuperconductingCircuitsCore` owns the docs-defined Julia Core authoring model: reusable components, endpoints, Circuit Plan, validation, compiler concepts, `JosephsonCompiledCircuit`, simulation helpers, and analysis helpers.
- `SuperconductingCircuitsRunner` calls Julia Core for deterministic task execution and owns task polling/claiming, dispatch, local Zarr staging, manifest writing, progress/heartbeat/complete/fail reporting.
- Runner adapters must not create a separate circuit construction path.
- Runner adapters must not preserve outdated Core APIs as fallback paths.
- Julia Runner does not write formal metadata DB records
- Python Backend validates Runner manifests and publishes result Zarr into official TraceStore

## No Fake-First Compute Policy

The project does not use fake Runner compute to make product workflows appear complete.

- Real task kinds execute real Julia Core / JosephsonCircuits / analysis logic.
- Unimplemented task kinds fail clearly.
- Test fixtures stay inside tests.
- Production dispatch must not call fixture writers.
- AI agents must not add smoke, fake, or dummy task kinds to satisfy tests.

### Removed Surface Notes

- root `backend/`, `frontend/`, and `desktop/` must not exist as active surfaces after relocation to `app/`
- root command workflow, legacy UI code, and retired root runtime-worker path names are removed from active package discovery
- Any mention of historical `src/worker` paths refers to retired legacy code, not the active Julia Runner role.
- root `src/` must not be re-legitimized as canonical target topology

## Forbidden Architecture Regressions

The following changes require a new SoT decision before implementation:

- Reintroducing Backend task submission into the Pluto Notebook role.
- Reintroducing Python Notebook as a Julia Core / JuliaCall compute surface.
- Removing Application Simulation Workbench as a first-class product surface.
- Removing Application Analysis Workbench as a first-class product surface.
- Running heavy simulation in Python Backend request threads.
- Reintroducing queue-service or standalone runtime-wall product metaphors for task execution.
- Treating fixture output as a product Runner task.
- Reintroducing a user-facing CLI product surface.
- Reintroducing NiceGUI or any retired Python UI runtime.
- Reintroducing Redis/RQ as the default local runtime queue.
- Recreating root-level `backend/`, `frontend/`, `desktop/`, `cli/`, or historical `src/worker` legacy paths as active architecture surfaces.

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
  - remote object storage requires a storage-backend SoT before it becomes part of the product contract

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
    - docs-defined Julia Core authoring model: reusable components, endpoints, Circuit Plan, validation, compiler concepts, `JosephsonCompiledCircuit`, simulation helpers, and analysis helpers
- **Julia Runner**:
    - `core/julia/SuperconductingCircuitsRunner/`
    - calls Julia Core for deterministic task execution
    - Runner adapters must not create a separate circuit construction path or preserve outdated Core APIs as fallback paths
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
    - Local Mode is not a shell-only product mode; UI-only shell previews are developer tools, not product runtime modes.
- **Interface boundaries**:
    - Pluto Notebook is the direct Julia Core research interface.
    - Backend task submission is outside the Pluto Notebook role.
    - Python Notebook is a programmable data-analysis and inspection surface; it may directly read data files, but platform state changes must go through Backend contracts.
    - Python Notebook must not directly call Julia Core or use JuliaCall as normal simulation compute.
    - Application Simulation Workbench and Analysis Workbench are first-class and submit persisted async tasks through Python Backend and Julia Runner.
    - Python Backend owns task lifecycle, metadata, publication, TraceStore APIs, and result view APIs.
    - Julia Runner owns async compute execution and local Zarr staging.
- **Scripts**:
    - `scripts/dev/`
    - `scripts/build/`
    - `scripts/test/`
    - `scripts/maintenance/`
    - no active command-line product surface
- **Topology**:
    - canonical architecture boundaries are `app/backend/`, `app/frontend/`, `app/desktop/`, `core/julia/`, `core/python/`, `notebooks/`, `scripts/`, and `docs/`
    - root-level `backend/`, `frontend/`, `desktop/`, `cli/`, and `src/` are not canonical product surfaces
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
