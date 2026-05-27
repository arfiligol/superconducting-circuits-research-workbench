---
aliases:
  - Restricted Netlist Generators
  - 受限 Netlist 生成器
tags:
  - diataxis/explanation
  - audience/team
  - topic/architecture
  - topic/netlist
status: stable
owner: docs-team
audience: team
scope: 說明為何 WebUI 採受限 repeat 生成，而不允許任意腳本
version: v0.1.1
last_updated: 2026-03-06
updated_by: codex
---

# Restricted Netlist Generators

本頁說明 Circuit Netlist 為何採用受限生成模型（`repeat` 等），而不採任意程式碼執行。

!!! note "Boundary"
    本頁只解釋為什麼 Web UI 採限制式生成。
    語法與 editor/save 契約請看 Reference。

## 設計理由

- **Deterministic**：同一份 Source Form 必須穩定展開成同一份 Expanded Form。
- **Debuggable**：語法錯誤與展開錯誤可以定位到具體 block。
- **Minimal Surface Area**：避免把 schema editor 變成腳本執行環境。

## M1 支援範圍

- `repeat`
- `count` / `start`
- `index` / `symbol` / `series`
- 受限模板插值（`${index}`、`${symbol}` 與固定偏移）

## 非目標

- 任意 `for/if`
- 巢狀 `repeat`
- 任意函式呼叫

## Related

- [Circuit Netlist Format](../../../reference/data-formats/circuit-netlist.md)
- [Schema Editor UI Reference](../../../reference/app/frontend/definition/schema-editor.md)
- [Julia Runner Compute Plane](../../../reference/architecture/julia-runner-compute-plane.md)
