---
aliases:
  - Data Storage Architecture
  - 資料儲存架構
tags:
  - diataxis/explanation
  - audience/team
  - topic/architecture
  - topic/data
status: stable
owner: docs-team
audience: team
scope: Metadata DB, runner staging, and canonical TraceStore responsibility split
version: v2.0.0
last_updated: 2026-05-28
updated_by: codex
sidebar:
  label: Data Storage
  order: 30
---

# Data Storage

The storage model separates metadata authority from numeric authority.
Python Backend owns metadata and publication.
TraceStore owns official numeric arrays.
Julia Runner only writes temporary staging packages.

## Core Model

```mermaid
flowchart TB
    Dataset["DatasetRecord"]
    Design["DesignRecord"]
    Task["TaskRecord"]
    Batch["TraceBatchRecord"]
    Trace["TraceRecord"]
    Staging["Runner Staging result.zarr"]
    Store["Canonical TraceStore Zarr"]
    Artifact["Task Artifacts"]

    Dataset --> Design
    Design --> Task
    Task --> Staging
    Staging --> Store
    Task --> Artifact
    Store --> Batch
    Batch --> Trace
```

## Filesystem Layout

Use this local layout:

```text
data/
├── metadata.db
├── trace_store/
│   └── datasets/<dataset_id>/designs/<design_id>/batches/<batch_id>.zarr/
├── artifacts/
│   └── tasks/<task_id>/
└── staging/
    └── tasks/<task_id>/
        ├── manifest.json
        ├── result.zarr/
        └── logs/
```

`data/staging/` is temporary.
`data/trace_store/` is the official numeric authority.
`data/artifacts/` keeps manifests, logs, reports, and summaries.

## Why Backend Publishes

The runner can generate arrays, but it does not own the formal database.
The backend validates before publishing:

- manifest path is local and safe
- `task_id` matches the task row
- Zarr format is v2
- every declared array exists
- real/imag arrays have matching shape, chunk shape, and dtype
- axis lengths match trace shapes

Only after validation does the backend create `TraceBatchRecord`, `TraceRecord`, and artifact metadata.

## Large Arrays

Do not put S/Y/Z matrices, sweeps, or ND traces in HTTP JSON.
Use HTTP JSON for control messages, status, progress, manifest locators, and error summaries.

For complex arrays, store real and imaginary arrays explicitly:

```text
/traces/S11/real
/traces/S11/imag
```

## Storage Backend Contract

The baseline storage contract is local filesystem Zarr v2 managed by the Python Backend.
Remote object storage is allowed only after a storage-backend SoT defines the backend adapter, publication semantics, validation rules, and operational ownership.
The Julia Runner writes local staging packages and does not write directly to object storage.

## Related

- [TraceStore Zarr](../../../reference/architecture/trace-store-zarr.md)
- [Runner Result Manifest](../../../reference/architecture/runner-result-manifest.md)
- [Backend Architecture](../../../reference/guardrails/project-basics/backend-architecture.mdx)
