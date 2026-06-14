---
aliases:
 - "LC resonator"
tags:
 - diataxis/tutorial
 - status/draft
sidebar:
 label: LC Resonator
 order: 20
---

# LC Resonator

The LC resonator is the most basic superconducting circuit model, and understanding it is the basis for learning more complex circuits.

## Physics Background

The resonant frequency of the LC circuit is determined by the inductor $L$ and capacitor $C$:

$$f_0 = \frac{1}{2\pi\sqrt{LC}}$$

At the resonant frequency, the circuit impedance reaches an extreme value and the reflection coefficient $S_{11}$ will show significant phase changes.

## Circuit model

```text
   ┌───────┐
 ────┤ Port ├────┬────
   │ 50Ω │  │
   └───────┘  │
        ┌─┴─┐
│ L │ Inductance
        └─┬─┘
         │
        ┌─┴─┐
│ C │ Capacitance
        └─┬─┘
         │
         GND
```

## Complete code

```julia title="examples/01_simple_lc/lc_resonator.jl"
using JosephsonCircuits
using PlotlyJS

# === Unit definition ===
const nH = 1e-9
const pF = 1e-12
const GHz = 1e9

# === Symbol variables ===
@variables L C R50

# === Circuit topology ===
circuit = [
  ("P1", "1", "0", 1),
  ("R50", "1", "0", R50),
  ("L", "1", "2", L),
  ("C", "2", "0", C),
]

# === Parameter value ===
circuitdefs = Dict(
  L => 10nH,
  C => 1pF,
  R50 => 50,
)

# === Mock settings ===
ws = 2π * (0.1:0.01:10) * GHz
wp = (2π * 5.0GHz,)
sources = [(mode=(1,), port=1, current=0.0)]

# === Execute simulation ===
sol = hbsolve(ws, wp, sources, (10,), (20,), circuit, circuitdefs)

# === Extract results ===
freqs = sol.linearized.w / (2π * GHz)
S11 = sol.linearized.S(outputmode=(0,), outputport=1, inputmode=(0,), inputport=1, freqindex=:)

# === Drawing ===
phase_deg = rad2deg.(angle.(S11))
trace = scatter(x=freqs, y=phase_deg, mode="lines", name="S11 Phase")
plot(trace)
```

[Download full code](https://github.com/arfiligol/superconducting-circuits-research-workbench/blob/main/examples/01_simple_lc/lc_resonator.jl)

## Parameter exploration

Try changing the values ​​of L and C and see how the resonant frequency changes:

| L (nH) | C (pF) | $f_0$ (GHz) |
|--------|--------|-------------|
| 10   | 1   | 1.59    |
| 5   | 1   | 2.25    |
| 10   | 0.5  | 2.25    |

## Next step

👉[Parameter Scan](parameter-sweep.md) — Learn how to automatically scan parameters
