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
- Analysis Workbench
- Task / Execution Center
- Data Ingestion
- Raw Data / Trace Browser
- Design Assets / Source Documents

Simulation and heavy analysis run as Julia Runner tasks. Application Simulation Workbench builds simulation requests, submits persisted tasks through the Backend, and renders published results. Analysis Workbench builds fitting, post-processing, comparison, and derived-parameter requests through the same async path.

Direct interactive research execution belongs in Pluto notebooks.

## Task Execution Model

The application product metaphor is Task Execution Pipeline, Runner Runtime, Task / Execution Center, and ResultView.

It must not present the local runtime as a separate queue-service product or standalone runtime wall. Persisted Backend tasks and Julia Runner claim / heartbeat / progress / complete / fail lifecycle remain the execution authority.

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

The former characterization route is represented by Analysis Workbench, Julia Runner analysis tasks, ResultView, and Raw Data Browser integration. Retired surfaces must stay inactive unless a new source-of-truth explicitly reintroduces them through first-class workbench or notebook workflow boundaries.
