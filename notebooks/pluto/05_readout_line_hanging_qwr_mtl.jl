### A Pluto.jl notebook ###
# v1.0.1

#> [frontmatter]
#> title = "05 Readout Line Hanging QWR MTL"
#> tags = ["julia-core", "pluto", "readout-line", "quarter-wave-resonator", "mtl-coupling"]
#> description = "Canonical Pluto notebook for a readout line with a hanging QWR and finite MTL coupled window."

using Markdown
using InteractiveUtils

# ╔═╡ 6d014f3d-d3ca-5721-8750-ace93cb7ac27
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

# ╔═╡ 73f73882-c2c8-565b-a20b-19543764b269
TableOfContents()

# ╔═╡ de8a31e4-34f6-530c-9264-f06d12b2c132
md"""
# 05 Readout Line / Hanging QWR / MTL Coupling

This notebook owns the finite distributed coupling-window convention for a readout line and hanging quarter-wave resonator.

## Purpose

Use a real MTL window primitive, inspect the coupled-window component, preserve explicit Core compile and HB solve cells, and plot real two-port `S11` / `S21` traces in one magnitude figure.
"""

# ╔═╡ 70a08ed6-f4be-58f6-8d83-3639dc817402
md"""
## Owns

- Readout CPW ladder plus hanging QWR ladder.
- Finite MTL coupled-window parameters.
- Distinction between point capacitive coupling and distributed coupling.
"""

# ╔═╡ 8b2bf24e-1591-5c5e-b84a-88d5de249f8e
LocalResource(joinpath(@__DIR__, "..", "..", "docs", "assets", "pluto-05-readout-line-hanging-qwr-mtl.svg"))

# ╔═╡ c63df8e5-f40f-5034-9a17-33dcccab6b1c
md"""
## LaTeX Physics

A quarter-wave resonator has a grounded or voltage-node end and an open or voltage-antinode end. In the ideal line model,

$$
f_{\lambda/4} \approx \frac{v_p}{4l}.
$$

A finite MTL window couples distributed sections rather than inserting one lumped capacitor:

$$
C_{12,sec}=C'_{12}\Delta x, \qquad M_{12,sec}=L'_m\Delta x.
$$
"""

# ╔═╡ c667696c-beb5-5b11-b7d8-4cadb6774d18
md"""
## Modeling Conventions

- The readout line is a two-port ladder.
- The QWR head is grounded/coupled and the tail is open.
- The coupling window is a physical span with start positions and length on both ladders.
"""

# ╔═╡ 21df14a8-b4ac-58da-851f-c4c5509e234a
begin
    readout_length_m = 9.0e-3
    resonator_length_m = 5.28371e-3
    section_length_m = 0.75e-3

    readout_l_per_m_h = 4.2e-7
    readout_c_per_m_f = 1.7e-10
    resonator_l_per_m_h = 4.2e-7
    resonator_c_per_m_f = 1.7e-10

    window_start_readout_m = 2.25e-3
    window_start_resonator_m = 0.0
    window_length_m = 200e-6
    c12_per_m_f = 8.09678e-11
    lm_per_m_h = 19.08527e-8

    port_resistance = 50.0

    start_frequency = 5.0e9
    stop_frequency = 6.0e9
    point_count = 1000

    pump_frequency = 14.0e9
    pump_current = 0.0

    optional_hb_kwargs = Dict{Symbol,Any}(
        :nbatches => 1,
        :iterations => 160,
        :ftol => 1e-8,
    )
end

# ╔═╡ 567fdfbc-ce0c-58fe-a0c0-884dfe084b2f
window_model = MTLCoupledWindowSpec(
    window_start_readout_m,
    window_start_resonator_m,
    window_length_m,
    section_length_m,
    c12_per_m_f,
    lm_per_m_h,
)

# ╔═╡ 49d7184f-ff4b-5a08-96df-5b1f54f7d5fa
let
    readout_model = RLGCSpec(
        length_m=readout_length_m,
        section_length_m=section_length_m,
        l_per_m_h=readout_l_per_m_h,
        c_per_m_f=readout_c_per_m_f,
    )
    resonator_model = RLGCSpec(
        length_m=resonator_length_m,
        section_length_m=section_length_m,
        l_per_m_h=resonator_l_per_m_h,
        c_per_m_f=resonator_c_per_m_f,
    )
    (
        readout_sections=readout_model.n_sections,
        resonator_sections=resonator_model.n_sections,
        qwr_frequency_estimate_ghz=phase_velocity(resonator_model) / (4 * resonator_length_m) / 1e9,
        mutual_k=window_model.lm_per_m_h / sqrt(readout_l_per_m_h * resonator_l_per_m_h),
    )
end

# ╔═╡ 6390bc28-0f63-5ba6-8443-041dec21f5d7
md"""
## Primitive-Built Component And Core Authoring

The coupled window is selected by distance from each ladder head. The readout line and QWR both include the window boundaries as ladder breakpoints, so Core can generate matching mutual-capacitance and mutual-inductance sections without silently rounding the physical length.
"""

# ╔═╡ c3dbbe99-e0d4-5dfe-bca2-b008a2e2e7e5
example = build_readout_line_hanging_qwr_mtl_example(
    readout_length_m=readout_length_m,
    resonator_length_m=resonator_length_m,
    section_length_m=section_length_m,
    readout_l_per_m_h=readout_l_per_m_h,
    readout_c_per_m_f=readout_c_per_m_f,
    resonator_l_per_m_h=resonator_l_per_m_h,
    resonator_c_per_m_f=resonator_c_per_m_f,
    window_start_readout_m=window_start_readout_m,
    window_start_resonator_m=window_start_resonator_m,
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

# ╔═╡ f1c0cab3-0945-54e8-86ec-dd0569c5b484
circuit_plan = example.plan

# ╔═╡ 0d63bc89-5809-51f9-9112-613b4608b662
engineering_graph = example.graph

# ╔═╡ ed91e532-4f0c-5b4c-8ae9-b012ad943890
compiled_circuit = example.compiled

# ╔═╡ ed05445e-32b9-563f-8558-0ab03419f337
primitive_component = (readout_line=example.readout_line, qwr=example.qwr, window=example.window)

# ╔═╡ 48866a58-6a35-569a-9ccb-860a20623e05
(
    readout_window_sections=primitive_component.window.section_range1,
    resonator_window_sections=primitive_component.window.section_range2,
    generated_c12_relations=length(primitive_component.window.capacitive_couplings),
    generated_m12_relations=length(primitive_component.window.inductive_couplings),
    qwr_head_termination=primitive_component.qwr.head_termination,
    qwr_tail_termination=primitive_component.qwr.tail_termination,
)

# ╔═╡ 6bd6bfb5-d12c-5568-a0f1-96423ec24416
(
    plan_id=circuit_plan.id,
    relation_count=length(circuit_plan.relations),
    parameter_count=length(circuit_plan.parameters),
    port_ids=sort(collect(keys(engineering_graph.ports))),
)

# ╔═╡ 00868c44-17b2-5c0b-a5c7-6bc7efe129ef
engineering_graph.relations

# ╔═╡ 9449b896-eb50-5e63-9059-23b38a8f2689
compiled_circuit.netlist

# ╔═╡ f5f3b87c-1273-5383-9d45-19705c72a0cf
compiled_circuit.component_values

# ╔═╡ 437f7cac-1c8b-563f-9437-a4914f2615d4
md"""
## HBProblemSpec And Real Solver Output

The notebook keeps the solve boundary visible. `hb_problem` is inspectable before execution, and the next cell is intentionally the explicit solver call used by all canonical Pluto notebooks.
"""

# ╔═╡ 32326c3a-ca01-5c63-9b84-22e802880b17
hb_problem = example.hb_problem

# ╔═╡ 0c2d392a-d6e5-5044-9c31-0554ba670226
(
    frequency_points=length(hb_problem.frequencies_hz),
    pump_axes=hb_problem.wp,
    sources=hb_problem.sources,
    controls=hb_problem.controls,
)

# ╔═╡ c09b35f4-1c61-5048-b5f9-e487a9ccc403
result = run_hb_problem(hb_problem)

# ╔═╡ 520668de-97b1-51ad-b157-fb353de9ed66
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

# ╔═╡ 5a4e581f-22f2-54c8-a8d2-2f0e34349281
begin
    frequencies_ghz = result.frequencies_hz ./ 1e9
    s11 = zero_mode_s(result, 1, 1)
    s21 = zero_mode_s(result, 2, 1)
    z11 = zero_mode_z(result, 1, 1)
    z21 = zero_mode_z(result, 2, 1)
end

# ╔═╡ 58ce3425-5f20-5de6-b5ce-704f2c467767
sanity = (
    point_count_matches=length(result.frequencies_hz) == point_count,
    s11_points=length(s11),
    s21_points=length(s21),
    finite_s_traces=all(isfinite, real.(s11)) && all(isfinite, imag.(s11)) && all(isfinite, real.(s21)) && all(isfinite, imag.(s21)),
    s21_notch_frequency_ghz=frequencies_ghz[argmin(db20(s21))],
)

# ╔═╡ 281ae891-b531-5d1d-80a7-e43b917e2e39
sanity

# ╔═╡ 9ce0e0f4-7283-5b11-9ea3-c12fa473410f
begin
    s_parameter_magnitude_figure(
        result.frequencies_hz,
        [
            "S11" => s11,
            "S21" => s21,
        ];
        title="Readout + Hanging QWR S-Parameter Magnitudes",
        config=figure_config,
    )
end |> wide_figure_cell

# ╔═╡ 65b22a67-fcfd-50c3-880c-260e6aa999ca
begin
    s_parameter_phase_figure(
        result.frequencies_hz,
        [
            "S11" => s11,
            "S21" => s21,
        ];
        title="Readout + Hanging QWR Phase",
        config=figure_config,
    )
end |> wide_figure_cell

# ╔═╡ fdde7f27-9497-599b-963a-f6a19dbd8baf
begin
    z_trace_figure(
        result.frequencies_hz,
        [
            "Z11" => z11,
            "Z21" => z21,
        ];
        title="Readout + Hanging QWR Z Parameters",
        config=figure_config,
    )
end |> wide_figure_cell

# ╔═╡ Cell order:
# ╠═6d014f3d-d3ca-5721-8750-ace93cb7ac27
# ╠═73f73882-c2c8-565b-a20b-19543764b269
# ╟─de8a31e4-34f6-530c-9264-f06d12b2c132
# ╟─70a08ed6-f4be-58f6-8d83-3639dc817402
# ╠═8b2bf24e-1591-5c5e-b84a-88d5de249f8e
# ╟─c63df8e5-f40f-5034-9a17-33dcccab6b1c
# ╟─c667696c-beb5-5b11-b7d8-4cadb6774d18
# ╠═21df14a8-b4ac-58da-851f-c4c5509e234a
# ╠═567fdfbc-ce0c-58fe-a0c0-884dfe084b2f
# ╠═49d7184f-ff4b-5a08-96df-5b1f54f7d5fa
# ╟─6390bc28-0f63-5ba6-8443-041dec21f5d7
# ╠═c3dbbe99-e0d4-5dfe-bca2-b008a2e2e7e5
# ╠═f1c0cab3-0945-54e8-86ec-dd0569c5b484
# ╠═0d63bc89-5809-51f9-9112-613b4608b662
# ╠═ed91e532-4f0c-5b4c-8ae9-b012ad943890
# ╠═ed05445e-32b9-563f-8558-0ab03419f337
# ╠═48866a58-6a35-569a-9ccb-860a20623e05
# ╠═6bd6bfb5-d12c-5568-a0f1-96423ec24416
# ╠═00868c44-17b2-5c0b-a5c7-6bc7efe129ef
# ╠═9449b896-eb50-5e63-9059-23b38a8f2689
# ╠═f5f3b87c-1273-5383-9d45-19705c72a0cf
# ╟─437f7cac-1c8b-563f-9437-a4914f2615d4
# ╠═32326c3a-ca01-5c63-9b84-22e802880b17
# ╠═0c2d392a-d6e5-5044-9c31-0554ba670226
# ╠═c09b35f4-1c61-5048-b5f9-e487a9ccc403
# ╠═520668de-97b1-51ad-b157-fb353de9ed66
# ╠═5a4e581f-22f2-54c8-a8d2-2f0e34349281
# ╠═58ce3425-5f20-5de6-b5ce-704f2c467767
# ╠═281ae891-b531-5d1d-80a7-e43b917e2e39
# ╠═9ce0e0f4-7283-5b11-9ea3-c12fa473410f
# ╠═65b22a67-fcfd-50c3-880c-260e6aa999ca
# ╠═fdde7f27-9497-599b-963a-f6a19dbd8baf
