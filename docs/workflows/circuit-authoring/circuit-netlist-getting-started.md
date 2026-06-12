---
aliases:
  - Circuit Netlist Getting Started
  - Netlist 入門
tags:
  - diataxis/tutorial
  - audience/user
  - topic/netlist
status: stable
owner: docs-team
audience: user
scope: Circuit Netlist Source Form 入門與最小可執行流程
version: v0.1.0
last_updated: 2026-03-05
updated_by: codex
sidebar:
  label: Circuit Netlist Getting Started
  order: 40
---

# Circuit Netlist Getting Started

本頁提供最小化的 Circuit Netlist Source Form 心智模型。研究主線應優先從 Julia Core / Pluto examples 學會元件、節點與參數如何對應到 solver-facing circuit。

## 快速開始

1. 先在 notebook 或 Julia Core helper 中建立 `name`、`components`、`topology` 的等價概念。
2. Ground node 只使用字串 `"0"`。
3. Component 僅可二選一：`default` 或 `value_ref`。
4. 在最小 LC 或 repeated section example 中檢查展開後的元件名稱、節點與 port 編號。

## Related

- [Circuit Netlist Format](../../reference/data-formats/circuit-netlist.mdx)
- [LC Resonator](lc-resonator.md)
- [Repeating Circuit Sections](repeating-circuit-sections.md)
