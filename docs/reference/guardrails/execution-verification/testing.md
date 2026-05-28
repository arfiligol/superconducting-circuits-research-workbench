---
aliases:
  - Testing
  - 測試規範
tags:
  - diataxis/reference
  - audience/contributor
  - sot/true
  - topic/execution
status: stable
owner: docs-team
audience: contributor
scope: current platform 的 app/backend、app/frontend、Julia Runner、desktop 與 docs 測試規範。
version: v3.1.0
last_updated: 2026-05-27
updated_by: codex
---

# Testing

本頁定義 current platform 的測試入口與最低測試期待。

!!! info "How to read this page"
    先判斷你碰的是 `root orchestration`、`app/backend`、`app/frontend`、`Julia Runner`、`desktop` 還是 `docs`。
    這頁回答的是「最低該跑什麼」，不是完整測試設計本身。

## Test Map

| Area | Minimum baseline |
| --- | --- |
| Foundation workspace | backend pytest + frontend unit + desktop lint + runner tests |
| Backend | `cd app/backend && uv run pytest` |
| Julia Core / Runner | `Pkg.test()` per Julia package |
| Frontend | unit tests，必要時 E2E |
| Desktop foundation | lint + build |
| Docs | source check + build + built-route check |

## Foundation Workspace Check

```bash
cd app/backend && uv run pytest
npm run test --prefix app/frontend
npm run lint --prefix app/desktop
julia --project=core/julia/SuperconductingCircuitsRunner -e 'using Pkg; Pkg.test()'
```

## Backend

```bash
cd app/backend && uv run pytest
```

Backend tests for Runner publication must cover create task, claim task, heartbeat/progress, complete with small staging Zarr manifest, canonical TraceStore publication, TraceRecord creation, trace slice read, invalid manifest rejection, and path traversal rejection.

## Julia Core / Runner

```bash
julia --project=core/julia/SuperconductingCircuitsCore -e 'using Pkg; Pkg.test()'
julia --project=core/julia/SuperconductingCircuitsRunner -e 'using Pkg; Pkg.test()'
```

Runner tests must cover JSON task contract parsing, manifest generation, local Zarr write with small real/imag trace, manifest path/shape validation helpers, and fake `julia_runner_smoke` dispatch.

## Frontend

=== "Unit"

    ```bash
    npm run test --prefix app/frontend
    ```

=== "E2E"

    ```bash
    npm run test:e2e --prefix app/frontend
    ```

foundation workflow 目前只要求 deterministic unit tests。
不要用 placeholder E2E 假裝覆蓋尚未遷移的真實 workflow。

!!! warning "Frontend review needs real browser evidence"
    若交付內容改動 shell、layout、header/sidebar behavior、dialog/drawer interaction、auth entry、或其他明顯 user-visible workflow，
    Review 不得只看 code diff 或 unit test。
    必須至少使用 Playwright 走一次實際流程，並透過 screenshot 或等價視覺證據檢查 UI 是否跑掉。

## Desktop Foundation

```bash
npm run lint --prefix app/desktop
npm run build --prefix app/desktop
```

## Docs

!!! warning "Docs changes must always verify routes"
    只 build 成功還不夠。
    docs 變更必須同時通過 source-side nav 檢查與 built-route 檢查。

```bash
uv run python scripts/check_docs_nav_routes.py --check-source
./scripts/prepare_docs_locales.sh
uv run --group dev zensical build -f zensical.toml
./scripts/build_docs_sites.sh
uv run python scripts/check_docs_nav_routes.py --check-built
```

## Policy

| Rule | Meaning |
| --- | --- |
| 關鍵 workflow 至少要有一條可重現測試路徑 | 不接受只靠手動驗證的核心交付 |
| backend service 與 Runner publication workflow 優先寫 deterministic tests | 先確保 task lifecycle 與 TraceStore publication |
| frontend component 與互動流程分別用 unit / E2E 覆蓋 | 不要用單一測試型態硬扛全部責任 |
| Frontend merge review 需要真實 UI 證據 | shell / layout / overlay / auth entry 之類的 user-visible 交付，至少要用 Playwright smoke + screenshot 檢查一次 |
| docs route 驗證必須用 canonical directory routes | 不依賴來源 `.md` 路徑推測 build 結果 |

!!! tip "Good default"
    若你不確定這輪該補哪種測試，先選最靠近 changed surface 的 deterministic test；
    只有當 user-visible workflow 真正跨過多個 surface 時，再補 integration / E2E。

## Agent Rule { #agent-rule }

```markdown
## Testing Commands
- **Foundation workspace check**:
    - `cd app/backend && uv run pytest`
    - `npm run test --prefix app/frontend`
    - `npm run lint --prefix app/desktop`
    - `julia --project=core/julia/SuperconductingCircuitsRunner -e 'using Pkg; Pkg.test()'`
- **Backend/core tests**:
    - `cd app/backend && uv run pytest`
    - `julia --project=core/julia/SuperconductingCircuitsCore -e 'using Pkg; Pkg.test()'`
    - `julia --project=core/julia/SuperconductingCircuitsRunner -e 'using Pkg; Pkg.test()'`
- **Frontend unit tests**: `npm run test --prefix app/frontend`
- **Frontend E2E tests**: `npm run test:e2e --prefix app/frontend`
- For user-visible frontend changes, use Playwright-based smoke verification and screenshot or equivalent visual evidence when practical.
- **Desktop foundation checks**:
    - `npm run lint --prefix app/desktop`
    - `npm run build --prefix app/desktop`
- **Docs checks**:
    - `uv run python scripts/check_docs_nav_routes.py --check-source`
    - `./scripts/prepare_docs_locales.sh`
    - `uv run --group dev zensical build -f zensical.toml`
    - `./scripts/build_docs_sites.sh`
    - `uv run python scripts/check_docs_nav_routes.py --check-built`
- Add tests for critical workflows instead of relying on manual verification only.
- Use canonical directory routes for docs route checks instead of source `.md` paths.
```
