### A Pluto.jl notebook ###
# v1.0.1

#> [frontmatter]
#> title = "HB Simulation Intent Tutorial"
#> tags = ["julia-core", "hb-intent", "engineering-graph", "acceptance-harness"]
#> description = "Markdown-first Pluto tutorial for the Julia Core CircuitPlan, EngineeringGraph, HBIntent, and HBProblemSpec workflow."

using Markdown
using InteractiveUtils

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37002
begin
    import Pkg

    core_project = normpath(joinpath(@__DIR__, "..", "..", "core", "julia", "SuperconductingCircuitsCore"))
    core_project_file = normpath(joinpath(core_project, "Project.toml"))
    active_project_file = normpath(something(Base.active_project(), ""))

    if active_project_file != core_project_file
        Pkg.develop(path=core_project)
    end

    using SuperconductingCircuitsCore
    using Plots
end

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37001
using Markdown

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37009
module NotebookComponents

using SuperconductingCircuitsCore

import SuperconductingCircuitsCore:
    component_id,
    component_pins,
    component_lines,
    default_line,
    component_parameters

Base.@kwdef struct GroundedResonator <: AbstractCircuitComponent
    id::String = "res"
    capacitance::Float64
    inductance::Float64
end

component_id(component::GroundedResonator) = component.id
component_pins(::GroundedResonator) = [:signal]
component_lines(::GroundedResonator) = Symbol[]
default_line(::GroundedResonator) = nothing

function component_parameters(component::GroundedResonator)
    return [
        ParameterMetadata(
            name=:capacitance,
            role=NumericParameter(),
            owner=component.id,
            targets=[:capacitance],
            sweep_name=:capacitance,
            units="F",
            assumptions=["changing capacitance does not change component topology"],
        ),
        ParameterMetadata(
            name=:inductance,
            role=NumericParameter(),
            owner=component.id,
            targets=[:inductance],
            sweep_name=:inductance,
            units="H",
            assumptions=["changing inductance does not change component topology"],
        ),
    ]
end

end

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf3700a
using .NotebookComponents: GroundedResonator

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37003
md"""
# HB Simulation Intent Tutorial

This notebook is a small, executable tutorial for the Julia Core authoring path:

```text
local component library object
    -> @circuit
    -> CircuitPlan
    -> EngineeringGraph
    -> HBIntent
    -> compile_to_josephson
    -> HBProblemSpec
    -> run_hb_problem
```

It does not synthesize solver output. The final cell remains the acceptance gate:

```julia
result = run_hb_problem(hb_problem)
```
"""

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37004
md"""
## Tutorial Parameters

Use simple Julia names for user-facing parameters. Frequencies are in hertz, currents are in amperes, capacitance is in farads, and inductance is in henries.
"""

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37005
begin
    capacitance = 80e-15
    inductance = 10e-9
    resistance = 50.0

    start_frequency = 4.0e9
    stop_frequency = 6.0e9
    point_count = 5

    hb_profile = :pump_off
    pump_frequency = 8.0e9
    pump_current = 0.0
    dc_current = 0.0

    n_pump_harmonics = 16
    n_modulation_harmonics = 8

    returnS = true
    returnZ = true
    returnQE = true
    returnCM = true

    optional_hb_kwargs = Dict{Symbol,Any}(
        :iterations => 200,
        :ftol => 1e-8,
        :alphamin => 1e-4,
        :switchofflinesearchtol => 1e-5,
        :nbatches => max(1, Threads.nthreads()),
        :maxintermodorder => 16,
    )
end

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37006
frequency_sweep = range(start_frequency, stop_frequency; length=point_count)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37007
begin
    hb_profile in (:pump_off, :pumped, :pumped_dc) ||
        error("Unsupported hb_profile: $(hb_profile). Use :pump_off, :pumped, or :pumped_dc.")
    isfinite(pump_frequency) && pump_frequency > 0 ||
        error("pump_frequency must be finite and positive, even when pump_current is zero.")

    effective_pump_current = hb_profile == :pump_off ? 0.0 : pump_current

    (
        capacitance=capacitance,
        inductance=inductance,
        resistance=resistance,
        frequency_sweep=collect(frequency_sweep),
        hb_profile=hb_profile,
        pump_frequency=pump_frequency,
        pump_current=effective_pump_current,
    )
end

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37008
md"""
## Local Reusable Component

Julia Core owns the authoring contract. Concrete component families belong in a component library.

For this tutorial, the component library is intentionally local to the notebook. It is not a Core-exported demo component.
"""

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf3700b
md"""
## CircuitPlan

The macro DSL is the human-facing authoring syntax. It should still expand to canonical Julia Core calls such as `CircuitPlan`, `register_component!`, `external_port!`, and EngineeringGraph recording.
"""

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf3700c
plan = @circuit "hb-intent-demo" begin
    resonator = component(
        GroundedResonator(
            capacitance=capacitance,
            inductance=inductance,
        );
        display_name=:resonator,
        role=:resonator,
    )

    port(:signal_port) do
        index = 1
        endpoint = pin(resonator, :signal)
        resistance = resistance
        role = :mixed
    end
end

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf3700d
resonator_capacitance = shunt_capacitor!(
    plan;
    id="resonator_capacitance",
    at=pin(resonator, :signal),
    capacitance=capacitance,
)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf3700e
resonator_inductance = shunt_inductor!(
    plan;
    id="resonator_inductance",
    at=pin(resonator, :signal),
    inductance=inductance,
)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37025
md"""
!!! note "EngineeringGraph relation recording"
    Physical Julia Core operations such as `shunt_capacitor!` and `shunt_inductor!`
    also record the corresponding EngineeringGraph relation. This keeps the solver
    model and the human-facing graph synchronized without a duplicate manual
    graph-recording call.
"""

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf3700f
md"""
The current lumped compiler MVP lowers explicit capacitor, inductor, and external port rows. The local component preserves both `capacitance` and `inductance` as component-library metadata, while explicit Core relations define the physical solver elements.
"""

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37010
md"""
## EngineeringGraph Inspection

The EngineeringGraph is the human-facing semantic graph. Keep this inspection component-level rather than reconstructing meaning from solver rows.
"""

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37011
graph = engineering_graph(plan)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37012
graph.components

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37013
graph.ports

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37014
graph.relations

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37015
md"""
## HBIntent

`CircuitPlan` declares the HB simulation intent. Runtime values bind to declared IDs later; they do not invent ports, pump axes, source slots, or observables.

Use `hb_profile = :pump_off`, `:pumped`, or `:pumped_dc`. Pump-off is still a declared pump problem: the pump axis and source slot exist, `pump_frequency` is finite and positive, and the bound `pump_current` is `0.0`.

For DC bias, add a `HBSourceSlot(role = :dc_bias, mode = (0,))` and bind its current through `source_currents`.
"""

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37016
hb_intent = if hb_profile in (:pump_off, :pumped)
    hb_intent!(
        plan;
        pump_axes=[
            PumpAxis(
                id=:pump,
                frequency_parameter=:pump_frequency,
            ),
        ],
        source_slots=[
            HBSourceSlot(
                id=:pump_in,
                role=:pump,
                port=:signal_port,
                mode=(1,),
                current_parameter=:pump_current,
            ),
        ],
        observables=[
            SParameterRequest(
                id=:s11_signal,
                outputmode=(0,),
                outputport=:signal_port,
                inputmode=(0,),
                inputport=:signal_port,
            ),
        ],
        default_solver_controls=HBSolverControls(
            n_pump_harmonics=n_pump_harmonics,
            n_modulation_harmonics=n_modulation_harmonics,
            dc=false,
            threewavemixing=false,
            fourwavemixing=true,
            returnS=returnS,
            returnZ=returnZ,
            returnQE=returnQE,
            returnCM=returnCM,
            sorting=:name,
            keyedarrays=false,
        ),
    )
elseif hb_profile == :pumped_dc
    hb_intent!(
        plan;
        pump_axes=[
            PumpAxis(
                id=:pump,
                frequency_parameter=:pump_frequency,
            ),
        ],
        source_slots=[
            HBSourceSlot(
                id=:dc_bias,
                role=:dc_bias,
                port=:signal_port,
                mode=(0,),
                current_parameter=:dc_current,
            ),
            HBSourceSlot(
                id=:pump_in,
                role=:pump,
                port=:signal_port,
                mode=(1,),
                current_parameter=:pump_current,
            ),
        ],
        observables=[
            SParameterRequest(
                id=:s11_signal,
                outputmode=(0,),
                outputport=:signal_port,
                inputmode=(0,),
                inputport=:signal_port,
            ),
        ],
        default_solver_controls=HBSolverControls(
            n_pump_harmonics=n_pump_harmonics,
            n_modulation_harmonics=n_modulation_harmonics,
            dc=true,
            threewavemixing=true,
            fourwavemixing=true,
            returnS=returnS,
            returnZ=returnZ,
            returnQE=returnQE,
            returnCM=returnCM,
            sorting=:name,
            keyedarrays=false,
        ),
    )
else
    error("Unsupported hb_profile: $(hb_profile). Use :pump_off, :pumped, or :pumped_dc.")
end

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37017
graph.hb_overlay

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37018
md"""
## Runtime Bindings

The runtime spec binds concrete frequency and current values to the compiled intent. `pump_current = 0.0` is a real source-off binding for the declared `:pump_in` slot, not a request to remove the pump axis.
"""

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37019
run_spec = begin
    currents = hb_profile == :pumped_dc ?
        Dict(:dc_bias => dc_current, :pump_in => effective_pump_current) :
        Dict(:pump_in => effective_pump_current)

    HBRunSpec(
        frequency_sweep=frequency_sweep,
        pump_frequencies=Dict(:pump => pump_frequency),
        source_currents=currents,
        optional_hb_kwargs=optional_hb_kwargs,
    )
end

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf3701a
md"""
## Validate, Compile, Normalize

These cells exercise the target Julia Core API up to HB problem construction. They inspect solver inputs, not solver outputs.
"""

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf3701b
authoring_report = validate_authoring(plan)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf3701c
compiled = compile_to_josephson(plan)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf3701d
compiled.netlist

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf3701e
compiled.port_map

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf3701f
hb_report = validate_hb_intent(compiled)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37020
hb_problem = build_hb_problem(compiled, run_spec)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37021
(
    compiled_netlist_rows=length(hb_problem.compiled.netlist),
    frequencies_hz=hb_problem.frequencies_hz,
    ws_count=length(hb_problem.ws),
    wp=hb_problem.wp,
    sources=hb_problem.sources,
    Nmodulationharmonics=hb_problem.Nmodulationharmonics,
    Npumpharmonics=hb_problem.Npumpharmonics,
    optional_hb_kwargs=hb_problem.optional_hb_kwargs,
)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37022
output_request_report = validate_output_request_configuration(compiled, hb_problem)

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37023
md"""
## Acceptance Gate

This is the implementation acceptance gate. It calls the executable HBProblemSpec API with the normalized compiled circuit, pump, source, harmonic, control, observable, and solver-kwarg values.

Do not replace this with substitute curves or non-solver values.
"""

# ╔═╡ 4b8f6c4c-bd0e-4554-bf14-c7267cf37024
result = run_hb_problem(hb_problem)

# ╔═╡ 0613bc7e-fe07-4d18-ba7a-a60bebf9168f
result

# ╔═╡ 652be638-dd53-4317-826c-7f54def7a8eb
keys(result.traces)

# ╔═╡ 42213dd5-376b-4bec-8754-ac98cdfb7bae
zero_mode_s11 = begin
    zero_mode_s_traces = get(result.traces, :zero_mode_s, Dict{String,Vector{ComplexF64}}())
    haskey(zero_mode_s_traces, "S11") ? zero_mode_s_traces["S11"] :
    "S11 is not available. Available zero-mode labels: $(join(sort(collect(keys(zero_mode_s_traces))), ", "))"
end

# ╔═╡ daf0be54-cca4-4ddf-ab78-6c9c2660dcb1
begin
    zero_mode_s_traces = get(result.traces, :zero_mode_s, nothing)
    zero_mode_s_traces isa AbstractDict ||
        error("result.traces does not contain :zero_mode_s.")
    haskey(zero_mode_s_traces, "S11") ||
        error("result.traces[:zero_mode_s] does not contain S11. Available labels: $(join(sort(collect(keys(zero_mode_s_traces))), ", "))")

    s11 = zero_mode_s_traces["S11"]
    plot(
        result.frequencies_hz ./ 1e9,
        20 .* log10.(abs.(s11));
        xlabel="Frequency (GHz)",
        ylabel="|S11| (dB)",
        label="S11",
        marker=:circle,
        title="Zero-mode S11 from HBSolveResult",
    )
end

# ╔═╡ Cell order:
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37001
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37002
# ╟─4b8f6c4c-bd0e-4554-bf14-c7267cf37003
# ╟─4b8f6c4c-bd0e-4554-bf14-c7267cf37004
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37005
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37006
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37007
# ╟─4b8f6c4c-bd0e-4554-bf14-c7267cf37008
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37009
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf3700a
# ╟─4b8f6c4c-bd0e-4554-bf14-c7267cf3700b
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf3700c
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf3700d
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf3700e
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37025
# ╟─4b8f6c4c-bd0e-4554-bf14-c7267cf3700f
# ╟─4b8f6c4c-bd0e-4554-bf14-c7267cf37010
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37011
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37012
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37013
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37014
# ╟─4b8f6c4c-bd0e-4554-bf14-c7267cf37015
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37016
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37017
# ╟─4b8f6c4c-bd0e-4554-bf14-c7267cf37018
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37019
# ╟─4b8f6c4c-bd0e-4554-bf14-c7267cf3701a
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf3701b
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf3701c
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf3701d
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf3701e
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf3701f
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37020
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37021
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37022
# ╟─4b8f6c4c-bd0e-4554-bf14-c7267cf37023
# ╠═4b8f6c4c-bd0e-4554-bf14-c7267cf37024
# ╠═0613bc7e-fe07-4d18-ba7a-a60bebf9168f
# ╠═652be638-dd53-4317-826c-7f54def7a8eb
# ╠═42213dd5-376b-4bec-8754-ac98cdfb7bae
# ╠═daf0be54-cca4-4ddf-ab78-6c9c2660dcb1
