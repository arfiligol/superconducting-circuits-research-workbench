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
scope: 定義 current platform 的 top-level canonical development surfaces 與 migration residue 邊界。
version: v3.1.0
last_updated: 2026-04-29
updated_by: codex
---

# Folder Structure

本 branch 的 canonical target layout 以 top-level folders 作為正式架構邊界。
`backend/`、`frontend/`、`core/`、`cli/`、`desktop/`、`legacy/` 是目前應被人類與 AI Agent 直接辨識的主要開發對象。

root-level `src/` 不再應被描述為 future canonical umbrella。
任何仍留在 root `src/` 底下的內容，都應視為 migration residue，除非另有文件明寫。

!!! info "How to use this page"
    當你不確定新檔案該放哪裡時，先看 placement rules，而不是先照習慣找最近的資料夾塞進去。這頁的重點是 owner boundary，不是完整檔案樹教學。

## Target Layout

```text
superconducting-circuits-tutorial/
├── backend/                   # canonical app/backend service surface
├── frontend/                  # canonical web app surface
├── core/                      # canonical shared scientific/core surface
├── cli/                       # canonical standalone CLI surface
├── desktop/                   # canonical desktop shell surface
├── legacy/
│   └── legacy_nicegui_archived/ # archived UI payload; not a new-work target
├── docs/                      # zh-TW docs, guardrails, and docs staging tree
├── Plans/                     # active multi-agent planning artifacts; not long-term SoT
├── data/                      # raw / processed / trace-store / local DB
├── openapi.json               # committed OpenAPI snapshot for contract sync
└── scripts/                   # repo helpers only
```

!!! important "Top-level folders are the architecture boundaries"
    這份 target layout 故意不把 root `src/` 畫成 umbrella。
    package-internal `src/` 可以存在於 `backend/`、`frontend/`、`desktop/`、`cli/` 之內，
    但 root-level `src/` 不再是未來架構的正式收納模型。

## Placement Rules

| 如果要改 | 應放位置 |
| --- | --- |
| Next.js page, layout, component | `frontend/` |
| Electron main / preload / packaging | `desktop/` |
| API router, service, persistence | `backend/` |
| CLI command or batch workflow | `cli/` |
| 可被 API / CLI / simulation 共用的科學邏輯 | `core/` |
| repo automation, docs helper, migration helper | `scripts/` |
| multi-agent planning, prompt handoff, test backlog | `Plans/`，由 Planning & Reviewing Agent 建立/退休/刪除 |
| archived NiceGUI residue | `legacy/legacy_nicegui_archived/`（current archived residue 仍可能在 `src/app/`） |
| worker runtime residue / redesign staging | 不屬於 target layout；若仍需碰 `src/worker/`，只能以 migration/redesign context 理解 |
| committed OpenAPI contract snapshot | root `openapi.json` |

!!! warning "Do not reintroduce root `src/` as umbrella"
    這次決策不是把 `backend/`、`frontend/`、`core/`、`cli/` 再包回 root `src/`。
    若現有 top-level 邊界已能表達責任，就不要再讓 root `src/` 重新變成大雜燴入口。

## Current Implementation Residue

| Current location | How to interpret it now |
| --- | --- |
| `src/app/` | archived legacy UI residue，pending relocation to `legacy/legacy_nicegui_archived/` |
| `src/worker/` | transition residue / pending backend worker-runtime redesign；不是 canonical current runtime folder，也不是新實作 owner |

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

1. frontend 依賴 API contract，不直接依賴 backend internals
2. desktop 依賴 frontend build 與受控 IPC，不承載業務規則
3. backend API 層依賴 services/domain，不反向耦合到 web framework 以外的層
4. CLI command 不得複製複雜 workflow logic；standalone CLI 的 shared logic 應優先收斂在 CLI-local runtime abstractions 或 top-level `core/`
5. top-level `core/` 不得依賴 Next.js、FastAPI、Electron 或 CLI framework
6. root `src/` residues 不得被重新解讀成正式 architecture boundary

??? note "Why the full tree is still shown"
    這頁保留完整 target layout，是因為 folder boundary 本身就是 reference contract。其餘 guardrails 不需要都像這樣展開。

## Agent Rule { #agent-rule }

```markdown
## Folder Structure
- **Frontend** work goes to `frontend/`.
- **Desktop shell** work goes to `desktop/`.
- **Backend** work goes to `backend/`.
- **Shared scientific logic** goes to top-level `core/`.
- **CLI** work goes to `cli/`.
- **Archived NiceGUI residue** targets `legacy/legacy_nicegui_archived/`; current `src/app/` should be read as archived payload pending relocation.
- **`src/worker/`** is transition residue under redesign, not a canonical development surface.
- **Docs and guardrails** go to `docs/`; `docs/docs_zhtw/` is generated staging, not a primary edit source.
- **Plans** go to `Plans/` only as active multi-agent coordination artifacts; Planning & Reviewing Agents own creation and cleanup, and long-term decisions must move to `docs/reference/**`.
- **Committed OpenAPI snapshot** stays at repo root as `openapi.json` for contract-sync verification.
- Root-level `src/` is not the future canonical umbrella.
- Dependency direction:
    - frontend depends on API contracts, not backend internals
    - desktop depends on frontend outputs and secure IPC, not business logic ownership
    - backend API layer depends inward on services/domain
    - standalone CLI shared logic belongs in CLI-local runtime abstractions or top-level `core/`; do not assume backend services are the default owner
    - top-level `core/` must stay framework-agnostic
```
