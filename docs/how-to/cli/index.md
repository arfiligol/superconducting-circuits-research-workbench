---
aliases:
  - "CLI 操作指南"
  - "CLI How-to"
tags:
  - diataxis/how-to
  - status/stable
  - audience/user
  - topic/cli
owner: team
status: stable
audience: user
scope: "目前正式支援的 CLI 指令快速索引與常見查詢入口"
version: v1.3.0
last_updated: 2026-03-16
updated_by: codex
---

# CLI 使用總覽

本指南提供目前正式支援的 CLI 指令快速索引。

## 常用指令速查

所有指令皆以 `sc` (Superconducting Circuits) 開頭：

```bash
uv run sc <GROUP> <COMMAND>
```

| 任務分類 | 指令前綴 | 相關參考 |
|----------|----------|----------|
| **Shared Core** | `sc core ...` | [sc core](../../reference/cli/sc-core.md) |
| **Session / Workspace** | `sc session ...` | [sc session](../../reference/cli/sc-session.md) |
| **Datasets** | `sc datasets ...` | [sc datasets](../../reference/cli/sc-datasets.md) |
| **Tasks** | `sc tasks ...` | [sc tasks](../../reference/cli/sc-tasks.md) |
| **Characterization / Analysis** | `sc characterization ...` | [sc characterization](../../reference/cli/sc-characterization.md) |
| **Run Events** | `sc events ...` | [sc events](../../reference/cli/sc-events.md) |
| **Run Results** | `sc results ...` | [sc results](../../reference/cli/sc-results.md) |
| **Operator Bundle** | `sc ops ...` | [sc ops](../../reference/cli/sc-ops.md) |

## 查看說明

您隨時可以使用 `--help` 查看指令用法：

```bash
uv run sc --help
uv run sc session --help
uv run sc datasets --help
uv run sc tasks --help
uv run sc characterization --help
```

## 相關參考

- [完整 CLI Reference](../../reference/cli/index.md)
