---
aliases:
  - "安裝環境"
tags:
  - diataxis/how-to
  - status/stable
  - topic/getting-started
sidebar:
  label: Installation
  order: 20
---

# 安裝環境

Start Here 的安裝路徑以 notebook research 為主：先讓 Pluto 可以載入本地 Julia packages，並讓 Julia Analysis Bridge 可以呼叫 Python Analysis Core。

## Requirements

研究主線需要：

- Python 3.12+
- `uv`
- Julia 1.12+

如果你要建置 public docs，再安裝：

- Node.js 22+
- npm

Check versions with:

```bash
python --version
uv --version
julia --version
node --version
npm --version
```

## Install Python And Julia Research Dependencies

From the repository root:

```bash
uv sync --all-packages
julia --project=core/julia/SuperconductingCircuitsCore -e 'using Pkg; Pkg.instantiate()'
julia --project=core/julia/SuperconductingCircuitsVisualizer -e 'using Pkg; Pkg.instantiate()'
JULIA_PYTHONCALL_EXE="$PWD/.venv/bin/python" julia --project=core/julia/SuperconductingCircuitsAnalysisBridge -e 'using Pkg; Pkg.instantiate()'
```

這一步同時準備：

- `SuperconductingCircuitsCore`：Pluto 直接研究與 reusable circuit authoring。
- `SuperconductingCircuitsVisualizer`：Pluto / report figure helpers。
- `SuperconductingCircuitsAnalysisBridge`：Pluto-friendly bridge into Python Analysis Core。
- `superconducting_circuits_analysis`：Python-owned fitting / matrix analysis package。

## Install Local Julia Packages For Pluto

Register Core, Visualizer, Analysis Bridge, and Revise in the Julia default environment that Pluto uses:

```bash
npm run julia:dev-install
```

For Julia REPL work, start the same environment and load Revise before the local packages:

```bash
julia --startup-file=no --project=@v1.12
```

```julia
using Revise
using SuperconductingCircuitsCore
using SuperconductingCircuitsVisualizer
using SuperconductingCircuitsAnalysisBridge
pathof(SuperconductingCircuitsCore)
pathof(SuperconductingCircuitsVisualizer)
pathof(SuperconductingCircuitsAnalysisBridge)
```

Start Pluto from that same environment:

```julia
using Pluto
Pluto.run()
```

After that, a notebook can start with:

```julia
import Pkg
Pkg.activate(joinpath(first(DEPOT_PATH), "environments", "v1.12"); io=devnull)

using Revise
using SuperconductingCircuitsCore
```

Add `using PlutoUI`, `using SuperconductingCircuitsVisualizer`, and `using SuperconductingCircuitsAnalysisBridge` only when the notebook needs UI helpers, PlotlyJS figures, or Python Analysis Core calls. The `Pkg.activate(...)` line disables Pluto's automatic per-notebook package manager for this local dev workflow.

If you launch Julia or Pluto with a custom environment, run the same install script against that environment, for example:

```bash
julia --startup-file=no --project=/path/to/env scripts/dev/install_julia_dev_packages.jl
```

Then replace the notebook activation path with that custom environment path.

## Validate The Research Path

Run the focused notebook / analysis checks:

```bash
julia --startup-file=no --project=@v1.12 -e 'using Revise; using SuperconductingCircuitsCore; using SuperconductingCircuitsVisualizer; using SuperconductingCircuitsAnalysisBridge; println(pathof(SuperconductingCircuitsCore)); println(pathof(SuperconductingCircuitsVisualizer)); println(pathof(SuperconductingCircuitsAnalysisBridge))'
julia --project=core/julia/SuperconductingCircuitsCore -e 'using Pkg; Pkg.test()'
julia --project=core/julia/SuperconductingCircuitsVisualizer -e 'using Pkg; Pkg.test()'
uv run --package superconducting-circuits-analysis pytest tests/core/analysis tests/core/shared -q
JULIA_PYTHONCALL_EXE="$PWD/.venv/bin/python" julia --project=core/julia/SuperconductingCircuitsAnalysisBridge -e 'using Pkg; Pkg.test()'
```

## Next Step

Run [First Pluto Notebook](first-pluto-notebook.md), then read [Prototype Path](prototype-path.md) when you need to decide which research code should become reusable.
