---
aliases:
 - From Netlist to Simulation
 - Netlist to mock
tags:
 - diataxis/tutorial
 - audience/user
 - topic/simulation
status: stable
owner: docs-team
audience: user
scope: Operation process from Schema Source Form to Simulation Result
version: v0.1.0
last_updated: 2026-03-05
updated_by: codex
sidebar:
 label: From Netlist to Runner Task
 order: 70
---

# From Netlist to Runner Task

> Legacy reference only. This page preserves old Application task workflow context under Product App Archive and is not part of the current research-first workflow path.

This page connects Schema and the shortest operation path of an asynchronous Julia Runner simulation task.

## process

1. Write Source Form in Schema Editor and save the schema.
2. Create a simulation task on the Application task surface.
3. Python Backend verifies dataset/design/schema and prepares staging directory.
4. Julia Runner claim task, execute Julia Core, and write `result.zarr` and `manifest.json`.
5. Backend publisher verifies and publishes to TraceStore.
6. Use `Tasks` and `Raw Data` to view the official results.

## Related

- [Schema Editor UI](../../frontend/definition/schema-editor.mdx)
- [Julia Runner Compute Plane](../../architecture/contracts/julia-runner-compute-plane.md)
- [Analysis Result Data Contract](../../data-contracts/analysis-result.mdx)
