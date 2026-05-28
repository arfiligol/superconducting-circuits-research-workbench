---
title: "Application Interface"
description: "Defines the Electron application surface for the current Product Async architecture."
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

Retired surfaces must stay inactive unless a new source-of-truth explicitly reintroduces them through the task/result workbench, Simulation Workbench, or a notebook workflow.
