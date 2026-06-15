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
scope: How S/Y/Z matrix traces support different equivalent-circuit modeling questions.
version: v1.0.0
last_updated: 2026-06-14
updated_by: codex
title: Network Trace Views
sidebar:
 label: Network Trace Views
 order: 20
---

# Network Trace Views

An external FEM result is not just a plot. It is a frequency-indexed network model with port order, reference impedance, units, and provenance. Equivalent-circuit modeling starts by choosing the view that makes the physics visible.

## S, Y, And Z Views

| View | Useful for | Main risk |
| --- | --- | --- |
| S matrix | measurement/FEM exchange, port matching, SAX-style downstream use | reference impedance and port-order mistakes |
| Z matrix | impedance peaks, series behavior, differential/common-mode reductions | ill-conditioned conversion near singular responses |
| Y matrix | shunt branches, capacitance/conductance behavior, admittance poles and zeros | unstable interpretation when the S-to-Y conversion assumptions are wrong |

Do not fit blindly in only one domain. A good equivalent-circuit candidate should explain the response in the domain where the physics is easiest to inspect and should remain plausible after conversion.

## Metadata Required Before Modeling

- frequency axis and unit
- complex trace convention
- port names and port order
- reference impedance when S-parameters are involved
- upstream solver/export provenance
- known symmetry, reciprocity, or grounding assumptions

## References

- [Touchstone 2.1 specification](https://ibis.org/touchstone_ver2.1/)
- [scikit-rf Networks tutorial](https://scikit-rf.readthedocs.io/en/latest/tutorials/Networks.html)
- [SAX documentation](https://gdsfactory.github.io/sax/)
- [External FEM Result Contract](../../reference/research-contracts/external-fem-result-contract.md)
