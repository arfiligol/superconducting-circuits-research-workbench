---
aliases:
- Visualization Backend
- Visual backend selection
tags:
 - diataxis/explanation
 - status/stable
 - topic/architecture
 - topic/visualization
 - audience/team
status: stable
owner: docs-team
audience: team
scope: Plotly vs Matplotlib Reasons to choose
version: v0.1.0
last_updated: 2026-01-28
updated_by: docs-team
sidebar:
 label: Visualization Backend
 order: 60
---

# Visualization Backend

This project uses **Plotly** by default, but retains **Matplotlib** as an alternative.

## Why Plotly by Default?

1. **Interactivity**
- Data Exploration requires Zoom-in and Hover to view values.
- Works great in Jupyter Notebook or the browser.

2. **Web Ready**
- You can directly export it to HTML and share it with team members, and you don’t need to install a Python environment to view it.

3. **Beautiful**
- The default style is modern and suitable for report display.

## Why Keep Matplotlib?

1. **Static Publishing (Publication)**
- Papers or PDF reports require high-quality vector graphics (PDF/SVG).
- Matplotlib is still the standard in this regard.

2. **Compatibility**
- Some environments (such as pure terminal servers) may not display interactive charts conveniently.

## Implementation

All drawing scripts support `--matplotlib` parameter switching:

```python
if use_matplotlib:
  _render_matplotlib(...)
else:
  _render_plotly(...)
```

This ensures that both needs are met.
