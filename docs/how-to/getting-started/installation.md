---
aliases:
  - "安裝環境"
tags:
  - diataxis/how-to
  - status/stable
  - topic/getting-started
---

# 安裝環境

This project uses Python for the backend/control plane, Julia for compute, Next.js for the application UI, and Electron for the desktop shell.

## Requirements

Install:

- Python 3.12+
- `uv`
- Julia 1.12+
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

## Install Dependencies

From the repository root:

```bash
uv sync
cd app/backend && uv sync
npm ci --prefix app/frontend
npm ci --prefix app/desktop
julia --project=core/julia/SuperconductingCircuitsCore -e 'using Pkg; Pkg.instantiate()'
julia --project=core/julia/SuperconductingCircuitsVisualizer -e 'using Pkg; Pkg.instantiate()'
julia --project=core/julia/SuperconductingCircuitsRunner -e 'using Pkg; Pkg.instantiate()'
```

## Install Local Julia Packages For Pluto And REPL

If you want new Julia or Pluto sessions to use the local packages directly, register Core, Visualizer, and Revise in the Julia default environment that Pluto uses:

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
pathof(SuperconductingCircuitsCore)
pathof(SuperconductingCircuitsVisualizer)
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

Add `using PlutoUI` and `using SuperconductingCircuitsVisualizer` only when the notebook needs Pluto UI helpers or PlotlyJS figures. The `Pkg.activate(...)` line disables Pluto's automatic per-notebook package manager for this local dev workflow.

If you launch Julia or Pluto with a custom environment, run the same install script against that environment, for example:

```bash
julia --startup-file=no --project=/path/to/env scripts/dev/install_julia_dev_packages.jl
```

Then replace the notebook activation path with that custom environment path.

## Validate

Run the retained checks:

```bash
cd app/backend && uv run pytest
npm run typecheck --prefix app/frontend
julia --startup-file=no --project=@v1.12 -e 'using Revise; using SuperconductingCircuitsCore; using SuperconductingCircuitsVisualizer; println(pathof(SuperconductingCircuitsCore)); println(pathof(SuperconductingCircuitsVisualizer))'
julia --project=core/julia/SuperconductingCircuitsCore -e 'using Pkg; Pkg.test()'
julia --project=core/julia/SuperconductingCircuitsVisualizer -e 'using Pkg; Pkg.test()'
julia --project=core/julia/SuperconductingCircuitsRunner -e 'using Pkg; Pkg.test()'
```

## Start The Local App

Start frontend, backend, and Julia Runner:

```bash
npm run app:dev
```

Stop them with:

```bash
npm run app:stop
```

## Next Step

Read [Application Interface](../../reference/app/application-interface.md) and [Notebook Interface](../../reference/notebooks/index.md).
