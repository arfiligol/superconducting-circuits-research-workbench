### A Pluto.jl notebook ###
# v1.0.1

#> [frontmatter]
#> title = "HB Simulation Intent + EngineeringGraph UX Prototype"
#> tags = ["julia-core", "hb-intent", "engineering-graph", "ux-prototype", "acceptance-harness"]
#> description = "Executable Pluto UX prototype for the target Macro DSL + EngineeringGraph + HBProblemSpec workflow."

using Markdown
using InteractiveUtils

# This Pluto notebook uses @bind for interactivity. When running this notebook outside of Pluto, the following standalone @bind definition gives bound variables a default value (instead of an error).
macro bind(def, element)
    #! format: off
    return quote
        local iv = try Base.loaded_modules[Base.PkgId(Base.UUID("6e696c72-6542-2067-7265-42206c756150"), "AbstractPlutoDingetjes")].Bonds.initial_value catch; b -> missing; end
        local el = $(esc(element))
        global $(esc(def)) = Core.applicable(Base.get, el) ? Base.get(el) : iv(el)
        el
    end
    #! format: on
end

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37001
begin
    import Pkg

    Pkg.develop(path = normpath(joinpath(@__DIR__, "..", "..", "core", "julia", "SuperconductingCircuitsCore")))

    using PlutoUI
    using HypertextLiteral: @htl
    using Plots
end

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37002
TableOfContents(title = "HB + EngineeringGraph UX Prototype")

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37003
md"""
# HB Simulation Intent + EngineeringGraph UX Prototype

This notebook is a tutorial, API design surface, and implementation acceptance harness for the target Julia Core HB workflow.

```text
Component Library
    -> Macro DSL
    -> CircuitPlan
    -> EngineeringGraph
    -> ExternalPort
    -> HBIntent
    -> compile_to_josephson
    -> HBProblemSpec
    -> run_hb_problem / run_frequency_sweep
```

It uses the target user-facing API directly. If Julia Core does not implement an API yet, the corresponding cell should fail clearly.
"""

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37004
@htl("""
<style>
    .hb-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
        gap: 0.75rem;
        margin: 0.75rem 0 1.25rem;
    }
    .hb-card {
        border: 1px solid rgba(125, 125, 125, 0.28);
        border-radius: 8px;
        padding: 0.85rem;
        background: color-mix(in srgb, Canvas 92%, CanvasText 8%);
        min-height: 88px;
    }
    .hb-card strong {
        display: block;
        margin-bottom: 0.35rem;
        font-size: 0.95rem;
    }
    .hb-card code {
        font-size: 0.85rem;
    }
    .hb-pill {
        display: inline-block;
        padding: 0.15rem 0.45rem;
        margin: 0.1rem 0.15rem 0.1rem 0;
        border-radius: 999px;
        border: 1px solid rgba(125, 125, 125, 0.35);
        font-size: 0.78rem;
    }
    .hb-panel {
        border-left: 4px solid #4f46e5;
        padding: 0.85rem 1rem;
        margin: 0.75rem 0 1.25rem;
        background: color-mix(in srgb, Canvas 90%, #4f46e5 10%);
    }
    .hb-mini-table {
        width: 100%;
        border-collapse: collapse;
        margin: 0.75rem 0;
    }
    .hb-mini-table th,
    .hb-mini-table td {
        border-bottom: 1px solid rgba(125, 125, 125, 0.25);
        padding: 0.45rem 0.35rem;
        text-align: left;
        vertical-align: top;
    }
    .hb-step {
        display: flex;
        align-items: center;
        justify-content: center;
        text-align: center;
        min-height: 72px;
    }
</style>

<div class="hb-panel">
    <strong>Notebook role:</strong> UX prototype + implementation acceptance harness<br>
    <strong>Execution policy:</strong> no generated solver traces<br>
    <strong>Current mode:</strong> target API<br>
    <strong>Expected behavior:</strong> fails if implementation is incomplete or inconsistent
</div>
""")

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37005
@htl("""
<div class="hb-grid">
    <div class="hb-card hb-step"><strong>CircuitPlan</strong><code>topology + intent owner</code></div>
    <div class="hb-card hb-step"><strong>HBIntent</strong><code>ports / sources / observables</code></div>
    <div class="hb-card hb-step"><strong>CompiledCircuit</strong><code>validated maps</code></div>
    <div class="hb-card hb-step"><strong>HBProblemSpec</strong><code>normalized hbsolve inputs</code></div>
    <div class="hb-card hb-step"><strong>Solver</strong><code>run_hb_problem</code></div>
</div>
""")

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37056
md"""
## Engineering Semantics Overview

Netlist rows are for solvers. `EngineeringGraph` is for humans.

The Macro DSL should capture reusable components, relation verbs, ports, HB source slots, observables, groups, and source provenance before compilation lowers anything to JosephsonCircuits rows.
"""

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37057
@htl("""
<div class="hb-grid">
    <div class="hb-card"><strong>Reusable Components</strong><span class="hb-pill">display names</span><span class="hb-pill">roles</span><span class="hb-pill">parameters</span></div>
    <div class="hb-card"><strong>Relations / Couplers</strong><span class="hb-pill">connect</span><span class="hb-pill">couple</span><span class="hb-pill">through</span></div>
    <div class="hb-card"><strong>Ports / Sources</strong><span class="hb-pill">signal</span><span class="hb-pill">pump</span><span class="hb-pill">readout</span></div>
    <div class="hb-card"><strong>Observables</strong><span class="hb-pill">S</span><span class="hb-pill">Z</span><span class="hb-pill">QE</span><span class="hb-pill">CM</span></div>
    <div class="hb-card"><strong>Compiled Netlist</strong><span class="hb-pill">solver rows</span><span class="hb-pill">trace links</span></div>
</div>
""")

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37006
md"""
## Interactive Parameter Panel

Parameter names are simple in the Julia API. Units are shown in labels and cards.

| Quantity | Default unit |
| --- | --- |
| capacitance | F |
| inductance | H |
| resistance | Ω |
| frequency | Hz |
| angular frequency after normalization | rad/s |
| current | A |
| length | m |
| time | s |
"""

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37007
md"### Circuit parameters"

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37008
@bind capacitance NumberField(1e-15:1e-15:500e-15; default = 80e-15)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37009
@bind inductance NumberField(1e-12:1e-12:100e-9; default = 10e-9)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf3700a
@bind port_resistance NumberField(1.0:1.0:200.0; default = 50.0)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf3700b
md"### Frequency sweep"

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf3700c
@bind start_frequency NumberField(1.0e9:0.1e9:20.0e9; default = 4.0e9)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf3700d
@bind stop_frequency NumberField(1.0e9:0.1e9:20.0e9; default = 6.0e9)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf3700e
@bind point_count Slider(11:10:1001; default = 401, show_value = true)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf3700f
md"### HB profile and source values"

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37010
@bind hb_profile Select([
    :pure_linear => "Pure linear / no pump",
    :pumped => "Pumped HB source slot",
])

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37011
@bind pump_frequency NumberField(1.0e9:0.1e9:30.0e9; default = 8.0e9)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37012
@bind pump_current NumberField(0.0:1e-9:1e-6; default = 0.0)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37013
@bind dc_enabled CheckBox(default = false)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37014
@bind dc_current NumberField(-1e-6:1e-9:1e-6; default = 0.0)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37015
md"### Harmonics"

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37016
@bind n_pump_harmonics NumberField(1:1:64; default = 16)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37017
@bind n_modulation_harmonics NumberField(0:1:64; default = 8)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37018
md"### Solver flags"

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37019
@bind threewavemixing CheckBox(default = false)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf3701a
@bind fourwavemixing CheckBox(default = true)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf3701b
@bind returnS CheckBox(default = true)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf3701c
@bind returnZ CheckBox(default = true)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf3701d
@bind returnQE CheckBox(default = true)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf3701e
@bind returnCM CheckBox(default = true)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf3701f
@bind sorting Select([:name => "name", :number => "number"])

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37020
@bind keyedarrays CheckBox(default = false)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37021
md"### Optional HB kwargs"

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37022
@bind iterations NumberField(1:1:5000; default = 200)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37023
@bind ftol NumberField(1e-12:1e-12:1e-5; default = 1e-8)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37024
@bind alphamin NumberField(1e-12:1e-12:1e-2; default = 1e-4)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37025
@bind switchofflinesearchtol NumberField(0.0:1e-8:1e-3; default = 1e-5)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37026
@bind nbatches NumberField(1:1:128; default = max(1, Threads.nthreads()))

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37027
@bind maxintermodorder NumberField(1:1:64; default = 16)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37028
md"### Inspection toggles"

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37054
@bind visible_key_cards MultiCheckBox(
    [
        :topology_key => "topology_key",
        :hb_intent_key => "hb_intent_key",
        :hb_problem_shape_key => "hb_problem_shape_key",
        :run_value_key => "run_value_key",
    ];
    default = [:topology_key, :hb_intent_key, :hb_problem_shape_key, :run_value_key],
)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37029
frequency_sweep = range(start_frequency, stop_frequency; length = point_count)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf3702a
optional_hb_kwargs = Dict(
    :iterations => iterations,
    :ftol => ftol,
    :alphamin => alphamin,
    :switchofflinesearchtol => switchofflinesearchtol,
    :nbatches => nbatches,
    :maxintermodorder => maxintermodorder,
)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf3702b
@htl("""
<table class="hb-mini-table">
    <thead>
        <tr><th>Parameter</th><th>Value</th><th>Unit</th></tr>
    </thead>
    <tbody>
        <tr><td><code>capacitance</code></td><td>$(capacitance)</td><td>F</td></tr>
        <tr><td><code>inductance</code></td><td>$(inductance)</td><td>H</td></tr>
        <tr><td><code>port_resistance</code></td><td>$(port_resistance)</td><td>Ω</td></tr>
        <tr><td><code>start_frequency</code></td><td>$(start_frequency)</td><td>Hz</td></tr>
        <tr><td><code>stop_frequency</code></td><td>$(stop_frequency)</td><td>Hz</td></tr>
        <tr><td><code>pump_frequency</code></td><td>$(pump_frequency)</td><td>Hz</td></tr>
        <tr><td><code>pump_current</code></td><td>$(pump_current)</td><td>A</td></tr>
    </tbody>
</table>
""")

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf3702c
md"""
## Frequency Grid Preview

This plot previews only the frequency grid. It is not a simulated S-parameter, gain trace, or solver result.
"""

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf3702d
plot(
    collect(frequency_sweep) ./ 1e9,
    zeros(length(frequency_sweep));
    xlabel = "Frequency (GHz)",
    ylabel = "Not solver result",
    label = "frequency grid only",
    title = "Frequency sweep grid preview",
)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37069
begin
    using SuperconductingCircuitsCore
end

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf3702e
md"""
## Macro DSL Circuit Section

The following cell uses the target Macro DSL as the primary authoring syntax.

It should fail until Julia Core implements `@circuit`, the macro expansion contract, and a component library provides `LumpedResonator`.
"""

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf3702f
plan = @circuit "hb-intent-demo" begin
    res = component(
        LumpedResonator(
            capacitance = capacitance,
            inductance = inductance,
        );
        display_name = :res,
        role = :resonator,
    )

    port(:signal_port) do
        index = 1
        endpoint = pin(res, :signal)
        resistance = port_resistance
        role = :mixed
    end
end

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37066
md"""
## Macro Expansion Preview

The macro expansion should show canonical Julia Core calls plus EngineeringGraph recording calls. This cell should fail if `@circuit` is missing or expands into unsupported hidden behavior.
"""

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37067
macro_expansion = macroexpand(
    @__MODULE__,
    quote
        @circuit "hb-intent-demo" begin
            res = component(
                LumpedResonator(
                    capacitance = capacitance,
                    inductance = inductance,
                );
                display_name = :res,
                role = :resonator,
            )

            port(:signal_port) do
                index = 1
                endpoint = pin(res, :signal)
                resistance = port_resistance
                role = :mixed
            end
        end
    end;
    recursive = true,
)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37058
md"""
## EngineeringGraph Preview

The EngineeringGraph is the component-level semantic graph created from the authored `CircuitPlan`. It is the source for human visualization and schematic export.
"""

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37059
engineering_graph = engineering_graph(plan)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf3705a
engineering_graph.components

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf3705b
engineering_graph.relations

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf3705c
engineering_graph.ports

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf3705d
engineering_graph.groups

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf3705e
@htl("""
<div class="hb-grid">
    <div class="hb-card">
        <strong>Engineering component</strong>
        <span class="hb-pill">display: <code>res</code></span>
        <span class="hb-pill">type: <code>LumpedResonator</code></span>
        <span class="hb-pill">role: <code>:resonator</code></span>
    </div>
    <div class="hb-card">
        <strong>Engineering port</strong>
        <span class="hb-pill">id: <code>:signal_port</code></span>
        <span class="hb-pill">role: <code>:mixed</code></span>
        <span class="hb-pill">component endpoint: <code>res.signal</code></span>
    </div>
</div>
""")

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf3705f
md"""
## DOT / Graph Preview

`to_dot(engineering_graph)` is the target component-graph export. This notebook displays DOT text directly; if a Graphviz renderer is added later, renderer errors should be visible rather than hidden.
"""

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37060
dot = to_dot(engineering_graph)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37061
Markdown.parse("```dot\n$(dot)\n```")

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37062
md"""
## Schemdraw Export Preview

`to_schemdraw_spec(engineering_graph)` returns renderer-neutral data intended for a later Python Schemdraw renderer.

Julia Core does not call Schemdraw directly in this notebook.
"""

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37063
schemdraw_spec = to_schemdraw_spec(engineering_graph)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37064
schemdraw_spec

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37065
md"""
### Python Schemdraw Future Renderer

A later Python renderer can consume `SchematicExportSpec` and call Schemdraw to produce SVG, PNG, or PDF. This keeps Python drawing dependencies outside Julia Core while preserving enough engineering semantics for schematic generation.
"""

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37030
md"""
## ExternalPort

The `:signal_port` declaration above belongs to `CircuitPlan` through the Macro DSL. Runner task payloads do not create it.
"""

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37031
engineering_graph.ports[:signal_port]

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37032
@htl("""
<div class="hb-grid">
    <div class="hb-card">
        <strong>Port</strong>
        <span class="hb-pill">id: <code>:signal_port</code></span>
        <span class="hb-pill">index: <code>1</code></span>
        <span class="hb-pill">endpoint: <code>pin(res, :signal)</code></span>
        <span class="hb-pill">role: <code>:mixed</code></span>
        <span class="hb-pill">resistance: <code>$(port_resistance) Ω</code></span>
    </div>
</div>
""")

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37033
md"""
## Pure Linear / No-Pump Profile

Pure linear sweep should not require a pump axis.

Rules:

- pure linear profile uses no pump axes;
- it has no pump source slot;
- it may still request S/Z/QE/CM outputs if the solver supports them;
- this notebook uses the empty mode tuple `()` as the pure-linear observable convention;
- do not create `PumpAxis(:pump)` with `pump_current = 0.0` for pure linear simulation.
"""

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37034
pure_linear_hb_intent = hb_intent!(
    plan;
    pump_axes = [],
    source_slots = [],
    observables = [
        SParameterRequest(
            id = :s11_signal,
            outputmode = (),
            outputport = :signal_port,
            inputmode = (),
            inputport = :signal_port,
        ),
    ],
    default_solver_controls = HBSolverControls(
        n_modulation_harmonics = 0,
        dc = false,
        threewavemixing = false,
        fourwavemixing = fourwavemixing,
        returnS = returnS,
        returnZ = returnZ,
        returnQE = returnQE,
        returnCM = returnCM,
        sorting = sorting,
        keyedarrays = keyedarrays,
    ),
)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37035
md"""
## Pumped HBIntent

`pump_current = 0.0` means the `:pump_in` source slot exists and is intentionally off. This is different from the pure linear no-pump profile.
"""

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37036
pumped_hb_intent = hb_intent!(
    plan;
    pump_axes = [
        PumpAxis(
            id = :pump,
            frequency_parameter = :pump_frequency,
        ),
    ],
    source_slots = [
        HBSourceSlot(
            id = :pump_in,
            role = :pump,
            port = :signal_port,
            mode = (1,),
            current_parameter = :pump_current,
        ),
    ],
    observables = [
        SParameterRequest(
            id = :s11_signal,
            outputmode = (0,),
            outputport = :signal_port,
            inputmode = (0,),
            inputport = :signal_port,
        ),
    ],
    default_solver_controls = HBSolverControls(
        n_pump_harmonics = n_pump_harmonics,
        n_modulation_harmonics = n_modulation_harmonics,
        dc = dc_enabled,
        threewavemixing = threewavemixing,
        fourwavemixing = fourwavemixing,
        returnS = returnS,
        returnZ = returnZ,
        returnQE = returnQE,
        returnCM = returnCM,
        sorting = sorting,
        keyedarrays = keyedarrays,
    ),
)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37037
hb_intent = hb_profile == :pure_linear ? pure_linear_hb_intent : pumped_hb_intent

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37038
@htl("""
<div class="hb-grid">
    <div class="hb-card">
        <strong>Pump axis</strong>
        $(hb_profile == :pure_linear ? @htl("<code>none</code>") : @htl("<code>:pump</code><br><span class='hb-pill'>frequency_parameter: :pump_frequency</span>"))
    </div>
    <div class="hb-card">
        <strong>Source slot</strong>
        $(hb_profile == :pure_linear ? @htl("<code>none</code>") : @htl("<code>:pump_in</code><br><span class='hb-pill'>mode: (1,)</span><span class='hb-pill'>current: $(pump_current) A</span>"))
    </div>
    <div class="hb-card">
        <strong>Observable</strong>
        <code>:s11_signal</code><br>
        <span class="hb-pill">profile: <code>$(hb_profile)</code></span>
    </div>
</div>
""")

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37039
md"""
## Runtime Bindings

Runtime values bind to compiled HB intent IDs. They do not define ports, source slots, mode tuples, or observables.
"""

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf3703a
run_spec = if hb_profile == :pure_linear
    HBRunSpec(
        frequency_sweep = frequency_sweep,
        pump_frequencies = Dict{Symbol,Float64}(),
        source_currents = Dict{Symbol,Float64}(),
        optional_hb_kwargs = optional_hb_kwargs,
    )
else
    HBRunSpec(
        frequency_sweep = frequency_sweep,
        pump_frequencies = Dict(:pump => pump_frequency),
        source_currents = Dict(:pump_in => pump_current),
        dc_currents = dc_enabled ? Dict(:dc_bias => dc_current) : Dict{Symbol,Float64}(),
        optional_hb_kwargs = optional_hb_kwargs,
    )
end

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf3703b
@htl("""
<table class="hb-mini-table">
    <thead>
        <tr><th>User-facing</th><th>Unit</th><th>Normalized JosephsonCircuits-facing value</th></tr>
    </thead>
    <tbody>
        <tr><td><code>pump_frequency</code></td><td>Hz</td><td><code>wp = 2π * pump_frequency</code></td></tr>
        <tr><td><code>pump_current</code></td><td>A</td><td><code>current = pump_current</code></td></tr>
        <tr><td><code>n_pump_harmonics</code></td><td>count</td><td><code>Npumpharmonics = ($(n_pump_harmonics),)</code></td></tr>
        <tr><td><code>n_modulation_harmonics</code></td><td>count</td><td><code>Nmodulationharmonics = ($(n_modulation_harmonics),)</code></td></tr>
    </tbody>
</table>
""")

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf3703c
md"""
## Key Separation

Changing UI controls affects different cache and validation keys.
"""

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf3703d
@htl("""
<div class="hb-grid">
    $("topology_key" in string.(visible_key_cards) || :topology_key in visible_key_cards ? @htl("""
    <div class="hb-card">
        <strong>topology_key</strong>
        <span class="hb-pill">capacitance</span>
        <span class="hb-pill">inductance</span>
        <span class="hb-pill">port rows</span>
    </div>
    """) : "")
    $("hb_intent_key" in string.(visible_key_cards) || :hb_intent_key in visible_key_cards ? @htl("""
    <div class="hb-card">
        <strong>hb_intent_key</strong>
        <span class="hb-pill">profile: $(hb_profile)</span>
        <span class="hb-pill">source slots</span>
        <span class="hb-pill">observables</span>
    </div>
    """) : "")
    $("hb_problem_shape_key" in string.(visible_key_cards) || :hb_problem_shape_key in visible_key_cards ? @htl("""
    <div class="hb-card">
        <strong>hb_problem_shape_key</strong>
        <span class="hb-pill">n_pump_harmonics</span>
        <span class="hb-pill">n_modulation_harmonics</span>
        <span class="hb-pill">return flags</span>
        <span class="hb-pill">maxintermodorder</span>
    </div>
    """) : "")
    $("run_value_key" in string.(visible_key_cards) || :run_value_key in visible_key_cards ? @htl("""
    <div class="hb-card">
        <strong>run_value_key</strong>
        <span class="hb-pill">frequency_sweep</span>
        <span class="hb-pill">pump_frequency</span>
        <span class="hb-pill">pump_current</span>
        <span class="hb-pill">ftol</span>
    </div>
    """) : "")
</div>
""")

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf3703e
md"""
## Validate / Compile / Normalize

These cells use the target validation and normalization API. They should fail clearly until Julia Core implements the missing contracts.
"""

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf3703f
authoring_report = validate_authoring(plan)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37040
compiled = compile_to_josephson(plan)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37068
compiled.netlist

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37041
hb_report = validate_hb_intent(compiled)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37042
hb_problem = build_hb_problem(compiled, run_spec)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37043
compiled.port_map

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37044
compiled.source_slot_map

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37045
compiled.observable_request_map

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37046
compiled.hb_validation_summary

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37047
hb_problem.ws

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37048
hb_problem.wp

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37049
hb_problem.sources

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf3704a
hb_problem.Nmodulationharmonics

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf3704b
hb_problem.Npumpharmonics

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf3704c
hb_problem.controls

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf3704d
if hb_profile == :pumped
    (
        hb_problem.Npumpharmonics == (n_pump_harmonics,),
        hb_problem.Nmodulationharmonics == (n_modulation_harmonics,),
        hb_problem.sources == [(mode = (1,), port = 1, current = pump_current)],
    )
else
    (
        isempty(hb_problem.wp),
        isempty(hb_problem.sources),
        hb_problem.Nmodulationharmonics == (n_modulation_harmonics,),
    )
end

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf3704e
md"""
## Output Family Capability Validation

Default requested outputs are S, Z, QE, and CM. Validation must confirm each requested family is supported by the selected circuit, HB profile, and solver configuration.

Unsupported requested families must fail clearly. Do not silently drop QE, CM, or any other requested output family.
"""

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf3704f
capability_report = validate_output_capabilities(compiled, hb_problem)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37050
@htl("""
<table class="hb-mini-table">
    <thead>
        <tr><th>Output</th><th>Requested</th><th>Supported</th><th>Action</th></tr>
    </thead>
    <tbody>
        <tr><td>S</td><td>$(returnS)</td><td><code>capability_report.S</code></td><td>run if supported</td></tr>
        <tr><td>Z</td><td>$(returnZ)</td><td><code>capability_report.Z</code></td><td>run if supported</td></tr>
        <tr><td>QE</td><td>$(returnQE)</td><td><code>capability_report.QE</code></td><td>fail if unsupported</td></tr>
        <tr><td>CM</td><td>$(returnCM)</td><td><code>capability_report.CM</code></td><td>fail if unsupported</td></tr>
    </tbody>
</table>
""")

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37051
md"""
## Implementation Acceptance Gate

The following cell is the implementation acceptance gate. It is expected to fail until runtime implementation catches up.

Do not generate a substitute solver trace for this cell.
"""

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37052
result = run_hb_problem(hb_problem)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37053
md"""
## UX Review Checklist

- [ ] I can understand where ports are declared.
- [ ] I can understand where pump axes are declared.
- [ ] I can understand where source slots are declared.
- [ ] I can distinguish source slots from S-parameter probes.
- [ ] I can set pump current to `0.0` and understand it means source-off.
- [ ] I can distinguish pure linear no-pump simulation from pump-off source-slot simulation.
- [ ] I can set common HB controls without reading JosephsonCircuits internals.
- [ ] I can inspect normalized JosephsonCircuits-facing values before running.
- [ ] I accept this API as the implementation target.
"""

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37055
md"""
## Appendix: JosephsonCircuits Call Shapes

Single-pump JPA:

```julia
ws = 2*pi*(4.5:0.001:5.0)*1e9
wp = (2*pi*4.75001*1e9,)
sources = [(mode=(1,), port=1, current=Ip)]
Npumpharmonics = (16,)
Nmodulationharmonics = (8,)
hbsolve(ws, wp, sources, Nmodulationharmonics, Npumpharmonics, circuit, circuitdefs)
```

Flux-pumped / DC style:

```julia
sources = [
    (mode=(0,), port=2, current=Idc),
    (mode=(1,), port=2, current=Ip),
]
hbsolve(ws, wp, sources, Nmodulationharmonics, Npumpharmonics,
    circuit, circuitdefs; dc=true, threewavemixing=true, fourwavemixing=true)
```

JTWPA larger harmonic example:

```julia
Npumpharmonics = (20,)
Nmodulationharmonics = (10,)
hbsolve(ws, wp, sources, Nmodulationharmonics, Npumpharmonics, circuit, circuitdefs)
```
"""

# ╔═╡ 00000000-0000-0000-0000-000000000001
PLUTO_PROJECT_TOML_CONTENTS = """
[deps]
HypertextLiteral = "ac1192a8-f4b3-4d9f-9b3f-fdef8e5ef241"
Plots = "91a5bcdd-55d7-5caf-9e0b-520d859cae80"
PlutoUI = "7f904dfe-b85e-4ff6-b463-dae2292396a8"
SuperconductingCircuitsCore = "b25d36e2-7598-4d7b-9e68-62f725d58ebd"
"""

# ╔═╡ 00000000-0000-0000-0000-000000000002
PLUTO_MANIFEST_TOML_CONTENTS = """
# This notebook intentionally omits a pinned manifest while the target API is still catching up.
"""

# ╔═╡ Cell order:
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37001
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37002
# ╟─4b8f6c4c-bd0e-4554-bf14-c7267cf37003
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37004
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37005
# ╟─4b8f6c4c-bd0e-4554-bf14-c7267cf37056
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37057
# ╟─4b8f6c4c-bd0e-4554-bf14-c7267cf37006
# ╟─4b8f6c4c-bd0e-4554-bf14-c7267cf37007
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37008
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37009
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf3700a
# ╟─4b8f6c4c-bd0e-4554-bf14-c7267cf3700b
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf3700c
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf3700d
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf3700e
# ╟─4b8f6c4c-bd0e-4554-bf14-c7267cf3700f
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37010
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37011
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37012
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37013
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37014
# ╟─4b8f6c4c-bd0e-4554-bf14-c7267cf37015
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37016
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37017
# ╟─4b8f6c4c-bd0e-4554-bf14-c7267cf37018
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37019
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf3701a
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf3701b
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf3701c
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf3701d
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf3701e
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf3701f
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37020
# ╟─4b8f6c4c-bd0e-4554-bf14-c7267cf37021
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37022
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37023
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37024
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37025
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37026
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37027
# ╟─4b8f6c4c-bd0e-4554-bf14-c7267cf37028
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37054
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37029
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf3702a
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf3702b
# ╟─4b8f6c4c-bd0e-4554-bf14-c7267cf3702c
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf3702d
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37069
# ╟─4b8f6c4c-bd0e-4554-bf14-c7267cf3702e
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf3702f
# ╟─4b8f6c4c-bd0e-4554-bf14-c7267cf37066
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37067
# ╟─4b8f6c4c-bd0e-4554-bf14-c7267cf37058
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37059
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf3705a
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf3705b
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf3705c
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf3705d
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf3705e
# ╟─4b8f6c4c-bd0e-4554-bf14-c7267cf3705f
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37060
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37061
# ╟─4b8f6c4c-bd0e-4554-bf14-c7267cf37062
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37063
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37064
# ╟─4b8f6c4c-bd0e-4554-bf14-c7267cf37065
# ╟─4b8f6c4c-bd0e-4554-bf14-c7267cf37030
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37031
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37032
# ╟─4b8f6c4c-bd0e-4554-bf14-c7267cf37033
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37034
# ╟─4b8f6c4c-bd0e-4554-bf14-c7267cf37035
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37036
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37037
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37038
# ╟─4b8f6c4c-bd0e-4554-bf14-c7267cf37039
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf3703a
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf3703b
# ╟─4b8f6c4c-bd0e-4554-bf14-c7267cf3703c
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf3703d
# ╟─4b8f6c4c-bd0e-4554-bf14-c7267cf3703e
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf3703f
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37040
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37068
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37041
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37042
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37043
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37044
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37045
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37046
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37047
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37048
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37049
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf3704a
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf3704b
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf3704c
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf3704d
# ╟─4b8f6c4c-bd0e-4554-bf14-c7267cf3704e
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf3704f
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37050
# ╟─4b8f6c4c-bd0e-4554-bf14-c7267cf37051
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37052
# ╟─4b8f6c4c-bd0e-4554-bf14-c7267cf37053
# ╟─4b8f6c4c-bd0e-4554-bf14-c7267cf37055
# ╟─00000000-0000-0000-0000-000000000001
# ╟─00000000-0000-0000-0000-000000000002
# ╟─00000000-0000-0000-0000-000000000001
# ╟─00000000-0000-0000-0000-000000000002
