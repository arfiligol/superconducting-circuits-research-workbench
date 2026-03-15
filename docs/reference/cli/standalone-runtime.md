---
aliases:
  - CLI Standalone Runtime
  - Standalone CLI Runtime
  - CLI 本地執行模型
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/cli
status: draft
owner: docs-team
audience: team
scope: standalone-first CLI 的 local context、local dataset catalog、local run registry、local artifacts 與 direct execution model
version: v0.3.0
last_updated: 2026-03-16
updated_by: codex
title: Standalone Runtime
---

# Standalone Runtime

本頁定義 `sc` 的 standalone-first 執行模型。CLI 預設是單機、本地、single-user 的工具，不以 backend service 為必要前提。

!!! info "Standalone-first default"
    `sc` 的正式起點是 local runtime。
    command 直接讀寫本地 context、本地 catalog、本地 run registry 與本地 artifact store。

!!! warning "Local Workspace Is Not App Workspace"
    `sc session workspace` 指的是 local project / working root，不是多使用者 App 的 collaboration workspace。
    standalone CLI 不消費 app shared auth、shared queue 或 active workspace semantics。

## Runtime Envelope

| Object | Required meaning |
|---|---|
| Local Profile | 目前 CLI 使用的本地身份與偏好設定 |
| Local Workspace Root | 目前 project / filesystem working root |
| Active Dataset | standalone CLI 的預設 dataset context |
| Local Run Registry | 本地 task / run 清單與 lifecycle state |
| Local Event Store | 每筆 local run 的 persisted event history |
| Local Result Store | result handles、trace refs、artifact metadata |

## Execution Model

| Rule | Meaning |
|---|---|
| Direct execution | `submit` 類命令直接在目前 terminal process 或 local child process 內啟動工作 |
| No remote queue dependency | standalone CLI 不依賴 backend queue 或 shared worker pool |
| Local run registry is authoritative | `sc tasks`、`sc events`、`sc results` 以本地 persisted state 為準 |
| Single-user scope | 不支援多使用者 auth、workspace membership 或 shared task visibility |
| Machine-readable output stays stable | `--output json` 一旦 published 即視為 CLI contract |

## Context Rules

| Concern | Rule |
|---|---|
| Active dataset fallback | 支援 `--dataset-id` 的命令，省略時可回退到 `sc session` 定義的 active dataset |
| Local workspace switching | 若 CLI 暴露 workspace command，它只切換本地 working context |
| Refresh / re-entry | 重新打開 terminal 後，若 local registry 仍存在，就應能透過 `task_id` 重新 inspect |

## Data Compatibility

| Concern | SoT |
|---|---|
| dataset / trace metadata compatibility | [Data Formats / Dataset / Design / Trace Schema](../data-formats/dataset-record.md) |
| result payload / artifact compatibility | [Data Formats / Analysis Result](../data-formats/analysis-result.md) |

## Related Commands

| Command group | Why it depends on standalone runtime |
|---|---|
| [sc session](sc-session.md) | 顯示與更新 local context |
| [sc datasets](sc-datasets.md) | 檢查本地 dataset catalog |
| [sc tasks](sc-tasks.md) | 檢查本地 run registry |
| [sc characterization](sc-characterization.md) | 啟動本地 characterization run |

## Related

- [CLI Options](index.md)
- [Local / App Interchange](local-app-interchange.md)
- [Core Reference](../core/index.md)
- [Data Formats](../data-formats/index.md)
