---
aliases:
  - First Pluto Notebook
  - 第一次 Pluto Notebook
tags:
  - diataxis/how-to
  - status/stable
  - topic/getting-started
sidebar:
  label: First Pluto Notebook
  order: 30
---

# First Pluto Notebook

用 `00_parallel_lc_resonator.jl` 確認研究入口可用。這條路徑從 Pluto 直接呼叫 Julia Core，不需要先啟動任何產品化 runtime。

## Goal

跑通一個 parallel LC resonator notebook，確認你可以：

- 從 Pluto 載入 local Julia Core packages。
- 建立 inspectable CircuitPlan / HB problem。
- 執行 real solver path。
- 用 Visualizer 看實際 result traces。

## Open Pluto

From the repository root:

```bash
julia --startup-file=no --project=@v1.12
```

Then start Pluto:

```julia
using Pluto
Pluto.run()
```

Open:

```text
notebooks/pluto/00_parallel_lc_resonator.jl
```

## What To Inspect

The first notebook should show the same research contract used by later examples:

```text
local teaching fixture or reusable builder
    -> CircuitPlan
    -> EngineeringGraph
    -> HBIntent / HBProblemSpec
    -> run_hb_problem
    -> real extracted output families
    -> Visualizer figures
```

The useful success signal is not only "the notebook opens". You should see real S11 / impedance-style traces produced from the solver path, not placeholder curves.

## Why This Comes First

Pluto is the direct research cockpit:

- It may call Julia Core directly.
- It may use the Visualizer for PlotlyJS figures.
- It may call Python Analysis Core through `SuperconductingCircuitsAnalysisBridge` when a fitting or matrix-analysis kernel is shared with Python.
- It keeps execution inside an explicit notebook research kernel.

Python Notebook work comes later, when a research workflow needs local file inspection or Python-side analysis notebooks.

## Next Step

- [Pluto Examples](../workflows/pluto/pluto-examples.mdx) - continue the numbered notebook learning path.
- [Pluto Authoring Workflow](../workflows/pluto/authoring-workflow.mdx) - learn the CircuitPlan authoring loop.
- [Prototype Path](prototype-path.md) - understand how a notebook workflow becomes reusable Julia Core, Python Analysis Core, or Python Notebook work.
