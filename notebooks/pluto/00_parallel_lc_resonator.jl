### A Pluto.jl notebook ###
# v1.0.1

#> [frontmatter]
#> title = "00 Parallel LC Resonator"
#> tags = ["julia-core", "pluto", "hb", "parallel-lc", "s-parameters"]
#> description = "Canonical Pluto notebook for a one-port parallel LC resonator and real HB S/Z traces."

using Markdown
using InteractiveUtils

# ╔═╡ 9534149b-2579-50b1-ad6e-3c803cdde067
begin
    import Pkg
    using PlutoUI

    core_project = normpath(joinpath(@__DIR__, "..", "..", "core", "julia", "SuperconductingCircuitsCore"))
    visualizer_project = normpath(joinpath(@__DIR__, "..", "..", "core", "julia", "SuperconductingCircuitsVisualizer"))
    core_project_file = normpath(joinpath(core_project, "Project.toml"))
    visualizer_project_file = normpath(joinpath(visualizer_project, "Project.toml"))
    active_project_file = normpath(something(Base.active_project(), ""))

    if active_project_file != core_project_file && active_project_file != visualizer_project_file
        Pkg.develop(path=core_project)
        Pkg.develop(path=visualizer_project)
    else
        core_project in LOAD_PATH || pushfirst!(LOAD_PATH, core_project)
        visualizer_project in LOAD_PATH || pushfirst!(LOAD_PATH, visualizer_project)
    end

    using SuperconductingCircuitsCore
    using SuperconductingCircuitsVisualizer

    figure_config = PlotlyFigureConfig(
        download_filename=splitext(basename(@__FILE__))[1],
    )

    wide_figure_cell = WideCell(;
        max_width=max(1000, something(figure_config.display_width_px, 1000) + 80),
    )

    include(joinpath(@__DIR__, "includes", "hb_example_helpers.jl"))
    using .HBExampleHelpers: zero_mode_z
end

# ╔═╡ 3507bfd4-fb7d-5010-8209-63cc178dad0f
TableOfContents()

# ╔═╡ 5d6cb8e5-d3d9-5fa0-b026-31082acf4e01
md"""
# 00 Parallel LC Resonator

This notebook establishes the smallest pump-off HB workflow: a 50 ohm one-port drives a node with a capacitor and inductor in parallel to ground.

## Purpose

Show the common notebook pattern before adding coupling, distributed lines, or nonlinear devices: parameters first, local reusable component construction from Core primitives next, `CircuitPlan` / `EngineeringGraph` / compiled circuit inspection, explicit `HBProblemSpec`, explicit `result = run_hb_problem(hb_problem)`, real trace extraction, PlotlyJS figures through `WideCell`, and a compact sanity check.
"""

# ╔═╡ 5660a2ba-95d5-5c48-bbd3-4002f33f40ff
md"""
## Owns

- One-port parallel LC teaching example.
- Pump-off HB setup with a zero pump source slot.
- Parallel LC admittance interpretation from real solver output.
"""

# ╔═╡ 5ede2082-1fbe-5a5b-8630-9788bee699a8
LocalResource(joinpath(@__DIR__, "..", "..", "docs", "assets", "pluto-00-parallel-lc-resonator.svg"))

# ╔═╡ 8a783451-e145-59fa-89bd-78bfb281fe00
md"""
## LaTeX Physics

For a parallel LC at angular frequency ``\omega``,

```math
Y_{LC}(\omega) = j\omega C + \frac{1}{j\omega L}
```

and the ideal resonance is

```math
f_0 = \frac{1}{2\pi\sqrt{LC}}.
```

The resonance is clearest in admittance: the imaginary part crosses zero and the admittance magnitude exposes the shunt response directly.
"""

# ╔═╡ 392f1aed-60a4-5ba5-918b-971c81b7fc8e
md"""
## Modeling Conventions

- Lumped elements only: no line section or coupling-window approximation.
- Port resistance is the reference impedance used by the HB problem.
- Pump current is set to `0.0`, but the pump axis remains present so the same solve path is exercised.
"""

# ╔═╡ d1a11a1e-5f11-597b-87a0-420a44d8102c
begin
    capacitance = 58.2e-15
    inductance = 21.5e-9
    port_resistance = 50.0

    start_frequency = 1.0e9
    stop_frequency = 10.0e9
    point_count = 1000

    pump_frequency = 8.0e9
    pump_current = 0.0

    optional_hb_kwargs = Dict{Symbol,Any}(
        :nbatches => 1,
        :iterations => 120,
        :ftol => 1e-8,
    )
end

# ╔═╡ 7e6b1165-f72b-5d3c-9639-289d164ff4b0
f0_estimate = 1 / (2π * sqrt(inductance * capacitance))

# ╔═╡ 8d7dd4c8-6a71-5279-84b6-015779f6dad0
(
    capacitance_f=capacitance,
    inductance_h=inductance,
    f0_estimate_ghz=f0_estimate / 1e9,
    frequency_span_ghz=(start_frequency / 1e9, stop_frequency / 1e9),
)

# ╔═╡ 17e5af7d-902d-5c6d-9e62-c4fa8d711d3c
md"""
## Primitive-Built Component And Core Authoring

The reusable component is just two Core primitive relations: a shunt capacitor and a shunt inductor attached to the same node. The local tutorial builder below creates the reusable component, attaches the visible HB intent, and leaves the compile and solve boundaries explicit in notebook cells.
"""

# ╔═╡ 5b98253a-2eb1-57d2-a61e-90da2fd7410a
begin
    function frequency_sweep_tutorial(start_frequency, stop_frequency, point_count)
        point_count > 0 || throw(ArgumentError("point_count must be positive."))
        point_count == 1 && return [Float64(start_frequency)]
        return range(Float64(start_frequency), Float64(stop_frequency); length=Int(point_count))
    end

    function port_hb_intent_tutorial!(
        plan::CircuitPlan;
        ports,
        pump_frequency_parameter=:pump_frequency,
        pump_current_parameter=:pump_current,
        pump_slot=:pump_in,
        input_port=first(ports),
        n_pump_harmonics=1,
        n_modulation_harmonics=1,
    )
        observables = Any[]
        for output_port in ports
            for source_port in ports
                push!(
                    observables,
                    SParameterRequest(
                        id=Symbol(:s, output_port, :_, source_port),
                        outputmode=(0,),
                        outputport=output_port,
                        inputmode=(0,),
                        inputport=source_port,
                    ),
                )
            end
        end

        return hb_intent!(
            plan;
            pump_axes=[
                PumpAxis(
                    id=:pump,
                    frequency_parameter=pump_frequency_parameter,
                ),
            ],
            source_slots=[
                HBSourceSlot(
                    id=pump_slot,
                    role=:pump,
                    port=input_port,
                    mode=(1,),
                    current_parameter=pump_current_parameter,
                ),
            ],
            observables=observables,
            default_solver_controls=HBSolverControls(
                n_pump_harmonics=n_pump_harmonics,
                n_modulation_harmonics=n_modulation_harmonics,
                returnS=true,
                returnZ=true,
                returnQE=true,
                returnCM=true,
                keyedarrays=false,
            ),
        )
    end

    function add_parallel_lc_resonator_tutorial!(
        plan::CircuitPlan;
        id,
        node,
        capacitance,
        inductance,
    )
        capacitor = shunt_capacitor!(
            plan;
            id="$(id)_capacitance",
            at=node,
            capacitance=capacitance,
            role=:parallel_lc_capacitance,
            label="parallel LC C",
        )
        inductor = shunt_inductor!(
            plan;
            id="$(id)_inductance",
            at=node,
            inductance=inductance,
            role=:parallel_lc_inductance,
            label="parallel LC L",
        )
        return (node=node, capacitor=capacitor, inductor=inductor)
    end

    function build_parallel_lc_plan_tutorial(;
        id="parallel-lc-resonator-tutorial",
        capacitance,
        inductance,
        port_resistance,
    )
        plan = CircuitPlan(id)
        signal = external_node("signal")
        external_port!(plan; id=:signal_port, index=1, endpoint=signal, resistance=port_resistance, role=:mixed)
        add_parallel_lc_resonator_tutorial!(
            plan;
            id="resonator",
            node=signal,
            capacitance=capacitance,
            inductance=inductance,
        )
        port_hb_intent_tutorial!(plan; ports=[:signal_port])
        return plan
    end

    function hb_run_spec_tutorial(;
        start_frequency,
        stop_frequency,
        point_count,
        pump_frequency,
        pump_current,
        optional_hb_kwargs,
    )
        return HBRunSpec(
            frequency_sweep=frequency_sweep_tutorial(start_frequency, stop_frequency, point_count),
            pump_frequencies=Dict(:pump => Float64(pump_frequency)),
            source_currents=Dict(:pump_in => Float64(pump_current)),
            optional_hb_kwargs=Dict{Symbol,Any}(optional_hb_kwargs),
        )
    end
end

# ╔═╡ f70f5b54-a011-54ff-9cd0-06484f69d097
circuit_plan = build_parallel_lc_plan_tutorial(
    capacitance=capacitance,
    inductance=inductance,
    port_resistance=port_resistance,
)

# ╔═╡ d1f9dcf2-e22c-555a-b847-c8a1a0f2ee45
engineering_graph = SuperconductingCircuitsCore.engineering_graph(circuit_plan)

# ╔═╡ e1b18589-45a7-5c49-b57f-f6beaeadc3be
compiled_circuit = compile_to_josephson(circuit_plan)

# ╔═╡ 2dd70db0-1de6-5bff-9285-a5d3065919ad
primitive_component = (
    shunt_capacitors=filter(relation -> relation isa ShuntCapacitor, circuit_plan.relations),
    shunt_inductors=filter(relation -> relation isa ShuntInductor, circuit_plan.relations),
)

# ╔═╡ 1d5d5042-a2c5-56e9-a192-9dd8744ba65c
primitive_component

# ╔═╡ 97b220ce-1687-5883-829f-8f15e27122d5
(
    plan_id=circuit_plan.id,
    relation_count=length(circuit_plan.relations),
    parameter_count=length(circuit_plan.parameters),
    port_ids=sort(collect(keys(engineering_graph.ports))),
)

# ╔═╡ 95f075ea-492e-5a7e-87b1-747df86eaccc
engineering_graph.relations

# ╔═╡ 23809eab-197e-589f-b6c9-c9f273f9f70c
compiled_circuit.netlist

# ╔═╡ 8c277327-69d3-5f71-b992-a6c34ac61c12
compiled_circuit.component_values

# ╔═╡ 725d1e59-b1b0-546a-847f-a2b2e48146c5
md"""
## HBProblemSpec And Real Solver Output

The notebook keeps the solve boundary visible. `hb_problem` is inspectable before execution, and the next cell is intentionally the explicit solver call used by all canonical Pluto notebooks.
"""

# ╔═╡ 1a072efd-3ba2-55f6-a4f3-9374c84517bb
hb_problem = build_hb_problem(
    compiled_circuit,
    hb_run_spec_tutorial(
        start_frequency=start_frequency,
        stop_frequency=stop_frequency,
        point_count=point_count,
        pump_frequency=pump_frequency,
        pump_current=pump_current,
        optional_hb_kwargs=optional_hb_kwargs,
    ),
)

# ╔═╡ b33ab863-eaa9-5797-815f-a8adfaf7d1d4
(
    frequency_points=length(hb_problem.frequencies_hz),
    pump_axes=hb_problem.wp,
    sources=hb_problem.sources,
    controls=hb_problem.controls,
)

# ╔═╡ 7d7143fd-9a05-53f7-ba2e-1f32ff78c38a
result = run_hb_problem(hb_problem)

# ╔═╡ c8e7067f-7077-514f-8788-45b6d484a293
output_family_labels = let
    labels = Dict{Symbol,Vector{String}}()
    for family_name in (:zero_mode_s, :s_parameter_mode, :z_parameter_mode, :qe_mode, :qeideal_mode, :cm_mode)
        traces = get(result.traces, family_name, nothing)
        if traces isa AbstractDict
            labels[family_name] = sort(string.(collect(keys(traces))))
        end
    end
    labels
end

# ╔═╡ b37adf3d-8eb2-5c29-9a44-1ca8edf83343
begin
    frequencies_ghz = result.frequencies_hz ./ 1e9
    z11 = zero_mode_z(result, 1, 1)
    y11 = 1 ./ z11
end

# ╔═╡ fbcb058d-2e35-5326-b0ea-c353390fd955
sanity = (
    point_count_matches=length(result.frequencies_hz) == point_count,
    z11_points=length(z11),
    y11_points=length(y11),
    finite_y_trace=all(isfinite, real.(y11)) && all(isfinite, imag.(y11)),
    resonance_in_span=start_frequency <= f0_estimate <= stop_frequency,
)

# ╔═╡ 3e628e29-6491-5103-a89b-e79c6ee0d078
sanity

# ╔═╡ 90ed2100-833a-58f4-8af8-d1af241015f6
begin
    y_trace_figure(
        result.frequencies_hz,
        ["Y11" => y11];
        title="Parallel LC Input Admittance",
        config=figure_config,
    )
end |> wide_figure_cell

# ╔═╡ Cell order:
# ╠═9534149b-2579-50b1-ad6e-3c803cdde067
# ╠═3507bfd4-fb7d-5010-8209-63cc178dad0f
# ╟─5d6cb8e5-d3d9-5fa0-b026-31082acf4e01
# ╟─5660a2ba-95d5-5c48-bbd3-4002f33f40ff
# ╠═5ede2082-1fbe-5a5b-8630-9788bee699a8
# ╟─8a783451-e145-59fa-89bd-78bfb281fe00
# ╟─392f1aed-60a4-5ba5-918b-971c81b7fc8e
# ╠═d1a11a1e-5f11-597b-87a0-420a44d8102c
# ╠═7e6b1165-f72b-5d3c-9639-289d164ff4b0
# ╠═8d7dd4c8-6a71-5279-84b6-015779f6dad0
# ╟─17e5af7d-902d-5c6d-9e62-c4fa8d711d3c
# ╠═5b98253a-2eb1-57d2-a61e-90da2fd7410a
# ╠═f70f5b54-a011-54ff-9cd0-06484f69d097
# ╠═d1f9dcf2-e22c-555a-b847-c8a1a0f2ee45
# ╠═e1b18589-45a7-5c49-b57f-f6beaeadc3be
# ╠═2dd70db0-1de6-5bff-9285-a5d3065919ad
# ╠═1d5d5042-a2c5-56e9-a192-9dd8744ba65c
# ╠═97b220ce-1687-5883-829f-8f15e27122d5
# ╠═95f075ea-492e-5a7e-87b1-747df86eaccc
# ╠═23809eab-197e-589f-b6c9-c9f273f9f70c
# ╠═8c277327-69d3-5f71-b992-a6c34ac61c12
# ╟─725d1e59-b1b0-546a-847f-a2b2e48146c5
# ╠═1a072efd-3ba2-55f6-a4f3-9374c84517bb
# ╠═b33ab863-eaa9-5797-815f-a8adfaf7d1d4
# ╠═7d7143fd-9a05-53f7-ba2e-1f32ff78c38a
# ╠═c8e7067f-7077-514f-8788-45b6d484a293
# ╠═b37adf3d-8eb2-5c29-9a44-1ca8edf83343
# ╠═fbcb058d-2e35-5326-b0ea-c353390fd955
# ╠═3e628e29-6491-5103-a89b-e79c6ee0d078
# ╠═90ed2100-833a-58f4-8af8-d1af241015f6
