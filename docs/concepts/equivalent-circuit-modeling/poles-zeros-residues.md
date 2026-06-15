---
aliases:
 - Poles Zeros Residues
tags:
 - diataxis/explanation
 - audience/team
 - topic/equivalent-circuit-modeling
status: stable
owner: docs-team
audience: team
scope: How poles, zeros, residues, and residuals guide equivalent-circuit model choice.
version: v1.0.0
last_updated: 2026-06-14
updated_by: codex
title: Poles, Zeros, And Residues
sidebar:
 label: Poles, Zeros, And Residues
 order: 30
---

# Poles, Zeros, And Residues

Poles, zeros, residues, and residuals are not just fitting artifacts. They are evidence for which equivalent-circuit family is plausible.

## Modeling Use

| Observation | Modeling pressure |
| --- | --- |
| isolated resonance feature | compact series or parallel RLC candidate |
| repeated mode spacing | distributed RLGC or transmission-line model |
| complex-conjugate pole pair | resonant mode with damping and coupling |
| large residue on a port pair | strong participation or coupling path |
| structured residual after low-order fit | missing branch, mode, port convention, or distributed effect |
| non-passive fitted response | model may inject energy and should not be connected downstream |

The goal is not the lowest numeric error alone. The goal is the simplest physical model that explains the features and survives checks across the relevant frequency band.

## Researcher Checklist

- Which domain shows the feature most clearly: S, Y, or Z?
- Are the dominant poles stable and physically plausible?
- Do residues point to a reasonable coupling topology?
- Does the residual reveal a missing mode or just measurement/noise floor?
- Does the fitted model remain passive and reciprocal where expected?

## References

- [SINTEF Vector Fitting](https://www.sintef.no/en/software/vector-fitting/)
- [Gustavsen and Semlyen, Rational approximation of frequency domain responses by vector fitting](https://www.sintef.no/globalassets/project/vectfit/vector_fitting_1999.pdf)
- [scikit-rf Vector Fitting tutorial](https://scikit-rf.readthedocs.io/en/latest/tutorials/VectorFitting.html)
- [scikit-rf vector_fit API](https://scikit-rf.readthedocs.io/en/latest/api/generated/skrf.vectorFitting.VectorFitting.vector_fit.html)
- [NIST, extracting distributed circuit parameters from S-parameters](https://www.nist.gov/publications/how-extract-distributed-circuit-parameters-scattering-parameters-transmission-line)
