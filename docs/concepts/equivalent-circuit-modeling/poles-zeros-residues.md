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
scope: Handoff from Workbench pole/residue implementations to the canonical SCQ_Design Poles, Zeros, and Residues node.
version: v1.1.0
last_updated: 2026-07-10
updated_by: codex
title: Poles, Zeros, And Residues
sidebar:
 label: Poles, Zeros, And Residues
 order: 30
---

# Poles, Zeros, And Residues

The reusable interpretation of poles, zeros, residues, and residuals is owned
by the SCQ_Design knowledge base:

- [Canonical knowledge: Poles, Zeros, And Residues](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/poles-zeros-residues.qmd)

This repository owns only the concrete implementation and workflow entry
points:

- `core/python/analysis/superconducting_circuits_analysis/superconducting_circuits_analysis/domain/math/s_parameters.py`
  owns `MultiResonanceVectorFitter` and its repository-specific pole extraction.
- `core/python/analysis/superconducting_circuits_analysis/superconducting_circuits_analysis/application/analysis/fitting/s_parameters.py`
  owns the `fit_complex_s21_vector` application payload.

Do not restate pole or residue theory here; update the canonical page and keep
only exact implementation contracts in this repository.
