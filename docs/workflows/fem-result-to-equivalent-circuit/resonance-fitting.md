---
aliases:
 - Resonance Fitting Workflow
 - Resonance fitting workflow
tags:
 - audience/team
status: stable
owner: docs-team
audience: team
scope: Workbench response-fitting workflow and handoff to canonical extraction semantics.
version: v1.1.0
last_updated: 2026-07-16
updated_by: codex
sidebar:
 label: Resonance Fitting
 order: 20
---

# Resonance Fitting

Resonance fitting extracts circuit parameters from valid traces. In the research path, traces come from Pluto sweeps, exported simulator files, or local analysis arrays, and the fitting algorithm belongs in Python Analysis Core when it becomes reusable.

For reusable Josephson and SQUID semantics, use:

- [Josephson Current, Phase, Energy, and Inductance](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/josephson-physics/josephson-current-phase-energy-and-inductance.qmd)
- [DC-SQUID Flux Tunability](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/josephson-physics/dc-squid-flux-tunability.qmd)

For an isolated hanger response measured as complex transmission, use:

- [Notch Resonator Complex S21 Fit](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/notch-resonator-complex-s21-fit.qmd)
- [Network Trace Views](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/network-trace-views.qmd)

For the frequency layers, initial-reference construction, and three-mode final
fit, use:

- [Bare, Coupling-On Diagonal, and Hybridized Modes](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/readout/bare-vs-hybridized-readout-filter-modes.qmd)
- [D3 Initial Reference Topologies](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/worked-examples/d3-initial-reference-topologies.qmd)
- [D3 Full Qubit--Readout--Filter Complex Response Fit](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/worked-examples/d3-full-qrp-complex-response-fit.qmd)

## Workflow

1. Identify the physical circuit, mode layer, and trace family: processed
   driving-point $Y$, complex $S$, or transfer $Z$.
2. Confirm units, frequency axis, port/load treatment, phasor convention, and
   source-circuit assumptions.
3. Use Pluto plus Analysis Bridge when the analysis starts from Julia Core simulation output.
4. Use Python Notebook when the analysis starts from exported files or Python-native tables.
5. Fit the eligible complex-response estimator: a topology-specific formula,
   a declared $Y/Z$ root, a uniquely owned isolated scalar Vector Fitting pole,
   or the topology-constrained full-$\mathcal T_{\mathrm{QRP}}$ complex-$S_{21}$
   $L_J$-sweep model. Retain residuals,
   candidates, stability evidence, and provenance.
6. Promote reusable fitting logic into Python Analysis Core with focused tests.

The trace family selects the model; it is not merely a plotting choice. An
Im(Y) zero crossing, a sampled $|S_{21}|$ dip, an isolated complex-notch fit,
and a broadband rational pole are different estimators with different evidence
contracts. A notebook must name which estimator owns each published field.
Closed generalized eigenfrequencies remain cross-checks. A scalar Vector
Fitting pole may own frequency and total linewidth only when the circuit
topology and continuation uniquely identify one isolated response mode; it does
not establish that identity by itself.

## Physics Check

For a floating qubit, form the compensated differential driving-point
admittance in the canonical order: evidence-authorized port-basis PTC,
power-conjugate coordinate transform, then zero-injection Kron reduction. Track
the intended root of $\operatorname{Im}Y_{\mathrm{diff}}=0$ with its slope,
$\operatorname{Re}Y$ at the root, complete candidate list, nearby
singularities, and continuation anchor. A nearest-zero search is not eligible.
The result is a linearized circuit frequency, not $f_{01}$.

For an isolated readout or filter that disappears from transmission at zero
observation coupling, fit the complex $S_{21}$ response independently at no
fewer than five positive $C_{\mathrm{probe}}$ values and extrapolate fitted
frequency to $C_{\mathrm{probe}}\to0$. Keep physical finite three-branch IDC
loading only in the loaded-filter reference. Configure the observation sweep
with `c_probe_capacitances_fF`; physical Layout loading uses one
provenance-bearing geometry mapping that returns all three IDC capacitances.

An eligible scalar Vector Fitting complex pole may supply each finite-probe
frequency and total linewidth. Track the same pole across the probe sweep and
check fit-window, model-order, residue, nearby-pole, and complex-residual
stability. The topology-specific `notch_s21` fit may run on the same trace as
an independent physical-model interpretation and comparison; it is not a
required validator of the Vector Fitting pole.

## Sampling and refinement gate

Pole fitting does not recover evidence absent from the sampled response. Before
promotion, retain the local frequency step and repeat the extraction on a
genuinely denser source trace. A trace whose local step is larger than the
extracted total linewidth is too coarse for promotion, even if Vector Fitting
converges with a small residual. Interpolation of the original samples does not
satisfy this gate.

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
before any Human acceptance or downstream design promotion. Reuse the shared
notch and Vector Fitting entry points; do not add a local fitter or default
quality threshold in the notebook.

For an eligible isolated hanger, both the scalar Vector Fitting pole and the
physical complex-$S_{21}$ fit may estimate resonance frequency and total
linewidth under their respective evidence gates. Vector Fitting may provide
the formal pole extractor; the notch formula provides independent hanger-model
interpretation. Internal/external decomposition is authoritative only when
complex $Q_c$, reference plane, background, and coupling topology are all
identified. In the current lossless D3 filter,
$\kappa_{p,\mathrm{LB},\mathrm{tot}}=\kappa_{p,\mathrm{LB},\mathrm{ext}}$;
the zero-probe readout reference has $\kappa_{r,\mathrm{LB}}=0$.

## D3 winner-only response comparison

The current D3 Same-Die search does not fit an Equivalent Circuit. It evaluates
physical candidates with the direct fixed-node Hybridized Circuit and obtains
the target quantities from the complete-complement open-EOM reduction.

After the search fixes one winner, pump-off harmonic balance and a constrained
C11 fit may compare the calibrated complex response. Those calculations are
diagnostic response comparisons. They do not create candidate coordinates,
change the winner, or replace the direct quantity authority. Any downstream
Equivalent representation must retain an explicit coordinate and response map
back to the same physical winner.

## Result Shape

A reusable fitting result should record:

- input trace references
- fitting configuration
- fitted parameters
- error metrics
- plots or tables used as evidence
- provenance that links back to source files or notebooks
- a separate numerical status and physical-interpretation status
- per-point `frequency_step_hz`, `linewidth_hz`, `samples_per_linewidth`,
  refinement level, and pole/linewidth shifts with declared tolerances
- any Human acceptance decision together with its stated rationale

## Related

- [SQUID Fitting](squid-fitting.mdx)
- [Flux Dependence Analysis](flux-analysis.md)
- [S-Parameter Resonance Fit Theory](../../concepts/equivalent-circuit-modeling/resonance-poles-and-circle-fit.md)
- [Python Core](../../reference/core/python-core.mdx)
