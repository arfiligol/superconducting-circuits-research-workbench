---
aliases:
  - CLI App Interchange
  - Local to App Interchange
  - CLI / App 交換契約
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/cli
status: draft
owner: docs-team
audience: team
scope: standalone CLI local dataset / result artifacts 與 multi-user app surfaces 之間的 import/export/copy-with-lineage bridge contract
version: v0.2.0
last_updated: 2026-03-16
updated_by: codex
title: Local / App Interchange
---

# Local / App Interchange

本頁定義 standalone CLI 與 multi-user app 之間的正式交換邊界。

!!! info "Bridge, not shared runtime"
    standalone CLI 不直接消費 app session、shared workspace 或 shared queue。
    兩者之間的正式橋接方式是 import / export / copy-with-lineage，而不是直接共享 runtime state。

## Supported Bridge Modes

| Mode | Direction | Meaning |
| --- | --- | --- |
| Export bundle | local CLI -> app or archive | 把 local definition / dataset / result 打包為可匯入 bundle |
| Import bundle | app -> local CLI or local archive restore | 將外部 bundle materialize 成本地 catalog / artifact |
| Publish / copy with lineage | app internal | app 內的共享或跨 workspace 派生，不由 CLI 直接擁有 |

## Required Rules

| Rule | Meaning |
| --- | --- |
| No implicit live sync | local runtime 與 app workspace 不保持雙向即時同步 |
| Lineage survives transport | export/import 後必須保留 lineage parent / source provenance |
| Data format compatibility stays canonical | bundle 內容仍必須遵守 [Data Formats](../data-formats/index.md) |
| App visibility is assigned at import | local bundle 不自帶多 workspace visibility |

## Interchange Payload Families

| Payload | Minimum contents |
| --- | --- |
| Dataset bundle | dataset profile、design scopes、trace metadata、TraceStore locator manifest |
| Result bundle | analysis run summary、artifact manifest、derived parameters、lineage |

## Related

- [CLI Options](index.md)
- [Standalone Runtime](standalone-runtime.md)
- [App / Shared / Resource Ownership & Visibility](../app/shared/resource-ownership-and-visibility.md)
- [Data Formats](../data-formats/index.md)
