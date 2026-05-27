---
aliases:
  - CI Gates
  - CI 品質關卡
tags:
  - diataxis/reference
  - audience/contributor
  - sot/true
  - topic/execution
status: stable
owner: docs-team
audience: contributor
scope: develop 日常整合與 main release promotion 的 PR 品質門檻，含 app layout、Julia Runner、desktop shell 與 docs route validation。
version: v3.0.0
last_updated: 2026-05-27
updated_by: codex
---

# CI Gates

所有 PR 在 merge 前必須通過與 touched area 對應的必要檢查。
日常 integration 的預設目標是 `develop`；`main` 只接 verified release promotion。

!!! info "How to use this page"
    先依 touched area 找對應 gate，再確認是否還需要 docs 或 desktop 的補充檢查。這頁定的是最低 merge bar，不是每次本地開發都要全跑。

## Gate Map

| touched area | 至少要過的 gate |
| --- | --- |
| foundation workspaces | backend pytest + frontend test/build + desktop lint/build + Julia Runner test |
| backend | startup smoke + backend pytest |
| frontend | lint + typecheck + test + build |
| desktop | lint + build |
| docs | source route check + docs build + built route check |

## Mandatory Gates

=== "Foundation Workspaces"

    - install：`cd app/backend && uv sync`、`npm install --prefix app/frontend`、`npm install --prefix app/desktop`
    - check：`cd app/backend && uv run pytest`、`npm run test --prefix app/frontend`、`npm run lint --prefix app/desktop`、`julia --project=core/julia/SuperconductingCircuitsRunner -e 'using Pkg; Pkg.test()'`
    - build：`npm run build --prefix app/frontend`、`npm run build --prefix app/desktop`

=== "Backend / Frontend / Desktop"

    - backend foundation：startup smoke 與 `cd app/backend && uv run pytest`
    - frontend：`npm run lint --prefix app/frontend`、`npm run typecheck --prefix app/frontend`、`npm run test --prefix app/frontend`、`npm run build --prefix app/frontend`
    - desktop：`npm run lint --prefix app/desktop`、`npm run build --prefix app/desktop`
    - Julia Runner：`julia --project=core/julia/SuperconductingCircuitsRunner -e 'using Pkg; Pkg.test()'`

=== "Docs / Review"

    - docs：`uv run python scripts/check_docs_nav_routes.py --check-source`、`./scripts/build_docs_sites.sh`、`uv run python scripts/check_docs_nav_routes.py --check-built`（docs touched 時）
    - 至少一位 reviewer approve

## Notes

- `zensical build` 預覽流程中的良性 `404` 警告不視為 CI 失敗
- backend 專用 lint / type-check gate 之後可再提升；目前 foundation gate 先以 startup smoke + pytest 為主

!!! warning "Merge blocking rule"
    任何 failing required check 都直接阻擋 merge；不要用「這次看起來只是小改」當作跳過 CI gate 的理由。

## Branch Policy

- `main` 禁止直接 push
- 日常 feature / docs / test work 預設 merge 到 `develop`
- `main` 只接從 `develop` 進行的 verified release promotion
- branch roles、isolated worktree 與 merge authority 以 [Branch & Worktree Flow](./branch-and-worktree-flow.md) 為準
- guardrail source 的規則變更需同步更新 `.agent/rules`

## Agent Rule { #agent-rule }

```markdown
## CI Gates
- Mandatory checks include:
    - backend startup smoke and `cd app/backend && uv run pytest`
    - `julia --project=core/julia/SuperconductingCircuitsRunner -e 'using Pkg; Pkg.test()'`
    - `npm run lint --prefix app/frontend`
    - `npm run typecheck --prefix app/frontend`
    - `npm run test --prefix app/frontend`
    - `npm run build --prefix app/frontend`
    - `npm run lint --prefix app/desktop`
    - `npm run build --prefix app/desktop`
    - `uv run python scripts/check_docs_nav_routes.py --check-source` when docs are touched
    - `./scripts/build_docs_sites.sh` when docs are touched
    - `uv run python scripts/check_docs_nav_routes.py --check-built` when docs are touched
- `main` must not receive direct pushes.
- Daily feature/docs/test integration targets `develop` by default.
- `main` only receives verified release promotion from `develop`.
- Branch roles, worktree policy, and merge authority are defined in `Branch & Worktree Flow`.
- Guardrail source changes must keep `.agent/rules` in sync.
- Benign `404` warnings from docs preview builds do not fail CI by themselves.
- Any failing required check blocks merge.
```
