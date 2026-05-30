### A Pluto.jl notebook ###
# v1.0.1

#> [frontmatter]
#> title = "02 Floating LC XY Line"
#> tags = ["julia-core", "pluto", "floating-lc", "xy-line", "two-port"]
#> description = "Canonical Pluto notebook structure for a floating LC mode coupled to an XY drive line."

using Markdown
using InteractiveUtils

# ╔═╡ 13020cc8-835e-5327-bf86-eb7c01e50f19
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

    include(joinpath(@__DIR__, "includes", "port_matrix_post_processing.jl"))
    using .PortMatrixPostProcessing:
        zero_mode_y_matrix_stack,
        apply_port_termination_compensation,
        common_differential_transform,
        apply_coordinate_transform,
        kron_reduce
end

# ╔═╡ 0c729fcd-821b-5f2b-89d3-f2f3b9cc2fc7
TableOfContents()

# ╔═╡ 86c983ea-44c9-5ad5-8415-abd2f1626613
md"""
# 02 Floating LC / XY Line

This notebook analyzes a floating LC mode capacitively coupled to an XY drive line terminated by 50 ohm ports.

## Purpose

Show the raw Core solve first, then apply notebook-side port-matrix post-processing: port termination compensation, common/differential coordinate transform, and Kron reduction.
"""

# ╔═╡ 4fcc1ac4-5803-594a-9dc9-fd654f146700
md"""
## Owns

- Two-port XY line with a side-coupled floating LC mode.
- Floating-mode parameter naming and trace display conventions.
- Combined `S11` / `S21` magnitude figure for two-port notebooks.
- Raw S/Z/Y post-processing from real solver traces.
"""

# ╔═╡ a717b102-1313-5de7-8881-86aadd9c8e27
LocalResource(joinpath(@__DIR__, "..", "..", "docs", "assets", "pluto-02-floating-lc-xy-line.svg"))

# ╔═╡ 41c9c683-71bc-5d69-a94c-261efb7e464a
md"""
## LaTeX Physics

The floating mode is represented by an effective capacitance and inductance,

$$
\omega_f = \frac{1}{\sqrt{L_f C_f}}.
$$

A small capacitive tap to the XY line loads the through-line response. The observable teaching question is how the side-coupled mode changes both reflection and transmission:

$$
S_{11}(\omega), \quad S_{21}(\omega).
$$
"""

# ╔═╡ a1d16a5e-a140-555d-b58b-69e9790212ff
md"""
## Modeling Conventions

- The XY line is a two-port distributed or ladder primitive owned by Core.
- The LC mode is floating, so its node ownership must not be collapsed to ground in the notebook.
- Coupling capacitance is a real primitive relation, not an analytic notch overlay.
"""

# ╔═╡ 973aee0b-0062-5eb5-9411-05ade9edcecd
begin
    line_length_m = 4.0e-3
    coupling_separation_m = 0.5e-3
    coupling_center_m = line_length_m / 2
    section_length_m = 0.5e-3
    l_per_m_h = 4.2e-7
    c_per_m_f = 1.7e-10

    resonator_capacitance = 75.0e-15
    resonator_inductance = 8.0e-9
    coupling_capacitance = 3.0e-15
    port_resistance = 50.0

    start_frequency = 2.0e9
    stop_frequency = 12.0e9
    point_count = 1000

    pump_frequency = 10.0e9
    pump_current = 0.0

    optional_hb_kwargs = Dict{Symbol,Any}(
        :nbatches => 1,
        :iterations => 140,
        :ftol => 1e-8,
    )
end

# ╔═╡ ba9caf28-78c2-5d90-97e0-ffb13ab2779c
floating_f0_estimate = 1 / (2π * sqrt(resonator_inductance * resonator_capacitance))

# ╔═╡ ee2e6985-d950-5e3c-8811-0f33591160d3
xy_line_model = RLGCSpec(
    length_m=line_length_m,
    section_length_m=section_length_m,
    l_per_m_h=l_per_m_h,
    c_per_m_f=c_per_m_f,
)

# ╔═╡ 5e47b9f1-5e14-5ce2-8538-0a8f3ee57584
(
    xy_line_sections=xy_line_model.n_sections,
    xy_line_phase_velocity_m_per_s=phase_velocity(xy_line_model),
    floating_f0_estimate_ghz=floating_f0_estimate / 1e9,
    coupling_fF=coupling_capacitance * 1e15,
)

# ╔═╡ e2a3b4ae-5787-5fe0-8c43-66f6f79c81a7
md"""
## Primitive-Built Component And Core Authoring

The component combines one RLGC line with a floating LC branch and two point coupling capacitors. The library-equivalent builder below keeps the primitive relations inspectable and leaves the solve boundary visible.
"""

# ╔═╡ 3cfd3e81-07d6-5bdd-82f9-f5e1a8425a0a
floating_lc_xy_core_builder = build_floating_lc_xy_line_example

# ╔═╡ d949456d-2760-5e42-92ee-e412c83587c5
example = floating_lc_xy_core_builder(
    line_length_m=line_length_m,
    coupling_separation_m=coupling_separation_m,
    coupling_center_m=coupling_center_m,
    section_length_m=section_length_m,
    l_per_m_h=l_per_m_h,
    c_per_m_f=c_per_m_f,
    resonator_capacitance=resonator_capacitance,
    resonator_inductance=resonator_inductance,
    coupling_capacitance=coupling_capacitance,
    port_resistance=port_resistance,
    start_frequency=start_frequency,
    stop_frequency=stop_frequency,
    point_count=point_count,
    pump_frequency=pump_frequency,
    pump_current=pump_current,
    optional_hb_kwargs=optional_hb_kwargs,
)

# ╔═╡ 613e431b-dcce-58a9-9df7-ff763690c4e9
circuit_plan = example.plan

# ╔═╡ be11e7b0-7f07-5e18-be95-dac21d35fbc4
engineering_graph = example.graph

# ╔═╡ 1a3a9e91-9ed4-5204-be6d-9a7d583b36b2
compiled_circuit = example.compiled

# ╔═╡ 45567dac-133c-5806-86f7-d5d358ee8014
primitive_component = (
    xy_line=example.line,
    resonator_capacitance=example.resonator_cap,
    resonator_inductance=example.resonator_ind,
    left_coupling=example.left_coupling,
    right_coupling=example.right_coupling,
)

# ╔═╡ 532f1460-c5ec-572c-94d6-220d68080b12
primitive_component

# ╔═╡ 52211667-cba2-51a5-a91d-510c08c68d6b
(
    plan_id=circuit_plan.id,
    relation_count=length(circuit_plan.relations),
    parameter_count=length(circuit_plan.parameters),
    port_ids=sort(collect(keys(engineering_graph.ports))),
)

# ╔═╡ 6bf122af-f7e1-5441-9d16-cb267b1a3c57
engineering_graph.relations

# ╔═╡ df4fe8a5-1feb-5ee7-9331-0ba21c34d75f
compiled_circuit.netlist

# ╔═╡ eea4693e-20fd-5d4a-89b4-5145be849477
compiled_circuit.component_values

# ╔═╡ 85c6f40e-978c-5ad1-b941-8d58b5255f31
md"""
## HBProblemSpec And Real Solver Output

The notebook keeps the solve boundary visible. `hb_problem` is inspectable before execution, and the next cell is intentionally the explicit solver call used by all canonical Pluto notebooks.
"""

# ╔═╡ 113902e3-ec9d-5436-9479-74d8b3cbc9ec
hb_problem = example.hb_problem

# ╔═╡ e071498e-12ed-5289-9665-99b5f358bf90
(
    frequency_points=length(hb_problem.frequencies_hz),
    pump_axes=hb_problem.wp,
    sources=hb_problem.sources,
    controls=hb_problem.controls,
)

# ╔═╡ ca45a85a-381e-5ae7-8d0c-5701ff588414
result = run_hb_problem(hb_problem)

# ╔═╡ 3b925f5b-b9f8-5ae6-828c-a05c4559fb12
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

# ╔═╡ f939dd9a-40ae-50bc-bf81-380299e6eb7c
begin
    frequencies_ghz = result.frequencies_hz ./ 1e9
    s11 = zero_mode_s(result, 1, 1)
    s21 = zero_mode_s(result, 2, 1)
    z11 = zero_mode_z(result, 1, 1)
    z21 = zero_mode_z(result, 2, 1)
end

# ╔═╡ 2eeaf4f8-e51f-4c55-841d-5d97f7a3a1db
begin
    raw_y_stack = zero_mode_y_matrix_stack(result; ports=[1, 2])
    deembedded_y_stack = apply_port_termination_compensation(
        raw_y_stack;
        resistance_ohm_by_port=Dict(1 => port_resistance, 2 => port_resistance),
    )
    common_differential_matrix = common_differential_transform(2, 1, 2)
    cd_y_stack = apply_coordinate_transform(
        deembedded_y_stack,
        common_differential_matrix;
        labels=["common", "differential"],
    )
    differential_y_stack = kron_reduce(cd_y_stack; keep_indices=[2])
    differential_y_trace = vec(differential_y_stack.values[1, 1, :])
end

# ╔═╡ 6b15f9b2-5654-48e4-a563-1c15b2f01667
(
    raw_y_source=raw_y_stack.source_kind,
    transformed_labels=cd_y_stack.labels,
    kron_reduced_labels=differential_y_stack.labels,
)

# ╔═╡ 16f1deb4-ec16-50f9-86d5-24d581dbda5d
sanity = (
    point_count_matches=length(result.frequencies_hz) == point_count,
    s11_points=length(s11),
    s21_points=length(s21),
    finite_s_traces=all(isfinite, real.(s11)) && all(isfinite, imag.(s11)) && all(isfinite, real.(s21)) && all(isfinite, imag.(s21)),
    floating_resonance_in_span=start_frequency <= floating_f0_estimate <= stop_frequency,
)

# ╔═╡ 3bf216fd-6f55-5344-98c6-213167ab49c5
sanity

# ╔═╡ ec574764-5b0d-5d25-bd69-3c505aea2b22
begin
    s_parameter_magnitude_figure(
        result.frequencies_hz,
        [
            "S11" => s11,
            "S21" => s21,
        ];
        title="Floating LC XY Line S-Parameter Magnitudes",
        config=figure_config,
    )
end |> wide_figure_cell

# ╔═╡ e802f724-8d53-5ce7-8856-5ec050ae5862
begin
    s_parameter_phase_figure(
        result.frequencies_hz,
        [
            "S11" => s11,
            "S21" => s21,
        ];
        title="Floating LC XY Line Phase",
        config=figure_config,
    )
end |> wide_figure_cell

# ╔═╡ 19344f88-8dee-50eb-90ab-c80f72cbae54
begin
    z_trace_figure(
        result.frequencies_hz,
        [
            "Z11" => z11,
            "Z21" => z21,
        ];
        title="Floating LC XY Line Z Parameters",
        config=figure_config,
    )
end |> wide_figure_cell

# ╔═╡ e1dbd97c-63d7-4ddb-8644-5f076703c7a2
begin
    y_trace_figure(
        result.frequencies_hz,
        ["differential Y" => differential_y_trace];
        title="Floating LC Differential Admittance After PTC / Transform / Kron",
        config=figure_config,
    )
end |> wide_figure_cell

# ╔═╡ Cell order:
# ╠═13020cc8-835e-5327-bf86-eb7c01e50f19
# ╠═0c729fcd-821b-5f2b-89d3-f2f3b9cc2fc7
# ╟─86c983ea-44c9-5ad5-8415-abd2f1626613
# ╟─4fcc1ac4-5803-594a-9dc9-fd654f146700
# ╠═a717b102-1313-5de7-8881-86aadd9c8e27
# ╟─41c9c683-71bc-5d69-a94c-261efb7e464a
# ╟─a1d16a5e-a140-555d-b58b-69e9790212ff
# ╠═973aee0b-0062-5eb5-9411-05ade9edcecd
# ╠═ba9caf28-78c2-5d90-97e0-ffb13ab2779c
# ╠═ee2e6985-d950-5e3c-8811-0f33591160d3
# ╠═5e47b9f1-5e14-5ce2-8538-0a8f3ee57584
# ╟─e2a3b4ae-5787-5fe0-8c43-66f6f79c81a7
# ╠═3cfd3e81-07d6-5bdd-82f9-f5e1a8425a0a
# ╠═d949456d-2760-5e42-92ee-e412c83587c5
# ╠═613e431b-dcce-58a9-9df7-ff763690c4e9
# ╠═be11e7b0-7f07-5e18-be95-dac21d35fbc4
# ╠═1a3a9e91-9ed4-5204-be6d-9a7d583b36b2
# ╠═45567dac-133c-5806-86f7-d5d358ee8014
# ╠═532f1460-c5ec-572c-94d6-220d68080b12
# ╠═52211667-cba2-51a5-a91d-510c08c68d6b
# ╠═6bf122af-f7e1-5441-9d16-cb267b1a3c57
# ╠═df4fe8a5-1feb-5ee7-9331-0ba21c34d75f
# ╠═eea4693e-20fd-5d4a-89b4-5145be849477
# ╟─85c6f40e-978c-5ad1-b941-8d58b5255f31
# ╠═113902e3-ec9d-5436-9479-74d8b3cbc9ec
# ╠═e071498e-12ed-5289-9665-99b5f358bf90
# ╠═ca45a85a-381e-5ae7-8d0c-5701ff588414
# ╠═3b925f5b-b9f8-5ae6-828c-a05c4559fb12
# ╠═f939dd9a-40ae-50bc-bf81-380299e6eb7c
# ╠═2eeaf4f8-e51f-4c55-841d-5d97f7a3a1db
# ╠═6b15f9b2-5654-48e4-a563-1c15b2f01667
# ╠═16f1deb4-ec16-50f9-86d5-24d581dbda5d
# ╠═3bf216fd-6f55-5344-98c6-213167ab49c5
# ╠═ec574764-5b0d-5d25-bd69-3c505aea2b22
# ╠═e802f724-8d53-5ce7-8856-5ec050ae5862
# ╠═19344f88-8dee-50eb-90ab-c80f72cbae54
# ╠═e1dbd97c-63d7-4ddb-8644-5f076703c7a2
