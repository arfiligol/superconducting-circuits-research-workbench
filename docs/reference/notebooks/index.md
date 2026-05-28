---
title: "Notebook Interface"
description: "Defines Pluto and Python notebook roles in the current architecture."
icon: lucide/notebook-tabs
---

# Notebook Interface

Use notebooks through two distinct roles. Pluto is the direct Julia research cockpit. Python notebooks are programmable clients for Backend data, task, trace, and result APIs.

## Pluto

Pluto notebooks own direct Julia exploration:

- circuit construction
- simulation experiments
- analysis sketches
- sweep design
- result inspection before productization

Direct Pluto execution is allowed. Application-triggered execution must still go through the async Runner path.

Pluto notebooks are not Backend task submitters. If their outputs should become official platform data, use an explicit import/publication path.

## Python

Python notebooks are for:

- Backend/data API inspection
- task and result API inspection
- migration checks
- emergency analysis
- local TraceStore investigation

Python notebooks should not become a second scientific compute surface. If a Python notebook needs heavier analysis dependencies for inspection or emergency work, use `notebooks/python/pyproject.toml` rather than adding them to `app/backend`.

## Handoff

When a notebook workflow becomes a product workflow:

1. move reusable Julia logic into `SuperconductingCircuitsCore`
2. add a Runner task dispatcher
3. write staged Zarr plus manifest
4. validate publication through the Backend
5. expose browsing and task monitoring through the application
