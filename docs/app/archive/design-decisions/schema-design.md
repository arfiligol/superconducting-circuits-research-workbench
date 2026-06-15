---
aliases:
- Dataset Schema Design
- Data set Schema design
- Schema Design
- Schema design
tags:
 - diataxis/explanation
 - status/stable
 - topic/architecture
 - topic/data-format
 - audience/team
status: stable
owner: docs-team
audience: team
scope: DatasetRecord/DataRecord’s data set Schema design details
version: v0.2.0
last_updated: 2026-02-27
updated_by: docs-team
sidebar:
 label: Dataset Schema Design
 order: 40
---

# Dataset Schema Design

The current standard data format is based on **SQLite Dataset** and uses `DatasetRecord`/`DataRecord` to store data and related information.

## Core concepts

- **DatasetRecord**: Metadata describing a set of data (name, source, label, creation time).
- **DataRecord**: stores actual measurement/simulation data and axis information (frequency, bias, etc.).
- **DerivedParameter**: Parameter results after analysis (such as $L_s, C$ obtained by fitting).

## Scalability considerations

- **Multi-axis support**: The same Dataset can contain multi-dimensional scan data.
- **Multiple Parameters**: A Dataset can contain multiple parameter families (S/Y/Z) or different representations at the same time.
- **Traceability**: Centralized management of data sources and tags to facilitate traceability and query.

## Related

- [Dataset Record Reference](../../data-contracts/dataset-record.mdx) - Complete field description
