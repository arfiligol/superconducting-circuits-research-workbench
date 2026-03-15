---
aliases:
  - "sc datasets 指令參考"
  - "sc datasets CLI Reference"
tags:
  - diataxis/reference
  - audience/user
  - sot/true
  - topic/cli
  - topic/dataset
status: stable
owner: docs-team
audience: user
scope: "`sc datasets` standalone CLI local dataset catalog 查詢與 metadata mutation 指令。"
version: v0.2.2
last_updated: 2026-03-16
updated_by: codex
title: sc datasets
---

# sc datasets

查詢 local dataset catalog、單筆 dataset detail，並更新 local dataset metadata。

!!! info "Command Role"
    `sc datasets` 是 CLI 對 local dataset catalog 的正式入口。
    它不負責 trace selection、analysis run 或 simulation execution。

!!! tip "Format compatibility"
    standalone CLI 雖然使用 local dataset catalog，但 dataset metadata 與 trace-related payload 仍需遵守 shared data-format contracts。

!!! warning "Metadata Mutation"
    `set-metadata` 會直接送出 `device_type`、`source` 與 `capabilities` metadata。
    若要提供多個 capability，必須重複使用 `--capability`。

## Command Map

=== "Browse"

    | Subcommand | Focus | Key inputs |
    |---|---|---|
    | `list` | dataset catalog | `--family`, `--status`, `--sort-by`, `--sort-order` |
    | `show` | 單筆 dataset detail | `DATASET_ID` |

=== "Mutate"

    | Subcommand | Focus | Key inputs |
    |---|---|---|
    | `set-metadata` | 更新 dataset metadata | `DATASET_ID`, `--device-type`, `--source`, repeated `--capability` |

## Shared Option

| Option | Values | Notes |
|---|---|---|
| `--output` | `text`, `json` | 所有 subcommands 皆支援 |

## `list` Filters

| Option | Values | Default |
|---|---|---|
| `--family` | free text | `None` |
| `--status` | `Ready`, `Queued`, `Review` | `None` |
| `--sort-by` | `updated_at`, `name`, `samples` | `updated_at` |
| `--sort-order` | `asc`, `desc` | `desc` |

!!! example "Common Usage"
    ```bash
    uv run sc datasets list
    uv run sc datasets show DATASET-001
    uv run sc datasets set-metadata DATASET-001 \
      --device-type FloatingQubit \
      --source inferred \
      --capability characterization \
      --capability analysis
    ```

## Standalone Pair

| Concern | Authority |
|---|---|
| local dataset catalog / detail | [Standalone Runtime](standalone-runtime.md) |
| dataset metadata contract | [Data Formats / Dataset / Design / Trace Schema](../data-formats/dataset-record.md) |

## Related

- [CLI Options](index.md)
- [Standalone Runtime](standalone-runtime.md)
- [Data Formats / Dataset / Design / Trace Schema](../data-formats/dataset-record.md)
