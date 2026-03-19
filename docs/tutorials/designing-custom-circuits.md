---
aliases:
  - Designing Custom Circuits
  - 自訂電路設計
tags:
  - diataxis/tutorial
  - audience/user
  - topic/circuit-design
status: stable
owner: docs-team
audience: user
scope: 自訂電路從 source netlist 到可模擬 setup 的設計指引
version: v0.1.0
last_updated: 2026-03-20
updated_by: codex
---

# Designing Custom Circuits

本頁聚焦自訂電路時的設計與驗證清單。

## Checklist

1. `components` 先定義可重用參數接口（`default`/`value_ref`）。
2. `topology` 僅處理連線，不混入參數語意。
3. 優先使用 `repeat` 降低展開後維護成本。
4. 用 Expanded Netlist Preview 做 deterministic 驗證。
5. 在 Simulation 端先驗證 base mode，再開 sideband/post-processing。

## Example: FloatingQubitWithXYLine

這是一個雙 port 浮接 qubit 與 XY line 的範例。其特點是：

1. `R50` 作為兩個 port 的匹配電阻。
2. `L_jun` 透過 `parameters` 與 `value_ref` 抽成可調參數。
3. `C_xy1`、`C_xy2` 將 qubit 節點耦合到第三個 port。

可直接作為 Schema Editor 的 JSON source：

```json
{
  "name": "FloatingQubitWithXYLine",
  "components": [
    { "name": "R50", "unit": "Ohm", "default": 50 },
    { "name": "C_q", "unit": "pF", "default": 0.05814 },
    { "name": "C_g1", "unit": "pF", "default": 0.10254 },
    { "name": "C_g2", "unit": "pF", "default": 0.10189 },
    { "name": "C_xy1", "unit": "pF", "default": 0.00017 },
    { "name": "C_xy2", "unit": "pF", "default": 0.00075 },
    { "name": "L_jun", "unit": "nH", "value_ref": "L_jun" }
  ],
  "topology": [
    ["P1", "1", "0", 1],
    ["R_p1", "1", "0", "R50"],
    ["P2", "2", "0", 2],
    ["R_p2", "2", "0", "R50"],
    ["P3", "3", "0", 3],
    ["R_p3", "3", "0", "R50"],
    ["C_q", "1", "2", "C_q"],
    ["L_jun1", "1", "2", "L_jun"],
    ["L_jun2", "1", "2", "L_jun"],
    ["C_g1", "1", "0", "C_g1"],
    ["C_g2", "2", "0", "C_g2"],
    ["C_xy1", "1", "3", "C_xy1"],
    ["C_xy2", "2", "3", "C_xy2"]
  ],
  "parameters": [
    { "name": "L_jun", "default": 24, "unit": "nH" }
  ]
}
```

## Validation Notes

1. `name` 會同步成 Schema Editor 中的 canonical source name。
2. `parameters.L_jun` 與 `components[].value_ref` 對應，適合後續做 sweep。
3. 建議先在 Expanded Netlist Preview 檢查 port 編號與節點 `3` 的耦合是否符合預期，再送 Simulation。

## Related

- [Circuit Netlist](../reference/data-formats/circuit-netlist.md)
- [Schema Editor UI](../reference/app/frontend/definition/schema-editor.md)
- [Simulation Workflow](simulation-workflow.md)
