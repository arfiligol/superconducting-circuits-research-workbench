### A Pluto.jl notebook ###
# v1.0.1

#> [frontmatter]
#> title = "05 Readout Line Hanging QWR MTL"
#> tags = ["julia-core", "pluto", "hb", "mtl", "qwr"]
#> description = "Macro DSL tutorial for a readout CPW finite-window coupled to a hanging quarter-wave resonator."

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
    using .HBExampleHelpers: db20, zero_mode_s, zero_mode_z
end

# ╔═╡ e21e8421-183a-5b9d-8d13-ee7d8ea6ebd0
TableOfContents()

# ╔═╡ caff7b9a-5b47-5983-9182-5f9e4d599779
md"""
# 05 Readout Line Hanging QWR With MTL Coupling

This notebook models a pure readout CPW coupled to a grounded-head/open-tail quarter-wave resonator by a finite MTL window.
"""

# ╔═╡ 46fe8430-f7c1-5559-a1d5-63b766f2147b
md"""
## Owns

- Readout CPW ladder plus hanging QWR ladder.
- Finite MTL coupled-window parameters and coupled-section overrides.
- Distinction between localized capacitor coupling and distributed coupled-window modeling.
"""

# ╔═╡ 3796afcc-0549-5af7-bb65-06052fb4db95
LocalResource(joinpath(@__DIR__, "..", "..", "docs", "assets", "circuit_draw", "pluto_examples", "readout_line_hanging_qwr_mtl", "diagram.light.svg"))

# ╔═╡ 179049e6-be96-5cd9-9af8-1841572bc7c0
md"""
## Modeling Convention

The uncoupled sections use the single-line RLGC baseline. Inside the coupled window, each line uses the coupled self terms from `MTLCoupledRLGCSpec`, and the window generator adds cross capacitance and mutual inductance relations.

Following the transmission-line convention used in Pozar's *Microwave Engineering*, first estimate the isolated quarter-wave frequency before reading the distributed simulation. For an ideal lossless line with phase velocity `v_p` and physical length `\ell`,

```math
v_p = \frac{c_0}{\sqrt{\epsilon_{\mathrm{eff}}}},
\qquad
f_{\lambda/4} = \frac{v_p}{4\ell}.
```

For an RLGC line with negligible `R'` and `G'`, the same phase velocity is

```math
v_p = \frac{1}{\sqrt{L'C'}},
\qquad
\epsilon_{\mathrm{eff}} = \left(\frac{c_0}{v_p}\right)^2.
```

This is an isolated-resonator estimate. The simulated notch is loaded by the through readout line, the finite MTL coupling window, and the distributed ladder discretization.

For each coupled section,

```math
C_{12,\mathrm{sec}} = C'_{12}\Delta x, \qquad
M_{12,\mathrm{sec}} = L'_m\Delta x.
```
"""

# ╔═╡ 10bffd4c-ab29-5687-83f3-d838361a516b
begin
    readout_length_m = 6.0e-3
    resonator_length_m = 5.28371e-3
    section_length_m = 10.0e-6
    readout_l_per_m_h = 409.73174e-9
    readout_c_per_m_f = 164.48779e-12
    resonator_l_per_m_h = 409.73174e-9
    resonator_c_per_m_f = 164.48779e-12

    window_start_readout_m = 2.25e-3
    window_start_resonator_m = 0.0
    window_length_m = 200.0e-6
    l_matrix_per_m_h = [414.15487 36.58878; 36.58878 414.16764] .* 1e-9
    c_matrix_per_m_f = [163.95741 -14.83887; -14.83887 163.94730] .* 1e-12
    port_resistance = 50.0

    start_frequency = 5.754e9
    stop_frequency = 5.757e9
    point_count = 3000

    pump_frequency = 14.0e9
    pump_current = 0.0

    optional_hb_kwargs = Dict{Symbol,Any}(:nbatches => 1, :iterations => 160, :ftol => 1e-8)
end

# ╔═╡ 9a4971cb-87fa-5155-82c8-acb1630b0c05
begin
    readout_spec = RLGCSpec(
        length_m=readout_length_m,
        section_length_m=section_length_m,
        l_per_m_h=readout_l_per_m_h,
        c_per_m_f=readout_c_per_m_f
    )
    qwr_spec = RLGCSpec(
        length_m=resonator_length_m,
        section_length_m=section_length_m,
        l_per_m_h=resonator_l_per_m_h,
        c_per_m_f=resonator_c_per_m_f
    )
    mtl_model = MTLCoupledRLGCSpec(
        start1_m=window_start_readout_m,
        start2_m=window_start_resonator_m,
        length_m=window_length_m,
        section_length_m=section_length_m,
        l_matrix_per_m_h=l_matrix_per_m_h,
        c_matrix_per_m_f=c_matrix_per_m_f,
    )
end

# ╔═╡ 2c36bd83-3f4f-50fc-8b68-bff6b3cab80d
begin
    speed_of_light_m_per_s = 299_792_458.0
    phase_velocity_m_per_s = 1 / sqrt(resonator_l_per_m_h * resonator_c_per_m_f)
    effective_permittivity = (speed_of_light_m_per_s / phase_velocity_m_per_s)^2
    qwr_pozar_frequency_hz = phase_velocity_m_per_s / (4 * resonator_length_m)
    qwr_pozar_frequency_ghz = qwr_pozar_frequency_hz / 1e9
    frequency_step_mhz = (stop_frequency - start_frequency) / (point_count - 1) / 1e6
    sweep_range_covers_pozar_estimate = start_frequency <= qwr_pozar_frequency_hz && qwr_pozar_frequency_hz <= stop_frequency
end

# ╔═╡ a15bfe4e-0d12-5033-86c9-53fbd5cbac53
parameter_table = [
    (name="readout length", value=readout_length_m, unit="m", meaning="through CPW length"),
    (name="QWR length", value=resonator_length_m, unit="m", meaning="grounded-head/open-tail resonator length"),
    (name="window start", value=(window_start_readout_m, window_start_resonator_m), unit="m", meaning="distance from each head"),
    (name="window length", value=window_length_m, unit="m", meaning="finite MTL span"),
    (name="Pozar QWR estimate", value=qwr_pozar_frequency_ghz, unit="GHz", meaning="isolated lossless quarter-wave estimate"),
    (name="explicit sweep", value=(start_frequency / 1e9, stop_frequency / 1e9, frequency_step_mhz), unit="GHz, GHz, MHz", meaning="user-selected HB sweep"),
]

# ╔═╡ f0e81442-9fc2-59aa-8792-b52990e871f0
if sweep_range_covers_pozar_estimate
    md"""
    !!! info "Pozar estimate"
        The table above lists the isolated quarter-wave estimate from Pozar-style transmission-line theory. The HB sweep range is still set explicitly by `start_frequency` and `stop_frequency` in the parameter cell.
    """
else
    md"""
    !!! warning "Pozar estimate outside sweep"
        The isolated quarter-wave estimate is outside the explicit sweep range. Update `start_frequency` and `stop_frequency` if this notch should be included.
    """
end

# ╔═╡ e53543ab-a42d-501d-bb90-22487840e775
begin
    circuit_plan = @circuit "readout-line-hanging-qwr-mtl" begin
        input = external_node("input")
        output = external_node("output")
        qwr_grounded_head = external_node("qwr_grounded_head")
        qwr_open_tail = external_node("qwr_open_tail")

        readout_line = transmission_line!(
            id=:readout_line,
            head=input,
            tail=output,
            spec=readout_spec,
            head_termination=:external,
            tail_termination=:external,
            breakpoints_m=[window_start_readout_m, window_start_readout_m + window_length_m],
            section_overrides=[coupled_line_section_override(mtl_model, 1)],
        )
        qwr = quarter_wave_resonator!(
            id=:qwr,
            grounded_head=qwr_grounded_head,
            open_tail=qwr_open_tail,
            spec=qwr_spec,
            breakpoints_m=[window_start_resonator_m, window_start_resonator_m + window_length_m],
            section_overrides=[coupled_line_section_override(mtl_model, 2)],
        )
        window = couple_transmission_window!(
            id=:readout_qwr_mtl_window,
            line1=readout_line,
            line2=qwr.line,
            start1=window_start_readout_m,
            start2=window_start_resonator_m,
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

        group(:readout_qwr_system) do
            label = "Readout line with hanging QWR"
            role = :readout_resonator_system
            members = [:readout_line, :qwr, :readout_qwr_mtl_window, :input_port, :output_port]
        end

        schematic!(:notebook_view) do
            track(:readout_track) do
                line = readout_line
                orientation = :left_to_right
                relative_order = :top
                role = :readout_line
                label = "readout"
            end
            track(:qwr_track) do
                line = qwr.line
                orientation = :left_to_right
                relative_order = :bottom
                role = :quarter_wave_resonator
                label = "QWR"
            end
            segment(:readout_window_segment) do
                track = :readout_track
                from = window_start_readout_m
                to = window_start_readout_m + window_length_m
                label = "coupled"
            end
            segment(:qwr_window_segment) do
                track = :qwr_track
                from = window_start_resonator_m
                to = window_start_resonator_m + window_length_m
                label = "coupled"
            end
            coupled_span(:readout_qwr_window_span) do
                relation = window
                track1 = :readout_track
                track2 = :qwr_track
                from1 = window_start_readout_m
                to1 = window_start_readout_m + window_length_m
                from2 = window_start_resonator_m
                to2 = window_start_resonator_m + window_length_m
                label = "MTL window"
                render = :parallel_cpw_window
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

# ╔═╡ 5c3f32ae-2a36-5ce0-af2a-b9b4dd676608
md"""
## Inspect Core Representations
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
    segments=sort(collect(keys(layout.segments)); by=string),
    coupled_spans=sort(collect(keys(layout.coupled_spans)); by=string),
    terminals=sort(collect(keys(layout.terminals)); by=string),
    node_labels=sort(collect(keys(layout.node_labels)); by=string),
)

# ╔═╡ f9dea896-7259-5a61-85e9-4a6ff2fb9170
export_summary = (
    components=length(schematic_export.components),
    relations=length(schematic_export.relations),
    ports=length(schematic_export.ports),
    tracks=length(schematic_export.tracks),
    terminals=length(schematic_export.terminals),
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
end

# ╔═╡ 6e2fd612-65b3-58a4-bbd5-8c6c9fb4ad61
begin
    s21_db = db20(s21)
    simulated_notch_db, simulated_notch_index = findmin(s21_db)
    simulated_notch_frequency_hz = result.frequencies_hz[simulated_notch_index]
    simulated_notch_frequency_ghz = simulated_notch_frequency_hz / 1e9
    frequency_delta_mhz = (simulated_notch_frequency_hz - qwr_pozar_frequency_hz) / 1e6
    relative_frequency_delta_percent = 100 * (simulated_notch_frequency_hz - qwr_pozar_frequency_hz) / qwr_pozar_frequency_hz
end

# ╔═╡ 8b9d54f7-0b4a-5571-bb76-bccff71037dd
frequency_comparison_table = [
    (quantity="Pozar isolated QWR estimate", value=qwr_pozar_frequency_ghz, unit="GHz", note="vp / 4l from RLGC phase velocity"),
    (quantity="Simulated S21 notch", value=simulated_notch_frequency_ghz, unit="GHz", note="minimum S21 dB from real HBSolveResult"),
    (quantity="Frequency difference", value=frequency_delta_mhz, unit="MHz", note="simulated notch minus Pozar estimate"),
    (quantity="Relative difference", value=relative_frequency_delta_percent, unit="%", note="loaded by finite MTL window and through-line environment"),
]

# ╔═╡ 1a1c1a7f-97e2-5ecc-a032-ab06222b603c
sanity = (
    point_count_matches=length(result.frequencies_hz) == point_count,
    has_coupled_span=haskey(layout.coupled_spans, :readout_qwr_window_span),
    finite_s21=all(isfinite, real.(s21)) && all(isfinite, imag.(s21)),
    finite_notch_frequency=isfinite(simulated_notch_frequency_hz),
    hb_intent_ok=!has_errors(hb_validation_report),
)

# ╔═╡ 4e9b8adf-b250-55d1-8ec0-1584153ac0ac
sanity

# ╔═╡ 5d53874b-0361-5d42-b1a0-c067a7ee7baa
begin
    s_parameter_db_magnitude_figure(result.frequencies_hz, ["S11" => s11, "S21" => s21]; title="Readout Line With Hanging QWR", config=figure_config)
end |> wide_figure_cell

# ╔═╡ 29f1a589-aa75-558c-8a22-a3dc21457061
begin
    s_parameter_abs_magnitude_figure(result.frequencies_hz, ["S11" => s11, "S21" => s21]; title="Readout-QWR Absolute Magnitude", config=figure_config, y_range=(0.0, 1.1))
end |> wide_figure_cell

# ╔═╡ Cell order:
# ╠═13c5bd32-cbbb-5d78-b539-5215862bf55f
# ╠═e21e8421-183a-5b9d-8d13-ee7d8ea6ebd0
# ╟─caff7b9a-5b47-5983-9182-5f9e4d599779
# ╟─46fe8430-f7c1-5559-a1d5-63b766f2147b
# ╠═3796afcc-0549-5af7-bb65-06052fb4db95
# ╟─179049e6-be96-5cd9-9af8-1841572bc7c0
# ╠═10bffd4c-ab29-5687-83f3-d838361a516b
# ╠═9a4971cb-87fa-5155-82c8-acb1630b0c05
# ╠═2c36bd83-3f4f-50fc-8b68-bff6b3cab80d
# ╠═a15bfe4e-0d12-5033-86c9-53fbd5cbac53
# ╟─f0e81442-9fc2-59aa-8792-b52990e871f0
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
# ╠═6e2fd612-65b3-58a4-bbd5-8c6c9fb4ad61
# ╠═8b9d54f7-0b4a-5571-bb76-bccff71037dd
# ╠═1a1c1a7f-97e2-5ecc-a032-ab06222b603c
# ╠═4e9b8adf-b250-55d1-8ec0-1584153ac0ac
# ╠═5d53874b-0361-5d42-b1a0-c067a7ee7baa
# ╠═29f1a589-aa75-558c-8a22-a3dc21457061
