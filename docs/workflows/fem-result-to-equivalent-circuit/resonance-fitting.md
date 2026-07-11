---
aliases:
 - Resonance Fitting Workflow
 - Resonance fitting workflow
tags:
 - audience/team
status: stable
owner: docs-team
audience: team
scope: Resonance fitting workflow and the explicit boundary of the current ideal two-junction LC surrogate
version: v0.3.0
last_updated: 2026-07-10
updated_by: codex
sidebar:
 label: Resonance Fitting
 order: 20
---

# Resonance Fitting

Resonance fitting extracts circuit parameters from compatible traces. In the research path, traces come from Pluto sweeps, exported simulator files, or local analysis arrays, and the fitting algorithm belongs in Python Analysis Core when it becomes reusable.

For reusable Josephson and SQUID semantics, use:

- [Josephson Current, Phase, Energy, and Inductance](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/josephson-physics/josephson-current-phase-energy-and-inductance.qmd)
- [DC-SQUID Flux Tunability](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/josephson-physics/dc-squid-flux-tunability.qmd)

For an isolated hanger response measured as complex transmission, use:

- [Notch Resonator Complex S21 Fit](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/notch-resonator-complex-s21-fit.qmd)
- [Network Trace Views](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/network-trace-views.qmd)

## Workflow

1. Identify the trace family: Im(Y), S-parameter phase, magnitude, or complex S-parameter.
2. Confirm units, frequency axis, and source circuit assumptions.
3. Use Pluto plus Analysis Bridge when the analysis starts from Julia Core simulation output.
4. Use Python Notebook when the analysis starts from exported files or Python-native tables.
5. Promote reusable fitting logic into Python Analysis Core with focused tests.

The trace family selects the model; it is not merely a plotting choice. An
Im(Y) zero crossing, a sampled $|S_{21}|$ dip, an isolated complex-notch fit,
and a broadband rational pole are different estimators with different evidence
contracts. A notebook must name which estimator owns each published field.

## Physics Check

Use Im(Y) zero crossings to estimate resonance frequency.
Then fit the resonance trend against design or sweep parameters.

```text
f = 1 / (2π * sqrt((L_jun / 2 + L_s) * C_eff))
```

In this implemented surrogate, `L_jun` is the supplied small-signal inductance
of each of two identical junctions, so `L_jun / 2` is their parallel
combination. This model does not map external flux to `L_jun` and must not be
presented as a full flux-tunable DC-SQUID model.

## Complex-S21 Notch Route

Use the shared `fit_complex_s21_notch` application entry point when the source
window contains one isolated hanger-like feature and carries the required
network metadata. The raw sampled magnitude minimum is an initializer
diagnostic, not the promoted resonance estimate.

The shared API owns trace validation, fit-window application, the direct
complex least-squares call, and the numerical evidence payload. A consuming
notebook owns source-artifact identity, evidence tables, and the explicit stop
before any Human acceptance or downstream design promotion. Do not add a local
fitter, vector-fit fallback, or default quality threshold in the notebook.

## Result Shape

A reusable fitting result should record:

- input trace references
- fitting configuration
- fitted parameters
- error metrics
- plots or tables used as evidence
- provenance that links back to source files or notebooks
- a separate numerical status and physical-interpretation status
- any Human acceptance decision together with its stated rationale

## Related

- [SQUID Fitting](squid-fitting.mdx)
- [Flux Dependence Analysis](flux-analysis.md)
- [S-Parameter Resonance Fit Theory](../../concepts/equivalent-circuit-modeling/resonance-poles-and-circle-fit.md)
- [Python Core](../../reference/core/python-core.mdx)
