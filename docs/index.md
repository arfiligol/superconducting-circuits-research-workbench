---
aliases:
  - Technical Documentation
  - 技術文件
tags:
  - diataxis/reference
  - audience/user
  - sot/true
  - topic/documentation
status: stable
owner: docs-team
audience: user
scope: "Zensical 技術文件入口：Tutorials、How-to、Explanation、Reference 與 Notebooks"
version: v2.0.0
last_updated: 2026-06-04
updated_by: codex
title: 技術文件
---

# 技術文件

這裡是 Superconducting Circuits Research Workbench 的技術文件入口。公開介紹頁由 Astro 站負責；Zensical 文件站只保留 Tutorials、How-to、Explanation、Reference 與 notebook authoring / inspection 類內容。

## 入口

| 區域 | 用途 |
| --- | --- |
| [Tutorials](tutorials/index.md) | 跟著完整流程理解 circuit definition、simulation 與分析工作流 |
| [How-to Guides](how-to/index.md) | 解決特定操作問題，例如資料匯入、模擬、Pluto authoring 與管理資料 |
| [Explanation](explanation/index.md) | 釐清物理、架構與設計取捨 |
| [Reference](reference/index.md) | 查找架構契約、資料格式、app/backend/frontend、Julia Core 與 guardrails |
| [Notebooks](reference/notebooks/index.md) | 確認 Pluto / Python notebook 的研究與檢查邊界 |

## 公開站分工

| URL | Owner | Role |
| --- | --- | --- |
| `/` | Astro site | 介紹頁、產品定位、受眾與主要入口 |
| `/about/` | Astro site | 平台定位、研究閉環與邊界 |
| `/docs/` | Zensical docs | 技術文件與 Source of Truth |

!!! info "維護邊界"
    若內容是介紹頁視覺敘事、受眾定位或公開 landing page，放在 `site/`。若內容是技術契約、工作流、reference 或 guardrails，放在 `docs/` 並同步 `zensical.toml` nav。
