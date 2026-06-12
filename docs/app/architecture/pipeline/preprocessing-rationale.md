---
aliases:
  - Preprocessing Rationale
  - 前處理設計理由
tags:
  - diataxis/explanation
  - status/stable
  - topic/architecture
  - topic/pipeline
  - audience/team
status: stable
owner: docs-team
audience: team
scope: 為什麼 ingestion、normalization、Runner staging 與 Backend publication 必須分層
version: v1.0.0
last_updated: 2026-05-28
updated_by: codex
sidebar:
  label: Preprocessing Rationale
  order: 30
---

# Preprocessing Rationale

Preprocessing exists to separate file-format normalization from platform authority. Raw files, Runner outputs, and official TraceStore records have different responsibilities.

## Why Normalize Before Publication

Input sources are naturally heterogeneous:

- HFSS or Q3D exports
- VNA measurements
- generated Runner result packages
- exported or manually collected research data

If each consumer parses raw files independently, unit handling, axis naming, shape checks, and provenance drift across the platform. The Backend keeps platform state coherent by owning metadata, publication, and result registration.

## Responsibility Split

| Stage | Owner | Responsibility |
| --- | --- | --- |
| Raw or exported files | data source / user workflow | provide source data without claiming platform authority |
| Ingestion and normalization | Python Backend | validate units, shape, metadata, workspace context, and provenance |
| Runner staging | Julia Runner | write local Zarr result packages and manifest files |
| Publication | Python Backend | validate staging output, publish TraceStore batches, create metadata records |
| Notebook analysis | Python Notebook | read files directly for ad hoc analysis without mutating platform state |

## Why This Is Not One Step

Direct file reads are useful for inspection, debugging, and emergency analysis. They do not create official dataset, trace, task, provenance, or result records.

Official platform state requires Backend publication because the Backend is the only surface that can connect numeric payloads to dataset/design/trace metadata and provenance.

## Related

- [Data Flow](data-flow.md)
- [Datasets & Results](../../backend/datasets-results.mdx)
- [TraceStore Zarr](../../../reference/architecture/trace-store-zarr.md)
