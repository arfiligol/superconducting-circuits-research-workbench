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
scope: 定義 current platform 中 frontend/backend/cli/desktop/core 的放置邊界。
version: v2.5.0
last_updated: 2026-03-21
updated_by: codex
---

# Folder Structure

本 branch 的目標結構是為了支援前後端分離，同時保留現有科學計算核心與文件系統。
舊版 UI 程式碼暫時保留在 legacy 區，但不應再作為新功能落點。

!!! info "How to use this page"
    當你不確定新檔案該放哪裡時，先看 placement rules，而不是先照習慣找最近的資料夾塞進去。這頁的重點是 owner boundary，不是完整檔案樹教學。

## Target Layout

```text
superconducting-circuits-tutorial/
├── frontend/                  # Next.js App Router frontend
│   ├── src/app/               # routes, layouts, pages
│   ├── src/components/        # shared UI components
│   ├── src/features/          # feature-local UI modules
│   ├── src/lib/               # API clients, schemas, utilities
│   └── tests/                 # Vitest / Playwright
├── desktop/                   # Electron shell
│   ├── src/main/              # Electron main process
│   ├── src/preload/           # secure preload bridge
│   └── resources/             # desktop packaging assets
├── backend/                   # FastAPI service
│   ├── src/app/api/           # routers, request/response mapping
│   ├── src/app/services/      # use cases / orchestration
│   ├── src/app/domain/        # domain models and rules
│   ├── src/app/infrastructure/# DB, external integrations
│   └── tests/                 # pytest unit / integration tests
├── cli/                       # Typer commands
│   ├── src/sc_cli/            # commands, presenters, runtime adapters
│   └── tests/
├── src/core/                  # shared scientific kernels during migration
│   ├── simulation/
│   ├── analysis/
│   └── shared/
├── docs/                      # zh-TW docs, guardrails, and docs staging tree
├── data/                      # raw / processed / trace-store / local DB
├── openapi.json               # committed OpenAPI snapshot for contract sync
├── scripts/                   # repo helpers only
└── src/app/                   # legacy UI code during migration only
```

## Placement Rules

| 如果要改 | 應放位置 |
| --- | --- |
| Next.js page, layout, component | `frontend/` |
| Electron main / preload / packaging | `desktop/` |
| API router, service, persistence | `backend/` |
| CLI command or batch workflow | `cli/` |
| 可被 API / CLI / simulation 共用的科學邏輯 | `src/core/` |
| repo automation, docs helper, migration helper | `scripts/` |
| 舊版 UI 修補 | `src/app/`，且需明確標註為 migration-only |
| committed OpenAPI contract snapshot | root `openapi.json` |

!!! warning "Do not invent new top-level homes"
    若現有邊界已能表達責任，就不要再新增新的 top-level package 或平行資料夾。先修正 placement，再考慮目錄擴張。

## Related Blueprints

- backend 的責任分層與模組邊界，參見 [Backend Architecture](./backend-architecture.md)
- shared core 的 canonical contract 與 adopter boundary，參見 [Core Reference](../../core/index.md)

## Dependency Direction

1. frontend 依賴 API contract，不直接依賴 backend internals
2. desktop 依賴 frontend build 與受控 IPC，不承載業務規則
3. backend API 層依賴 services/domain，不反向耦合到 web framework 以外的層
4. CLI command 不得複製複雜 workflow logic；standalone CLI 的 shared logic 應優先收斂在 CLI-local runtime abstractions 或 `src/core/`
5. `src/core/` 不得依賴 Next.js、FastAPI、Electron 或 CLI framework

??? note "Why the full tree is still shown"
    這頁保留完整 target layout，是因為 folder boundary 本身就是 reference contract。其餘 guardrails 不需要都像這樣展開。

## Agent Rule { #agent-rule }

```markdown
## Folder Structure
- **Frontend** work goes to `frontend/`.
- **Desktop shell** work goes to `desktop/`.
- **Backend** work goes to `backend/`.
- **CLI** work goes to `cli/`.
- **Shared scientific logic** goes to `src/core/`.
- **Docs and guardrails** go to `docs/`; `docs/docs_zhtw/` is generated staging, not a primary edit source.
- **Committed OpenAPI snapshot** stays at repo root as `openapi.json` for contract-sync verification.
- Existing `src/app/` legacy UI code is legacy and should only receive migration-support fixes.
- Dependency direction:
    - frontend depends on API contracts, not backend internals
    - desktop depends on frontend outputs and secure IPC, not business logic ownership
    - backend API layer depends inward on services/domain
    - standalone CLI shared logic belongs in CLI-local runtime abstractions or `src/core/`; do not assume backend services are the default owner
    - `src/core/` must stay framework-agnostic
```
