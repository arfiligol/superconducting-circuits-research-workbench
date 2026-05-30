### A Pluto.jl notebook ###
# v1.0.1

#> [frontmatter]
#> title = "01 Reflective JPA Capacitive-Coupled LC"
#> tags = ["julia-core", "pluto", "jpa", "nonlinear", "reflection"]
#> description = "Canonical Pluto notebook structure for a reflective JPA with a capacitively coupled LC mode."

using Markdown
using InteractiveUtils

# ╔═╡ 5b5fb3c0-7d7b-528c-bc3e-b01bf07f7185
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
    using .HBExampleHelpers: db20, phase_deg, zero_mode_s, zero_mode_z
end

# ╔═╡ a79e2c58-acd9-57c1-bff0-634f473c981e
TableOfContents()

# ╔═╡ dbd7364d-5052-57d5-89c2-2bc2e40ca7cc
md"""
# 01 Reflective JPA / Capacitive-Coupled LC

This notebook builds a one-port reflective JPA from a coupling capacitor, a resonator capacitance, and a Josephson junction branch.

## Purpose

Show how nonlinear Core primitives enter the same authoring flow as passive LC circuits: parameters, reusable component construction, `CircuitPlan`, `EngineeringGraph`, compiled circuit, `HBProblemSpec`, explicit solve, real trace extraction, PlotlyJS figures through `WideCell`, and sanity checks.
"""

# ╔═╡ 3f45a386-f4b4-5257-85fa-2f768634f88c
md"""
## Owns

- One-port reflective JPA topology.
- Capacitive coupling between a 50 ohm environment and the nonlinear LC mode.
- Real `S11` magnitude, phase, and input impedance from the pumped HB solve.
"""

# ╔═╡ 1567e5ff-6e0a-5589-b7f1-9f1eb1a0aeca
LocalResource(joinpath(@__DIR__, "..", "..", "docs", "assets", "pluto-01-reflective-jpa-capacitive-coupled-lc.svg"))

# ╔═╡ 03e9e911-d989-5ed1-93e3-c18cd562353c
md"""
## LaTeX Physics

A pumped reflective JPA is read through its reflection coefficient

$$
\Gamma(\omega) = \frac{Z_{in}(\omega) - Z_0}{Z_{in}(\omega) + Z_0}.
$$

The small-signal resonance is set by the effective nonlinear inductance and total capacitance,

$$
\omega_r \approx \frac{1}{\sqrt{L_{J,eff} C_\Sigma}}.
$$

The notebook does not invent gain curves. The plotted traces come from `run_hb_problem(hb_problem)`.
"""

# ╔═╡ 31e5052e-4f40-5d6d-9c31-b74660a4b59d
md"""
## Modeling Conventions

- One reflective signal port.
- A lumped coupling capacitor separates the port node from the JPA resonator node.
- Pump parameters are explicit drive inputs, not hidden notebook state.
- The Josephson branch lowers to a JosephsonCircuits `Lj` row.
"""

# ╔═╡ 30fa5e0f-8a16-58db-b33a-d46b621843ad
begin
    coupling_capacitance = 6.0e-15
    resonator_capacitance = 90.0e-15
    josephson_inductance = 7.5e-9
    port_resistance = 50.0

    start_frequency = 4.0e9
    stop_frequency = 9.0e9
    point_count = 1000

    pump_frequency = 12.0e9
    pump_current = 20.0e-9

    optional_hb_kwargs = Dict{Symbol,Any}(
        :nbatches => 1,
        :iterations => 180,
        :ftol => 1e-8,
    )
end

# ╔═╡ bc03d638-9631-53e9-b857-48ec8cd6d994
linear_f0_estimate = 1 / (2π * sqrt(josephson_inductance * resonator_capacitance))

# ╔═╡ c471be37-792a-50ca-9252-8fd1f895ccb4
(
    coupling_capacitance_f=coupling_capacitance,
    resonator_capacitance_f=resonator_capacitance,
    josephson_inductance_h=josephson_inductance,
    linear_f0_estimate_ghz=linear_f0_estimate / 1e9,
)

# ╔═╡ 7d62378c-f755-5076-8405-22a4071c2fac
md"""
## Primitive-Built Component And Core Authoring

The reusable component is made from the same Core relations used by passive notebooks: a point coupling capacitor, shunt capacitance, and a `JosephsonJunction`. The library-equivalent builder below keeps the full `CircuitPlan` and `HBProblemSpec` visible before the explicit solve.
"""

# ╔═╡ 8c11a0c6-5045-53f3-bf4f-2026bb14e7a5
reflective_jpa_core_builder = build_reflective_jpa_capacitive_coupled_lc_example

# ╔═╡ 61c90184-a06a-5ec4-ac38-d54203445552
example = reflective_jpa_core_builder(
    coupling_capacitance=coupling_capacitance,
    resonator_capacitance=resonator_capacitance,
    josephson_inductance=josephson_inductance,
    port_resistance=port_resistance,
    start_frequency=start_frequency,
    stop_frequency=stop_frequency,
    point_count=point_count,
    pump_frequency=pump_frequency,
    pump_current=pump_current,
    optional_hb_kwargs=optional_hb_kwargs,
)

# ╔═╡ 00db8292-dc5c-5faf-b7cd-974c2533e7f2
circuit_plan = example.plan

# ╔═╡ f203fae3-8592-5073-ba37-d5a6857884c9
engineering_graph = example.graph

# ╔═╡ 1fe44711-dab7-5539-ae04-5d5abd87e63f
compiled_circuit = example.compiled

# ╔═╡ c61d0c0b-e261-52dd-840b-d8bd7aaf9d3c
primitive_component = example.jpa

# ╔═╡ e6746168-653d-5c68-a8a4-d69dcd95f1db
primitive_component

# ╔═╡ 6e26ea2b-52c9-521e-84bc-ac335a92f33b
(
    plan_id=circuit_plan.id,
    relation_count=length(circuit_plan.relations),
    parameter_count=length(circuit_plan.parameters),
    port_ids=sort(collect(keys(engineering_graph.ports))),
)

# ╔═╡ 22a09ccb-0b18-52b2-99c2-9e32184a5dc8
engineering_graph.relations

# ╔═╡ 07a42219-4279-5eff-be2b-1af83d2b6b1c
compiled_circuit.netlist

# ╔═╡ ac62cbc1-e775-5b1f-9aa5-f499e387bc46
compiled_circuit.component_values

# ╔═╡ 0652553d-aa70-5814-a1a9-c22078dd90f3
md"""
## HBProblemSpec And Real Solver Output

The notebook keeps the solve boundary visible. `hb_problem` is inspectable before execution, and the next cell is intentionally the explicit solver call used by all canonical Pluto notebooks.
"""

# ╔═╡ c5291a16-c18c-50a3-b9dd-7a5551d137e3
hb_problem = example.hb_problem

# ╔═╡ c4f02681-e9e0-5d70-b514-88d5eddba7d1
(
    frequency_points=length(hb_problem.frequencies_hz),
    pump_axes=hb_problem.wp,
    sources=hb_problem.sources,
    controls=hb_problem.controls,
)

# ╔═╡ a53a7ef1-4154-5042-b400-12723ce7b2b1
result = run_hb_problem(hb_problem)

# ╔═╡ 2c17fe33-6b3e-54a5-b691-fb323084d0be
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

# ╔═╡ c59a0ca6-a945-5424-8350-626685df4c15
begin
    frequencies_ghz = result.frequencies_hz ./ 1e9
    s11 = zero_mode_s(result, 1, 1)
    z11 = zero_mode_z(result, 1, 1)
end

# ╔═╡ 83182941-8356-5e40-a688-e58332642138
sanity = (
    point_count_matches=length(result.frequencies_hz) == point_count,
    s11_points=length(s11),
    finite_s11=all(isfinite, real.(s11)) && all(isfinite, imag.(s11)),
    linear_resonance_in_span=start_frequency <= linear_f0_estimate <= stop_frequency,
)

# ╔═╡ 55b4a31d-7821-545d-be25-e63d027f63b8
sanity

# ╔═╡ a891c8e6-4f03-5541-89c5-96a37a6f0a11
begin
    s_parameter_magnitude_figure(
        result.frequencies_hz,
        ["S11" => s11];
        title="Reflective JPA S11 Magnitude",
        config=figure_config,
    )
end |> wide_figure_cell

# ╔═╡ 0aaa76ba-15d7-5440-a6b1-8420d0106a2f
begin
    s_parameter_phase_figure(
        result.frequencies_hz,
        ["S11" => s11];
        title="Reflective JPA S11 Phase",
        config=figure_config,
    )
end |> wide_figure_cell

# ╔═╡ 897da0f4-16e9-55e7-8fa5-2d6d9cce2a08
begin
    z_trace_figure(
        result.frequencies_hz,
        ["Z11" => z11];
        title="Reflective JPA Input Impedance",
        config=figure_config,
    )
end |> wide_figure_cell

# ╔═╡ Cell order:
# ╠═5b5fb3c0-7d7b-528c-bc3e-b01bf07f7185
# ╠═a79e2c58-acd9-57c1-bff0-634f473c981e
# ╟─dbd7364d-5052-57d5-89c2-2bc2e40ca7cc
# ╟─3f45a386-f4b4-5257-85fa-2f768634f88c
# ╠═1567e5ff-6e0a-5589-b7f1-9f1eb1a0aeca
# ╟─03e9e911-d989-5ed1-93e3-c18cd562353c
# ╟─31e5052e-4f40-5d6d-9c31-b74660a4b59d
# ╠═30fa5e0f-8a16-58db-b33a-d46b621843ad
# ╠═bc03d638-9631-53e9-b857-48ec8cd6d994
# ╠═c471be37-792a-50ca-9252-8fd1f895ccb4
# ╟─7d62378c-f755-5076-8405-22a4071c2fac
# ╠═8c11a0c6-5045-53f3-bf4f-2026bb14e7a5
# ╠═61c90184-a06a-5ec4-ac38-d54203445552
# ╠═00db8292-dc5c-5faf-b7cd-974c2533e7f2
# ╠═f203fae3-8592-5073-ba37-d5a6857884c9
# ╠═1fe44711-dab7-5539-ae04-5d5abd87e63f
# ╠═c61d0c0b-e261-52dd-840b-d8bd7aaf9d3c
# ╠═e6746168-653d-5c68-a8a4-d69dcd95f1db
# ╠═6e26ea2b-52c9-521e-84bc-ac335a92f33b
# ╠═22a09ccb-0b18-52b2-99c2-9e32184a5dc8
# ╠═07a42219-4279-5eff-be2b-1af83d2b6b1c
# ╠═ac62cbc1-e775-5b1f-9aa5-f499e387bc46
# ╟─0652553d-aa70-5814-a1a9-c22078dd90f3
# ╠═c5291a16-c18c-50a3-b9dd-7a5551d137e3
# ╠═c4f02681-e9e0-5d70-b514-88d5eddba7d1
# ╠═a53a7ef1-4154-5042-b400-12723ce7b2b1
# ╠═2c17fe33-6b3e-54a5-b691-fb323084d0be
# ╠═c59a0ca6-a945-5424-8350-626685df4c15
# ╠═83182941-8356-5e40-a688-e58332642138
# ╠═55b4a31d-7821-545d-be25-e63d027f63b8
# ╠═a891c8e6-4f03-5541-89c5-96a37a6f0a11
# ╠═0aaa76ba-15d7-5440-a6b1-8420d0106a2f
# ╠═897da0f4-16e9-55e7-8fa5-2d6d9cce2a08
