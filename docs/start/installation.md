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

The Start Here installation path only does one thing: make a fresh checkout able to launch Pluto and load the local Julia packages used by the first notebook.

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
- `SuperconductingCircuitsVisualizer`: Pluto / report figure helpers.

Python Analysis Core and Analysis Bridge are subsequent fitting / matrix-analysis workflows; the first Pluto notebook does not require understanding them first.

## Prepare The Pluto Environment

Register Core, Visualizer, Pluto, PlutoUI, and Revise in the Julia default environment that Pluto uses:

```bash
npm run julia:dev-install
```

This command prepares the Julia environment. It does not start Pluto yet.

## Launch Pluto

Start Julia from the same default environment:

```bash
julia --startup-file=no --project=@v1.12
```

Then launch Pluto:

```julia
using Pluto
Pluto.run()
```

After Pluto opens in the browser, open the first notebook from the repository and run the notebook cells.

## Notebook Startup Cell

Repository Pluto notebooks use an explicit startup cell like this:

```julia
import Pkg
Pkg.activate(joinpath(first(DEPOT_PATH), "environments", "v1.12"); io=devnull)

using Revise
using SuperconductingCircuitsCore
```

Add `using PlutoUI` and `using SuperconductingCircuitsVisualizer` when the notebook needs UI helpers or PlotlyJS figures.

The `Pkg.activate(...)` line tells Pluto to use the prepared local development environment instead of creating a separate per-notebook package environment. `Revise` lets a running notebook pick up local package edits while you develop reusable circuit code.

## Check Local Package Resolution

If Pluto cannot load a local package, check the same environment from a Julia REPL:

```julia
using Revise
using SuperconductingCircuitsCore
using SuperconductingCircuitsVisualizer
pathof(SuperconductingCircuitsCore)
pathof(SuperconductingCircuitsVisualizer)
```

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
