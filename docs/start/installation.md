---
aliases:
 - "Installation environment"
tags:
 - diataxis/how-to
 - status/stable
 - topic/getting-started
sidebar:
 label: Installation
 order: 20
---

# Installation

The Start Here installation path only does one thing: allows fresh checkout to start Pluto, and allows the notebook to load local Julia packages.

## Requirements

The main line of research requires:

- Python 3.12+
- `uv`
- Julia 1.12+

If you want to build public docs, then install:

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

## Install The Local Environment

From the repository root:

```bash
uv sync --all-packages
julia --project=core/julia/SuperconductingCircuitsCore -e 'using Pkg; Pkg.instantiate()'
julia --project=core/julia/SuperconductingCircuitsVisualizer -e 'using Pkg; Pkg.instantiate()'
```

This step prepares the two core packages needed for the first Pluto notebook:

- `SuperconductingCircuitsCore`: Pluto direct research and reusable circuit authoring.
- `SuperconductingCircuitsVisualizer`:Pluto / report figure helpers.

Python Analysis Core and Analysis Bridge are subsequent fitting / matrix-analysis workflows; the first Pluto notebook does not require understanding them first.

## Register Local Packages For Pluto

Register Core, Visualizer, Pluto, PlutoUI, and Revise in the Julia default environment that Pluto uses:

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

Add `using PlutoUI` and `using SuperconductingCircuitsVisualizer` when the notebook needs UI helpers or PlotlyJS figures. The `Pkg.activate(...)` line disables Pluto's automatic per-notebook package manager for this local dev workflow.

If you launch Julia or Pluto with a custom environment, run the same install script against that environment, for example:

```bash
julia --startup-file=no --project=/path/to/env scripts/dev/install_julia_dev_packages.jl
```

Then replace the notebook activation path with that custom environment path.

## Validate The Pluto Path

Run the focused Julia checks:

```bash
julia --startup-file=no --project=@v1.12 -e 'using Revise; using SuperconductingCircuitsCore; using SuperconductingCircuitsVisualizer; println(pathof(SuperconductingCircuitsCore)); println(pathof(SuperconductingCircuitsVisualizer))'
julia --project=core/julia/SuperconductingCircuitsCore -e 'using Pkg; Pkg.test()'
julia --project=core/julia/SuperconductingCircuitsVisualizer -e 'using Pkg; Pkg.test()'
```

## Next Step

Run [First Pluto Notebook](first-pluto-notebook.md), then read [Reusable Circuit Design](reusable-circuit-design.md).
