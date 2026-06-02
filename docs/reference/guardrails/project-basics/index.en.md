---
aliases:
  - Project Basics
  - Workspace Basics
tags:
  - diataxis/reference
  - audience/contributor
  - sot/true
  - topic/project-basics
status: stable
owner: docs-team
audience: contributor
scope: Index for the platform mission, stack direction, and folder structure.
version: v2.0.0
last_updated: 2026-05-28
updated_by: codex
---

# Project Basics

This section defines the platform fundamentals: product scope, technical direction, and repository structure.
Any change that affects workspace-wide development direction should update these documents first.

- [Project Overview](./project-overview.en.md)
- [Tech Stack](./tech-stack.en.md)
- [Folder Structure](./folder-structure.en.md)

## Agent Rule { #agent-rule }

```markdown
## Project Basics
- Project Basics defines the platform mission, scope, stack, and structure.
- Any change that affects workspace-wide collaboration or architecture must update this section first.
- The current UI direction is Next.js, the API direction is FastAPI, the compute plane is Julia Runner, and Notebook is the research cockpit.
- Legacy command workflow, retired Python UI runtime, separate queue worker runtime, and Python in-process Julia runtime are not product contracts and must not be the default landing zone for new features.
```
