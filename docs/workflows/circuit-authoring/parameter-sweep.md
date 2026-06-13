---
aliases:
 - "parameter sweep"
tags:
 - diataxis/tutorial
 - status/draft
sidebar:
 label: Parameter Sweep
 order: 30
---

# Parameter scan

Learn how to systematically scan circuit parameters, an important technique for analyzing circuit behavior.

## Single dimension scan

Scan a single parameter and observe its effect on the circuit's response.

### Example: Scan inductor value

```julia title="examples/02_parameter_sweep/single_sweep.jl"
using JosephsonCircuits
using PlotlyJS

const nH = 1e-9
const pF = 1e-12
const GHz = 1e9

@variables L C R50

circuit = [
  ("P1", "1", "0", 1),
  ("R50", "1", "0", R50),
  ("L", "1", "2", L),
  ("C", "2", "0", C),
]

#Basic parameters
base_defs = Dict(C => 1pF, R50 => 50)

# Scan range
L_values = (5:1:15) * nH

# Mock settings
ws = 2π * (0.1:0.01:10) * GHz
wp = (2π * 5.0GHz,)
sources = [(mode=(1,), port=1, current=0.0)]

# Save results
traces = []

for L_val in L_values
  defs = merge(base_defs, Dict(L => L_val))
  sol = hbsolve(ws, wp, sources, (10,), (20,), circuit, defs)

  freqs = sol.linearized.w / (2π * GHz)
  S11 = sol.linearized.S(outputmode=(0,), outputport=1, inputmode=(0,), inputport=1, freqindex=:)

  push!(traces, scatter(
    x=freqs,
    y=rad2deg.(angle.(S11)),
    mode="lines",
    name="L = $(round(L_val/nH, digits=1)) nH"
  ))
end

plot(traces)
```

## Multi-dimensional scanning

Scan multiple parameters simultaneously.

### Example: Scan L and C

```julia title="examples/02_parameter_sweep/multi_sweep.jl"
using JosephsonCircuits
using DataFrames

const nH = 1e-9
const pF = 1e-12
const GHz = 1e9

# Scan the grid
L_values = [5, 10, 15] * nH
C_values = [0.5, 1.0, 1.5] * pF

# Result table
results = DataFrame(L_nH=Float64[], C_pF=Float64[], f0_GHz=Float64[])

for L_val in L_values
  for C_val in C_values
#Theoretical resonance frequency
    f0 = 1 / (2π * sqrt(L_val * C_val)) / GHz

    push!(results, (L_val/nH, C_val/pF, f0))
  end
end

println(results)
```

## View results

Direct sweeps in research can be plotted in Pluto notebooks, and sweep inputs, units, axes, and figure generation can be placed in the same reproducible notebook.

## Next step

👉 [Notebook Interface](../../reference/notebooks/index.md) — Understand the research role of Pluto and Python notebook
