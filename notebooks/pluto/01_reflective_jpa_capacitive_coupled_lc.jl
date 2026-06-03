### A Pluto.jl notebook ###
# v1.0.1

#> [frontmatter]
#> title = "01 Reflective JPA Capacitive-Coupled LC"
#> tags = ["julia-core", "pluto", "hb", "jpa"]
#> description = "Macro DSL tutorial for a capacitively coupled reflective JPA and real HB S11 traces."

using Markdown
using InteractiveUtils

# ╔═╡ 84d7ce6d-9fff-5e7e-9a64-7c723c625a2a
begin
    import Pkg
    Pkg.activate(joinpath(first(DEPOT_PATH), "environments", "v1.12"); io=devnull)

    using Revise
    using PlutoUI
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

# ╔═╡ aaded962-1fa3-552d-b154-4e926d3249f6
TableOfContents()

# ╔═╡ 43dfba0c-e615-5124-a5e6-f2bd66a9ef23
md"""
# 01 Reflective JPA: Capacitively Coupled LC

This notebook adds a nonlinear Josephson element to the same one-port authoring flow. A port couples through a capacitor into a resonator node with a shunt capacitor and Josephson junction.
"""

# ╔═╡ f281bf9f-c353-5f2c-85da-bb7e064826fe
md"""
## Owns

- Reflective JPA topology with capacitive input coupling.
- Josephson junction as a nonlinear Core primitive.
- Pumped HB intent and real S11 traces.
"""

# ╔═╡ b4b5301b-0394-57ad-9fb4-64eee1b5d8d4
LocalResource(joinpath(@__DIR__, "..", "..", "docs", "assets", "pluto-01-reflective-jpa-capacitive-coupled-lc.svg"))

# ╔═╡ cfc3ab1e-2a99-5f78-8e17-08c85a98065d
md"""
## Physics

The coupling capacitor separates the external 50 ohm environment from the resonator node. The Josephson junction contributes a nonlinear inductive element; the pump is declared explicitly in HB intent.

The plotted S-parameters are not invented by the notebook. They are extracted from `run_hb_problem(hb_problem)`.
"""

# ╔═╡ 13a4980e-252e-564b-a9e4-b363117635e4
begin
    coupling_capacitance = 16.0e-15
    resonator_capacitance = 90.0e-15
    josephson_inductance = 7.5e-9
    port_resistance = 50.0

    start_frequency = 4.0e9
    stop_frequency = 9.0e9
    point_count = 1000

    pump_frequency = 12.0e9
    pump_current = 0.12e-6

    optional_hb_kwargs = Dict{Symbol,Any}(
        :nbatches => 1,
        :iterations => 160,
        :ftol => 1e-8,
    )
end

# ╔═╡ 9ac3a1c5-c268-5bcf-8b8c-5529b396e4f3
parameter_table = [
    (name="Cc", value=coupling_capacitance, unit="F", meaning="port-to-resonator coupling capacitor"),
    (name="Cres", value=resonator_capacitance, unit="F", meaning="resonator shunt capacitance"),
    (name="Lj", value=josephson_inductance, unit="H", meaning="Josephson inductance"),
    (name="pump", value=(pump_frequency, pump_current), unit="Hz, A", meaning="large-signal pump binding"),
]

# ╔═╡ 10e5dd9a-7e4b-5f15-a19d-13552892fd39
md"""
## Reusable Component

The reusable JPA component exposes only the external signal pin. The resonator node is private to the component instance.
"""

# ╔═╡ 4262a5cb-e929-51b2-b46c-b09972aeb727
reflective_jpa! = @circuit_component "reflective_jpa" begin
    pin :signal

    parameter(:coupling_capacitance; unit="F")
    parameter(:resonator_capacitance; unit="F")
    parameter(:josephson_inductance; unit="H")

    resonator_node = external_node("resonator_node")

    couple_capacitive!(
        id=:coupling_capacitance,
        from=pin(:signal),
        to=resonator_node,
        capacitance=coupling_capacitance,
        role=:jpa_coupling_capacitance,
        label="Cc",
    )
    shunt_capacitor!(
        id=:resonator_capacitance,
        at=resonator_node,
        capacitance=resonator_capacitance,
        role=:jpa_resonator_capacitance,
        label="Cres",
    )
    josephson_junction!(
        id=:junction,
        from=resonator_node,
        to=ground(),
        josephson_inductance=josephson_inductance,
        role=:jpa_josephson_junction,
        label="JJ",
    )
end

# ╔═╡ 03936a83-ffc8-58b7-b639-691d48a1dd2c
begin
    circuit_plan = @circuit "reflective-jpa-capacitive-coupled-lc" begin
        signal = external_node("signal")
        jpa = reflective_jpa!(
            id=:jpa,
            signal=signal,
            coupling_capacitance=coupling_capacitance,
            resonator_capacitance=resonator_capacitance,
            josephson_inductance=josephson_inductance,
        )

        port(:signal_port) do
            index = 1
            endpoint = pin(jpa, :signal)
            resistance = port_resistance
            role = :reflection
        end

        group(:reflective_jpa) do
            label = "Capacitively coupled reflective JPA"
            role = :nonlinear_reflection_circuit
            members = [:jpa, :signal_port]
        end

        schematic!(:notebook_view) do
            terminal(:signal_terminal) do
                endpoint = signal
                side = :left
                kind = :port
                label = "1"
            end
            node_label(:signal_label) do
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
            n_pump_harmonics = 4
            n_modulation_harmonics = 2
            returnS = true
            returnZ = true
            returnQE = true
            returnCM = true
            keyedarrays = false
        end
    end

    circuit_plan
end
# ╔═╡ 618a152f-eb74-5acb-a12f-029f073be5ad
md"""
## Inspect Core Representations
"""

# ╔═╡ 67bc027a-71cb-572e-a7d8-a9d93339628c
hb_validation_report = validate_hb_intent(circuit_plan)

# ╔═╡ ca8dfa30-70ef-5690-ab04-e29be313be1e
graph = engineering_graph(circuit_plan)

# ╔═╡ 1dafabd8-0ffe-57c0-a634-341a3ed4cc75
layout = schematic_layout_intent(circuit_plan)

# ╔═╡ c0955fa0-9a39-527c-88f7-f2a45a3e0317
schematic_export = to_schematic_export_spec(circuit_plan)

# ╔═╡ 9ef16c4f-a3d0-5dc5-a1a9-9aa908007990
graph_summary = (
    components=sort(collect(keys(graph.components)); by=string),
    ports=sort(collect(keys(graph.ports)); by=string),
    groups=sort(collect(keys(graph.groups)); by=string),
    relation_count=length(graph.relations),
)

# ╔═╡ 3e5ef822-ee55-5a17-ad3c-08e9aac6ce58
layout_summary = (
    tracks=sort(collect(keys(layout.tracks)); by=string),
    segments=sort(collect(keys(layout.segments)); by=string),
    coupled_spans=sort(collect(keys(layout.coupled_spans)); by=string),
    terminals=sort(collect(keys(layout.terminals)); by=string),
    node_labels=sort(collect(keys(layout.node_labels)); by=string),
)

# ╔═╡ ad5c9ec6-0e14-5944-bf00-ab04c6e7c23e
export_summary = (
    components=length(schematic_export.components),
    relations=length(schematic_export.relations),
    ports=length(schematic_export.ports),
    tracks=length(schematic_export.tracks),
    terminals=length(schematic_export.terminals),
)

# ╔═╡ 67758047-49cb-5b6e-bcf5-aa599fd2d6e0
compiled_circuit = compile_to_josephson(circuit_plan)

# ╔═╡ fa21a3c5-dc7c-50bc-babd-623cbe6cb1df
compiled_summary = (
    netlist_rows=length(compiled_circuit.netlist),
    port_ids=sort(collect(keys(compiled_circuit.port_map)); by=string),
    warning_count=length(compiled_circuit.warnings),
)

# ╔═╡ ab59648f-4803-51fa-9f45-a01ac0c13089
begin
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
end

# ╔═╡ bb5b884c-946a-54f0-86c6-98826db7a954
output_request_report = validate_output_request_configuration(compiled_circuit, hb_problem)

# ╔═╡ 5a0a9249-1633-5556-8ecb-2b89266d7ff7
result = run_hb_problem(hb_problem)

# ╔═╡ 9bd75fdc-1092-5d3b-bdeb-af7a6dd028c9
trace_families = sort(collect(keys(result.traces)); by=string)

# ╔═╡ c2e9380c-3fd1-5bfc-9614-7e5c723f2b06
s11 = zero_mode_s(result, 1, 1)

# ╔═╡ f333b9a9-5b74-5e6c-9867-5a3678f8acac
sanity = (
    point_count_matches=length(result.frequencies_hz) == point_count,
    finite_s11=all(isfinite, real.(s11)) && all(isfinite, imag.(s11)),
    hb_intent_ok=!has_errors(hb_validation_report),
)

# ╔═╡ 6de17a18-ec12-5a57-97cb-60325ddad5b1
sanity

# ╔═╡ da2c33b1-42c7-5666-bdb8-15f78ca59cc1
begin
    s_parameter_db_magnitude_figure(
        result.frequencies_hz,
        ["S11" => s11];
        title="Reflective JPA S11 Magnitude",
        config=figure_config,
    )
end |> wide_figure_cell

# ╔═╡ 4286746d-40e4-50dc-bbfb-35e2c3e97b35
begin
    s_parameter_abs_magnitude_figure(
        result.frequencies_hz,
        ["S11" => s11];
        title="Reflective JPA S11 Absolute Magnitude",
        config=figure_config,
    )
end |> wide_figure_cell

# ╔═╡ 15d62b6b-1afe-5cd7-bd87-07a75c2d7a4d
begin
    s_parameter_phase_figure(
        result.frequencies_hz,
        ["S11" => s11];
        title="Reflective JPA S11 Phase",
        config=figure_config,
    )
end |> wide_figure_cell

# ╔═╡ Cell order:
# ╠═84d7ce6d-9fff-5e7e-9a64-7c723c625a2a
# ╠═aaded962-1fa3-552d-b154-4e926d3249f6
# ╟─43dfba0c-e615-5124-a5e6-f2bd66a9ef23
# ╟─f281bf9f-c353-5f2c-85da-bb7e064826fe
# ╠═b4b5301b-0394-57ad-9fb4-64eee1b5d8d4
# ╟─cfc3ab1e-2a99-5f78-8e17-08c85a98065d
# ╠═13a4980e-252e-564b-a9e4-b363117635e4
# ╠═9ac3a1c5-c268-5bcf-8b8c-5529b396e4f3
# ╟─10e5dd9a-7e4b-5f15-a19d-13552892fd39
# ╠═4262a5cb-e929-51b2-b46c-b09972aeb727
# ╠═03936a83-ffc8-58b7-b639-691d48a1dd2c
# ╟─618a152f-eb74-5acb-a12f-029f073be5ad
# ╠═67bc027a-71cb-572e-a7d8-a9d93339628c
# ╠═ca8dfa30-70ef-5690-ab04-e29be313be1e
# ╠═1dafabd8-0ffe-57c0-a634-341a3ed4cc75
# ╠═c0955fa0-9a39-527c-88f7-f2a45a3e0317
# ╠═9ef16c4f-a3d0-5dc5-a1a9-9aa908007990
# ╠═3e5ef822-ee55-5a17-ad3c-08e9aac6ce58
# ╠═ad5c9ec6-0e14-5944-bf00-ab04c6e7c23e
# ╠═67758047-49cb-5b6e-bcf5-aa599fd2d6e0
# ╠═fa21a3c5-dc7c-50bc-babd-623cbe6cb1df
# ╠═ab59648f-4803-51fa-9f45-a01ac0c13089
# ╠═bb5b884c-946a-54f0-86c6-98826db7a954
# ╠═5a0a9249-1633-5556-8ecb-2b89266d7ff7
# ╠═9bd75fdc-1092-5d3b-bdeb-af7a6dd028c9
# ╠═c2e9380c-3fd1-5bfc-9614-7e5c723f2b06
# ╠═f333b9a9-5b74-5e6c-9867-5a3678f8acac
# ╠═6de17a18-ec12-5a57-97cb-60325ddad5b1
# ╠═da2c33b1-42c7-5666-bdb8-15f78ca59cc1
# ╠═4286746d-40e4-50dc-bbfb-35e2c3e97b35
# ╠═15d62b6b-1afe-5cd7-bd87-07a75c2d7a4d
