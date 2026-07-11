---
aliases:
 - "Resonance Frequency Extraction via Complex S-Parameters"
 - "S-parameter resonance frequency extraction"
tags:
 - diataxis/explanation
 - audience/team
 - sot/true
 - topic/physics
 - topic/simulation
status: provisional
owner: docs-team
audience: team
scope: "Handoff from Workbench complex-notch fitting APIs to the canonical SCQ_Design Notch Resonator Complex S21 Fit node"
version: v0.2.0
last_updated: 2026-07-10
updated_by: codex
sidebar:
 label: S-Parameter Resonance Fit Theory
 order: 100
---

# How is the resonant frequency calculated from the S parameters?

The reusable physics and engineering explanation is owned by the SCQ_Design
knowledge base:

- [Canonical knowledge: Notch Resonator Complex S21 Fit](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/notch-resonator-complex-s21-fit.qmd)

This repository owns only the concrete API and implementation entry points:

- `core/python/analysis/superconducting_circuits_analysis/superconducting_circuits_analysis/domain/math/s_parameters.py`
  owns `notch_s21`, `estimate_notch_initial_guess`, and `fit_notch_s21`: the
  numerical model, initializer, and direct nonlinear complex least-squares fit.
- `core/python/analysis/superconducting_circuits_analysis/superconducting_circuits_analysis/application/analysis/fitting/s_parameters.py`
  owns `fit_complex_s21_notch`: trace validation, optional fit-window handling,
  fit orchestration, and the application result payload.

`fit_notch_s21` is a direct nonlinear fit over complex residuals; it is not an
algebraic circle fit, even though both routes use complex resonance geometry.
This repository currently implements only the direct nonlinear route and has no
algebraic circle-fit API or implementation.

## Shared Application Contract

`fit_complex_s21_notch` accepts one strictly increasing complex-$S_{21}$ trace,
an optional fit window, and either no initial guess or one complete physical
initial-guess record. It returns a failed result when the selected samples do
not bracket the candidate notch or when the numerical solve cannot satisfy the
declared model contract.

A successful result publishes four distinct kinds of evidence:

- physical fit parameters, raw $Q_i^{-1}$, and its exact algebraic status;
- the actual initial guess plus the selected frequency window and internal
  scaling;
- optimizer termination details; and
- the fitted complex trace with explicitly named complex-$S_{21}$ residual
  metrics.

Requested window edges and the first/last samples actually used are reported
separately. Every required parameter, curve sample, residual metric, and
optimizer diagnostic must be finite in a successful result; otherwise the API
returns an explicit failure instead of replacing invalid evidence with nulls.

Application `status = success` means numerical convergence only. In
particular, `qi_status = nonphysical` preserves a converged curve for audit but
rejects a finite passive-$Q_i$ interpretation. This API does not encode RMSE,
$R^2$, residual-shape, stability, or near-zero-$Q_i^{-1}$ acceptance
thresholds; those remain Human decisions recorded by the consuming workflow.

## D3 Evidence Handoff

[Python Notebook 02](https://github.com/arfiligol/superconducting-circuits-research-workbench/blob/main/notebooks/python/02_filter_frequency_loading_analysis.py)
consumes only trace paths named by the current fine-sweep manifest and publishes
candidate fit and residual tables. It does not own accepted loaded-bare
frequencies, $C_{\mathrm{ext}}$ regression, linewidth, length correction, or
design promotion. Those downstream steps fail explicitly until the required
source metadata and Human decisions are recorded.

Do not duplicate the reusable fitting theory here; update the canonical page
and keep only repository-specific contracts at these entry points.
