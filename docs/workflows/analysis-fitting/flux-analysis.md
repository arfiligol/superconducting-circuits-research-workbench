---
aliases:
  - Flux Analysis Workflow
  - 磁通分析工作流
tags:
  - audience/team
status: stable
owner: docs-team
audience: team
scope: 磁通掃描分析在 notebook research 與 Python Analysis Core 下的流程
version: v0.2.1
last_updated: 2026-05-29
updated_by: codex
sidebar:
  label: Flux Dependence Analysis
  order: 50
---

# Flux Dependence Analysis

Flux analysis visualizes how resonance changes with external flux or bias current.
Use notebooks for exploratory flux maps, axis validation, resonance picking, and report figures.

## Workflow

```mermaid
flowchart LR
    VNA["VNA Flux Sweep"] --> Files["Local Export Files"]
    Files --> Notebook["Notebook Analysis"]
    Notebook --> Core["Reusable Analysis Helper"]
```

## Physics Check

SQUID inductance is periodic in flux:

```text
L_jun(Phi) = Phi0 / (2*pi*Ic*abs(cos(pi*Phi/Phi0)))
```

As inductance changes, resonance frequency shifts.
The expected map usually shows periodic arches or sweet spots where frequency is less sensitive to flux.

## Usage

1. Keep the VNA export and source metadata together.
2. Verify axes, units, and flux/bias coordinate naming.
3. Use a Python notebook to inspect magnitude and phase maps.
4. Promote repeated extraction logic into Python Analysis Core.

## Result Shape

Tracked analysis should record:

- input trace references
- flux/bias axis metadata
- phase wrapping or unwrapping settings
- extracted resonance points
- plots or summary tables as evidence

## Related

- [Notebook Interface](../../reference/notebooks/index.md)
- [Python Core](../../reference/core/python-core.mdx)
