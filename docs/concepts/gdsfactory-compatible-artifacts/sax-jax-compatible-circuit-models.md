---
aliases:
 - SAX JAX Compatible Circuit Models
 - SAX-compatible artifacts
tags:
 - diataxis/explanation
 - audience/team
 - topic/gdsfactory-compatible-artifacts
status: stable
owner: docs-team
audience: team
scope: How equivalent-circuit results should stay compatible with SAX/JAX-style downstream circuit simulation.
version: v1.0.0
last_updated: 2026-06-14
updated_by: codex
title: SAX/JAX-Compatible Circuit Models
sidebar:
 label: SAX/JAX-Compatible Models
 order: 30
---

# SAX/JAX-Compatible Circuit Models

GDSFactory ecosystem compatibility means artifact compatibility, not runtime ownership. This repo should be able to consume upstream FEM/network traces and produce equivalent-circuit artifacts that can be understood by SAX/JAX-style downstream circuit workflows.

## Compatibility Targets

- stable port names and port order
- S-matrix orientation and frequency or wavelength axis semantics
- explicit units and reference impedance
- parameterized equivalent-circuit model fields
- provenance back to upstream trace evidence
- differentiable or sweepable parameters when the model family supports it

## Non-Goals

This repo does not run GDSFactory layout, gsim FEM, gplugins process tooling, qpdk setup, mesh generation, or Palace jobs. It should document and produce compatible circuit-level artifacts from results that those tools or other upstream workflows export.

## References

- [GDSFactory gsim](https://gdsfactory.github.io/gsim/)
- [gsim Palace inductor tutorial](https://gdsfactory.github.io/gsim/nbs/palace_inductor/)
- [gplugins documentation](https://gdsfactory.github.io/gplugins/)
- [SAX documentation](https://gdsfactory.github.io/sax/)
- [SAX repository](https://github.com/flaport/sax)
