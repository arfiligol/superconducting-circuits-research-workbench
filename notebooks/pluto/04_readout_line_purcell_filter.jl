### A Pluto.jl notebook ###
# v1.0.1

#> [frontmatter]
#> title = "04 Readout Line Purcell Filter"
#> tags = ["julia-core", "pluto", "hb", "purcell-filter"]
#> description = "Macro DSL tutorial for a point-capacitively coupled readout line with Purcell filter."

using Markdown
using InteractiveUtils

# ╔═╡ 193ffc9d-f436-564b-b3f3-15c47df5be3b
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

# ╔═╡ ac644a42-c825-52d4-be98-ae788e104ce7
TableOfContents()

# ╔═╡ bed06084-b41d-54af-953a-aac75cf738c5
md"""
# 04 Readout Line With Purcell Filter

This notebook builds a three-CPW readout chain with localized coupling capacitors into a half-wave Purcell/filter resonator. The coupling elements here are lumped capacitors.
"""

# ╔═╡ 805e52b6-2d9d-5285-b3af-cde211b816ab
md"""
## Owns

- Reusable readout/Purcell component construction from Core primitives.
- Three CPW ladders plus two localized coupling capacitors.
- Two-port S11/S21 response from real HB traces.
"""

# ╔═╡ 588383a1-2b78-5f7e-97ea-ab6787a9315b
LocalResource(joinpath(@__DIR__, "..", "..", "docs", "assets", "circuit_draw", "pluto_examples", "readout_line_purcell_filter", "diagram.light.svg"))

# ╔═╡ c383c879-7a2d-571c-8efd-0db460a7462e
md"""
## Modeling Convention

The readout input line, Purcell/filter ladder, and output line are independent CPW ladders. Coupling occurs only through the declared lumped capacitors.

A finite coupled-window model is a different distributed model and is introduced in the later hanging-QWR notebooks.
"""

# ╔═╡ abcaa547-1fbf-51f2-a1bb-4f8c1fd87153
begin
    input_line_length_m = 2.0e-3
    filter_length_m = 4.0e-3
    output_line_length_m = 2.0e-3
    section_length_m = 0.5e-3
    l_per_m_h = 404.313e-9
    c_per_m_f = 179.86e-12
    input_coupling_f = 2.0e-15
    output_coupling_f = 2.0e-15
    port_resistance = 50.0

    start_frequency = 2.0e9
    stop_frequency = 10.0e9
    point_count = 1000

    pump_frequency = 12.0e9
    pump_current = 0.0

    optional_hb_kwargs = Dict{Symbol,Any}(
        :nbatches => 1,
        :iterations => 120,
        :ftol => 1e-8,
    )
end

# ╔═╡ 6c1016d7-f9b8-533b-a13d-edb3f6eeb32d
begin
    input_line_spec = RLGCSpec(length_m=input_line_length_m, section_length_m=section_length_m, l_per_m_h=l_per_m_h, c_per_m_f=c_per_m_f)
    filter_spec = RLGCSpec(length_m=filter_length_m, section_length_m=section_length_m, l_per_m_h=l_per_m_h, c_per_m_f=c_per_m_f)
    output_line_spec = RLGCSpec(length_m=output_line_length_m, section_length_m=section_length_m, l_per_m_h=l_per_m_h, c_per_m_f=c_per_m_f)
end

# ╔═╡ 430640dd-0e76-5d8b-a0d1-917d6a75efe3
parameter_table = [
    (name="input line", value=input_line_length_m, unit="m", meaning="input CPW length"),
    (name="filter", value=filter_length_m, unit="m", meaning="half-wave filter length"),
    (name="output line", value=output_line_length_m, unit="m", meaning="output CPW length"),
    (name="Cc input/output", value=(input_coupling_f, output_coupling_f), unit="F", meaning="localized coupling capacitors"),
]

# ╔═╡ 622288b3-3956-5224-9fdf-263ddda04f74
point_coupled_readout_purcell! = @circuit_component "point_coupled_readout_purcell" begin
    pin :input
    pin :output

    parameter(:input_line_spec; unit="RLGC")
    parameter(:filter_spec; unit="RLGC")
    parameter(:output_line_spec; unit="RLGC")
    parameter(:input_coupling_f; unit="F")
    parameter(:output_coupling_f; unit="F")

    input_tail = external_node("input_tail")
    filter_head = external_node("filter_head")
    filter_tail = external_node("filter_tail")
    output_head = external_node("output_head")

    transmission_line!(id=:input_line, head=pin(:input), tail=input_tail, spec=input_line_spec, head_termination=:external, tail_termination=:open)
    transmission_line!(id=:purcell_filter, head=filter_head, tail=filter_tail, spec=filter_spec, head_termination=:open, tail_termination=:open)
    transmission_line!(id=:output_line, head=output_head, tail=pin(:output), spec=output_line_spec, head_termination=:open, tail_termination=:external)
    couple_capacitive!(id=:input_coupling, from=input_tail, to=filter_head, capacitance=input_coupling_f, role=:localized_filter_coupling, label="Cc in")
    couple_capacitive!(id=:output_coupling, from=filter_tail, to=output_head, capacitance=output_coupling_f, role=:localized_filter_coupling, label="Cc out")
end

# ╔═╡ d2d5230c-9b3a-5c83-9b4c-a64d35985409
begin
    circuit_plan = @circuit "readout-line-purcell-filter" begin
        input = external_node("input")
        output = external_node("output")

        readout_filter = point_coupled_readout_purcell!(
            id=:readout_filter,
            input=input,
            output=output,
            input_line_spec=input_line_spec,
            filter_spec=filter_spec,
            output_line_spec=output_line_spec,
            input_coupling_f=input_coupling_f,
            output_coupling_f=output_coupling_f,
        )

        port(:input_port) do
            index = 1
            endpoint = pin(readout_filter, :input)
            resistance = port_resistance
            role = :readout_input
        end
        port(:output_port) do
            index = 2
            endpoint = pin(readout_filter, :output)
            resistance = port_resistance
            role = :readout_output
        end

        group(:readout_filter_chain) do
            label = "Readout line with Purcell filter"
            role = :readout_filter_chain
            members = [:readout_filter, :input_port, :output_port]
        end

        schematic!(:notebook_view) do
            terminal(:input_terminal) do
                endpoint = input
                side = :left
                kind = :port
                label = "1"
            end
            terminal(:output_terminal) do
                endpoint = output
                side = :right
                kind = :port
                label = "2"
            end
            node_label(:input_label) do
                target = input
                label = "input"
            end
            node_label(:output_label) do
                target = output
                label = "output"
            end
        end
    end


    @hbintent circuit_plan begin
        pump_axis(:pump; frequency_parameter=:pump_frequency)
        source_slot(:pump_in) do
            role = :pump
            port = :input_port
            mode = (1,)
            current_parameter = :pump_current
        end
        sparameter(:s11) do
            outputmode = (0,)
            outputport = :input_port
            inputmode = (0,)
            inputport = :input_port
        end
        sparameter(:s21) do
            outputmode = (0,)
            outputport = :output_port
            inputmode = (0,)
            inputport = :input_port
        end
        sparameter(:s12) do
            outputmode = (0,)
            outputport = :input_port
            inputmode = (0,)
            inputport = :output_port
        end
        sparameter(:s22) do
            outputmode = (0,)
            outputport = :output_port
            inputmode = (0,)
            inputport = :output_port
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
# ╔═╡ d5fe8b58-0627-58d7-b587-fb5680b65b82
md"""
## Inspect Core Representations
"""

# ╔═╡ 7ae86c5d-3260-5ba4-a27a-f7c0df8547aa
hb_validation_report = validate_hb_intent(circuit_plan)

# ╔═╡ a83d348d-c8f8-5d13-b380-dc757776abfb
graph = engineering_graph(circuit_plan)

# ╔═╡ adda6fb6-ab79-5572-91a9-185f2bad251c
layout = schematic_layout_intent(circuit_plan)

# ╔═╡ 8cf83f50-652c-5809-b321-741d7d8e580f
schematic_export = to_schematic_export_spec(circuit_plan)

# ╔═╡ 5fbcccbf-f134-5785-9f96-83795f9d13c8
graph_summary = (
    components=sort(collect(keys(graph.components)); by=string),
    ports=sort(collect(keys(graph.ports)); by=string),
    groups=sort(collect(keys(graph.groups)); by=string),
    relation_count=length(graph.relations),
)

# ╔═╡ e6f929c6-cc0f-5dcf-9e5c-ce38e5de4b41
layout_summary = (
    tracks=sort(collect(keys(layout.tracks)); by=string),
    segments=sort(collect(keys(layout.segments)); by=string),
    coupled_spans=sort(collect(keys(layout.coupled_spans)); by=string),
    terminals=sort(collect(keys(layout.terminals)); by=string),
    node_labels=sort(collect(keys(layout.node_labels)); by=string),
)

# ╔═╡ f97e6883-133e-5e50-aa5b-18134f3f963c
export_summary = (
    components=length(schematic_export.components),
    relations=length(schematic_export.relations),
    ports=length(schematic_export.ports),
    tracks=length(schematic_export.tracks),
    terminals=length(schematic_export.terminals),
)

# ╔═╡ 8fc56e58-8ec6-5a7a-be51-5d81dabbf216
compiled_circuit = compile_to_josephson(circuit_plan)

# ╔═╡ b8530c2d-dd4c-5e24-9654-175f9e9ba4e9
compiled_summary = (
    netlist_rows=length(compiled_circuit.netlist),
    port_ids=sort(collect(keys(compiled_circuit.port_map)); by=string),
    warning_count=length(compiled_circuit.warnings),
)

# ╔═╡ 3066d1a8-81e2-50b6-9954-f8e45ff0ffc2
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

# ╔═╡ 6793e07d-b1e0-5765-ab93-37ce7d657abb
output_request_report = validate_output_request_configuration(compiled_circuit, hb_problem)

# ╔═╡ aa9656fe-5e79-58b5-a722-eec145ef40af
result = run_hb_problem(hb_problem)

# ╔═╡ 15d943a2-cc83-5176-bc5e-258217d56311
trace_families = sort(collect(keys(result.traces)); by=string)

# ╔═╡ 655ed2e7-d893-5ea5-a71b-f54b232a8b5d
begin
    s11 = zero_mode_s(result, 1, 1)
    s21 = zero_mode_s(result, 2, 1)
end

# ╔═╡ 0d46f7ee-49fa-5026-a871-5d3fa08258c9
sanity = (
    point_count_matches=length(result.frequencies_hz) == point_count,
    finite_s11=all(isfinite, real.(s11)) && all(isfinite, imag.(s11)),
    finite_s21=all(isfinite, real.(s21)) && all(isfinite, imag.(s21)),
    hb_intent_ok=!has_errors(hb_validation_report),
)

# ╔═╡ 8fcf03f4-4eab-5b40-b062-bd5aab15de03
sanity

# ╔═╡ 6d44924f-8809-56be-917a-106542795004
begin
    s_parameter_db_magnitude_figure(result.frequencies_hz, ["S11" => s11, "S21" => s21]; title="Readout Filter Reflection And Transmission", config=figure_config)
end |> wide_figure_cell

# ╔═╡ f34d467f-887f-5cee-b16d-8c44e39b0d19
begin
    s_parameter_abs_magnitude_figure(result.frequencies_hz, ["S11" => s11, "S21" => s21]; title="Readout Filter Absolute Magnitude", config=figure_config, y_range=(0.0, 1.1))
end |> wide_figure_cell

# ╔═╡ Cell order:
# ╠═193ffc9d-f436-564b-b3f3-15c47df5be3b
# ╠═ac644a42-c825-52d4-be98-ae788e104ce7
# ╟─bed06084-b41d-54af-953a-aac75cf738c5
# ╟─805e52b6-2d9d-5285-b3af-cde211b816ab
# ╠═588383a1-2b78-5f7e-97ea-ab6787a9315b
# ╟─c383c879-7a2d-571c-8efd-0db460a7462e
# ╠═abcaa547-1fbf-51f2-a1bb-4f8c1fd87153
# ╠═6c1016d7-f9b8-533b-a13d-edb3f6eeb32d
# ╠═430640dd-0e76-5d8b-a0d1-917d6a75efe3
# ╠═622288b3-3956-5224-9fdf-263ddda04f74
# ╠═d2d5230c-9b3a-5c83-9b4c-a64d35985409
# ╟─d5fe8b58-0627-58d7-b587-fb5680b65b82
# ╠═7ae86c5d-3260-5ba4-a27a-f7c0df8547aa
# ╠═a83d348d-c8f8-5d13-b380-dc757776abfb
# ╠═adda6fb6-ab79-5572-91a9-185f2bad251c
# ╠═8cf83f50-652c-5809-b321-741d7d8e580f
# ╠═5fbcccbf-f134-5785-9f96-83795f9d13c8
# ╠═e6f929c6-cc0f-5dcf-9e5c-ce38e5de4b41
# ╠═f97e6883-133e-5e50-aa5b-18134f3f963c
# ╠═8fc56e58-8ec6-5a7a-be51-5d81dabbf216
# ╠═b8530c2d-dd4c-5e24-9654-175f9e9ba4e9
# ╠═3066d1a8-81e2-50b6-9954-f8e45ff0ffc2
# ╠═6793e07d-b1e0-5765-ab93-37ce7d657abb
# ╠═aa9656fe-5e79-58b5-a722-eec145ef40af
# ╠═15d943a2-cc83-5176-bc5e-258217d56311
# ╠═655ed2e7-d893-5ea5-a71b-f54b232a8b5d
# ╠═0d46f7ee-49fa-5026-a871-5d3fa08258c9
# ╠═8fcf03f4-4eab-5b40-b062-bd5aab15de03
# ╠═6d44924f-8809-56be-917a-106542795004
# ╠═f34d467f-887f-5cee-b16d-8c44e39b0d19
