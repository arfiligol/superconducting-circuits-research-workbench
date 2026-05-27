---
aliases:
  - "重排 Record IDs"
  - "Reorder Record IDs"
tags:
  - diataxis/how-to
  - status/stable
  - topic/database
status: deprecated
owner: docs-team
audience: user
scope: "Record ID 重排政策"
version: v0.2.0
last_updated: 2026-05-28
updated_by: codex
---

# 重排 Record IDs

Record IDs are persisted metadata identifiers.
Do not reorder them as a routine workflow.

## Current policy

Use stable IDs and add display-order fields when the UI needs a sorted view.
If a development database must be reset, recreate the local metadata DB instead of rewriting identifiers in place.

For local development reset:

```bash
rm -f data/metadata.db
cd app/backend && uv run pytest
```

## Notes / Warnings

!!! warning "不可重複 ID"
    ID rewrite tools can break provenance and TraceStore references.
    Do not reintroduce an active `auto-reorder` CLI command.
