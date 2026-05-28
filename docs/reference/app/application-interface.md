---
title: "Application Interface"
description: "Defines the Electron application surface after the runner refactor."
icon: lucide/layout-dashboard
---

# Application Interface

The application is a productized data and simulation workbench. It submits asynchronous tasks, monitors task state, browses datasets and traces, and opens published results.

## Surfaces

Keep the main application navigation focused on:

- Dashboard
- Dataset
- Simulation Workbench
- Tasks / Result Browser
- Data Ingestion
- Raw Data / Trace Browser
- Design Assets / Source Documents

Simulation and heavy analysis run as Julia Runner tasks. Application Simulation Workbench builds product requests, submits persisted tasks through the Backend, and renders published results. Direct interactive research execution belongs in Pluto notebooks.

## Local Mode

Local mode starts:

```text
Next.js frontend
Python Backend
Julia Runner
```

Do not start a separate local queue worker service.

## Removed Product Surfaces

These are not active application surfaces:

- user-facing command workflow
- retired Python UI runtime
- standalone Schemdraw workflow
- Characterization Workbench

If a legacy feature is needed later, reintroduce it through the task/result workbench, the Simulation Workbench, or a notebook workflow rather than exposing a half-working runtime entrypoint.
