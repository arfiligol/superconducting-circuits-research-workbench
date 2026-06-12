### A Pluto.jl notebook ###
# v1.0.1

#> [frontmatter]
#> title = "03 Transmission Line Circuit Model"
#> tags = ["julia-core", "pluto", "hb", "transmission-line"]
#> description = "Macro DSL tutorial for the Core RLGC transmission-line generator and real two-port traces."

using Markdown
using InteractiveUtils

# ╔═╡ fabc7ade-dc7d-50aa-8924-b3290b2aa296
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

# ╔═╡ 5ada4b82-0196-526a-9a45-495c1cbddf2c
TableOfContents()

# ╔═╡ d35acb0a-da29-5d63-9321-df35b3bd147e
md"""
# 03 Transmission Line Circuit Model

This notebook teaches the Core transmission-line generator directly. A CPW/RLGC line is sectioned into an LC ladder with a head endpoint, a tail endpoint, and ordered sections.
"""

# ╔═╡ 27f0ccb6-1fdd-524d-a4c7-4ceaad6f9700
md"""
## Owns

- CPW/RLGC ladder convention.
- Head/tail, section length, open/short/external termination meaning.
- Two-port through response from real HB traces.
"""

# ╔═╡ df021fa3-6aca-5b66-955f-3cb6e18578b0
LocalResource(joinpath(@__DIR__, "..", "..", "docs", "assets", "circuit_draw", "pluto_examples", "transmission_line_circuit_model", "diagram.light.svg"))

# ╔═╡ a37a8240-3c52-5896-8e35-085e425b1918
md"""
## Modeling Convention

For a section of length ``\Delta x``,

```math
L_{\mathrm{sec}} = L' \Delta x, \qquad C_{\mathrm{sec}} = C' \Delta x.
```

This notebook uses the generator directly because the transmission-line model itself is the subject being taught.
"""

# ╔═╡ 3a0820c2-905e-5ddd-aacf-9be1281e42b4
begin
    line_length_m = 4.0e-3
    section_length_m = 0.5e-3
    l_per_m_h = 404.313e-9
    c_per_m_f = 179.86e-12
    port_resistance = 50.0

    start_frequency = 2.0e9
    stop_frequency = 8.0e9
    point_count = 1000

    pump_frequency = 10.0e9
    pump_current = 0.0

    optional_hb_kwargs = Dict{Symbol,Any}(
        :nbatches => 1,
        :iterations => 120,
        :ftol => 1e-8,
    )
end

# ╔═╡ 0b4978e6-65db-521e-b5f1-9d74f48da92f
line_spec = RLGCSpec(
    length_m=line_length_m,
    section_length_m=section_length_m,
    l_per_m_h=l_per_m_h,
    c_per_m_f=c_per_m_f,
)

# ╔═╡ 84e1a342-0415-59a5-af82-6546a2208f46
parameter_table = [
    (name="length", value=line_length_m, unit="m", meaning="CPW physical length"),
    (name="section", value=section_length_m, unit="m", meaning="reference section length"),
    (name="L'", value=l_per_m_h, unit="H/m", meaning="per-unit-length inductance"),
    (name="C'", value=c_per_m_f, unit="F/m", meaning="per-unit-length capacitance"),
]

# ╔═╡ 34ebf27a-4ebd-5837-981f-e0ee37652236
begin
    circuit_plan = @circuit "transmission-line-circuit-model" begin
        input = external_node("input")
        output = external_node("output")

        cpw = transmission_line!(
            id=:cpw,
            head=input,
            tail=output,
            spec=line_spec,
            head_termination=:external,
            tail_termination=:external,
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

        schematic!(:notebook_view) do
            track(:cpw_track) do
                line = cpw
                orientation = :left_to_right
                relative_order = :center
                role = :transmission_line
                label = "CPW"
            end
            segment(:cpw_full) do
                track = :cpw_track
                from = 0.0
                to = line_length_m
                label = "l"
            end
            terminal(:input_terminal) do
                endpoint = input
                track = :cpw_track
                side = :left
                kind = :port
                label = "1"
            end
            terminal(:output_terminal) do
                endpoint = output
                track = :cpw_track
                side = :right
                kind = :port
                label = "2"
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
# ╔═╡ db35ecef-f172-5d50-9fcc-5b2af72cba29
md"""
## Inspect Core Representations
"""

# ╔═╡ 3ea2313c-2854-57c3-9574-e5c1014bc2a2
hb_validation_report = validate_hb_intent(circuit_plan)

# ╔═╡ 0a4a6017-7f19-5f10-87d2-429373de1bd5
graph = engineering_graph(circuit_plan)

# ╔═╡ 89690e87-86c9-500c-939e-15cc248fda71
layout = schematic_layout_intent(circuit_plan)

# ╔═╡ e34496c7-81e2-5587-939a-e88d3b9663ec
schematic_export = to_schematic_export_spec(circuit_plan)

# ╔═╡ ec8cffd5-b0ae-5da6-b539-24371d4e771a
graph_summary = (
    components=sort(collect(keys(graph.components)); by=string),
    ports=sort(collect(keys(graph.ports)); by=string),
    groups=sort(collect(keys(graph.groups)); by=string),
    relation_count=length(graph.relations),
)

# ╔═╡ 2bd292e6-de83-593e-b21a-6a3ca208d7cd
layout_summary = (
    tracks=sort(collect(keys(layout.tracks)); by=string),
    segments=sort(collect(keys(layout.segments)); by=string),
    coupled_spans=sort(collect(keys(layout.coupled_spans)); by=string),
    terminals=sort(collect(keys(layout.terminals)); by=string),
    node_labels=sort(collect(keys(layout.node_labels)); by=string),
)

# ╔═╡ 0929a0d8-a125-501f-9aee-5426ea359f98
export_summary = (
    components=length(schematic_export.components),
    relations=length(schematic_export.relations),
    ports=length(schematic_export.ports),
    tracks=length(schematic_export.tracks),
    terminals=length(schematic_export.terminals),
)

# ╔═╡ 6967b13b-331c-5174-a8dc-eafbb74ab425
compiled_circuit = compile_to_josephson(circuit_plan)

# ╔═╡ d7b3b46d-bfb2-57da-a7f3-0e02255b1e65
compiled_summary = (
    netlist_rows=length(compiled_circuit.netlist),
    port_ids=sort(collect(keys(compiled_circuit.port_map)); by=string),
    warning_count=length(compiled_circuit.warnings),
)

# ╔═╡ 73d0abc3-15b2-571a-89ec-217f2d5edf69
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

# ╔═╡ b4f45518-c807-5b7b-94a0-502abbf23761
output_request_report = validate_output_request_configuration(compiled_circuit, hb_problem)

# ╔═╡ c2e80506-d522-5fa6-9edd-d3885258958e
result = run_hb_problem(hb_problem)

# ╔═╡ c7f08c87-e76d-55df-a23e-e7c71988894c
trace_families = sort(collect(keys(result.traces)); by=string)

# ╔═╡ ac588b59-a8cc-54f6-8b72-9863c7e03b52
begin
    s11 = zero_mode_s(result, 1, 1)
    s21 = zero_mode_s(result, 2, 1)
end

# ╔═╡ 349bfe9e-72f7-5df5-9b96-2834841f50a0
sanity = (
    point_count_matches=length(result.frequencies_hz) == point_count,
    finite_s11=all(isfinite, real.(s11)) && all(isfinite, imag.(s11)),
    finite_s21=all(isfinite, real.(s21)) && all(isfinite, imag.(s21)),
    hb_intent_ok=!has_errors(hb_validation_report),
)

# ╔═╡ 290e4c5c-b9b3-57ff-80ee-e6c72edc0b34
sanity

# ╔═╡ bc6c5e90-048c-5352-a921-eaefd4b0207c
begin
    s_parameter_db_magnitude_figure(
        result.frequencies_hz,
        ["S11" => s11, "S21" => s21];
        title="Transmission Line Reflection And Transmission",
        config=figure_config,
    )
end |> wide_figure_cell

# ╔═╡ 26e856ee-a60c-5220-8cb7-6a46ab1c3ded
begin
    s_parameter_abs_magnitude_figure(
        result.frequencies_hz,
        ["S11" => s11, "S21" => s21];
        title="Transmission Line Absolute Magnitude",
        config=figure_config,
        y_range=(0.0, 1.1),
    )
end |> wide_figure_cell

# ╔═╡ Cell order:
# ╠═fabc7ade-dc7d-50aa-8924-b3290b2aa296
# ╠═5ada4b82-0196-526a-9a45-495c1cbddf2c
# ╟─d35acb0a-da29-5d63-9321-df35b3bd147e
# ╟─27f0ccb6-1fdd-524d-a4c7-4ceaad6f9700
# ╠═df021fa3-6aca-5b66-955f-3cb6e18578b0
# ╟─a37a8240-3c52-5896-8e35-085e425b1918
# ╠═3a0820c2-905e-5ddd-aacf-9be1281e42b4
# ╠═0b4978e6-65db-521e-b5f1-9d74f48da92f
# ╠═84e1a342-0415-59a5-af82-6546a2208f46
# ╠═34ebf27a-4ebd-5837-981f-e0ee37652236
# ╟─db35ecef-f172-5d50-9fcc-5b2af72cba29
# ╠═3ea2313c-2854-57c3-9574-e5c1014bc2a2
# ╠═0a4a6017-7f19-5f10-87d2-429373de1bd5
# ╠═89690e87-86c9-500c-939e-15cc248fda71
# ╠═e34496c7-81e2-5587-939a-e88d3b9663ec
# ╠═ec8cffd5-b0ae-5da6-b539-24371d4e771a
# ╠═2bd292e6-de83-593e-b21a-6a3ca208d7cd
# ╠═0929a0d8-a125-501f-9aee-5426ea359f98
# ╠═6967b13b-331c-5174-a8dc-eafbb74ab425
# ╠═d7b3b46d-bfb2-57da-a7f3-0e02255b1e65
# ╠═73d0abc3-15b2-571a-89ec-217f2d5edf69
# ╠═b4f45518-c807-5b7b-94a0-502abbf23761
# ╠═c2e80506-d522-5fa6-9edd-d3885258958e
# ╠═c7f08c87-e76d-55df-a23e-e7c71988894c
# ╠═ac588b59-a8cc-54f6-8b72-9863c7e03b52
# ╠═349bfe9e-72f7-5df5-9b96-2834841f50a0
# ╠═290e4c5c-b9b3-57ff-80ee-e6c72edc0b34
# ╠═bc6c5e90-048c-5352-a921-eaefd4b0207c
# ╠═26e856ee-a60c-5220-8cb7-6a46ab1c3ded
