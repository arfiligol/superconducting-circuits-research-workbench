---
aliases:
  - Resonance Fitting Workflow
  - 共振擬合工作流
tags:
  - audience/team
status: stable
owner: docs-team
audience: team
scope: SQUID resonance fitting workflow for Python Analysis Core and notebook research
version: v0.2.0
last_updated: 2026-05-28
updated_by: codex
sidebar:
  label: Resonance Fitting
  order: 20
---

# Resonance Fitting

Resonance fitting extracts circuit parameters from compatible traces. In the research path, traces come from Pluto sweeps, exported simulator files, or local analysis arrays, and the fitting algorithm belongs in Python Analysis Core when it becomes reusable.

## Workflow

1. Identify the trace family: Im(Y), S-parameter phase, magnitude, or complex S-parameter.
2. Confirm units, frequency axis, and source circuit assumptions.
3. Use Pluto plus Analysis Bridge when the analysis starts from Julia Core simulation output.
4. Use Python Notebook when the analysis starts from exported files or Python-native tables.
5. Promote reusable fitting logic into Python Analysis Core with focused tests.

## Physics Check

Use Im(Y) zero crossings to estimate resonance frequency.
Then fit the resonance trend against design or sweep parameters.

```text
f = 1 / (2π * sqrt((L_jun / 2 + L_s) * C_eff))
```

## Result Shape

A reusable fitting result should record:

- input trace references
- fitting configuration
- fitted parameters
- error metrics
- plots or tables used as evidence
- provenance that links back to source files or notebooks

## Related

- [SQUID Fitting](squid-fitting.mdx)
- [Python Core](../../reference/core/python-core.mdx)
