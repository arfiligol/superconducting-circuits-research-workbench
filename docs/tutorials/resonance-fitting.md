---
aliases:
  - Resonance Fitting Workflow
  - 共振擬合工作流
tags:
  - audience/team
status: stable
owner: docs-team
audience: team
scope: SQUID resonance fitting workflow under the Julia Runner architecture
version: v0.2.0
last_updated: 2026-05-28
updated_by: codex
---

# Resonance Fitting

Resonance fitting extracts circuit parameters from compatible traces.
In the current architecture, the data authority is TraceStore and the compute authority is either an explicit notebook kernel or a Julia Runner task.

## Workflow

1. Ingest or publish traces into TraceStore.
2. Inspect Im(Y), S-parameter phase, or other compatible traces in the Raw Data Browser.
3. Use a Pluto/Python notebook for exploratory fitting.
4. Add a Julia Runner task for tracked fitting and publication.

## Physics Check

Use Im(Y) zero crossings to estimate resonance frequency.
Then fit the resonance trend against design or sweep parameters.

```text
f = 1 / (2π * sqrt((L_jun / 2 + L_s) * C_eff))
```

## Result Contract

A tracked fitting run should publish:

- input trace references
- fitting configuration
- fitted parameters
- error metrics
- plots or tables as artifacts
- provenance that links back to the source task and trace batch

## Related

- [SQUID Fitting](../how-to/fit-model/squid.md)
- [TraceStore Zarr](../reference/architecture/trace-store-zarr.md)
- [Runner Result Manifest](../reference/architecture/runner-result-manifest.md)
