---
title: "Notebook Interface"
description: "Defines Pluto and Python notebook roles in the current architecture."
icon: lucide/notebook-tabs
---

# Notebook Interface

Use notebooks through two distinct roles. Pluto is the direct Julia research cockpit. Python notebooks are programmable data-analysis and inspection surfaces.

## Pluto

Pluto notebooks own direct Julia exploration:

- circuit construction
- simulation experiments
- analysis sketches
- sweep design
- result inspection before productization

Direct Pluto execution is allowed. Application-triggered execution must still go through the async Runner path.

Backend task submission is outside the Pluto notebook role. If Pluto outputs should become official platform data, use an explicit import/publication path.

## Python

Python notebooks are for:

- direct local Zarr, CSV/raw file, exported data, and canonical TraceStore file inspection
- Backend/data API inspection when platform metadata, indexing, provenance, or permissions matter
- task submission through the same Backend contracts used by the Application
- task and result API inspection
- migration checks
- emergency analysis
- local TraceStore investigation

Python notebooks may read data files directly for ad hoc analysis. They must use Backend import, publication, task, and result contracts for any write that should become platform state.

Python notebooks should not become a second scientific compute authority. They must not directly mutate the metadata DB, directly publish or overwrite canonical TraceStore records, define a separate simulation request schema, or use JuliaCall / Julia Core as the normal simulation compute path.

If a Python notebook needs heavier analysis dependencies for inspection or emergency work, use `notebooks/python/pyproject.toml` rather than adding them to `app/backend`.

## Handoff

When a notebook workflow becomes a product workflow:

1. move reusable Julia logic into `SuperconductingCircuitsCore`
2. add a Runner task dispatcher
3. write staged Zarr plus manifest
4. validate publication through the Backend
5. expose browsing and task monitoring through the application
