---
aliases:
  - "Fitting SQUID Parameters"
  - "SQUID 參數擬合"
tags:
  - diataxis/how-to
  - audience/user
  - sot/true
  - topic/analysis
status: stable
owner: team
audience: user
scope: "如何從 Admittance 數據擬合 SQUID 電路參數 (Ls, C)"
version: v1.1.0
last_updated: 2026-01-31
updated_by: team
---

# Fitting SQUID Models

本指南說明 LC-SQUID fitting 在新架構中的執行邊界。
Heavy fitting belongs to the Julia Runner compute plane or an explicit research notebook kernel.

!!! info "前置條件"
    - 數據已匯入資料庫（請參閱 [Ingest HFSS Admittance Data](../ingest-data/hfss-admittance.md)）。
    - 知道目標 Dataset 的 **名稱 (Name)** 或 **ID**。

---

## 選擇擬合策略

根據您的電路設計與數據特性，選擇合適的擬合模式：

| 模式 | 適用情境 | Runner input |
|------|----------|------------|
| **Standard (With Ls)** | 一般情況，需同時決定 $L_s$ 與 $C$ | `mode = "standard"` |
| **Fixed Capacitance** | 已知量測或設計的準確電容值，僅需優化 $L_s$ | `fixed_capacitance` |
| **Ideal LC (No Ls)** | 忽略系列電感，僅擬合純 LC 共振 (較少用) | `mode = "ideal_lc"` |

---

## 操作步驟

### Notebook

Use a Pluto notebook when you need direct exploration or model iteration.
The notebook may call Julia Core directly and inspect intermediate arrays.

### Application task

Use the Application Interface when the fit should become a tracked task.
The backend creates a task such as `julia_analysis_resonance_fit`, the Julia Runner writes result artifacts, and the backend validates and publishes derived results.

!!! warning "Initial implementation scope"
    The first Julia Runner implementation only needs `julia_runner_smoke` and `julia_simulation_parameter_sweep`.
    LC-SQUID fitting is a compute-plane task kind reserved by the contract, not a required first task implementation.

---

## 結果檢視

擬合完成後，正式結果必須由 Python Backend 發布：

1. Runner writes staging artifacts under `data/staging/tasks/<task_id>/`.
2. Backend validates the manifest and result arrays.
3. Backend records provenance and publishes canonical metadata/artifacts.
4. Application or notebook reads the official result through backend APIs.

---

## 相關參考

- [Tutorial: End-to-End Fitting](../../tutorials/end-to-end-fitting.md)
- [Julia Runner Compute Plane](../../reference/architecture/julia-runner-compute-plane.md)
