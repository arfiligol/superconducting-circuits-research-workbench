---
aliases:
- Visualization Backend
- 視覺化後端選擇
tags:
  - diataxis/explanation
  - status/stable
  - topic/architecture
  - topic/visualization
  - audience/team
status: stable
owner: docs-team
audience: team
scope: Plotly vs Matplotlib 選擇理由
version: v0.1.0
last_updated: 2026-01-28
updated_by: docs-team
sidebar:
  label: Visualization Backend
  order: 60
---

# Visualization Backend

本專案預設使用 **Plotly**，但保留 **Matplotlib** 作為備選。

## Why Plotly by Default?

1. **互動性 (Interactivity)**
   - 資料探勘 (Data Exploration) 非常需要 Zoom-in、Hover 查看數值。
   - 在 Jupyter Notebook 或瀏覽器中體驗極佳。

2. **Web Ready**
   - 可以直接匯出成 HTML 分享給團隊成員，無需安裝 Python 環境即可查看。

3. **美觀**
   - 預設樣式現代化，適合報告展示。

## Why Keep Matplotlib?

1. **靜態出版 (Publication)**
   - 論文或 PDF 報告需要高品質的向量圖 (PDF/SVG)。
   - Matplotlib 在這方面仍是標準。

2. **相容性**
   - 某些環境 (如純終端機伺服器) 可能無法方便地顯示互動式圖表。

## Implementation

所有繪圖腳本都支援 `--matplotlib` 參數切換：

```python
if use_matplotlib:
    _render_matplotlib(...)
else:
    _render_plotly(...)
```

這確保了兩種需求都能被滿足。
