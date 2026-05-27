---
aliases:
  - Flux Analysis Workflow
  - 磁通分析工作流
tags:
  - audience/team
status: stable
owner: docs-team
audience: team
scope: 磁通掃描分析在 Application/Notebook/Runner 架構下的流程
version: v0.2.0
last_updated: 2026-05-28
updated_by: codex
---

# Flux Dependence Analysis

Flux analysis visualizes how resonance changes with external flux or bias current.
Use the Raw Data Browser for official TraceStore data and notebooks for exploratory analysis.

## Workflow

```mermaid
flowchart LR
    VNA["VNA Flux Sweep"] --> Ingest["Data Ingestion"]
    Ingest --> Store["TraceStore"]
    Store --> Browser["Raw Data Browser"]
    Browser --> Notebook["Notebook Analysis"]
    Notebook --> Runner["Optional Runner Task"]
```

## Physics Check

SQUID inductance is periodic in flux:

```text
L_jun(Phi) = Phi0 / (2*pi*Ic*abs(cos(pi*Phi/Phi0)))
```

As inductance changes, resonance frequency shifts.
The expected map usually shows periodic arches or sweet spots where frequency is less sensitive to flux.

## Usage

1. Import the VNA sweep through `Data Ingestion`.
2. Verify axes and units in `Raw Data`.
3. Use a Python notebook to inspect amplitude and phase maps.
4. Promote repeated analysis into a Julia Runner task when it needs tracked execution and artifacts.

## Result Contract

Tracked analysis should record:

- input trace references
- flux/bias axis metadata
- phase wrapping or unwrapping settings
- extracted resonance points
- plots or summary tables as artifacts

## Related

- [Notebook Interface](../reference/notebooks/index.md)
- [Application Interface](../reference/app/application-interface.md)
- [Julia Runner Compute Plane](../reference/architecture/julia-runner-compute-plane.md)
