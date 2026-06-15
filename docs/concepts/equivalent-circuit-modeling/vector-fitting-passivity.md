---
aliases:
 - Vector Fitting And Passivity
tags:
 - diataxis/explanation
 - audience/team
 - topic/equivalent-circuit-modeling
status: stable
owner: docs-team
audience: team
scope: Why rational equivalent models need vector fitting, stability, passivity, and residual checks.
version: v1.0.0
last_updated: 2026-06-14
updated_by: codex
title: Vector Fitting And Passivity
sidebar:
 label: Vector Fitting And Passivity
 order: 40
---

# Vector Fitting And Passivity

Vector fitting is the practical route when a broadband or multiport network cannot be captured by one compact RLC feature. It approximates frequency-domain responses with poles, residues, and direct terms that can be inspected, exported, and compared.

## Why Passivity Matters

A fitted network can match samples and still be unsafe as a connected model. If a macromodel is non-passive, it can inject energy into a downstream simulator. That is why passivity, stability, reciprocity, and residual checks are part of the modeling workflow, not optional polish.

## Fit Review Checklist

- Fit S, Y, or Z according to the physical question, then cross-check in another domain when possible.
- Inspect pole locations and residues, not only RMSE.
- Check per-port and cross-port residuals over the full frequency range.
- Check passivity before using the model in a connected simulation.
- Record the selected pole count and why the residuals justify it.

## References

- [SINTEF Vector Fitting](https://www.sintef.no/en/software/vector-fitting/)
- [Gustavsen and Semlyen, Rational approximation of frequency domain responses by vector fitting](https://www.sintef.no/globalassets/project/vectfit/vector_fitting_1999.pdf)
- [scikit-rf Vector Fitting tutorial](https://scikit-rf.readthedocs.io/en/latest/tutorials/VectorFitting.html)
- [scikit-rf vector_fit API](https://scikit-rf.readthedocs.io/en/latest/api/generated/skrf.vectorFitting.VectorFitting.vector_fit.html)
- [scikit-rf passivity_enforce API](https://scikit-rf.readthedocs.io/en/latest/api/generated/skrf.vectorFitting.VectorFitting.passivity_enforce.html)
