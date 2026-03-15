---
aliases:
  - "sc characterization 指令參考"
  - "sc characterization CLI Reference"
tags:
  - diataxis/reference
  - audience/user
  - sot/true
  - topic/cli
  - topic/characterization
status: stable
owner: docs-team
audience: user
scope: "`sc characterization` standalone CLI characterization / analysis-lane local run 操作指令。"
version: v0.3.0
last_updated: 2026-03-16
updated_by: codex
title: sc characterization
---

# sc characterization

操作 characterization / analysis lane 上的 local run。

!!! info "Lane Wrapper"
    `sc characterization` 是 generic local run contract 的 lane-specific wrapper。
    它保留 generic local run 的 inspect / latest / wait semantics，但會自動限制在 `characterization` lane。

!!! tip "Dataset Fallback"
    `submit` 的 `--dataset-id` 若省略，會回退到目前 local session 的 active dataset。

## Command Map

=== "Submit"

    | Subcommand | Focus | Key inputs |
    |---|---|---|
    | `submit` | 送出 characterization-lane task | `--dataset-id`, `--summary` |

=== "Inspect"

    | Subcommand | Focus | Key inputs |
    |---|---|---|
    | `show` | 顯示單筆 characterization-lane task detail | `TASK_ID` |
    | `inspect` | 顯示 operator-oriented detail | `TASK_ID` |
    | `latest` | 顯示符合條件的最新 characterization-lane task | `--status`, `--dataset-id` |
    | `wait` | 等待單筆 task 達到目標狀態 | `TASK_ID`, `--until-status`, `--interval`, `--timeout` |

## Shared Option

| Option | Values | Notes |
|---|---|---|
| `--output` | `text`, `json` | 所有 subcommands 皆支援 |

## Filters

| Option | Values | Default |
|---|---|---|
| `--status` | `queued`, `running`, `completed`, `failed` | `None` (`latest`) |
| `--dataset-id` | free text | `None` |

!!! example "Common Usage"
    ```bash
    uv run sc characterization submit --dataset-id DATASET-001
    uv run sc characterization latest --status completed
    uv run sc characterization inspect 412
    uv run sc characterization wait 412 --until-status terminal
    ```

## Standalone Pairing

| Concern | Authority |
|---|---|
| characterization-lane local run lifecycle | [Standalone Runtime](standalone-runtime.md) |
| characterization result payload | [Data Formats / Analysis Result](../data-formats/analysis-result.md) |

## Related

- [sc tasks](sc-tasks.md)
- [sc ops](sc-ops.md)
- [Standalone Runtime](standalone-runtime.md)
