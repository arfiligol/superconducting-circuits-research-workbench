### A Pluto.jl notebook ###
# v1.0.1

#> [frontmatter]
#> title = "00 Parallel LC Resonator"
#> tags = ["julia-core", "pluto", "hb", "parallel-lc"]
#> description = "Macro DSL tutorial for a one-port parallel LC resonator and real HB admittance traces."

using Markdown
using InteractiveUtils

# ╔═╡ 3d128bb8-1bcf-57bb-a996-eb9d4cbe06e5
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
    using .HBExampleHelpers: zero_mode_s, zero_mode_z
end

# ╔═╡ dbd30a94-62de-54a8-ac42-f8bbc3594c88
TableOfContents()

# ╔═╡ 7b464e61-ff9e-5113-b753-aeefd1116a04
md"""
# 00 Parallel LC Resonator

This notebook studies a one-port parallel LC resonator. A 50 ohm port drives one node, and the capacitor and inductor are both shunted from that node to ground.

The authoring path is the Core SoT flow: define a reusable component, instantiate it with `@circuit`, declare solver intent with `@hbintent`, inspect semantic graph and schematic export, compile, run HB, then plot real solver traces.
"""

# ╔═╡ c6c8d380-bb0f-57dc-88d9-4e8abfe13c7e
md"""
## Owns

- Parallel LC resonator physics.
- Admittance interpretation of a one-port resonator.
- Minimal pump-off HB workflow using `@circuit_component`, `@circuit`, and `@hbintent`.
"""

# ╔═╡ 9b7f1ff5-8378-5874-893c-896642fedd35
LocalResource(joinpath(@__DIR__, "..", "..", "docs", "assets", "pluto-00-parallel-lc-resonator.svg"))

# ╔═╡ ccd34d3a-7df7-5497-bd1d-0f35522f00f6
md"""
## Physics

For a parallel LC at angular frequency ``\omega``,

```math
Y_{LC}(\omega) = j\omega C + \frac{1}{j\omega L}.
```

The ideal resonance occurs when the capacitive and inductive susceptances cancel:

```math
f_0 = \frac{1}{2\pi\sqrt{LC}}.
```

Because this is a shunt resonator, admittance is the natural quantity to inspect.
"""

# ╔═╡ 1779d63b-0581-584c-b3de-63f5bfb1bcf0
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

# ╔═╡ 3cec03d7-4422-57cf-9c82-edbcd40a315f
parameter_table = [
    (name="C", value=capacitance, unit="F", meaning="parallel capacitance"),
    (name="L", value=inductance, unit="H", meaning="parallel inductance"),
    (name="Z0", value=port_resistance, unit="ohm", meaning="port resistance"),
    (name="frequency span", value=(start_frequency, stop_frequency), unit="Hz", meaning="HB sweep"),
]

# ╔═╡ 3baaa01d-e6ba-5be2-99a6-6bb7a054be20
f0_estimate = 1 / (2π * sqrt(inductance * capacitance))

# ╔═╡ 4c9a3754-d8fd-564d-981d-53da43ba3c55
md"""
## Reusable Component

The component exposes one electrical pin, `:signal`. Its internal implementation is two primitive shunt relations. The component does not create ports or solver intent; those belong to the system-level circuit.
"""

# ╔═╡ 6bd95036-eb4d-5549-a226-9d2910e953f0
parallel_lc_resonator! = @circuit_component "parallel_lc_resonator" begin
    pin :signal

    parameter(:capacitance; unit="F")
    parameter(:inductance; unit="H")

    shunt_capacitor!(
        id=:capacitance,
        at=pin(:signal),
        capacitance=capacitance,
        role=:parallel_lc_capacitance,
        label="C",
    )
    shunt_inductor!(
        id=:inductance,
        at=pin(:signal),
        inductance=inductance,
        role=:parallel_lc_inductance,
        label="L",
    )
end

# ╔═╡ 72a243d3-d8cf-5137-bd5f-bedf26221d4f
md"""
## Circuit Plan

The complete runnable system is a component instance plus one physical port. The port role is descriptive metadata only; the solver source and observable are declared later in `@hbintent`.
"""

# ╔═╡ 04935fb0-fbc0-537c-9dd4-0ae9462a0ce0
begin
    circuit_plan = @circuit "parallel-lc-resonator" begin
        signal = external_node("signal")
        resonator = parallel_lc_resonator!(
            id=:resonator,
            signal=signal,
            capacitance=capacitance,
            inductance=inductance,
        )

        port(:signal_port) do
            index = 1
            endpoint = pin(resonator, :signal)
            resistance = port_resistance
            role = :reflection
        end

        group(:one_port_resonator) do
            label = "One-port parallel LC"
            role = :resonator_example
            members = [:resonator, :signal_port]
        end

        schematic!(:notebook_view) do
            terminal(:signal_terminal) do
                endpoint = signal
                side = :left
                kind = :port
                label = "1"
            end
            node_label(:signal_node) do
                target = signal
                label = "signal"
            end
        end
    end


    @hbintent circuit_plan begin
        pump_axis(:pump; frequency_parameter=:pump_frequency)
        source_slot(:pump_in) do
            role = :pump
            port = :signal_port
            mode = (1,)
            current_parameter = :pump_current
        end
        sparameter(:s11) do
            outputmode = (0,)
            outputport = :signal_port
            inputmode = (0,)
            inputport = :signal_port
        end
        solver_controls() do
            n_pump_harmonics = 1
            n_modulation_harmonics = 1
            returnS = true
            returnZ = true
            returnQE = true
            returnCM = true
            keyedarrays = false
        end
    end

    circuit_plan
end
# ╔═╡ c4a819ae-cd12-5994-bad2-c2375369e34b
md"""
## Inspect Core Representations
"""

# ╔═╡ 7995b3e2-9e90-5dbb-9e1d-a6accb4f8835
hb_validation_report = validate_hb_intent(circuit_plan)

# ╔═╡ 8c9512d6-4746-577c-94c9-dd65a987fe3f
graph = engineering_graph(circuit_plan)

# ╔═╡ 3db97704-1928-5103-a6e3-182828cadef4
layout = schematic_layout_intent(circuit_plan)

# ╔═╡ 2195250e-8da9-52ad-81d4-039583dc9d82
schematic_export = to_schematic_export_spec(circuit_plan)

# ╔═╡ a9fc3311-b430-547b-8a2e-a85b582f7dae
graph_summary = (
    components=sort(collect(keys(graph.components)); by=string),
    ports=sort(collect(keys(graph.ports)); by=string),
    groups=sort(collect(keys(graph.groups)); by=string),
    relation_count=length(graph.relations),
)

# ╔═╡ 2d9f25da-d25d-56cb-8ffd-f3c593c1ab96
layout_summary = (
    tracks=sort(collect(keys(layout.tracks)); by=string),
    segments=sort(collect(keys(layout.segments)); by=string),
    coupled_spans=sort(collect(keys(layout.coupled_spans)); by=string),
    terminals=sort(collect(keys(layout.terminals)); by=string),
    node_labels=sort(collect(keys(layout.node_labels)); by=string),
)

# ╔═╡ 8a753a11-84ab-5ee5-948f-a4a533751027
export_summary = (
    components=length(schematic_export.components),
    relations=length(schematic_export.relations),
    ports=length(schematic_export.ports),
    tracks=length(schematic_export.tracks),
    terminals=length(schematic_export.terminals),
)

# ╔═╡ 72441715-726a-5788-a1f7-2241b06f02ca
compiled_circuit = compile_to_josephson(circuit_plan)

# ╔═╡ a2dc1188-3746-5b63-b2f9-ecdf9f44a83e
compiled_summary = (
    netlist_rows=length(compiled_circuit.netlist),
    port_ids=sort(collect(keys(compiled_circuit.port_map)); by=string),
    warning_count=length(compiled_circuit.warnings),
)

# ╔═╡ 1a0328f5-f32d-5679-8851-11b3b2e17105
frequency_sweep = point_count == 1 ? [Float64(start_frequency)] : range(Float64(start_frequency), Float64(stop_frequency); length=Int(point_count))

hb_problem = build_hb_problem(
    compiled_circuit,
    HBRunSpec(
        frequency_sweep=frequency_sweep,
        pump_frequencies=Dict(:pump => Float64(pump_frequency)),
        source_currents=Dict(:pump_in => Float64(pump_current)),
        optional_hb_kwargs=Dict{Symbol,Any}(optional_hb_kwargs),
    ),
)

# ╔═╡ 3481f53c-8125-574b-b8b0-3cb7362d384a
output_request_report = validate_output_request_configuration(compiled_circuit, hb_problem)

# ╔═╡ 4684a14f-a683-59c4-ab6f-3a0cd5c0cded
result = run_hb_problem(hb_problem)

# ╔═╡ 3aec22cc-b6b7-599a-ba08-1b9459956adc
trace_families = sort(collect(keys(result.traces)); by=string)

# ╔═╡ d834a02a-a42e-5003-834d-6376a55ad823
begin
    z11 = zero_mode_z(result, 1, 1)
    y11 = 1 ./ z11
end

# ╔═╡ a33fb5f5-b5e5-599c-8ace-9190213ac952
sanity = (
    point_count_matches=length(result.frequencies_hz) == point_count,
    finite_y_trace=all(isfinite, real.(y11)) && all(isfinite, imag.(y11)),
    resonance_in_span=start_frequency <= f0_estimate <= stop_frequency,
    hb_intent_ok=!has_errors(hb_validation_report),
)

# ╔═╡ a296f796-4254-5479-a43a-f9e7f05815dc
sanity

# ╔═╡ 4aab55d3-0e73-515d-906a-74d7afe36186
begin
    y_trace_figure(
        result.frequencies_hz,
        ["Y11" => y11];
        title="Parallel LC Input Admittance",
        config=figure_config,
    )
end |> wide_figure_cell

# ╔═╡ Cell order:
# ╠═3d128bb8-1bcf-57bb-a996-eb9d4cbe06e5
# ╠═dbd30a94-62de-54a8-ac42-f8bbc3594c88
# ╟─7b464e61-ff9e-5113-b753-aeefd1116a04
# ╟─c6c8d380-bb0f-57dc-88d9-4e8abfe13c7e
# ╠═9b7f1ff5-8378-5874-893c-896642fedd35
# ╟─ccd34d3a-7df7-5497-bd1d-0f35522f00f6
# ╠═1779d63b-0581-584c-b3de-63f5bfb1bcf0
# ╠═3cec03d7-4422-57cf-9c82-edbcd40a315f
# ╠═3baaa01d-e6ba-5be2-99a6-6bb7a054be20
# ╟─4c9a3754-d8fd-564d-981d-53da43ba3c55
# ╠═6bd95036-eb4d-5549-a226-9d2910e953f0
# ╟─72a243d3-d8cf-5137-bd5f-bedf26221d4f
# ╠═04935fb0-fbc0-537c-9dd4-0ae9462a0ce0
# ╟─c4a819ae-cd12-5994-bad2-c2375369e34b
# ╠═7995b3e2-9e90-5dbb-9e1d-a6accb4f8835
# ╠═8c9512d6-4746-577c-94c9-dd65a987fe3f
# ╠═3db97704-1928-5103-a6e3-182828cadef4
# ╠═2195250e-8da9-52ad-81d4-039583dc9d82
# ╠═a9fc3311-b430-547b-8a2e-a85b582f7dae
# ╠═2d9f25da-d25d-56cb-8ffd-f3c593c1ab96
# ╠═8a753a11-84ab-5ee5-948f-a4a533751027
# ╠═72441715-726a-5788-a1f7-2241b06f02ca
# ╠═a2dc1188-3746-5b63-b2f9-ecdf9f44a83e
# ╠═1a0328f5-f32d-5679-8851-11b3b2e17105
# ╠═3481f53c-8125-574b-b8b0-3cb7362d384a
# ╠═4684a14f-a683-59c4-ab6f-3a0cd5c0cded
# ╠═3aec22cc-b6b7-599a-ba08-1b9459956adc
# ╠═d834a02a-a42e-5003-834d-6376a55ad823
# ╠═a33fb5f5-b5e5-599c-8ace-9190213ac952
# ╠═a296f796-4254-5479-a43a-f9e7f05815dc
# ╠═4aab55d3-0e73-515d-906a-74d7afe36186
