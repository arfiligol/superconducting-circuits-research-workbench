---
aliases:
 - D3 Finite-Order Port-Response Scalar Fit API
tags:
 - diataxis/reference
 - audience/team
 - topic/equivalent-circuit-modeling
status: provisional
owner: analysis-team
audience: team
scope: Workbench boundary for the D3 topology-constrained Finite-Order Port-Response scalar-formula fit.
version: v2.0.0
last_updated: 2026-07-31
updated_by: codex
title: D3 Finite-Order Port-Response Scalar Fit API
description: Define the fail-closed Workbench boundary for fitting the exact D3 scalar response in its declared basis, sparsity, and port convention.
sidebar:
 label: D3 Port-Response Fit API
 order: 45
---

# D3 Finite-Order Port-Response Scalar Fit API

The host D3 Design Target owns the physical meaning, retained basis, target
quantities, and optimization policy. This page owns only the Workbench fitting
boundary.

The intended inverse problem is

$$
S_{21}^{\mathrm{target}}(\omega)
\xrightarrow[\text{same sparsity, basis, and ports}]
{\text{scalar-formula fit}}
\left(
\widehat{\mathbf h},
\widehat{\boldsymbol\Delta},
\widehat{\boldsymbol\Sigma}_{P}(\omega),
\widehat{\mathbf W},
\widehat{\mathbf D}
\right).
$$

It is not an independent free-$LC$ circuit fit and it is not a reduced
three-mode compatibility model.

## Required fixed identity

Every fit must retain the identity declared by the source candidate:

- physical-node reduction and ordered finite-order basis;
- Exact doubled and RWA representation conventions;
- allowed matrix sparsity, symmetry, and passivity relations;
- port count, port order, attachment coordinates, reference impedance, and
  reference planes;
- direct-through convention and calibration;
- the declared finite-dimensional parameterization of
  $\boldsymbol\Sigma_P(\omega)$;
- frequency grid, fit window, units, and phasor convention.

An arbitrary sampled self-energy or an unconstrained state-space realization
is ineligible because either can absorb the response without preserving the
declared physical coordinates.

## Output and closure

The result must publish:

- fitted and matrix-calculated response parameters in the same basis;
- calibrated complex-$S_{21}$ reconstruction and residuals;
- fixed/free registry, bounds, starts, and optimizer evidence;
- passivity, stability, pole, and response-resolution evidence;
- an identifiability result for the declared free coordinates.

Stage 2 uses its circuit-derived matrices as the numerical authority. The
scalar-formula fit is an independent recovery check against the solver trace.
Stage 3 may use the same fitter as a response-effective bridge only after the
Stage-2 blind-recovery check passes.

## Removed reduced route

The former reduced runtime fitted seven RWA coefficients with a filter-only
port projection and profiled background terms. It did not evaluate the
declared Exact finite-order scalar formula and is not part of this API. Its
Python entry point, Julia bridge wrapper, schema, and diagnostic scripts have
been removed rather than retained as a misleading fallback.

## Current execution status

The exact scalar-formula inverse fitter is `CONVERGING` and has no public
production entry point yet. Callers must fail closed until the D3 fixed/free
matrix registry and self-energy parameterization are implemented and reviewed.
The forward Exact-12/RWA-6 evaluator remains available independently.
