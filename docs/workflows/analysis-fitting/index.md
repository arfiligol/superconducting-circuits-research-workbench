---
aliases:
 - Analysis & Fitting
 - Analysis and Fitting
tags:
 - diataxis/how-to
 - audience/user
 - topic/analysis
status: stable
owner: docs-team
audience: user
scope: Python Analysis Core, Analysis Bridge, resonance fitting, SQUID fitting and flux analysis workflow map.
version: v2.0.0
last_updated: 2026-06-12
updated_by: codex
title: Analysis & Fitting
sidebar:
 label: Overview
 order: 10
---

# Python Analysis Core

This area answers "How do I get reusable physical parameters from traces or sweep data?" Reusable fitting / matrix algorithms belong to Python Analysis Core; Pluto can call it through `SuperconductingCircuitsAnalysisBridge`.

## Page Map

| Page | Use it when |
| --- | --- |
| [Resonance Fitting](resonance-fitting.md) | To estimate model parameters from resonance traces |
| [SQUID Fitting](squid-fitting.mdx) | To fit SQUID circuit parameters |
| [End-to-End SQUID Fitting](end-to-end-squid-fitting.mdx) | To run the complete fitting flow |
| [Flux Dependence Analysis](flux-analysis.md) | To analyze VNA flux sweep |

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
