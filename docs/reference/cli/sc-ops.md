---
aliases:
  - "sc ops 指令參考"
  - "sc ops CLI Reference"
tags:
  - diataxis/reference
  - audience/user
  - sot/true
  - topic/cli
  - topic/tasks
status: stable
owner: docs-team
audience: user
scope: "`sc ops` standalone CLI operator bundle 指令。"
version: v0.2.0
last_updated: 2026-03-16
updated_by: codex
title: sc ops
---

# sc ops

以 connected operator bundle 的角度查看與操作 local run。

!!! info "Command Role"
    `sc ops` 不代表一套新的 workflow engine。
    它是把 local run、recent events、result attachment 收斂成較適合操作人員的 bundle view。

!!! warning "Bundle Boundary"
    `sc ops` 呈現的是既有 local persisted state 的組合視圖。
    若需要單獨查 event history 或 result refs，仍應回到 [sc events](sc-events.md) 與 [sc results](sc-results.md)。

## Command Map

| Subcommand | Focus | Key inputs |
|---|---|---|
| `inspect` | 單筆 task 的 operator bundle | `TASK_ID`, `--recent-events` |
| `latest` | 依條件取最新 task bundle | `--status`, `--lane`, `--dataset-id`, `--recent-events` |
| `wait` | 等待 task 後再輸出 bundle | `TASK_ID`, `--until-status`, `--interval`, `--timeout`, `--recent-events` |
| `submit` | 送出 task 並輸出 bundle | `KIND`, `--dataset-id`, `--summary`, `--wait`, `--until-status`, `--interval`, `--timeout`, `--recent-events` |

## Shared Option

| Option | Values | Notes |
|---|---|---|
| `--output` | `text`, `json` | 所有 subcommands 皆支援 |
| `--recent-events` | `1..10` | bundle 中附帶的 recent event 數量 |

## Submit Kind

| Value | Meaning |
|---|---|
| `characterization` | dataset-driven characterization task |
| `post_processing` | dataset-bound analysis / post-processing task |

!!! example "Common Usage"
    ```bash
    uv run sc ops latest --lane characterization --recent-events 5
    uv run sc ops inspect 306
    uv run sc ops wait 306 --until-status terminal
    uv run sc ops submit characterization --dataset-id DATASET-001 --wait
    ```

## Standalone Pairing

| Concern | Authority |
|---|---|
| task / event / result bundle source | [Standalone Runtime](standalone-runtime.md) |
| result attachment semantics | [Data Formats / Analysis Result](../data-formats/analysis-result.md) |

## Related

- [sc tasks](sc-tasks.md)
- [sc events](sc-events.md)
- [sc results](sc-results.md)
- [Standalone Runtime](standalone-runtime.md)
