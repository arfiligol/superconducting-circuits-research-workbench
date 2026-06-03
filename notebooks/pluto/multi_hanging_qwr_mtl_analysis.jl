### A Pluto.jl notebook ###
# v1.0.1

#> [frontmatter]
#> title = "Multi Hanging QWR MTL Analysis"
#> tags = ["julia-core", "pluto", "hb", "mtl", "qwr", "analysis"]
#> description = "Analysis notebook for one readout CPW coupled to seven hanging quarter-wave resonators through finite MTL windows."

using Markdown
using InteractiveUtils

# ╔═╡ 13c5bd32-cbbb-5d78-b539-5215862bf55f
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
    using .HBExampleHelpers: db20, zero_mode_s
end

# ╔═╡ e21e8421-183a-5b9d-8d13-ee7d8ea6ebd0
TableOfContents()

# ╔═╡ caff7b9a-5b47-5983-9182-5f9e4d599779
md"""
# Multi Hanging QWR MTL Analysis

This analysis notebook models one readout CPW coupled to seven grounded-head/open-tail quarter-wave resonators. Each resonator uses a finite MTL coupled window; no point capacitor is used as a stand-in for distributed coupling.
"""

# ╔═╡ 179049e6-be96-5cd9-9af8-1841572bc7c0
md"""
## Analysis Setup

The single-line readout and resonator sections use the same RLGC baseline as the current `05` notebook. Each coupled window replaces the local self RLGC terms with the coupled-section matrices and then adds section-wise mutual capacitance and mutual inductance.

The resonator frequency estimate is the isolated quarter-wave value

```math
f_{\lambda/4} = \frac{1}{4\ell\sqrt{L'C'}}.
```

The simulated notches are extracted from real `S21` traces after `run_hb_problem(hb_problem)`.
"""

# ╔═╡ 10bffd4c-ab29-5687-83f3-d838361a516b
begin
    readout_length_m = 6.0e-3
    section_length_m = 10.0e-6
    l_per_m_h = 383.83846e-9
    c_per_m_f = 152.91443e-12

    resonator_lengths_um = [5283.71, 5183.6, 5088.39, 4998.08, 4912.68, 4832.17, 4797.12]
    resonator_lengths_m = resonator_lengths_um .* 1e-6
    resonator_ids = Symbol.("qwr_" .* string.(1:length(resonator_lengths_m)))

    window_start_readout_m_list = [1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5] .* 1e-3
    window_start_qwr_m = 0.0
    window_length_m = 110.0e-6
    l_matrix_per_m_h = [382.76533 136.62025; 136.62025 382.76533] .* 1e-9
    c_matrix_per_m_f = [171.00826 -12.17656; -12.17656 171.01348] .* 1e-12
    port_resistance = 50.0

    start_frequency = 5.8e9
    stop_frequency = 7.2e9
    point_count = 10000
    pump_frequency = 14.0e9
    pump_current = 0.0
    optional_hb_kwargs = Dict{Symbol,Any}(:nbatches => 1, :iterations => 160, :ftol => 1e-8)
end

# ╔═╡ 2c36bd83-3f4f-50fc-8b68-bff6b3cab80d
begin
    phase_velocity_m_per_s = 1 / sqrt(l_per_m_h * c_per_m_f)
    pozar_frequencies_hz = phase_velocity_m_per_s ./ (4 .* resonator_lengths_m)
    minimum_pozar_spacing_hz = minimum(diff(sort(pozar_frequencies_hz)))
    notch_search_window_hz = 0.7 * minimum_pozar_spacing_hz
    frequency_step_mhz = (stop_frequency - start_frequency) / (point_count - 1) / 1e6
    sweep_range_covers_pozar_estimates = start_frequency <= minimum(pozar_frequencies_hz) && stop_frequency >= maximum(pozar_frequencies_hz)
    sweep_resolution_warning = frequency_step_mhz > 0.5
end

# ╔═╡ a15bfe4e-0d12-5033-86c9-53fbd5cbac53
resonator_parameter_table = [
    (
        id=resonator_ids[index],
        length_um=resonator_lengths_um[index],
        pozar_frequency_ghz=pozar_frequencies_hz[index] / 1e9,
        readout_window_start_mm=window_start_readout_m_list[index] / 1e-3,
        readout_window_stop_mm=(window_start_readout_m_list[index] + window_length_m) / 1e-3,
    )
    for index in eachindex(resonator_lengths_m)
]

# ╔═╡ 70a778cf-2a9a-5cc5-9f58-2d80143ad7bf
if sweep_range_covers_pozar_estimates
    md"""
    !!! info "Pozar estimate"
        The table above lists isolated quarter-wave estimates from Pozar-style transmission-line theory. The HB sweep range is still set explicitly by `start_frequency` and `stop_frequency` in the parameter cell.
    """
else
    md"""
    !!! warning "Pozar estimate outside sweep"
        At least one isolated quarter-wave estimate is outside the explicit sweep range. Update `start_frequency` and `stop_frequency` if those notches should be included.
    """
end

# ╔═╡ a9ea9510-c567-560f-9a7b-7f2b53e07f7d
parameter_summary = (
    readout_length_m=readout_length_m,
    section_length_m=section_length_m,
    l_per_m_h=l_per_m_h,
    c_per_m_f=c_per_m_f,
    window_length_m=window_length_m,
    frequency_range_ghz=(start_frequency / 1e9, stop_frequency / 1e9),
    frequency_step_mhz=frequency_step_mhz,
    notch_search_window_mhz=notch_search_window_hz / 1e6,
    sweep_range_covers_pozar_estimates=sweep_range_covers_pozar_estimates,
)

# ╔═╡ 9a4971cb-87fa-5155-82c8-acb1630b0c05
begin
    readout_spec = RLGCSpec(
        length_m=readout_length_m,
        section_length_m=section_length_m,
        l_per_m_h=l_per_m_h,
        c_per_m_f=c_per_m_f,
    )

    qwr_spec_1 = RLGCSpec(length_m=resonator_lengths_m[1], section_length_m=section_length_m, l_per_m_h=l_per_m_h, c_per_m_f=c_per_m_f)
    qwr_spec_2 = RLGCSpec(length_m=resonator_lengths_m[2], section_length_m=section_length_m, l_per_m_h=l_per_m_h, c_per_m_f=c_per_m_f)
    qwr_spec_3 = RLGCSpec(length_m=resonator_lengths_m[3], section_length_m=section_length_m, l_per_m_h=l_per_m_h, c_per_m_f=c_per_m_f)
    qwr_spec_4 = RLGCSpec(length_m=resonator_lengths_m[4], section_length_m=section_length_m, l_per_m_h=l_per_m_h, c_per_m_f=c_per_m_f)
    qwr_spec_5 = RLGCSpec(length_m=resonator_lengths_m[5], section_length_m=section_length_m, l_per_m_h=l_per_m_h, c_per_m_f=c_per_m_f)
    qwr_spec_6 = RLGCSpec(length_m=resonator_lengths_m[6], section_length_m=section_length_m, l_per_m_h=l_per_m_h, c_per_m_f=c_per_m_f)
    qwr_spec_7 = RLGCSpec(length_m=resonator_lengths_m[7], section_length_m=section_length_m, l_per_m_h=l_per_m_h, c_per_m_f=c_per_m_f)

    mtl_model_1 = MTLCoupledRLGCSpec(start1_m=window_start_readout_m_list[1], start2_m=window_start_qwr_m, length_m=window_length_m, section_length_m=section_length_m, l_matrix_per_m_h=l_matrix_per_m_h, c_matrix_per_m_f=c_matrix_per_m_f)
    mtl_model_2 = MTLCoupledRLGCSpec(start1_m=window_start_readout_m_list[2], start2_m=window_start_qwr_m, length_m=window_length_m, section_length_m=section_length_m, l_matrix_per_m_h=l_matrix_per_m_h, c_matrix_per_m_f=c_matrix_per_m_f)
    mtl_model_3 = MTLCoupledRLGCSpec(start1_m=window_start_readout_m_list[3], start2_m=window_start_qwr_m, length_m=window_length_m, section_length_m=section_length_m, l_matrix_per_m_h=l_matrix_per_m_h, c_matrix_per_m_f=c_matrix_per_m_f)
    mtl_model_4 = MTLCoupledRLGCSpec(start1_m=window_start_readout_m_list[4], start2_m=window_start_qwr_m, length_m=window_length_m, section_length_m=section_length_m, l_matrix_per_m_h=l_matrix_per_m_h, c_matrix_per_m_f=c_matrix_per_m_f)
    mtl_model_5 = MTLCoupledRLGCSpec(start1_m=window_start_readout_m_list[5], start2_m=window_start_qwr_m, length_m=window_length_m, section_length_m=section_length_m, l_matrix_per_m_h=l_matrix_per_m_h, c_matrix_per_m_f=c_matrix_per_m_f)
    mtl_model_6 = MTLCoupledRLGCSpec(start1_m=window_start_readout_m_list[6], start2_m=window_start_qwr_m, length_m=window_length_m, section_length_m=section_length_m, l_matrix_per_m_h=l_matrix_per_m_h, c_matrix_per_m_f=c_matrix_per_m_f)
    mtl_model_7 = MTLCoupledRLGCSpec(start1_m=window_start_readout_m_list[7], start2_m=window_start_qwr_m, length_m=window_length_m, section_length_m=section_length_m, l_matrix_per_m_h=l_matrix_per_m_h, c_matrix_per_m_f=c_matrix_per_m_f)

    mtl_models = [mtl_model_1, mtl_model_2, mtl_model_3, mtl_model_4, mtl_model_5, mtl_model_6, mtl_model_7]
    readout_section_overrides = [coupled_line_section_override(model, 1) for model in mtl_models]
end

# ╔═╡ e8e1a39a-6fd4-5db1-b8ac-222db2df2b64
if sweep_resolution_warning
    md"""
    !!! warning "Sweep resolution"
        The current sweep step is wider than 0.5 MHz. Weak 200 µm MTL windows can produce narrow notches, so use the dB plot and the extracted notch table carefully.
    """
else
    md"""
    !!! info "Sweep resolution"
        The current sweep step is below 0.5 MHz, which is a reasonable first pass for locating the seven notches.
    """
end

# ╔═╡ e53543ab-a42d-501d-bb90-22487840e775
begin
    circuit_plan = @circuit "multi-hanging-qwr-mtl-analysis" begin
        input = external_node("input")
        output = external_node("output")

        qwr_1_grounded_head = external_node("qwr_1_grounded_head")
        qwr_1_open_tail = external_node("qwr_1_open_tail")
        qwr_2_grounded_head = external_node("qwr_2_grounded_head")
        qwr_2_open_tail = external_node("qwr_2_open_tail")
        qwr_3_grounded_head = external_node("qwr_3_grounded_head")
        qwr_3_open_tail = external_node("qwr_3_open_tail")
        qwr_4_grounded_head = external_node("qwr_4_grounded_head")
        qwr_4_open_tail = external_node("qwr_4_open_tail")
        qwr_5_grounded_head = external_node("qwr_5_grounded_head")
        qwr_5_open_tail = external_node("qwr_5_open_tail")
        qwr_6_grounded_head = external_node("qwr_6_grounded_head")
        qwr_6_open_tail = external_node("qwr_6_open_tail")
        qwr_7_grounded_head = external_node("qwr_7_grounded_head")
        qwr_7_open_tail = external_node("qwr_7_open_tail")

        readout_line = transmission_line!(
            id=:readout_line,
            head=input,
            tail=output,
            spec=readout_spec,
            head_termination=:external,
            tail_termination=:external,
            section_overrides=readout_section_overrides,
        )

        qwr_1 = quarter_wave_resonator!(id=:qwr_1, grounded_head=qwr_1_grounded_head, open_tail=qwr_1_open_tail, spec=qwr_spec_1, breakpoints_m=[window_start_qwr_m, window_start_qwr_m + window_length_m], section_overrides=[coupled_line_section_override(mtl_model_1, 2)])
        qwr_2 = quarter_wave_resonator!(id=:qwr_2, grounded_head=qwr_2_grounded_head, open_tail=qwr_2_open_tail, spec=qwr_spec_2, breakpoints_m=[window_start_qwr_m, window_start_qwr_m + window_length_m], section_overrides=[coupled_line_section_override(mtl_model_2, 2)])
        qwr_3 = quarter_wave_resonator!(id=:qwr_3, grounded_head=qwr_3_grounded_head, open_tail=qwr_3_open_tail, spec=qwr_spec_3, breakpoints_m=[window_start_qwr_m, window_start_qwr_m + window_length_m], section_overrides=[coupled_line_section_override(mtl_model_3, 2)])
        qwr_4 = quarter_wave_resonator!(id=:qwr_4, grounded_head=qwr_4_grounded_head, open_tail=qwr_4_open_tail, spec=qwr_spec_4, breakpoints_m=[window_start_qwr_m, window_start_qwr_m + window_length_m], section_overrides=[coupled_line_section_override(mtl_model_4, 2)])
        qwr_5 = quarter_wave_resonator!(id=:qwr_5, grounded_head=qwr_5_grounded_head, open_tail=qwr_5_open_tail, spec=qwr_spec_5, breakpoints_m=[window_start_qwr_m, window_start_qwr_m + window_length_m], section_overrides=[coupled_line_section_override(mtl_model_5, 2)])
        qwr_6 = quarter_wave_resonator!(id=:qwr_6, grounded_head=qwr_6_grounded_head, open_tail=qwr_6_open_tail, spec=qwr_spec_6, breakpoints_m=[window_start_qwr_m, window_start_qwr_m + window_length_m], section_overrides=[coupled_line_section_override(mtl_model_6, 2)])
        qwr_7 = quarter_wave_resonator!(id=:qwr_7, grounded_head=qwr_7_grounded_head, open_tail=qwr_7_open_tail, spec=qwr_spec_7, breakpoints_m=[window_start_qwr_m, window_start_qwr_m + window_length_m], section_overrides=[coupled_line_section_override(mtl_model_7, 2)])

        window_1 = couple_transmission_window!(id=:readout_qwr_1_window, line1=readout_line, line2=qwr_1.line, start1=window_start_readout_m_list[1], start2=window_start_qwr_m, length=window_length_m, model=mtl_model_1)
        window_2 = couple_transmission_window!(id=:readout_qwr_2_window, line1=readout_line, line2=qwr_2.line, start1=window_start_readout_m_list[2], start2=window_start_qwr_m, length=window_length_m, model=mtl_model_2)
        window_3 = couple_transmission_window!(id=:readout_qwr_3_window, line1=readout_line, line2=qwr_3.line, start1=window_start_readout_m_list[3], start2=window_start_qwr_m, length=window_length_m, model=mtl_model_3)
        window_4 = couple_transmission_window!(id=:readout_qwr_4_window, line1=readout_line, line2=qwr_4.line, start1=window_start_readout_m_list[4], start2=window_start_qwr_m, length=window_length_m, model=mtl_model_4)
        window_5 = couple_transmission_window!(id=:readout_qwr_5_window, line1=readout_line, line2=qwr_5.line, start1=window_start_readout_m_list[5], start2=window_start_qwr_m, length=window_length_m, model=mtl_model_5)
        window_6 = couple_transmission_window!(id=:readout_qwr_6_window, line1=readout_line, line2=qwr_6.line, start1=window_start_readout_m_list[6], start2=window_start_qwr_m, length=window_length_m, model=mtl_model_6)
        window_7 = couple_transmission_window!(id=:readout_qwr_7_window, line1=readout_line, line2=qwr_7.line, start1=window_start_readout_m_list[7], start2=window_start_qwr_m, length=window_length_m, model=mtl_model_7)

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

        group(:multi_qwr_system) do
            label = "Readout line with seven hanging QWRs"
            role = :multi_resonator_readout_analysis
            members = [:readout_line, :qwr_1, :qwr_2, :qwr_3, :qwr_4, :qwr_5, :qwr_6, :qwr_7]
        end

        schematic!(:analysis_view) do
            track(:readout_track) do
                line = readout_line
                orientation = :left_to_right
                relative_order = :top
                role = :readout_line
                label = "readout"
            end
            track(:qwr_1_track) do
                line = qwr_1.line
                orientation = :left_to_right
                relative_order = :bottom
                role = :quarter_wave_resonator
                label = "QWR 1"
            end
            track(:qwr_2_track) do
                line = qwr_2.line
                orientation = :left_to_right
                relative_order = :bottom
                role = :quarter_wave_resonator
                label = "QWR 2"
            end
            track(:qwr_3_track) do
                line = qwr_3.line
                orientation = :left_to_right
                relative_order = :bottom
                role = :quarter_wave_resonator
                label = "QWR 3"
            end
            track(:qwr_4_track) do
                line = qwr_4.line
                orientation = :left_to_right
                relative_order = :bottom
                role = :quarter_wave_resonator
                label = "QWR 4"
            end
            track(:qwr_5_track) do
                line = qwr_5.line
                orientation = :left_to_right
                relative_order = :bottom
                role = :quarter_wave_resonator
                label = "QWR 5"
            end
            track(:qwr_6_track) do
                line = qwr_6.line
                orientation = :left_to_right
                relative_order = :bottom
                role = :quarter_wave_resonator
                label = "QWR 6"
            end
            track(:qwr_7_track) do
                line = qwr_7.line
                orientation = :left_to_right
                relative_order = :bottom
                role = :quarter_wave_resonator
                label = "QWR 7"
            end
            terminal(:input_terminal) do
                endpoint = input
                track = :readout_track
                side = :left
                kind = :port
                label = "1"
            end
            terminal(:output_terminal) do
                endpoint = output
                track = :readout_track
                side = :right
                kind = :port
                label = "2"
            end
            coupled_span(:readout_qwr_1_span) do
                relation = window_1
                track1 = :readout_track
                track2 = :qwr_1_track
                from1 = window_start_readout_m_list[1]
                to1 = window_start_readout_m_list[1] + window_length_m
                from2 = window_start_qwr_m
                to2 = window_start_qwr_m + window_length_m
                label = "QWR 1"
                render = :parallel_cpw_window
            end
            coupled_span(:readout_qwr_2_span) do
                relation = window_2
                track1 = :readout_track
                track2 = :qwr_2_track
                from1 = window_start_readout_m_list[2]
                to1 = window_start_readout_m_list[2] + window_length_m
                from2 = window_start_qwr_m
                to2 = window_start_qwr_m + window_length_m
                label = "QWR 2"
                render = :parallel_cpw_window
            end
            coupled_span(:readout_qwr_3_span) do
                relation = window_3
                track1 = :readout_track
                track2 = :qwr_3_track
                from1 = window_start_readout_m_list[3]
                to1 = window_start_readout_m_list[3] + window_length_m
                from2 = window_start_qwr_m
                to2 = window_start_qwr_m + window_length_m
                label = "QWR 3"
                render = :parallel_cpw_window
            end
            coupled_span(:readout_qwr_4_span) do
                relation = window_4
                track1 = :readout_track
                track2 = :qwr_4_track
                from1 = window_start_readout_m_list[4]
                to1 = window_start_readout_m_list[4] + window_length_m
                from2 = window_start_qwr_m
                to2 = window_start_qwr_m + window_length_m
                label = "QWR 4"
                render = :parallel_cpw_window
            end
            coupled_span(:readout_qwr_5_span) do
                relation = window_5
                track1 = :readout_track
                track2 = :qwr_5_track
                from1 = window_start_readout_m_list[5]
                to1 = window_start_readout_m_list[5] + window_length_m
                from2 = window_start_qwr_m
                to2 = window_start_qwr_m + window_length_m
                label = "QWR 5"
                render = :parallel_cpw_window
            end
            coupled_span(:readout_qwr_6_span) do
                relation = window_6
                track1 = :readout_track
                track2 = :qwr_6_track
                from1 = window_start_readout_m_list[6]
                to1 = window_start_readout_m_list[6] + window_length_m
                from2 = window_start_qwr_m
                to2 = window_start_qwr_m + window_length_m
                label = "QWR 6"
                render = :parallel_cpw_window
            end
            coupled_span(:readout_qwr_7_span) do
                relation = window_7
                track1 = :readout_track
                track2 = :qwr_7_track
                from1 = window_start_readout_m_list[7]
                to1 = window_start_readout_m_list[7] + window_length_m
                from2 = window_start_qwr_m
                to2 = window_start_qwr_m + window_length_m
                label = "QWR 7"
                render = :parallel_cpw_window
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

# ╔═╡ 5c3f32ae-2a36-5ce0-af2a-b9b4dd676608
md"""
## Core Representations
"""

# ╔═╡ c83c8e19-5e5c-506e-83e2-3bdef3176de6
hb_validation_report = validate_hb_intent(circuit_plan)

# ╔═╡ 3201f07f-7c08-5797-90b6-f543429580ef
graph = engineering_graph(circuit_plan)

# ╔═╡ c57921e8-e67f-5c79-82a6-bc9c4b1135ca
layout = schematic_layout_intent(circuit_plan)

# ╔═╡ 1ef26e6f-ff68-5a6c-8e46-42596f6c9991
schematic_export = to_schematic_export_spec(circuit_plan)

# ╔═╡ f5abe72b-3325-5874-8669-6a13d33a4472
graph_summary = (
    components=sort(collect(keys(graph.components)); by=string),
    ports=sort(collect(keys(graph.ports)); by=string),
    groups=sort(collect(keys(graph.groups)); by=string),
    relation_count=length(graph.relations),
)

# ╔═╡ 7b6094c2-4f2e-5980-be4d-f0a57d9525bb
layout_summary = (
    tracks=sort(collect(keys(layout.tracks)); by=string),
    coupled_spans=sort(collect(keys(layout.coupled_spans)); by=string),
    terminals=sort(collect(keys(layout.terminals)); by=string),
)

# ╔═╡ f9dea896-7259-5a61-85e9-4a6ff2fb9170
export_summary = (
    components=length(schematic_export.components),
    relations=length(schematic_export.relations),
    ports=length(schematic_export.ports),
    tracks=length(schematic_export.tracks),
    coupled_spans=length(schematic_export.coupled_spans),
)

# ╔═╡ bf70b2a1-fd3e-59be-a5bc-8b0557479241
compiled_circuit = compile_to_josephson(circuit_plan)

# ╔═╡ 9d9c2880-668e-5629-868b-dba3d8a17c58
compiled_summary = (
    netlist_rows=length(compiled_circuit.netlist),
    port_ids=sort(collect(keys(compiled_circuit.port_map)); by=string),
    warning_count=length(compiled_circuit.warnings),
)

# ╔═╡ fd65d7c1-daa1-57d4-8946-72dbfff30e77
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

# ╔═╡ 77cd668f-767d-5593-99ae-7d1f26d99c15
output_request_report = validate_output_request_configuration(compiled_circuit, hb_problem)

# ╔═╡ 108ae9d7-f1c8-5af9-b1d7-8f99c1544a65
result = run_hb_problem(hb_problem)

# ╔═╡ 52250c2e-558d-5839-b1f9-4f621178fae3
trace_families = sort(collect(keys(result.traces)); by=string)

# ╔═╡ 88d882a0-9c93-541a-bd80-a97a454bd08f
begin
    s11 = zero_mode_s(result, 1, 1)
    s21 = zero_mode_s(result, 2, 1)
    s21_db = db20(s21)
end

# ╔═╡ f8e71b84-d557-54c7-8b84-32844564a0d2
function local_notch_record(frequencies_hz, s21_db_trace, estimate_hz, id, length_um; search_window_hz=80.0e6)
    candidate_indices = findall(frequency -> abs(frequency - estimate_hz) <= search_window_hz / 2, frequencies_hz)
    if isempty(candidate_indices)
        candidate_indices = collect(eachindex(frequencies_hz))
    end
    local_value, local_position = findmin(s21_db_trace[candidate_indices])
    result_index = candidate_indices[local_position]
    notch_frequency_hz = frequencies_hz[result_index]
    return (
        id=id,
        length_um=length_um,
        pozar_frequency_ghz=estimate_hz / 1e9,
        notch_frequency_ghz=notch_frequency_hz / 1e9,
        delta_mhz=(notch_frequency_hz - estimate_hz) / 1e6,
        notch_db=local_value,
    )
end

# ╔═╡ 55d8e8be-7002-5df1-964a-a4df7b3b180a
notch_table = [
    local_notch_record(
        result.frequencies_hz,
        s21_db,
        pozar_frequencies_hz[index],
        resonator_ids[index],
        resonator_lengths_um[index],
        search_window_hz=notch_search_window_hz,
    )
    for index in eachindex(resonator_lengths_um)
]

# ╔═╡ 1a1c1a7f-97e2-5ecc-a032-ab06222b603c
sanity = (
    point_count_matches=length(result.frequencies_hz) == point_count,
    has_seven_coupled_spans=length(layout.coupled_spans) == 7,
    has_seven_notch_records=length(notch_table) == 7,
    finite_s21=all(isfinite, real.(s21)) && all(isfinite, imag.(s21)),
    hb_intent_ok=!has_errors(hb_validation_report),
)

# ╔═╡ 4e9b8adf-b250-55d1-8ec0-1584153ac0ac
sanity

# ╔═╡ 5d53874b-0361-5d42-b1a0-c067a7ee7baa
begin
    s_parameter_db_magnitude_figure(result.frequencies_hz, ["S11" => s11, "S21" => s21]; title="Multi Hanging QWR Readout Response", config=figure_config)
end |> wide_figure_cell

# ╔═╡ 29f1a589-aa75-558c-8a22-a3dc21457061
begin
    s_parameter_abs_magnitude_figure(result.frequencies_hz, ["S11" => s11, "S21" => s21]; title="Multi Hanging QWR Absolute Magnitude", config=figure_config, y_range=(0.0, 1.1))
end |> wide_figure_cell

# ╔═╡ Cell order:
# ╠═13c5bd32-cbbb-5d78-b539-5215862bf55f
# ╠═e21e8421-183a-5b9d-8d13-ee7d8ea6ebd0
# ╟─caff7b9a-5b47-5983-9182-5f9e4d599779
# ╟─179049e6-be96-5cd9-9af8-1841572bc7c0
# ╠═10bffd4c-ab29-5687-83f3-d838361a516b
# ╠═2c36bd83-3f4f-50fc-8b68-bff6b3cab80d
# ╠═a15bfe4e-0d12-5033-86c9-53fbd5cbac53
# ╟─70a778cf-2a9a-5cc5-9f58-2d80143ad7bf
# ╠═a9ea9510-c567-560f-9a7b-7f2b53e07f7d
# ╠═9a4971cb-87fa-5155-82c8-acb1630b0c05
# ╟─e8e1a39a-6fd4-5db1-b8ac-222db2df2b64
# ╠═e53543ab-a42d-501d-bb90-22487840e775
# ╟─5c3f32ae-2a36-5ce0-af2a-b9b4dd676608
# ╠═c83c8e19-5e5c-506e-83e2-3bdef3176de6
# ╠═3201f07f-7c08-5797-90b6-f543429580ef
# ╠═c57921e8-e67f-5c79-82a6-bc9c4b1135ca
# ╠═1ef26e6f-ff68-5a6c-8e46-42596f6c9991
# ╠═f5abe72b-3325-5874-8669-6a13d33a4472
# ╠═7b6094c2-4f2e-5980-be4d-f0a57d9525bb
# ╠═f9dea896-7259-5a61-85e9-4a6ff2fb9170
# ╠═bf70b2a1-fd3e-59be-a5bc-8b0557479241
# ╠═9d9c2880-668e-5629-868b-dba3d8a17c58
# ╠═fd65d7c1-daa1-57d4-8946-72dbfff30e77
# ╠═77cd668f-767d-5593-99ae-7d1f26d99c15
# ╠═108ae9d7-f1c8-5af9-b1d7-8f99c1544a65
# ╠═52250c2e-558d-5839-b1f9-4f621178fae3
# ╠═88d882a0-9c93-541a-bd80-a97a454bd08f
# ╠═f8e71b84-d557-54c7-8b84-32844564a0d2
# ╠═55d8e8be-7002-5df1-964a-a4df7b3b180a
# ╠═1a1c1a7f-97e2-5ecc-a032-ab06222b603c
# ╠═4e9b8adf-b250-55d1-8ec0-1584153ac0ac
# ╠═5d53874b-0361-5d42-b1a0-c067a7ee7baa
# ╠═29f1a589-aa75-558c-8a22-a3dc21457061
