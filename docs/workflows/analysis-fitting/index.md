---
aliases:
  - Analysis & Fitting
  - 分析與擬合
tags:
  - diataxis/how-to
  - audience/user
  - topic/analysis
status: stable
owner: docs-team
audience: user
scope: Python Analysis Core、Analysis Bridge、resonance fitting、SQUID fitting 與 flux analysis workflow map。
version: v2.0.0
last_updated: 2026-06-12
updated_by: codex
title: Analysis & Fitting
sidebar:
  label: Overview
  order: 10
---

# Python Analysis Core

這一區回答「我要怎麼從 traces 或 sweep data 得到可重用的物理參數」。Reusable fitting / matrix algorithms 屬於 Python Analysis Core；Pluto 可以透過 `SuperconductingCircuitsAnalysisBridge` 呼叫它。

## Page Map

| Page | Use it when |
| --- | --- |
| [Resonance Fitting](resonance-fitting.md) | 要從 resonance traces 估計模型參數 |
| [SQUID Fitting](squid-fitting.mdx) | 要擬合 SQUID circuit parameters |
| [End-to-End SQUID Fitting](end-to-end-squid-fitting.mdx) | 要跑完整 fitting flow |
| [Flux Dependence Analysis](flux-analysis.md) | 要分析 VNA flux sweep |

## Owner Model

| Surface | Role |
| --- | --- |
| Python Analysis Core | owns reusable fitting, preprocessing, matrix analysis, and JSON-friendly result shapes |
| Julia Analysis Bridge | exposes selected Python Analysis Core functions to Pluto through PythonCall |
| Pluto Notebook | selects traces, parameters, plots, and research-facing analysis flow |
| Python Notebook | performs Python-native file inspection, fitting experiments, and report assembly |

## Related

- [Research Data & Evidence](../research-data/index.mdx)
- [Python Core](../../reference/core/python-core.mdx)
- [Notebook Interface](../../reference/notebooks/index.md)
- [Analysis Result Contract](../../reference/data-formats/analysis-result.mdx)
