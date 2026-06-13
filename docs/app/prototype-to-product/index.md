---
aliases:
 - Prototype To Product
 - Notebook Prototype To Product
 - App Prototyping Workflow
tags:
 - diataxis/how-to
 - audience/team
 - topic/productization
 - topic/notebooks
status: stable
owner: docs-team
audience: team
scope: Workflow for moving Pluto and Python Notebook prototypes into reusable Core, Analysis Core, Runner, Backend, or Product App surfaces.
version: v1.0.0
last_updated: 2026-06-12
updated_by: codex
sidebar:
 label: Overview
 order: 10
---

# Prototype To Product

Use this workflow when a notebook idea is no longer just exploration. The goal is to keep research fast while moving stable responsibilities into the correct owner.

## Decide The Owner

| Prototype signal | Move the stable part to |
| --- | --- |
| Reusable circuit construction, component composition, CircuitPlan, compiler, sweep, or extraction logic | Julia Core or a component library |
| Reusable fitting, preprocessing, matrix analysis, or JSON-friendly analysis result shape | Python Analysis Core |
| Product task submission, ResultView inspection, Backend metadata checks, or App API assumptions | Python Notebook first, then Product App |
| Async compute execution, staged Zarr, manifest, progress, completion, cancellation | Julia Runner + Backend task/result contracts |
| Repeated user interaction that should become a product workflow | Product App |

## Recommended Flow

```text
Pluto Notebook
 -> reusable Julia Core / component-library logic
 -> optional Python Analysis Core through Analysis Bridge
 -> Python Notebook validation for app-facing data/API/task assumptions
 -> Product App contract and implementation
```

Do not turn Python Notebook into the normal Julia compute cockpit. It may read data files, inspect Backend APIs, submit product tasks, and validate ResultView assumptions; direct research-grade simulation remains Pluto or Julia Runner.

## When To Use Python Notebook

Use Python Notebook when you need to verify Product App behavior before the App UI is mature:

- Does the Backend API expose the metadata the future page needs?
- Does a task request shape produce the expected Runner / ResultView path?
- Does a trace preview or bounded slice match the intended UI interaction?
- Can a migration, repair check, or emergency analysis be expressed without directly mutating platform state?

If the answer becomes stable and user-facing, move the contract into Product App docs and keep implementation under `app/`.

## Related

- [Prototype Path](../../workflows/research-tools/promote-pluto-prototype-to-reusable-core.md)
- [Notebook Interface](../../reference/notebooks/index.md)
- [Python Core](../../reference/core/python-core.mdx)
- [Application Authoring Map](../application-authoring.md)
