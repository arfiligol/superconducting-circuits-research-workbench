---
aliases:
  - "sc tasks 指令參考"
  - "sc tasks CLI Reference"
tags:
  - diataxis/reference
  - audience/user
  - sot/true
  - topic/cli
  - topic/tasks
status: stable
owner: docs-team
audience: user
scope: "`sc tasks` standalone CLI local analysis run registry 查詢與操作指令。"
version: v0.3.0
last_updated: 2026-03-16
updated_by: codex
title: sc tasks
---

# sc tasks

查詢 local analysis run registry，並對任務做 submit、latest、wait 等操作。

!!! info "Command Role"
    `sc tasks` 是 standalone CLI 的 generic local run surface。
    `sc characterization` 是 lane-specific wrapper；底層仍依賴同一組 local run semantics。

!!! warning "No Shared Queue"
    `sc tasks` 看的是 local run registry，不是 multi-user shared queue。
    任何列表、latest、wait 與 inspect 操作都只對 local persisted state 生效。

!!! warning "Primary Recovery Key"
    `task_id` 是 attach、inspect、wait 的 primary key。
    `dataset_id` 只能當輔助查詢條件，不可取代 `task_id`。

## Command Map

=== "Browse"

    | Subcommand | Focus | Key inputs |
    |---|---|---|
    | `list` | local run list | `--status`, `--lane`, `--dataset-id`, `--limit` |
    | `latest` | 取符合條件的最新 local run | `--status`, `--lane`, `--dataset-id` |

=== "Inspect"

    | Subcommand | Focus | Key inputs |
    |---|---|---|
    | `show` | 單筆 task detail | `TASK_ID` |
    | `inspect` | operator-oriented detail，含 event / result summary | `TASK_ID` |

=== "Operate"

    | Subcommand | Focus | Key inputs |
    |---|---|---|
    | `wait` | 輪詢到指定狀態 | `TASK_ID`, `--until-status`, `--interval`, `--timeout` |
    | `submit` | 建立 local analysis run record 並啟動工作 | `KIND`, `--dataset-id`, `--summary` |

## Shared Option

| Option | Values | Notes |
|---|---|---|
| `--output` | `text`, `json` | 所有 subcommands 皆支援 |

## `list` / `latest` Filters

| Option | Values | Default |
|---|---|---|
| `--status` | `queued`, `running`, `completed`, `failed` | `None` |
| `--lane` | `characterization`, `post_processing` | `None` |
| `--dataset-id` | free text | `None` |
| `--limit` | `1..50` | `20` (`list` only) |

## `submit` Kind

| Value | Meaning |
|---|---|
| `characterization` | dataset-driven characterization task |
| `post_processing` | dataset-bound analysis / post-processing task |

!!! example "Common Usage"
    ```bash
    uv run sc tasks list --lane characterization --status running
    uv run sc tasks show 306
    uv run sc tasks inspect 306
    uv run sc tasks submit characterization --dataset-id DATASET-001
    uv run sc tasks wait 306 --until-status terminal
    ```

!!! tip "Direct execution model"
    `submit` 在 standalone CLI 中代表直接啟動本地工作。
    實作可以在目前 terminal process 或 local child process 執行，但結果必須回寫到同一份 local run registry。

## Standalone Pairing

| Concern | Authority |
|---|---|
| local run lifecycle、wait semantics、result attachment | [Standalone Runtime](standalone-runtime.md) |
| characterization / analysis result payload compatibility | [Data Formats / Analysis Result](../data-formats/analysis-result.md) |

## Related

- [sc events](sc-events.md)
- [sc results](sc-results.md)
- [sc characterization](sc-characterization.md)
- [Standalone Runtime](standalone-runtime.md)
