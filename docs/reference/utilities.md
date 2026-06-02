---
aliases:
  - "繪圖工具 ili_plot"
tags:
  - diataxis/reference
  - audience/user
  - topic/core-reference
status: draft
owner: team
audience: user
scope: utilities 的補充入口；正式 compute 與 plotting workflow 目前由 notebooks / runner docs 承接。
version: v0.3.0
last_updated: 2026-05-28
updated_by: codex
---

# Utilities

本頁是 utility-oriented workflows 的補充入口。

舊的 root Julia plotting helpers 已從 active code surface 移除。新的可視化 workflow 應從 app result browser、Pluto notebooks，或 Python notebook inspection 開始。

!!! info "Current routing"
    App-facing result visualization lives in the Application Interface.
    Research visualization belongs in notebooks.
    Staged numeric output belongs to the Julia Runner manifest + TraceStore contracts.

## Current References

- [Application Interface](app/application-interface.md)
- [Notebook Interface](notebooks/index.md)
- [TraceStore Zarr](architecture/trace-store-zarr.md)
