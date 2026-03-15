---
aliases:
- CLI Reference
- CLI 指令參考
tags:
- diataxis/reference
- audience/team
- sot/true
- topic/cli
status: stable
owner: docs-team
audience: team
scope: 目前正式支援的 standalone-first `sc` 命令列介面，說明 CLI 如何以 local runtime 與 canonical data formats 實踐 data ingestion、browsing、management 與 characterization/analysis workflow。
version: v0.6.0
last_updated: 2026-03-16
updated_by: codex
---

# CLI Options

本區收錄 `sc` 的正式 command surface，以及 standalone-first CLI 如何以 local runtime 與 canonical data formats 實踐 data ingestion、browsing、management 與 characterization/analysis workflow。

!!! info "How To Read CLI Docs"
    先讀 [Standalone Runtime](standalone-runtime.md) 了解 local execution model，
    再讀 `Session`、`Datasets` 取得目前工作上下文，接著讀 `Tasks`、`Events`、`Results` 查 local persisted state，最後讀 `Characterization`、`Ops` 了解 workflow-level 操作。

!!! tip "Service-backed mode is out of scope"
    目前 CLI reference 只定義 standalone-first CLI。
    多使用者 app 的 auth、shared queue、shared workspace 與 audit semantics 由 `App` reference 擁有，不由 CLI 直接消費。

!!! warning "Published Surface Rule"
    只要 command group 已由 `cli/src/sc_cli/app.py` 掛進 root `sc`，本區就必須有對應 reference page。
    `uv run sc --help` 與 CLI reference 不得分岐。

## Command Map

=== "Local Runtime"

    | Command | 核心聚焦 | Authority Pair |
    |---|---|---|
    | [Standalone Runtime](standalone-runtime.md) | local profile、local workspace、active dataset、local run registry | [Core / Python Core](../core/python-core.md), [Data Formats](../data-formats/index.md) |
    | [sc session](sc-session.md) | local context、active dataset fallback、workspace root | [Standalone Runtime](standalone-runtime.md) |
    | [sc datasets](sc-datasets.md) | local dataset catalog、dataset detail、metadata mutation | [Standalone Runtime](standalone-runtime.md), [Data Formats / Dataset / Design / Trace Schema](../data-formats/dataset-record.md) |
    | [Local / App Interchange](local-app-interchange.md) | local dataset / result bundle 的正式交換邊界 | [Standalone Runtime](standalone-runtime.md), [App / Shared / Resource Ownership & Visibility](../app/shared/resource-ownership-and-visibility.md), [Data Formats](../data-formats/index.md) |

=== "Run Registry"

    | Command | 核心聚焦 | Authority Pair |
    |---|---|---|
    | [sc tasks](sc-tasks.md) | local run list、detail、submit、wait | [Standalone Runtime](standalone-runtime.md) |
    | [sc events](sc-events.md) | local persisted run event history | [Standalone Runtime](standalone-runtime.md) |
    | [sc results](sc-results.md) | local persisted result refs、trace payload、result handles | [Standalone Runtime](standalone-runtime.md), [Data Formats / Analysis Result](../data-formats/analysis-result.md) |
    | [sc ops](sc-ops.md) | local operator bundle over task / event / result surfaces | [Standalone Runtime](standalone-runtime.md) |

=== "Workflow"

    | Command | 核心聚焦 | Authority Pair |
    |---|---|---|
    | [sc characterization](sc-characterization.md) | characterization / analysis-lane local execution / inspect / wait | [Standalone Runtime](standalone-runtime.md), [Data Formats / Analysis Result](../data-formats/analysis-result.md) |

=== "Core Boundary"

    | Command | 核心聚焦 | Authority Pair |
    |---|---|---|
    | [sc core](sc-core.md) | inspect the installable `sc_core` boundary | [Core / Python Core](../core/python-core.md) |

## Shared Contracts

| Concern | CLI Rule | SoT |
|---|---|---|
| Machine-readable output | 多數 operational subcommands 支援 `--output text|json`。目前 `sc core preview-artifacts` 仍為 text-only。 | [Canonical Contract Registry](../architecture/canonical-contract-registry.md) |
| Local runtime context | active dataset、local workspace 與 local run registry 由 standalone runtime 擁有，不依賴 app session。 | [Standalone Runtime](standalone-runtime.md) |
| Run lifecycle | `task_id` 是 inspect / wait / result lookup 的 primary key。lane-specific commands 只是在 local run registry 上加 lane filter。 | [Standalone Runtime](standalone-runtime.md), [sc tasks](sc-tasks.md) |
| Dataset and result compatibility | local ingestion / browsing / characterization payload 仍需遵守 shared data formats。 | [Data Formats](../data-formats/index.md) |

!!! example "Root Command"
    ```bash
    uv run sc --help
    ```
    目前正式 surface 應公開：
    `core`、`session`、`datasets`、`tasks`、`ops`、`events`、`results`、`characterization`

## Related

- [Standalone Runtime](standalone-runtime.md) - local execution 與 local run registry
- [Local / App Interchange](local-app-interchange.md) - local-first CLI 與 app surfaces 的交換邊界
- [Core Reference](../core/index.md) - 核心能力與 Python/Julia 邊界
- [Data Formats](../data-formats/index.md) - 共享 payload 與 schema rules
- [How-to Guides](../../how-to/index.md) - 操作指南
