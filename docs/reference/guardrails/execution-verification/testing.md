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
scope: rewrite branch 的 backend、frontend、desktop、CLI 與 docs 測試規範。
version: v2.3.0
last_updated: 2026-03-16
updated_by: codex
---

# Testing

本頁定義 rewrite branch 的測試入口與最低測試期待。

!!! info "How to read this page"
    先判斷你碰的是 `root orchestration`、`backend/core`、`frontend`、`desktop` 還是 `docs`。
    這頁回答的是「最低該跑什麼」，不是完整測試設計本身。

## Test Map

| Area | Minimum baseline |
| --- | --- |
| Rewrite root | `npm run rewrite:check` |
| Backend / Core | `pytest` |
| Frontend | unit tests，必要時 E2E |
| Desktop foundation | lint + build |
| Docs | source check + build + built-route check |

## Rewrite Root Check

```bash
npm run rewrite:check
```

## Backend / Core

```bash
cd backend && uv run pytest
uv run pytest
```

## Frontend

=== "Unit"

    ```bash
    npm run test --prefix frontend
    ```

=== "E2E"

    ```bash
    npm run test:e2e --prefix frontend
    ```

rewrite foundation 目前只要求 deterministic unit tests。
不要用 placeholder E2E 假裝覆蓋尚未遷移的真實 workflow。

!!! warning "Frontend review needs real browser evidence"
    若交付內容改動 shell、layout、header/sidebar behavior、dialog/drawer interaction、auth entry、或其他明顯 user-visible workflow，
    `Planning & Reviewing Agent` 在 merge pass 不得只看 code diff 或 unit test。
    必須至少使用 Playwright 走一次實際流程，並透過 screenshot 或等價視覺證據檢查 UI 是否跑掉。

## Desktop Foundation

```bash
npm run lint --prefix desktop
npm run build --prefix desktop
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
| backend service 與 CLI workflow 優先寫 pytest | 先確保 deterministic automation |
| frontend component 與互動流程分別用 unit / E2E 覆蓋 | 不要用單一測試型態硬扛全部責任 |
| Frontend merge review 需要真實 UI 證據 | shell / layout / overlay / auth entry 之類的 user-visible 交付，至少要用 Playwright smoke + screenshot 檢查一次 |
| docs route 驗證必須用 canonical directory routes | 不依賴來源 `.md` 路徑推測 build 結果 |

!!! tip "Good default"
    若你不確定這輪該補哪種測試，先選最靠近 changed surface 的 deterministic test；
    只有當 user-visible workflow 真正跨過多個 surface 時，再補 integration / E2E。

## Agent Rule { #agent-rule }

```markdown
## Testing Commands
- **Root rewrite check**: `npm run rewrite:check`
- **Backend/core tests**:
    - `cd backend && uv run pytest`
    - `uv run pytest`
- **Frontend unit tests**: `npm run test --prefix frontend`
- **Frontend E2E tests**: `npm run test:e2e --prefix frontend`
- For user-visible frontend changes, Planning & Reviewing Agents must use Playwright-based smoke verification and screenshot or equivalent visual evidence during merge review.
- **Desktop foundation checks**:
    - `npm run lint --prefix desktop`
    - `npm run build --prefix desktop`
- **Docs checks**:
    - `uv run python scripts/check_docs_nav_routes.py --check-source`
    - `./scripts/prepare_docs_locales.sh`
    - `uv run --group dev zensical build -f zensical.toml`
    - `./scripts/build_docs_sites.sh`
    - `uv run python scripts/check_docs_nav_routes.py --check-built`
- Add tests for critical workflows instead of relying on manual verification only.
- Use canonical directory routes for docs route checks instead of source `.md` paths.
```
