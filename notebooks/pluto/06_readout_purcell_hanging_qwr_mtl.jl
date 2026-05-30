### A Pluto.jl notebook ###
# v1.0.1

#> [frontmatter]
#> title = "06 Readout Purcell Hanging QWR MTL"
#> tags = ["julia-core", "pluto", "readout-line", "purcell-filter", "quarter-wave-resonator", "mtl-coupling"]
#> description = "Canonical Pluto notebook structure for the integrated readout line with Purcell filter and hanging QWR MTL coupling."

using Markdown
using InteractiveUtils

# ╔═╡ 78b612d2-b8e6-51ba-9373-a23fc4c65d8b
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

# ╔═╡ f9011236-1723-5c41-b1f5-ae138dbd83e2
TableOfContents()

# ╔═╡ c734d07f-7823-5962-bc6c-3ff5292a1e80
md"""
# 06 Readout / Purcell / Hanging QWR / MTL

This notebook combines the point-coupled Purcell-filter readout path with the finite-window MTL hanging-QWR coupling pattern.

## Purpose

Expose the integrated topology as one compiled circuit: parameters, primitive component extraction, graph and compile inspection, explicit `HBProblemSpec`, explicit solve, real `S11` / `S21` traces in one magnitude figure, and sanity checks.
"""

# ╔═╡ fbdc641a-af8c-5840-901b-59ce29209138
md"""
## Owns

- Integrated readout path containing both a Purcell filter and a hanging QWR.
- Combined two-port response display.
- Middle-section selection for the MTL window on the Purcell-filter CPW ladder.
"""

# ╔═╡ cc961a20-47b0-5687-9b89-1d23d6e5630d
LocalResource(joinpath(@__DIR__, "..", "..", "docs", "assets", "pluto-06-readout-purcell-hanging-qwr-mtl.svg"))

# ╔═╡ f4a138d2-8e35-504d-b1b2-8a2b6409f6eb
md"""
## LaTeX Physics

The integrated response is a product of loading and interference effects, not a sum of independent curves. The notebook should expose the actual Core solve for

$$
S_{11}(\omega), \quad S_{21}(\omega)
$$

with the Purcell filter and QWR present in the same compiled circuit.

The QWR estimate remains

$$
f_{\lambda/4} \approx \frac{v_p}{4l},
$$

while the Purcell filter contributes an additional mode and admittance transformation along the readout path.
"""

# ╔═╡ 6a54b27f-9031-5e90-8e91-05cb21108081
md"""
## Modeling Conventions

- The Purcell filter uses point capacitive coupling.
- The hanging QWR uses a finite MTL coupled window.
- The final notebook must not overlay separately simulated traces; all curves come from one `result` for the integrated circuit.
"""

# ╔═╡ 097190d0-49a6-5502-ad87-19d66b3aef34
begin
    input_line_length_m = 2.0e-3
    filter_length_m = 8.0e-3
    output_line_length_m = 2.0e-3
    qwr_length_m = 5.28371e-3
    section_length_m = 0.75e-3

    l_per_m_h = 4.2e-7
    c_per_m_f = 1.7e-10

    input_coupling_f = 2.0e-15
    output_coupling_f = 2.0e-15

    window_start_filter_m = 2.25e-3
    window_start_qwr_m = 0.0
    window_length_m = 200e-6
    c12_per_m_f = 8.09678e-11
    lm_per_m_h = 19.08527e-8

    port_resistance = 50.0

    start_frequency = 4.0e9
    stop_frequency = 8.0e9
    point_count = 1000

    pump_frequency = 14.0e9
    pump_current = 0.0

    optional_hb_kwargs = Dict{Symbol,Any}(
        :nbatches => 1,
        :iterations => 180,
        :ftol => 1e-8,
    )
end

# ╔═╡ 632d69f3-2300-5ab2-b27a-e96000077456
combined_window_model = MTLCoupledWindowSpec(
    window_start_filter_m,
    window_start_qwr_m,
    window_length_m,
    section_length_m,
    c12_per_m_f,
    lm_per_m_h,
)

# ╔═╡ 5b15341e-c123-5cd4-8d8a-0af9af04a0a8
let
    purcell_model = RLGCSpec(
        length_m=filter_length_m,
        section_length_m=section_length_m,
        l_per_m_h=l_per_m_h,
        c_per_m_f=c_per_m_f,
    )
    qwr_model = RLGCSpec(
        length_m=qwr_length_m,
        section_length_m=section_length_m,
        l_per_m_h=l_per_m_h,
        c_per_m_f=c_per_m_f,
    )
    (
        purcell_sections=purcell_model.n_sections,
        qwr_sections=qwr_model.n_sections,
        qwr_frequency_estimate_ghz=phase_velocity(qwr_model) / (4 * qwr_length_m) / 1e9,
        input_coupling_fF=input_coupling_f * 1e15,
        output_coupling_fF=output_coupling_f * 1e15,
        mutual_k=combined_window_model.lm_per_m_h / l_per_m_h,
    )
end

# ╔═╡ 49bec8d4-acae-5e23-b624-6d6ca2003d6a
md"""
## Primitive-Built Component And Core Authoring

The builder below constructs one integrated `CircuitPlan`. The selected MTL window is on the Purcell filter's middle CPW segment, not on a separate overlaid circuit.
"""

# ╔═╡ 3037fa4d-26eb-58f9-b9f5-d8c7b13f3a44
integrated_readout_core_builder = build_readout_purcell_hanging_qwr_mtl_example

# ╔═╡ d7bee3d9-27d1-56e1-9ad2-25fb1621dd3b
example = integrated_readout_core_builder(
    input_line_length_m=input_line_length_m,
    filter_length_m=filter_length_m,
    output_line_length_m=output_line_length_m,
    qwr_length_m=qwr_length_m,
    section_length_m=section_length_m,
    l_per_m_h=l_per_m_h,
    c_per_m_f=c_per_m_f,
    input_coupling_f=input_coupling_f,
    output_coupling_f=output_coupling_f,
    window_start_filter_m=window_start_filter_m,
    window_start_qwr_m=window_start_qwr_m,
    window_length_m=window_length_m,
    c12_per_m_f=c12_per_m_f,
    lm_per_m_h=lm_per_m_h,
    port_resistance=port_resistance,
    start_frequency=start_frequency,
    stop_frequency=stop_frequency,
    point_count=point_count,
    pump_frequency=pump_frequency,
    pump_current=pump_current,
    optional_hb_kwargs=optional_hb_kwargs,
)

# ╔═╡ fb51b586-34e7-5a06-a67a-24e6075a6051
circuit_plan = example.plan

# ╔═╡ 76c373da-ab0b-5c48-abff-73ecc89fa520
engineering_graph = example.graph

# ╔═╡ f8ffd151-ea2d-57ff-bedc-abdca4964e37
compiled_circuit = example.compiled

# ╔═╡ 2a9d094a-3d50-5816-b56b-bee289feadf1
primitive_component = (readout_filter=example.readout_purcell, qwr=example.qwr, window=example.window)

# ╔═╡ 69063dd9-6c63-5970-8923-08d18df48d76
(
    input_line_sections=length(primitive_component.readout_filter.input_line.series_inductors),
    filter_sections=length(primitive_component.readout_filter.filter_line.series_inductors),
    output_line_sections=length(primitive_component.readout_filter.output_line.series_inductors),
    qwr_sections=length(primitive_component.qwr.series_inductors),
    window_filter_sections=primitive_component.window.section_range1,
    window_qwr_sections=primitive_component.window.section_range2,
)

# ╔═╡ 7bdb50b3-759d-5c6f-ac6c-6207aa710db0
(
    plan_id=circuit_plan.id,
    relation_count=length(circuit_plan.relations),
    parameter_count=length(circuit_plan.parameters),
    port_ids=sort(collect(keys(engineering_graph.ports))),
)

# ╔═╡ 3a6e820d-38bf-5bb4-b60c-b8518690fe3b
engineering_graph.relations

# ╔═╡ d30e08bd-27c5-50e9-8abf-50a6dada8ece
compiled_circuit.netlist

# ╔═╡ 145fdcb0-735c-5838-b192-aecd7e8350b3
compiled_circuit.component_values

# ╔═╡ 2b068335-6d0a-5555-9240-35d6007413a5
md"""
## HBProblemSpec And Real Solver Output

The notebook keeps the solve boundary visible. `hb_problem` is inspectable before execution, and the next cell is intentionally the explicit solver call used by all canonical Pluto notebooks.
"""

# ╔═╡ d734e4ce-5648-553d-9acb-660371400896
hb_problem = example.hb_problem

# ╔═╡ 2021cda9-02a3-53fd-ac3c-6e7431179766
(
    frequency_points=length(hb_problem.frequencies_hz),
    pump_axes=hb_problem.wp,
    sources=hb_problem.sources,
    controls=hb_problem.controls,
)

# ╔═╡ 4d117b3d-4e90-5c1a-b413-456c0ab7bb69
result = run_hb_problem(hb_problem)

# ╔═╡ df41b413-f5b7-5bd3-8bb2-477b50a63eb6
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

# ╔═╡ e44cf3bf-544e-532c-9a8d-3e28316bf79f
begin
    frequencies_ghz = result.frequencies_hz ./ 1e9
    s11 = zero_mode_s(result, 1, 1)
    s21 = zero_mode_s(result, 2, 1)
    z11 = zero_mode_z(result, 1, 1)
    z21 = zero_mode_z(result, 2, 1)
end

# ╔═╡ 1e6bafa2-fe43-5ccc-9c71-714512cb71e4
sanity = (
    point_count_matches=length(result.frequencies_hz) == point_count,
    s11_points=length(s11),
    s21_points=length(s21),
    finite_s_traces=all(isfinite, real.(s11)) && all(isfinite, imag.(s11)) && all(isfinite, real.(s21)) && all(isfinite, imag.(s21)),
    strongest_s21_feature_ghz=frequencies_ghz[argmin(db20(s21))],
)

# ╔═╡ 9b2aade8-f188-58cd-8b01-c53cf3e11922
sanity

# ╔═╡ 6b1ddff1-1ee0-59ac-8c69-071451b0158c
begin
    s_parameter_magnitude_figure(
        result.frequencies_hz,
        [
            "S11" => s11,
            "S21" => s21,
        ];
        title="Integrated Readout S-Parameter Magnitudes",
        config=figure_config,
    )
end |> wide_figure_cell

# ╔═╡ ccc6f3d0-e693-5a9c-8a35-2e9fe1e1c51a
begin
    s_parameter_phase_figure(
        result.frequencies_hz,
        [
            "S11" => s11,
            "S21" => s21,
        ];
        title="Integrated Readout Phase",
        config=figure_config,
    )
end |> wide_figure_cell

# ╔═╡ cccf082e-792f-520f-a003-08baa0590594
begin
    z_trace_figure(
        result.frequencies_hz,
        [
            "Z11" => z11,
            "Z21" => z21,
        ];
        title="Integrated Readout Z Parameters",
        config=figure_config,
    )
end |> wide_figure_cell

# ╔═╡ Cell order:
# ╠═78b612d2-b8e6-51ba-9373-a23fc4c65d8b
# ╠═f9011236-1723-5c41-b1f5-ae138dbd83e2
# ╟─c734d07f-7823-5962-bc6c-3ff5292a1e80
# ╟─fbdc641a-af8c-5840-901b-59ce29209138
# ╠═cc961a20-47b0-5687-9b89-1d23d6e5630d
# ╟─f4a138d2-8e35-504d-b1b2-8a2b6409f6eb
# ╟─6a54b27f-9031-5e90-8e91-05cb21108081
# ╠═097190d0-49a6-5502-ad87-19d66b3aef34
# ╠═632d69f3-2300-5ab2-b27a-e96000077456
# ╠═5b15341e-c123-5cd4-8d8a-0af9af04a0a8
# ╟─49bec8d4-acae-5e23-b624-6d6ca2003d6a
# ╠═3037fa4d-26eb-58f9-b9f5-d8c7b13f3a44
# ╠═d7bee3d9-27d1-56e1-9ad2-25fb1621dd3b
# ╠═fb51b586-34e7-5a06-a67a-24e6075a6051
# ╠═76c373da-ab0b-5c48-abff-73ecc89fa520
# ╠═f8ffd151-ea2d-57ff-bedc-abdca4964e37
# ╠═2a9d094a-3d50-5816-b56b-bee289feadf1
# ╠═69063dd9-6c63-5970-8923-08d18df48d76
# ╠═7bdb50b3-759d-5c6f-ac6c-6207aa710db0
# ╠═3a6e820d-38bf-5bb4-b60c-b8518690fe3b
# ╠═d30e08bd-27c5-50e9-8abf-50a6dada8ece
# ╠═145fdcb0-735c-5838-b192-aecd7e8350b3
# ╟─2b068335-6d0a-5555-9240-35d6007413a5
# ╠═d734e4ce-5648-553d-9acb-660371400896
# ╠═2021cda9-02a3-53fd-ac3c-6e7431179766
# ╠═4d117b3d-4e90-5c1a-b413-456c0ab7bb69
# ╠═df41b413-f5b7-5bd3-8bb2-477b50a63eb6
# ╠═e44cf3bf-544e-532c-9a8d-3e28316bf79f
# ╠═1e6bafa2-fe43-5ccc-9c71-714512cb71e4
# ╠═9b2aade8-f188-58cd-8b01-c53cf3e11922
# ╠═6b1ddff1-1ee0-59ac-8c69-071451b0158c
# ╠═ccc6f3d0-e693-5a9c-8a35-2e9fe1e1c51a
# ╠═cccf082e-792f-520f-a003-08baa0590594
