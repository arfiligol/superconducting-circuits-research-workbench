### A Pluto.jl notebook ###
# v1.0.1

#> [frontmatter]
#> title = "06 Readout Purcell Hanging QWR MTL"
#> tags = ["julia-core", "pluto", "hb", "mtl", "purcell-filter"]
#> description = "Macro DSL tutorial for an integrated readout/Purcell system coupled to a hanging QWR by an MTL window."

using Markdown
using InteractiveUtils

# ╔═╡ 593a76d0-37a6-53ac-b6c6-ab63781461bc
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

# ╔═╡ ed04767c-f9af-531a-9a90-2c02a6dfc766
TableOfContents()

# ╔═╡ e161a517-53b5-59b6-9bb4-4b8423d44dbe
md"""
# 06 Readout Purcell Filter With Hanging QWR MTL

This notebook combines the previous ideas: input CPW, middle Purcell/filter CPW, output CPW, localized coupling capacitors, and a QWR coupled to the middle CPW by a finite MTL window.
"""

# ╔═╡ 78e4e6eb-b954-536b-bf86-c5fab6b25245
md"""
## Owns

- Integrated readout/Purcell/QWR system construction.
- Explicit selection of the middle Purcell/filter CPW for the MTL window.
- Two-port S11/S21 response from real HB traces.
"""

# ╔═╡ f72f6f2e-1de1-58f5-8e40-180cdb235d49
LocalResource(joinpath(@__DIR__, "..", "..", "docs", "assets", "pluto-06-readout-purcell-hanging-qwr-mtl.svg"))

# ╔═╡ 9432e8aa-9a78-51fa-b794-c42182810335
md"""
## Modeling Convention

The input and output CPWs couple to the middle filter CPW through localized capacitors. The QWR coupling is a finite coupled-window model applied only to the middle filter line.

This notebook keeps the complete topology visible in `@circuit` so the selected coupled segment is inspectable.
"""

# ╔═╡ 607cd7d5-0e85-5614-96ea-72d7f63028b5
begin
    input_line_length_m = 2.0e-3
    filter_length_m = 6.0e-3
    output_line_length_m = 2.0e-3
    qwr_length_m = 3.0e-3
    section_length_m = 0.75e-3
    l_per_m_h = 404.313e-9
    c_per_m_f = 179.86e-12
    input_coupling_f = 2.0e-15
    output_coupling_f = 2.0e-15

    window_start_filter_m = 2.25e-3
    window_start_qwr_m = 0.0
    window_length_m = 1.5e-3
    l_matrix_per_m_h = [410.86374 19.08527; 19.08527 410.85454] .* 1e-9
    c_matrix_per_m_f = [170.29805 -8.09678; -8.09678 170.29538] .* 1e-12
    port_resistance = 50.0

    start_frequency = 6.0e9
    stop_frequency = 12.0e9
    point_count = 1000

    pump_frequency = 14.0e9
    pump_current = 0.0

    optional_hb_kwargs = Dict{Symbol,Any}(:nbatches => 1, :iterations => 160, :ftol => 1e-8)
end

# ╔═╡ 08d0a9f3-7f6b-5e92-980f-d5ed4e09e471
begin
    input_line_spec = RLGCSpec(length_m=input_line_length_m, section_length_m=section_length_m, l_per_m_h=l_per_m_h, c_per_m_f=c_per_m_f)
    filter_spec = RLGCSpec(length_m=filter_length_m, section_length_m=section_length_m, l_per_m_h=l_per_m_h, c_per_m_f=c_per_m_f)
    output_line_spec = RLGCSpec(length_m=output_line_length_m, section_length_m=section_length_m, l_per_m_h=l_per_m_h, c_per_m_f=c_per_m_f)
    qwr_spec = RLGCSpec(length_m=qwr_length_m, section_length_m=section_length_m, l_per_m_h=l_per_m_h, c_per_m_f=c_per_m_f)
    mtl_model = MTLCoupledRLGCSpec(
        start1_m=window_start_filter_m,
        start2_m=window_start_qwr_m,
        length_m=window_length_m,
        section_length_m=section_length_m,
        l_matrix_per_m_h=l_matrix_per_m_h,
        c_matrix_per_m_f=c_matrix_per_m_f,
    )
end

# ╔═╡ 49a2a3c8-5286-516b-88f2-a8052fdc8881
parameter_table = [
    (name="input/filter/output", value=(input_line_length_m, filter_length_m, output_line_length_m), unit="m", meaning="three CPW lengths"),
    (name="QWR", value=qwr_length_m, unit="m", meaning="grounded-head/open-tail resonator"),
    (name="Cc", value=(input_coupling_f, output_coupling_f), unit="F", meaning="localized readout/filter coupling"),
    (name="MTL window", value=(window_start_filter_m, window_start_qwr_m, window_length_m), unit="m", meaning="middle-line window selection"),
]

# ╔═╡ 88393f37-7c0f-5e1e-863e-b3fa7b9ddfe0
begin
    circuit_plan = @circuit "readout-purcell-hanging-qwr-mtl" begin
        input = external_node("input")
        output = external_node("output")
        input_tail = external_node("input_tail")
        filter_head = external_node("filter_head")
        filter_tail = external_node("filter_tail")
        output_head = external_node("output_head")
        qwr_grounded_head = external_node("qwr_grounded_head")
        qwr_open_tail = external_node("qwr_open_tail")

        input_line = transmission_line!(id=:input_line, head=input, tail=input_tail, spec=input_line_spec, head_termination=:external, tail_termination=:open)
        filter_line = transmission_line!(
            id=:purcell_filter,
            head=filter_head,
            tail=filter_tail,
            spec=filter_spec,
            head_termination=:open,
            tail_termination=:open,
            breakpoints_m=[window_start_filter_m, window_start_filter_m + window_length_m],
            section_overrides=[coupled_line_section_override(mtl_model, 1)],
        )
        output_line = transmission_line!(id=:output_line, head=output_head, tail=output, spec=output_line_spec, head_termination=:open, tail_termination=:external)
        input_coupling = couple_capacitive!(id=:input_coupling, from=input_tail, to=filter_head, capacitance=input_coupling_f, role=:localized_filter_coupling, label="Cc in")
        output_coupling = couple_capacitive!(id=:output_coupling, from=filter_tail, to=output_head, capacitance=output_coupling_f, role=:localized_filter_coupling, label="Cc out")
        qwr = quarter_wave_resonator!(
            id=:qwr,
            grounded_head=qwr_grounded_head,
            open_tail=qwr_open_tail,
            spec=qwr_spec,
            breakpoints_m=[window_start_qwr_m, window_start_qwr_m + window_length_m],
            section_overrides=[coupled_line_section_override(mtl_model, 2)],
        )
        window = couple_transmission_window!(
            id=:purcell_qwr_mtl_window,
            line1=filter_line,
            line2=qwr.line,
            start1=window_start_filter_m,
            start2=window_start_qwr_m,
            length=window_length_m,
            model=mtl_model,
        )

        port(:input_port) do
            index = 1
            endpoint = input
            resistance = port_resistance
            role = :readout_input
        end
        port(:output_port) do
            index = 2
            endpoint = output
            resistance = port_resistance
            role = :readout_output
        end

        group(:integrated_readout_system) do
            label = "Readout + Purcell + QWR"
            role = :readout_chain_with_hanging_resonator
            members = [:input_line, :purcell_filter, :output_line, :qwr, :purcell_qwr_mtl_window]
        end

        schematic!(:notebook_view) do
            track(:readout_input_track) do
                line = input_line
                orientation = :left_to_right
                relative_order = :top
                role = :readout_input_line
                label = "input"
            end
            track(:filter_track) do
                line = filter_line
                orientation = :left_to_right
                relative_order = :middle
                role = :purcell_filter
                label = "filter"
            end
            track(:output_track) do
                line = output_line
                orientation = :left_to_right
                relative_order = :top
                role = :readout_output_line
                label = "output"
            end
            track(:qwr_track) do
                line = qwr.line
                orientation = :left_to_right
                relative_order = :bottom
                role = :quarter_wave_resonator
                label = "QWR"
            end
            segment(:filter_window_segment) do
                track = :filter_track
                from = window_start_filter_m
                to = window_start_filter_m + window_length_m
                label = "selected MTL span"
            end
            segment(:qwr_window_segment) do
                track = :qwr_track
                from = window_start_qwr_m
                to = window_start_qwr_m + window_length_m
                label = "QWR span"
            end
            coupled_span(:filter_qwr_window_span) do
                relation = window
                track1 = :filter_track
                track2 = :qwr_track
                from1 = window_start_filter_m
                to1 = window_start_filter_m + window_length_m
                from2 = window_start_qwr_m
                to2 = window_start_qwr_m + window_length_m
                label = "MTL window"
                render = :parallel_cpw_window
            end
            terminal(:input_terminal) do
                endpoint = input
                track = :readout_input_track
                side = :left
                kind = :port
                label = "1"
            end
            terminal(:output_terminal) do
                endpoint = output
                track = :output_track
                side = :right
                kind = :port
                label = "2"
            end
            terminal(:qwr_ground_terminal) do
                endpoint = qwr_grounded_head
                track = :qwr_track
                side = :left
                kind = :ground
                label = "ground"
            end
            terminal(:qwr_open_terminal) do
                endpoint = qwr_open_tail
                track = :qwr_track
                side = :right
                kind = :open
                label = "open"
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
# ╔═╡ 1a44259c-58e2-531c-8c6b-dca85d5d2f92
md"""
## Inspect Core Representations
"""

# ╔═╡ 246fb14e-c17b-5ea6-b6e0-35f432f0b7b1
hb_validation_report = validate_hb_intent(circuit_plan)

# ╔═╡ a9735bb4-0db5-5a0c-8dd6-e52f3936d3e7
graph = engineering_graph(circuit_plan)

# ╔═╡ 1af0f9bd-da98-570b-bb13-802dc961a601
layout = schematic_layout_intent(circuit_plan)

# ╔═╡ 0e393ce5-801d-5ef3-8791-0b9d5c5569e7
schematic_export = to_schematic_export_spec(circuit_plan)

# ╔═╡ 21d42709-a4dd-5663-ad59-57254b98b48f
graph_summary = (
    components=sort(collect(keys(graph.components)); by=string),
    ports=sort(collect(keys(graph.ports)); by=string),
    groups=sort(collect(keys(graph.groups)); by=string),
    relation_count=length(graph.relations),
)

# ╔═╡ 8a3cc622-459e-5555-b936-ce76cf75843a
layout_summary = (
    tracks=sort(collect(keys(layout.tracks)); by=string),
    segments=sort(collect(keys(layout.segments)); by=string),
    coupled_spans=sort(collect(keys(layout.coupled_spans)); by=string),
    terminals=sort(collect(keys(layout.terminals)); by=string),
    node_labels=sort(collect(keys(layout.node_labels)); by=string),
)

# ╔═╡ f76fabd8-5660-50f6-9651-1a54cd9ed244
export_summary = (
    components=length(schematic_export.components),
    relations=length(schematic_export.relations),
    ports=length(schematic_export.ports),
    tracks=length(schematic_export.tracks),
    terminals=length(schematic_export.terminals),
)

# ╔═╡ 92b098f4-e580-5d5f-89ed-86db76d5556a
compiled_circuit = compile_to_josephson(circuit_plan)

# ╔═╡ 7b317e5d-a892-54a3-a801-ab7ebb6d4b7c
compiled_summary = (
    netlist_rows=length(compiled_circuit.netlist),
    port_ids=sort(collect(keys(compiled_circuit.port_map)); by=string),
    warning_count=length(compiled_circuit.warnings),
)

# ╔═╡ fd1b0287-5c86-5450-9d0a-0b31bff3eb46
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

# ╔═╡ 8ed5fe3a-b988-57a6-9f77-efe72a990e52
output_request_report = validate_output_request_configuration(compiled_circuit, hb_problem)

# ╔═╡ 0aff306c-9cc2-5ca2-9b22-eaf5deb4cea7
result = run_hb_problem(hb_problem)

# ╔═╡ 2b4612d3-f4e6-5e18-8dc7-ffa4e933fab1
trace_families = sort(collect(keys(result.traces)); by=string)

# ╔═╡ 2f8107cc-1a9e-5e5b-873d-8f1dc13cfc0a
begin
    s11 = zero_mode_s(result, 1, 1)
    s21 = zero_mode_s(result, 2, 1)
end

# ╔═╡ 98af16b7-7554-5e63-8c1f-daec0b86c5c2
sanity = (
    point_count_matches=length(result.frequencies_hz) == point_count,
    has_coupled_span=haskey(layout.coupled_spans, :filter_qwr_window_span),
    finite_s21=all(isfinite, real.(s21)) && all(isfinite, imag.(s21)),
    hb_intent_ok=!has_errors(hb_validation_report),
)

# ╔═╡ e3f683e9-82d7-58a7-850c-4fd2cfff4418
sanity

# ╔═╡ a3670ee0-9469-5fe1-bde8-4ba1e9d185f3
begin
    s_parameter_db_magnitude_figure(result.frequencies_hz, ["S11" => s11, "S21" => s21]; title="Readout Purcell QWR MTL Response", config=figure_config)
end |> wide_figure_cell

# ╔═╡ 6af2c069-79d2-56d5-a85c-f8829d3ffa86
begin
    s_parameter_abs_magnitude_figure(result.frequencies_hz, ["S11" => s11, "S21" => s21]; title="Readout Purcell QWR Absolute Magnitude", config=figure_config, y_range=(0.0, 1.1))
end |> wide_figure_cell

# ╔═╡ Cell order:
# ╠═593a76d0-37a6-53ac-b6c6-ab63781461bc
# ╠═ed04767c-f9af-531a-9a90-2c02a6dfc766
# ╟─e161a517-53b5-59b6-9bb4-4b8423d44dbe
# ╟─78e4e6eb-b954-536b-bf86-c5fab6b25245
# ╠═f72f6f2e-1de1-58f5-8e40-180cdb235d49
# ╟─9432e8aa-9a78-51fa-b794-c42182810335
# ╠═607cd7d5-0e85-5614-96ea-72d7f63028b5
# ╠═08d0a9f3-7f6b-5e92-980f-d5ed4e09e471
# ╠═49a2a3c8-5286-516b-88f2-a8052fdc8881
# ╠═88393f37-7c0f-5e1e-863e-b3fa7b9ddfe0
# ╟─1a44259c-58e2-531c-8c6b-dca85d5d2f92
# ╠═246fb14e-c17b-5ea6-b6e0-35f432f0b7b1
# ╠═a9735bb4-0db5-5a0c-8dd6-e52f3936d3e7
# ╠═1af0f9bd-da98-570b-bb13-802dc961a601
# ╠═0e393ce5-801d-5ef3-8791-0b9d5c5569e7
# ╠═21d42709-a4dd-5663-ad59-57254b98b48f
# ╠═8a3cc622-459e-5555-b936-ce76cf75843a
# ╠═f76fabd8-5660-50f6-9651-1a54cd9ed244
# ╠═92b098f4-e580-5d5f-89ed-86db76d5556a
# ╠═7b317e5d-a892-54a3-a801-ab7ebb6d4b7c
# ╠═fd1b0287-5c86-5450-9d0a-0b31bff3eb46
# ╠═8ed5fe3a-b988-57a6-9f77-efe72a990e52
# ╠═0aff306c-9cc2-5ca2-9b22-eaf5deb4cea7
# ╠═2b4612d3-f4e6-5e18-8dc7-ffa4e933fab1
# ╠═2f8107cc-1a9e-5e5b-873d-8f1dc13cfc0a
# ╠═98af16b7-7554-5e63-8c1f-daec0b86c5c2
# ╠═e3f683e9-82d7-58a7-850c-4fd2cfff4418
# ╠═a3670ee0-9469-5fe1-bde8-4ba1e9d185f3
# ╠═6af2c069-79d2-56d5-a85c-f8829d3ffa86
