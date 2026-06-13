---
aliases:
  - API Reference
  - Generated API Reference
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/api-reference
status: stable
owner: docs-team
audience: team
scope: Starlight entry point for generated Sphinx and Documenter.jl API reference sites.
version: v1.0.0
last_updated: 2026-06-12
updated_by: codex
---

# API Reference

本頁是 generated API reference 的入口。Astro + Starlight 維持 high-level Source of Truth、架構契約與工作流說明；Sphinx 與 Documenter.jl 負責從 package docstrings 產生可查找的 API reference。

## Reference Sites

| Site | Owner | Scope |
| --- | --- | --- |
| [Python API Reference](../../../api/python/) | Sphinx | `superconducting_circuits_analysis`、`schemdraw_circuit_library` |
| [Julia API Reference](../../../api/julia/) | Documenter.jl | `SuperconductingCircuitsCore`、`SuperconductingCircuitsVisualizer`、`SuperconductingCircuitsRunner`、`SuperconductingCircuitsAnalysisBridge` |

## Boundary

- Starlight pages describe product contracts, architecture ownership, workflows, concepts, and guardrails.
- Sphinx pages describe Python package objects, signatures, type hints, and Google-style docstrings.
- Documenter.jl pages describe Julia exported package objects and Documenter-compatible Markdown docstrings.
- FastAPI backend internals are not a public Python package API surface. Use Backend reference docs and OpenAPI for HTTP contracts.

## Related

- [Python Core](../core/python-core.mdx)
- [Julia Core Authoring](../julia-core/index.mdx)
- [Julia Package Surface](../core/julia-core.mdx)
- [API Reference Guardrail](../guardrails/documentation-design/api-reference.mdx)
