---
aliases:
 - Add Data Source
 - Add new data source
tags:
 - audience/team
status: stable
owner: docs-team
audience: team
scope: How to extend data import to support new data formats
version: v0.2.0
last_updated: 2026-05-28
updated_by: codex
sidebar:
 label: Add Data Source
 order: 20
---

# Add New Data Source

Add new data sources through the Python Backend data plane.
The backend validates metadata, writes official traces to TraceStore, and exposes the imported data through app/notebook APIs.

## Strategy

Create a parser or maintenance script that maps the source file into the backend ingestion contract.
Do not add a product CLI command for the new source.

## Steps

1. Analyze the raw format:
  - header structure
  - axis columns
  - complex value representation
  - units
  - source metadata
2. Add a parser in the backend or a developer-only helper under `scripts/maintenance/`.
3. Write tests that cover a small fixture and the resulting TraceStore metadata.
4. Verify imported traces in the Application Raw Data Browser.

## Checklist

- [ ] Units are converted to the canonical contract.
- [ ] Complex arrays use explicit real/imag representation.
- [ ] Source file provenance is retained.
- [ ] The backend can read a preview slice.
- [ ] No large arrays travel through HTTP JSON.

## Related

- [TraceStore Zarr](../architecture/contracts/trace-store-zarr.md)
- [Dataset Record](../data-contracts/dataset-record.mdx)
- [Script Authoring](../../reference/guardrails/code-quality/script-authoring.mdx)
