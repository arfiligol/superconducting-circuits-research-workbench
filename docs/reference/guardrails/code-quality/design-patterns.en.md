---
aliases:
  - Design Patterns
  - Architecture Patterns
tags:
  - diataxis/reference
  - audience/contributor
  - sot/true
  - topic/code-quality
status: stable
owner: docs-team
audience: contributor
scope: Service boundaries, dependency direction, and shared-logic rules for the rewrite branch.
version: v2.0.0
last_updated: 2026-05-28
updated_by: codex
---

# Design Patterns

The design goal in this project is to keep shared rules in stable places instead of letting each entry layer grow its own copy of the workflow.

## Core Rules

### Dependency Direction

- React components must not own business workflow orchestration
- FastAPI routers must not own full workflow logic
- scripts must not duplicate backend service or Runner logic
- Python Backend must not execute heavy simulation / analysis compute
- Julia Runner must not write formal metadata DB records
- shared rules belong in app backend services, Julia Core, Julia Runner, or explicit contract packages

### Dependency Injection

- inject service dependencies via constructors or explicit factories
- do not instantiate repositories, clients, or adapters ad hoc inside workflow functions
- framework-specific wiring belongs in the composition root

### Compute Boundary

- Python Backend owns task lifecycle, metadata, publication, provenance, TraceStore registration, and data APIs
- Julia Runner owns simulation, sweep, post-processing, analysis, fitting, derived parameter extraction, and staging package generation
- application-triggered simulation and analysis must be asynchronous

### API Layer Responsibility

- request parsing
- auth / permission checks
- service invocation
- response mapping

It should not contain:

- long-form business branching
- persistence details
- duplicated transformations shared by multiple modules

## Agent Rule { #agent-rule }

```markdown
## Design Patterns
- Keep shared workflow logic in app backend services, Julia Core, Julia Runner, or explicit contract packages, not in React components, FastAPI routers, notebooks, or scripts.
- Use dependency injection or explicit factories for services, repositories, and adapters.
- Python Backend is the control/data plane and must not execute heavy simulation or analysis compute in process.
- Julia Runner is the compute plane and must not write formal metadata DB records.
- Application-triggered simulation and analysis must be asynchronous.
- API handlers should do I/O, auth, validation, service invocation, and response mapping only.
- Scripts are dev/build/test/maintenance helpers only and must not become user-facing workflow contracts.
```
