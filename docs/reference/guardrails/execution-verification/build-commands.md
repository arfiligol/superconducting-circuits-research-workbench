---
aliases:
  - Build Commands
  - 執行指令
tags:
  - diataxis/reference
  - audience/contributor
  - sot/true
  - topic/execution
status: stable
owner: docs-team
audience: contributor
scope: current platform 的 app、backend、Julia Runner、desktop、docs 與 repo-root orchestration 常用指令。
version: v3.0.0
last_updated: 2026-05-28
updated_by: codex
---

# Build Commands

本文件列出 current platform 目前可用的 repo-root orchestration 與 workspace 指令。
platform foundation 必須使用 `app/` layout、Python Backend、Julia Runner 與 local filesystem TraceStore，不再啟動 Redis/RQ 或 CLI product surface。

!!! info "How to use this page"
    先決定你是在跑 `repo baseline`、單一 workspace、還是 docs build。
    不要每次都從頭到尾把所有命令跑一遍；依 touched area 挑最小必要集合。

## Command Map

| Situation | Open this section |
| --- | --- |
| 初次進 repo 或補齊基礎依賴 | `Current Baseline` |
| 要啟動 repo 層級協調流程 | `Repo Root Orchestration` |
| 只改單一 workspace | `Workspace Commands` |
| 要驗證 Runner-backed local runtime topology | `Local Runner Runtime Runbook` |
| 只改 docs / nav / frontmatter | `Docs` |

## Current Baseline

!!! tip "Run this first on a fresh checkout"

```bash
uv sync
cd app/backend && uv sync
npm install --prefix app/frontend
npm install --prefix app/desktop
julia --project=core/julia/SuperconductingCircuitsCore -e 'using Pkg; Pkg.instantiate()'
julia --project=core/julia/SuperconductingCircuitsRunner -e 'using Pkg; Pkg.instantiate()'
./scripts/prepare_docs_locales.sh
```

## Repo Root Orchestration

!!! info "Use these when you want repo-level orchestration"

```bash
npm run app:dev
npm run app:stop
```

## Workspace Commands

=== "Frontend"

    ```bash
    npm install --prefix app/frontend
    npm run dev --prefix app/frontend
    npm run test --prefix app/frontend
    npm run lint --prefix app/frontend
    npm run typecheck --prefix app/frontend
    npm run build --prefix app/frontend
    ```

=== "Backend"

    ```bash
    cd app/backend && uv sync
    cd app/backend && uv run pytest
    cd app/backend && uv run uvicorn src.app.main:app --reload --port 8000
    ```

    `app/backend/` workspace 必須能單獨完成這些命令，不可依賴 repo-root `uv sync` 先偷裝 runtime 依賴。

=== "Desktop"

    ```bash
    npm install --prefix app/desktop
    npm run dev --prefix app/desktop
    npm run lint --prefix app/desktop
    npm run build --prefix app/desktop
    ```

=== "Julia Core"

    ```bash
    julia --project=core/julia/SuperconductingCircuitsCore -e 'using Pkg; Pkg.test()'
    ```

=== "Julia Runner"

    ```bash
    julia --project=core/julia/SuperconductingCircuitsRunner -e 'using Pkg; Pkg.test()'
    ```

## Local Runner Runtime Runbook

!!! important "Runner-backed local runtime is the verification baseline"
    compute isolation 驗證的正式 baseline 不是 app-local thread execution。
    你必須同時驗證 frontend、Python Backend、Julia Runner 是分離進程，且不需要 Redis/RQ。

### Bring-up

| Step | Command / expectation |
| --- | --- |
| frontend process | `npm run dev --prefix app/frontend` |
| backend process | `cd app/backend && uv run uvicorn src.app.main:app --reload --port 8000` |
| runner process | `julia --project=core/julia/SuperconductingCircuitsRunner -e 'using SuperconductingCircuitsRunner; SuperconductingCircuitsRunner.main()'` |
| optional repo helper | `npm run app:dev` or `./scripts/dev/start_app.sh` starts frontend、backend、runner |

!!! example "Minimal local runtime bring-up"
    ```bash
    npm run dev --prefix app/frontend
    cd app/backend && uv run uvicorn src.app.main:app --reload --port 8000
    julia --project=core/julia/SuperconductingCircuitsRunner -e 'using SuperconductingCircuitsRunner; SuperconductingCircuitsRunner.main()'
    ```

### Verification

| Check | Command / expected result |
| --- | --- |
| app health | `curl --fail http://127.0.0.1:8000/health` |
| session bootstrap | `curl --fail http://127.0.0.1:8000/session` |
| task read model | `curl --fail 'http://127.0.0.1:8000/tasks?status_filter=active'` |
| task submit path | 透過 app workflow 或 `/tasks` submit mutation 建立一筆 local task，確認 task row 與 detail 都以 `task_id` 回應 |
| runner claim path | `POST /runner/v1/tasks/claim` can claim one queued task |
| publication path | completing a smoke task writes staging Zarr, validates manifest, and publishes canonical TraceStore batch |
| process separation | 使用 `lsof -ti tcp:8000`、frontend dev-server PID、runner PID 或等價工具確認 backend、frontend、runner 不是同一個 PID |

### Teardown

| Concern | Command / expectation |
| --- | --- |
| repo helper processes | `npm run app:stop` 或 `./scripts/dev/stop_app.sh` |
| runner process | 在 runner shell 中停止，或以 PID-aware tooling 關閉 |
| Redis/RQ | 不屬於 current local runtime |

!!! tip "Helper scripts manage app processes only"
    `scripts/dev/start_app.sh` 與 `scripts/dev/stop_app.sh` 管理 frontend、backend 與 runner。
    Redis/RQ 不再是本地 runtime prerequisite。

## Docs

!!! warning "Docs build always needs prepare first"
    若你改了 docs 內容、導覽或 frontmatter，先跑 `./scripts/prepare_docs_locales.sh`，再做 build / route check。

```bash
uv run python scripts/check_docs_nav_routes.py --check-source
./scripts/prepare_docs_locales.sh
uv run --group dev zensical build -f zensical.toml
./scripts/build_docs_sites.sh
uv run python scripts/check_docs_nav_routes.py --check-built
```

??? info "Why both source and built checks exist"
    `--check-source` 先驗證來源樹與 nav 是否一致。
    `--check-built` 再驗證最終 build 出來的路徑是否能被站點正確解析。

## Agent Rule { #agent-rule }

```markdown
## Run / Build Commands
- **Repo-root orchestration**:
    - `npm run app:dev`
    - `npm run app:stop`
- **Python install**: `uv sync`
- **Julia Core install**: `julia --project=core/julia/SuperconductingCircuitsCore -e 'using Pkg; Pkg.instantiate()'`
- **Julia Runner install**: `julia --project=core/julia/SuperconductingCircuitsRunner -e 'using Pkg; Pkg.instantiate()'`
- **Frontend**:
    - `npm install --prefix app/frontend`
    - `npm run dev --prefix app/frontend`
    - `npm run test --prefix app/frontend`
    - `npm run lint --prefix app/frontend`
    - `npm run typecheck --prefix app/frontend`
    - `npm run build --prefix app/frontend`
- **Backend**:
    - `cd app/backend && uv sync`
    - `cd app/backend && uv run pytest`
    - `cd app/backend && uv run uvicorn src.app.main:app --reload --port 8000`
- **Julia Runner**:
    - `julia --project=core/julia/SuperconductingCircuitsRunner -e 'using Pkg; Pkg.test()'`
- **Desktop**:
    - `npm install --prefix app/desktop`
    - `npm run dev --prefix app/desktop`
    - `npm run lint --prefix app/desktop`
    - `npm run build --prefix app/desktop`
- **Docs**:
    - `uv run python scripts/check_docs_nav_routes.py --check-source`
    - `./scripts/prepare_docs_locales.sh`
    - `uv run --group dev zensical build -f zensical.toml`
    - `./scripts/build_docs_sites.sh`
    - `uv run python scripts/check_docs_nav_routes.py --check-built`
```
