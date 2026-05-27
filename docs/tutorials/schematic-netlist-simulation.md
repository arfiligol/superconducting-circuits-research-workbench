---
aliases:
  - From Netlist to Simulation
  - Netlist 到模擬
tags:
  - diataxis/tutorial
  - audience/user
  - topic/simulation
status: stable
owner: docs-team
audience: user
scope: 從 Schema Source Form 到 Simulation Result 的操作流程
version: v0.1.0
last_updated: 2026-03-05
updated_by: codex
---

# From Netlist to Runner Task

本頁串接 Schema 與非同步 Julia Runner simulation task 的最短操作路徑。

## 流程

1. 在 Schema Editor 撰寫 Source Form，儲存 schema。
2. 在 Application task surface 建立 simulation task。
3. Python Backend 驗證 dataset/design/schema，準備 staging directory。
4. Julia Runner claim task、執行 Julia Core、寫入 `result.zarr` 與 `manifest.json`。
5. Backend publisher 驗證並 publish 到 TraceStore。
6. 使用 `Tasks` 與 `Raw Data` 檢視正式結果。

## Related

- [Schema Editor UI](../reference/app/frontend/definition/schema-editor.md)
- [Julia Runner Compute Plane](../reference/architecture/julia-runner-compute-plane.md)
- [Analysis Result Data Contract](../reference/data-formats/analysis-result.md)
