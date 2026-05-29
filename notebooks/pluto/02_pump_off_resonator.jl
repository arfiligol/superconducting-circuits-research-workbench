### A Pluto.jl notebook ###
# v1.0.1

#> [frontmatter]
#> title = "02 Pump-Off Resonator"
#> tags = ["julia-core", "hb-problem-spec", "pump-off", "s11"]
#> description = "Tutorial Pluto notebook showing pump-off HBProblemSpec semantics and real S11 magnitude/phase plots from HBSolveResult."

using Markdown
using InteractiveUtils

# ╔═╡ dff36107-e537-4860-b82f-da4d57384156
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

    include(joinpath(@__DIR__, "includes", "hb_example_helpers.jl"))
    using .HBExampleHelpers
end

# ╔═╡ e5e8fa53-c206-4b31-baf9-7893c5cd377f
using Markdown

# ╔═╡ 7f98c42b-6c98-4640-9b62-3d2cc85c7b3b
module PumpOffResonatorComponents

using SuperconductingCircuitsCore

import SuperconductingCircuitsCore:
    component_id,
    component_pins,
    component_lines,
    default_line,
    component_parameters

Base.@kwdef struct OnePortResonator <: AbstractCircuitComponent
    id::String = "one_port_resonator"
    capacitance::Float64
    inductance::Float64
end

component_id(component::OnePortResonator) = component.id
component_pins(::OnePortResonator) = [:signal]
component_lines(::OnePortResonator) = Symbol[]
default_line(::OnePortResonator) = nothing

function component_parameters(component::OnePortResonator)
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

# ╔═╡ c17576c5-b9a0-4d4d-86fe-48d487cd6b12
using .PumpOffResonatorComponents: OnePortResonator

# ╔═╡ a9ca93fb-90f8-4eed-8ead-5f4ba4c1dd57
md"""
# 02 Pump-Off Resonator

This notebook focuses on the pump-off HB contract:

- the pump axis remains present;
- `hb_problem.wp` is finite and positive;
- the pump source slot remains present;
- `current = 0.0` turns that declared source off.

It follows the shared seven-point structure: parameters, local component and plan, EngineeringGraph, HBIntent, runtime-bound HBProblemSpec, real solver execution, and S11 extraction from `HBSolveResult`.
"""

# ╔═╡ b8185681-28c4-4c14-9389-3934d664e501
md"""
## 1. Parameters

Pump-off still declares a finite pump axis. The source current is the value that turns the declared pump source off.
"""

# ╔═╡ f2ae0d84-1f77-408e-ac56-424d5bc5ea90
begin
    capacitance = 80e-15
    inductance = 10e-9
    port_resistance = 50.0

    frequency_sweep = range(4.8e9, 6.4e9; length=21)
    pump_frequency = 8.0e9
    pump_current = 0.0

    optional_hb_kwargs = Dict{Symbol,Any}(
        :nbatches => 1,
        :iterations => 100,
        :ftol => 1e-8,
    )
end

# ╔═╡ 4b31128a-5ba3-462a-a243-187fa966d616
md"""
## 2. Local Component And CircuitPlan

This version uses the functional Core API directly: `CircuitPlan`, `register_component!`, `external_port!`, and explicit shunt relation calls.
"""

# ╔═╡ 83ffa7d6-4c36-41f6-8581-3fb53319fc75
begin
    plan = CircuitPlan("pump-off-resonator-s11")

    resonator = register_component!(
        plan,
        OnePortResonator(
            capacitance=capacitance,
            inductance=inductance,
        );
        display_name=:resonator,
        role=:resonator,
    )

    external_port!(
        plan;
        id=:signal_port,
        index=1,
        endpoint=pin(resonator, :signal),
        resistance=port_resistance,
        role=:reflection,
    )

    shunt_capacitor!(
        plan;
        id="resonator_c",
        at=pin(resonator, :signal),
        capacitance=capacitance,
    )

    shunt_inductor!(
        plan;
        id="resonator_l",
        at=pin(resonator, :signal),
        inductance=inductance,
    )

    plan
end

# ╔═╡ e9dfe7d7-340d-4177-b7d1-c08f7be004eb
md"""
## 3. EngineeringGraph

The graph remains the human-facing component and relation view. It records the local component, external port, and shunt C/L relations before the solver netlist is inspected.
"""

# ╔═╡ c32fc5ef-44e4-41d2-8f31-a86be9c9bdec
graph = engineering_graph(plan)

# ╔═╡ cf5f2ce3-d458-4eff-86b5-026d9cfb5f13
graph.components

# ╔═╡ da13a1c6-9c3f-4714-b43e-0e6fd24e560f
graph.ports

# ╔═╡ 50c1cde3-847f-4cc8-944e-45f83645fa84
graph.relations

# ╔═╡ f142b834-b1c8-43b3-b611-0e356473cfbc
md"""
## 4. HBIntent Pump-Off Semantics

`HBIntent` declares the pump axis and `:pump_in` source slot. Pump-off does not delete those declarations; it binds `source_currents[:pump_in] = 0.0` later.
"""

# ╔═╡ 868fc6e8-ece0-47bd-bbf2-cbbca5edb773
hb_intent = hb_intent!(
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
        n_pump_harmonics=1,
        n_modulation_harmonics=1,
        returnS=true,
        returnZ=true,
        returnQE=true,
        returnCM=true,
        sorting=:name,
        keyedarrays=false,
    ),
)

# ╔═╡ c3c29a06-df24-4a59-b2d9-592233c6df08
engineering_graph(plan).hb_overlay

# ╔═╡ a58ac752-32b4-4b2b-8f88-cd4212e31398
md"""
## 5. Runtime Binding And HBProblemSpec

The runtime binding keeps `pump_frequency` positive and binds the declared pump source to exactly zero current. `build_hb_problem` then normalizes hertz into `wp`, ports into source tuples, and controls into solver-ready fields.
"""

# ╔═╡ db30702c-7cd8-4bc1-8c06-0fe3a593d6e3
run_spec = HBRunSpec(
    frequency_sweep=frequency_sweep,
    pump_frequencies=Dict(:pump => pump_frequency),
    source_currents=Dict(:pump_in => pump_current),
    optional_hb_kwargs=optional_hb_kwargs,
)

# ╔═╡ 72c011a2-1bb0-4559-a2e9-646365877f64
run_spec.source_currents[:pump_in]

# ╔═╡ 449f522a-5440-4bb1-8642-bb31fb935941
authoring_report = validate_authoring(plan)

# ╔═╡ 1d6394d7-f724-473e-923b-868e7920576b
compiled = compile_to_josephson(plan)

# ╔═╡ 12df95ef-aef9-46b8-8dd9-53772b3df89a
compiled.netlist

# ╔═╡ 678965a9-adbd-4f81-a531-a218fa647147
compiled.port_map

# ╔═╡ b2850017-6db9-4e50-b61a-40ea7424728e
hb_report = validate_hb_intent(compiled)

# ╔═╡ bd259bfc-48b4-4d78-a1f2-2a53a95be7bf
hb_problem = build_hb_problem(compiled, run_spec)

# ╔═╡ 9eca5afa-e6a2-4049-a489-573381a874ec
hb_problem.wp

# ╔═╡ 465707c8-5b82-49cb-9895-01ccb2da8891
hb_problem.sources

# ╔═╡ afe8e52e-bcab-4a74-b8dd-9c8f621d0978
begin
    pump_source = only(hb_problem.sources)

    (
        pump_frequency_hz=pump_frequency,
        wp_rad_per_second=only(hb_problem.wp),
        source_mode=pump_source.mode,
        source_port=pump_source.port,
        source_current_ampere=pump_source.current,
        pump_axis_present=!isempty(hb_problem.wp),
        source_current_is_zero=iszero(pump_source.current),
    )
end

# ╔═╡ 66d2a5f2-290d-472e-b1c4-1964e942af71
output_request_report = validate_output_request_configuration(compiled, hb_problem)

# ╔═╡ f4f3bfd5-543f-465d-8b72-cf78b0f8fc3d
md"""
## 6. Solve With run_hb_problem

This is the executable acceptance gate for the normalized `HBProblemSpec`. The solver call remains real even though the pump source current is zero.
"""

# ╔═╡ 10205e5c-196f-4418-8cef-c110d631dd95
result = run_hb_problem(hb_problem)

# ╔═╡ 5beff9b9-1238-425c-a680-be6a3de30329
result

# ╔═╡ af12f93d-f5cb-4f03-9e58-a3fbfcf6249d
md"""
## 7. Real S11 Magnitude And Phase

The S11 trace is read from `result.traces[:zero_mode_s]["S11"]`; no substitute or synthetic trace is used.
"""

# ╔═╡ 810dec94-4d58-49cc-8b84-b710d7c92632
keys(result.traces)

# ╔═╡ 8a2e7566-2024-4e39-a03b-9c8350c3fd35
s11 = begin
    zero_mode_s_traces = get(result.traces, :zero_mode_s, nothing)
    zero_mode_s_traces isa AbstractDict ||
        error("result.traces does not contain :zero_mode_s.")
    haskey(zero_mode_s_traces, "S11") ||
        error("result.traces[:zero_mode_s] does not contain S11. Available labels: $(join(sort(collect(keys(zero_mode_s_traces))), ", "))")
    zero_mode_s_traces["S11"]
end

# ╔═╡ 80f93110-704a-4f7d-9995-758dda622f5d
plot(
    result.frequencies_hz ./ 1e9,
    20 .* log10.(abs.(s11));
    xlabel="Frequency (GHz)",
    ylabel="|S11| (dB)",
    label="S11",
    marker=:circle,
    title="Pump-off Resonator S11 Magnitude",
)

# ╔═╡ 1db75b77-c0d0-4cf7-82a9-a015094ab779
plot(
    result.frequencies_hz ./ 1e9,
    phase_deg(s11);
    xlabel="Frequency (GHz)",
    ylabel="phase(S11) (deg)",
    label="S11 phase",
    marker=:circle,
    title="Pump-off Resonator S11 Phase",
)

# ╔═╡ Cell order:
# ╠═e5e8fa53-c206-4b31-baf9-7893c5cd377f
# ╠═dff36107-e537-4860-b82f-da4d57384156
# ╟─a9ca93fb-90f8-4eed-8ead-5f4ba4c1dd57
# ╟─b8185681-28c4-4c14-9389-3934d664e501
# ╠═f2ae0d84-1f77-408e-ac56-424d5bc5ea90
# ╟─4b31128a-5ba3-462a-a243-187fa966d616
# ╠═7f98c42b-6c98-4640-9b62-3d2cc85c7b3b
# ╠═c17576c5-b9a0-4d4d-86fe-48d487cd6b12
# ╠═83ffa7d6-4c36-41f6-8581-3fb53319fc75
# ╟─e9dfe7d7-340d-4177-b7d1-c08f7be004eb
# ╠═c32fc5ef-44e4-41d2-8f31-a86be9c9bdec
# ╠═cf5f2ce3-d458-4eff-86b5-026d9cfb5f13
# ╠═da13a1c6-9c3f-4714-b43e-0e6fd24e560f
# ╠═50c1cde3-847f-4cc8-944e-45f83645fa84
# ╟─f142b834-b1c8-43b3-b611-0e356473cfbc
# ╠═868fc6e8-ece0-47bd-bbf2-cbbca5edb773
# ╠═c3c29a06-df24-4a59-b2d9-592233c6df08
# ╟─a58ac752-32b4-4b2b-8f88-cd4212e31398
# ╠═db30702c-7cd8-4bc1-8c06-0fe3a593d6e3
# ╠═72c011a2-1bb0-4559-a2e9-646365877f64
# ╠═449f522a-5440-4bb1-8642-bb31fb935941
# ╠═1d6394d7-f724-473e-923b-868e7920576b
# ╠═12df95ef-aef9-46b8-8dd9-53772b3df89a
# ╠═678965a9-adbd-4f81-a531-a218fa647147
# ╠═b2850017-6db9-4e50-b61a-40ea7424728e
# ╠═bd259bfc-48b4-4d78-a1f2-2a53a95be7bf
# ╠═9eca5afa-e6a2-4049-a489-573381a874ec
# ╠═465707c8-5b82-49cb-9895-01ccb2da8891
# ╠═afe8e52e-bcab-4a74-b8dd-9c8f621d0978
# ╠═66d2a5f2-290d-472e-b1c4-1964e942af71
# ╟─f4f3bfd5-543f-465d-8b72-cf78b0f8fc3d
# ╠═10205e5c-196f-4418-8cef-c110d631dd95
# ╠═5beff9b9-1238-425c-a680-be6a3de30329
# ╟─af12f93d-f5cb-4f03-9e58-a3fbfcf6249d
# ╠═810dec94-4d58-49cc-8b84-b710d7c92632
# ╠═8a2e7566-2024-4e39-a03b-9c8350c3fd35
# ╠═80f93110-704a-4f7d-9995-758dda622f5d
# ╠═1db75b77-c0d0-4cf7-82a9-a015094ab779
