---
aliases:
 - "Native Julia Simulation"
 - "Native Julia emulation"
tags:
 - diataxis/how-to
 - status/stable
 - topic/simulation
 - topic/julia
 - topic/advanced
status: stable
owner: docs-team
audience: user
scope: "Advanced tutorial on native Julia simulation"
version: v0.2.0
last_updated: 2026-05-28
updated_by: codex
sidebar:
 label: Native Julia Simulation
 order: 30
---

# Native Julia mocking

This tutorial explains how to directly use JosephsonCircuits.jl to perform circuit simulation. It is suitable for advanced users or developers who need expanded functions.

## When to choose native Julia?

| Situation | Suggested approach |
|------|----------|
| Complex circuits, custom components | **Native Julia** |
| Developing new simulation features | **Native Julia** |
| Performance critical applications | **Native Julia** |

## Preferences

### Using the project Julia environment

```bash
cd superconducting-circuits-research-workbench
julia --project=core/julia/SuperconductingCircuitsCore
```

### Loading the package

```julia
using JosephsonCircuits
using Plots # optional, used for plotting
```

## Basic syntax

### Unit definition

```julia
# Commonly used units
nH = 1e-9  # nanohenry
pF = 1e-12 # picofarad
fF = 1e-15 # femtofarad
GHz = 1e9  # gigahertz
MHz = 1e6  # megahertz
```

### Symbol variables

```julia
using JosephsonCircuits: @variables

@variables L C Cj Lj R50
```

### Circuit definition

The circuit is defined as a Tuple array, and the format of each element is:
`(component name, node1, node2, value)`

```julia
circuit = [
("P1", "1", "0", 1), # Port (fixed value 1)
("R50", "1", "0", R50), # Resistor
("L", "1", "2", L), # inductor
("C", "2", "0", C), # capacitor
]
```

### Parameter value

```julia
circuitdefs = Dict(
  L => 10nH,
  C => 1pF,
  R50 => 50.0,
)
```

## Execute Harmonic Balance

### Frequency setting

```julia
# Frequency range
f_start, f_stop, n_points = 0.1GHz, 5GHz, 100
frequencies = range(f_start, f_stop, length=n_points)
ws = 2π .* frequencies # Angular frequency
```

### Pump settings

```julia
# Pump frequency and source settings
wp = (2π * 5GHz,) # Pump frequency
sources = [(mode=(1,), port=1, current=0.0)]
```

### Execute simulation

```julia
# hbsolve parameters: (ws, wp, sources, Npumpharmonics, Nmodulationharmonics, circuit, circuitdefs)
sol = hbsolve(ws, wp, sources, (10,), (20,), circuit, circuitdefs)
```

## Extract S parameters

```julia
# Extract S11
S11 = sol.linearized.S(
  outputmode=(0,),
  outputport=1,
  inputmode=(0,),
  inputport=1,
  freqindex=:
)

# Calculate amplitude and phase
S11_mag = abs.(S11)
S11_phase = angle.(S11)

# Find resonance
min_idx = argmin(S11_mag)
resonance_freq = frequencies[min_idx] / GHz
println("Resonance frequency: $(resonance_freq) GHz")
```

## Advanced: Josephson Junction

Simulate a circuit with a Josephson Junction:

```julia
@variables Lj Cj Ic

# SQUID circuit example
circuit = [
  ("P1", "1", "0", 1),
  ("R50", "1", "0", 50.0),
  ("C", "1", "2", C),
("Lj", "2", "0", Lj), # Junction inductor
("Cj", "2", "0", Cj), # Junction capacitor
]

# Junction parameters
Φ0 = 2.067833848e-15 # Magnetic flux quantum
Ic = 1e-6 # Critical current (1 μA)
Lj0 = Φ0 / (2π * Ic) #Josephson Inductor

circuitdefs = Dict(
  C => 10fF,
  Lj => Lj0,
  Cj => 5fF,
)
```

## Parameter scan

```julia
#Scan capacitance value
C_values = [0.5, 1.0, 1.5, 2.0] .* pF
results = []

for C_val in C_values
  circuitdefs[C] = C_val
  sol = hbsolve(ws, wp, sources, (10,), (20,), circuit, circuitdefs)
  S11 = sol.linearized.S(outputmode=(0,), outputport=1, inputmode=(0,), inputport=1, freqindex=:)
  push!(results, (C=C_val, S11=S11))
end
```

## Multi-thread acceleration

```julia
using Base.Threads

# Confirm the number of execution threads
println("Using $(nthreads()) threads")

# parallel scan
Threads.@threads for i in 1:length(C_values)
# ... simulation logic
end
```

Specify the number of threads when starting Julia:

```bash
julia --project=. --threads=auto
```

## Related resources

- [JosephsonCircuits.jl docs](https://qicklab.github.io/JosephsonCircuits.jl/)
- [Tutorial: LC Resonator](../circuit-authoring/lc-resonator.md) - Getting Started Case
- [Extending Research Tools](../research-tools/extend-julia-functions.mdx) - Contributor Guide
