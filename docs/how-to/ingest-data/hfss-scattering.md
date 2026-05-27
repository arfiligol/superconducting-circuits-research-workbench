---
aliases:
  - "Ingest HFSS Scattering"
  - "匯入 HFSS 散射參數數據"
tags:
  - diataxis/how-to
  - audience/user
  - sot/true
  - topic/data-ingestion
status: stable
owner: team
audience: user
scope: "如何將 HFSS 匯出的 S-parameter CSV 檔案匯入 TraceStore"
version: v2.0.0
last_updated: 2026-05-28
updated_by: codex
---

# Ingesting HFSS Scattering Data

Use the Application Interface to import HFSS S-parameter data.
The backend stores official numeric traces in TraceStore and keeps metadata/provenance in the database.

## Prepare The Export

Export S-parameter traces from HFSS as `.csv` files.
Include enough information in the filename or import metadata to identify the parameter, for example `S11`, `S21`, phase, magnitude, real, or imaginary representation.

## Import

1. Open the Electron App.
2. Go to `Data Ingestion`.
3. Choose the target dataset and design.
4. Add the scattering files.
5. Submit the import.

## Validate

Open `Raw Data` and inspect:

- trace key and family
- representation
- frequency axis
- units
- preview values

## Notes

!!! warning "No active CLI"
    Former command-based import and database paths are no longer active product surfaces.
