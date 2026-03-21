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
scope: current platform 的 frontend、backend、desktop、CLI、docs 與 repo-root orchestration 常用指令。
version: v2.4.0
last_updated: 2026-03-21
updated_by: codex
---

# Build Commands

本文件列出 current platform 目前可用的 repo-root orchestration 與 workspace 指令。
platform foundation 必須使用獨立於 legacy UI runtime 的 entrypoints。

!!! info "How to use this page"
    先決定你是在跑 `repo baseline`、單一 workspace、還是 docs build。
    不要每次都從頭到尾把所有命令跑一遍；依 touched area 挑最小必要集合。

## Command Map

| Situation | Open this section |
| --- | --- |
| 初次進 repo 或補齊基礎依賴 | `Current Baseline` |
| 要啟動 repo 層級協調流程 | `Repo Root Orchestration` |
| 只改單一 workspace | `Workspace Commands` |
| 要驗證 queue-backed local worker topology | `Local Worker Runtime Runbook` |
| 只改 docs / nav / frontmatter | `Docs` |

## Current Baseline

!!! tip "Run this first on a fresh checkout"

```bash
uv sync
julia --project=. -e 'using Pkg; Pkg.instantiate()'
./scripts/prepare_docs_locales.sh
```

## Repo Root Orchestration

!!! info "Use these when you want repo-level orchestration"

```bash
npm run platform:install
npm run platform:check
npm run platform:build
npm run platform:dev
npm run platform:stop
```

## Workspace Commands

=== "Frontend"

    ```bash
    npm install --prefix frontend
    npm run dev --prefix frontend
    npm run test --prefix frontend
    npm run lint --prefix frontend
    npm run typecheck --prefix frontend
    npm run build --prefix frontend
    ```

=== "Backend"

    ```bash
    cd backend && uv sync
    cd backend && uv run pytest
    cd backend && uv run uvicorn src.app.main:app --reload --port 8000
    ```

    `backend/` workspace 必須能單獨完成這些命令，不可依賴 repo-root `uv sync` 先偷裝 shared-core 依賴。

=== "Desktop"

    ```bash
    npm install --prefix desktop
    npm run dev --prefix desktop
    npm run lint --prefix desktop
    npm run build --prefix desktop
    ```

=== "CLI"

    ```bash
    uv run sc --help
    ```

## Local Worker Runtime Runbook

!!! important "Queue-backed local runtime is the verification baseline"
    worker isolation 驗證的正式 baseline 不是 app-local thread execution。
    你必須同時驗證 Redis、`sc-app`、`sc-worker-simulation`、`sc-worker-characterization` 是分離進程。

### Bring-up

| Step | Command / expectation |
| --- | --- |
| Redis requirement | 準備一個可連線的 local Redis，並設定 `SC_RQ_REDIS_URL`（preferred）或 `SC_REDIS_URL` |
| app process | `uv run sc-app` |
| simulation lane worker | `uv run sc-worker-simulation` |
| characterization lane worker | `uv run sc-worker-characterization` |
| optional repo helper | `npm run platform:dev` 或 `./scripts/platform_start.sh` 目前可協助拉起 frontend/backend shell，但不取代 Redis + worker bring-up |

!!! example "Minimal local runtime bring-up"
    ```bash
    export SC_RQ_REDIS_URL=redis://127.0.0.1:6379/0
    uv run sc-app
    uv run sc-worker-simulation
    uv run sc-worker-characterization
    ```

### Verification

| Check | Command / expected result |
| --- | --- |
| app health | `curl --fail http://127.0.0.1:8000/health` |
| session bootstrap | `curl --fail http://127.0.0.1:8000/session` |
| queue read model | `curl --fail 'http://127.0.0.1:8000/tasks?scope_filter=local&status_filter=active'` |
| task submit path | 透過 app workflow 或 `/tasks` submit mutation 建立一筆 local task，確認 queue row 與 detail 都以 `task_id` 回應 |
| worker summary | 驗證 queue response 的 `worker_summary[]` 同時回傳 simulation / characterization lane summary |
| process separation | 使用 `lsof -ti tcp:8000`、`pgrep -f sc-worker-simulation`、`pgrep -f sc-worker-characterization` 或等價工具確認 app 與兩個 worker 不是同一個 PID |

### Teardown

| Concern | Command / expectation |
| --- | --- |
| repo helper processes | `npm run platform:stop` 或 `./scripts/platform_stop.sh`（目前只處理 frontend/backend helper processes） |
| worker processes | 在各自 shell 中停止 `sc-worker-simulation`、`sc-worker-characterization`，或以 PID-aware tooling 關閉 |
| Redis | 依本機 Redis 管理方式停止；repo 目前沒有代管 Redis 的 stop script |

!!! tip "Helper scripts are partial helpers"
    `scripts/platform_start.sh`、`scripts/platform_stop.sh`、`scripts/platform_check.sh` 目前主要覆蓋 frontend/backend shell baseline。
    若你要驗證 isolated worker topology，仍必須額外確認 Redis 與兩條 worker lanes。

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
    - `npm run platform:install`
    - `npm run platform:check`
    - `npm run platform:build`
    - `npm run platform:dev`
    - `npm run platform:stop`
- **Python install**: `uv sync`
- **Julia install**: `julia --project=. -e 'using Pkg; Pkg.instantiate()'`
- **Frontend**:
    - `npm install --prefix frontend`
    - `npm run dev --prefix frontend`
    - `npm run test --prefix frontend`
    - `npm run lint --prefix frontend`
    - `npm run typecheck --prefix frontend`
    - `npm run build --prefix frontend`
- **Backend**:
    - `cd backend && uv sync`
    - `cd backend && uv run pytest`
    - `export SC_RQ_REDIS_URL=redis://127.0.0.1:6379/0`
    - `uv run sc-app`
    - `uv run sc-worker-simulation`
    - `uv run sc-worker-characterization`
    - `cd backend && uv run uvicorn src.app.main:app --reload --port 8000` (`uvicorn` 只適用於 backend-only API debug，不是 isolated worker topology 驗證 baseline)
- **Desktop**:
    - `npm install --prefix desktop`
    - `npm run dev --prefix desktop`
    - `npm run lint --prefix desktop`
    - `npm run build --prefix desktop`
- **CLI**: `uv run sc --help`
- **Docs**:
    - `uv run python scripts/check_docs_nav_routes.py --check-source`
    - `./scripts/prepare_docs_locales.sh`
    - `uv run --group dev zensical build -f zensical.toml`
    - `./scripts/build_docs_sites.sh`
    - `uv run python scripts/check_docs_nav_routes.py --check-built`
```
