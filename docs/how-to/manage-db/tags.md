---
aliases:
  - "管理 Tags"
  - "Manage Tags"
tags:
  - diataxis/how-to
  - status/stable
  - topic/database
status: stable
owner: docs-team
audience: user
scope: "使用 Application Interface 或 Backend API 管理 Tags"
version: v0.2.0
last_updated: 2026-05-28
updated_by: codex
---

# 管理 Tags

當你需要整理或統一資料集標籤時，先使用 Application Interface 的 dataset surface。
需要批次維護時，呼叫 Python Backend 的 metadata API 或撰寫 maintenance script。

## Usage

1. 在 Electron App 開啟 `Dataset`。
2. 選取目標 dataset。
3. 檢查 tag 與 provenance metadata。
4. 如需批次改名或刪除，透過 backend maintenance script 呼叫正式 metadata API。

## Validation

Tag maintenance must leave dataset, design, trace, and provenance records consistent.
Run backend tests after changing maintenance code:

```bash
uv run --package superconducting-circuits-backend pytest app/backend/tests -q
```

## Notes / Warnings

!!! warning "刪除會影響關聯"
    刪除 Tag 會同步移除與 Dataset 的關聯。請先確認下游分析不再依賴該標籤。

!!! warning "No active CLI"
    The old command-based database tools are no longer active product surfaces.
    Keep new database maintenance behind backend APIs or `scripts/maintenance/`.
