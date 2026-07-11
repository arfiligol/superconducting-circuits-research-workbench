---
aliases:
 - Network Trace Views
 - S Y Z matrix traces
tags:
 - diataxis/explanation
 - audience/team
 - topic/equivalent-circuit-modeling
status: stable
owner: docs-team
audience: team
scope: Handoff from Workbench S/Y/Z implementations to the canonical SCQ_Design Network Trace Views node.
version: v1.1.0
last_updated: 2026-07-10
updated_by: codex
title: Network Trace Views
sidebar:
 label: Network Trace Views
 order: 20
---

# Network Trace Views

The reusable physics and engineering explanation is owned by the SCQ_Design
knowledge base:

- [Canonical knowledge: Network Trace Views](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/network-trace-views.qmd)
- [Canonical knowledge: Port Reference Impedance Semantics](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/simulation/port-reference-impedance-semantics.qmd)

This repository owns only the concrete API, implementation, and workflow entry
points that consume S-parameter traces:

- `core/python/analysis/superconducting_circuits_analysis/superconducting_circuits_analysis/domain/math/s_parameters.py`
  owns the numerical S21 models and fitting implementations.
- `core/python/analysis/superconducting_circuits_analysis/superconducting_circuits_analysis/application/analysis/fitting/s_parameters.py`
  owns trace validation, fit-window handling, orchestration, and result payloads.

Do not duplicate reusable network-trace theory here; update the canonical page
and keep only repository-specific contracts at these entry points.
