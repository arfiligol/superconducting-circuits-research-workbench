---
aliases:
  - "Database Management"
  - "資料庫管理"
tags:
  - diataxis/how-to
  - audience/user
  - sot/true
  - topic/database
status: stable
owner: team
audience: user
scope: "資料庫管理指南索引"
version: v1.0.0
last_updated: 2026-01-31
updated_by: team
---

# Database Management

本區提供關於資料庫操作與維護的相關指南。

## Guides

- **[Managing Datasets](./datasets.md)**
    - 如何列出、搜尋與刪除 Datasets。
- **[Managing Tags](./tags.md)**
    - 如何為 Dataset 添加或移除標籤，以便分類管理。
- **[Reordering Record IDs](./reorder-record-ids.md)**
    - 當 ID 不連續或混亂時，如何重整資料庫 ID。

---

## Current access path

Use the Electron Application Interface for routine dataset inspection and trace browsing.
Use the Python Backend metadata APIs for scripted maintenance.

!!! warning "No active CLI"
    The old command-based database surface is no longer an active product contract. Do not add new maintenance workflows through CLI entrypoints.
