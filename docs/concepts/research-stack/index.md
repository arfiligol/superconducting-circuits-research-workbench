---
aliases:
  - Research Stack
  - Research Runtime Boundaries
tags:
  - diataxis/explanation
  - audience/team
  - topic/architecture
status: stable
owner: docs-team
audience: team
scope: Research-first responsibility model for Pluto, Julia Core, Visualizer, Analysis Bridge, Python Analysis Core, and Python notebooks.
version: v1.0.0
last_updated: 2026-06-12
updated_by: codex
title: Research Stack
sidebar:
  label: Overview
  order: 10
---

# Research Stack

The research stack keeps fast notebook work separate from reusable package code. Pluto is the direct Julia research surface; Julia Core owns reusable circuit semantics; Python Analysis Core owns reusable fitting and matrix algorithms.

## Responsibility Model

| Layer | Owns | Does not own |
| --- | --- | --- |
| Pluto Notebook | research execution, sliders, figures, solver experiments | reusable package APIs |
| Julia Core | components, systems, compiler model, simulation helpers | plotting libraries or Python calls |
| Julia Visualizer | PlotlyJS figure construction for Julia traces | circuit semantics |
| Analysis Bridge | explicit Pluto-to-Python analysis calls | Python algorithm ownership |
| Python Analysis Core | fitting, preprocessing, matrix analysis, plain result shapes | notebook narrative |
| Python Notebook | file inspection, Python-native analysis sketches, report evidence | reusable package contracts |

## Design Pressure

Notebook cells should stay fast to change. Package code should stay small, testable, and reusable. When the same cell logic appears in multiple studies, move the stable computation into Julia Core or Python Analysis Core and keep notebooks as evidence surfaces.

## Related

- [Pluto Research](../../workflows/pluto/index.md)
- [Julia Core Circuit Authoring](../../workflows/circuit-authoring/index.md)
- [Python Analysis Core](../../workflows/analysis-fitting/index.md)
- [Python Notebooks](../../workflows/python-notebooks/index.md)
