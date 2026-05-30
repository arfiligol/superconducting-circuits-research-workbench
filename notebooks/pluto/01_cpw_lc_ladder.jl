### A Pluto.jl notebook ###
# v1.0.1

#> [frontmatter]
#> title = "01 CPW LC Ladder"
#> tags = ["julia-core", "cpw", "transmission-line", "lc-ladder"]
#> description = "Self-contained Julia Core Pluto tutorial for CPW / transmission-line LC ladder modeling and real S/Z traces."

using Markdown
using InteractiveUtils

# ╔═╡ 1a0f5f3a-48a3-49ee-ae7a-4d9d9e55a101
begin
    import Pkg

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

    include(joinpath(@__DIR__, "includes", "hb_example_helpers.jl"))
    using .HBExampleHelpers: db20, phase_deg, zero_mode_s, zero_mode_z
end

# ╔═╡ b8cc375e-ea09-4529-8b57-df98ac14e102
md"""
# 01 CPW As An LC Ladder

This notebook models a CPW / transmission line as an ordered LC ladder:

```text
head/input -> section 1 -> section 2 -> ... -> tail/output
```

It is self-contained. For the lumped LC resonator introduction, see Notebook 00.
"""

# ╔═╡ 7011e609-68a5-4de9-a58b-f82068afe103
md"""
## Physics And Conventions Before Code

The line has a **head** endpoint and a **tail** endpoint. Section index starts at the head.

For each uniform section with length `dx`:

```text
L_section = L' * dx
C_section = C' * dx
```

Julia Core emits a series inductor between neighboring section nodes and a shunt capacitor from each section tail node to ground.

Open end: the terminal node is not connected to ground.

Short / grounded end: the terminal node is connected to ground.

This notebook uses a two-port through line, so both head and tail are external port nodes.
"""

# ╔═╡ 6756e25d-9ca5-457e-9c9e-fc0e0e605104
begin
    line_length_m = 4.0e-3
    section_length_m = 0.5e-3
    l_per_m_h = 4.2e-7
    c_per_m_f = 1.7e-10
    port_resistance = 50.0

    start_frequency = 2.0e9
    stop_frequency = 8.0e9
    point_count = 81

    pump_frequency = 10.0e9
    pump_current = 0.0

    optional_hb_kwargs = Dict{Symbol,Any}(
        :nbatches => 1,
        :iterations => 120,
        :ftol => 1e-8,
    )
end

# ╔═╡ c5a43ea3-4e3d-4c59-90c1-c2ad6a060105
line_spec = TransmissionLineSpec(
    length_m=line_length_m,
    section_length_m=section_length_m,
    l_per_m_h=l_per_m_h,
    c_per_m_f=c_per_m_f,
)

# ╔═╡ e4e684aa-3900-4a44-95e2-f5ace6d63e40
(
    length_m=line_spec.length_m,
    section_length_m=line_spec.section_length_m,
    n_sections=line_spec.n_sections,
    l_section_h=section_values(line_spec).l_h,
    c_section_f=section_values(line_spec).c_f,
    phase_velocity_m_per_s=phase_velocity(line_spec),
)

# ╔═╡ e64f422f-d4e0-4377-9622-6f8474e0c106
md"""
## Julia Core Description

The Core builder returns the `TransmissionLineLadder` so later APIs can resolve node positions and section ranges by distance from the head.
"""

# ╔═╡ f691ba87-7167-409f-82f5-5ea1c7176107
example = build_cpw_ladder_example(
    length_m=line_length_m,
    section_length_m=section_length_m,
    l_per_m_h=l_per_m_h,
    c_per_m_f=c_per_m_f,
    port_resistance=port_resistance,
    start_frequency=start_frequency,
    stop_frequency=stop_frequency,
    point_count=point_count,
    pump_frequency=pump_frequency,
    pump_current=pump_current,
    optional_hb_kwargs=optional_hb_kwargs,
)

# ╔═╡ b0f31923-bab3-40ea-8539-ebcae6eb5108
(
    head=example.line.head,
    tail=example.line.tail,
    node_count=length(example.line.nodes),
    section_count=length(example.line.series_inductors),
    node_at_1mm=node_at_distance(example.line, 1.0e-3),
    section_at_1mm=section_index_at_distance(example.line, 1.0e-3),
)

# ╔═╡ e3c78175-29f0-4c60-8d3e-cfe2f0d22109
md"""
## EngineeringGraph And Solver Representation
"""

# ╔═╡ dccf3bc7-c81b-4d3e-970d-7ec71df28c11
filter(relation -> relation.relation_type == :transmission_line_ladder, example.graph.relations)

# ╔═╡ 82e4a09f-4271-4cce-85b5-07502ed20113
example.compiled.netlist

# ╔═╡ 0628a6a0-c657-43c4-a5d1-3ff51a85e114
md"""
## HBProblemSpec And Real Solver Output
"""

# ╔═╡ 9a26d923-7564-4b81-9c9f-4fe6ca3bc115
hb_problem = example.hb_problem

# ╔═╡ 8ea65a3c-ad6e-43f5-a9bb-ff110069d116
result = run_hb_problem(hb_problem)

# ╔═╡ 2f877939-7baf-47b0-9c12-49f0e5b7c117
begin
    frequencies_ghz = result.frequencies_hz ./ 1e9
    s11 = zero_mode_s(result, 1, 1)
    s21 = zero_mode_s(result, 2, 1)
    z11 = zero_mode_z(result, 1, 1)
    z21 = zero_mode_z(result, 2, 1)
end

# ╔═╡ 42184796-1c83-4276-b302-f7813e7f5118
(
    s21_phase_start_deg=phase_deg(s21)[1],
    s21_phase_stop_deg=phase_deg(s21)[end],
    max_s11_db=maximum(db20(s11)),
    z21_samples=length(z21),
)

# ╔═╡ 18192ca9-3b02-4c54-9e30-c1e4b6dce119
s_parameter_magnitude_figure(
    result.frequencies_hz,
    [
        "S21" => s21,
        "S11" => s11,
    ];
    title="CPW Ladder S-Parameter Magnitudes",
    config=figure_config,
)

# ╔═╡ 902a5432-0bde-48ed-9eb6-f26e8c1c3119
s_parameter_phase_figure(
    result.frequencies_hz,
    [
        "S21" => s21,
        "S11" => s11,
    ];
    title="CPW Ladder Phase",
    config=figure_config,
)

# ╔═╡ e7bc5417-07fd-4f83-bbaa-ee9f9cbdf120
z_trace_figure(
    result.frequencies_hz,
    [
        "Z11" => z11,
        "Z21" => z21,
    ];
    title="CPW Ladder Z Parameters",
    config=figure_config,
)

# ╔═╡ Cell order:
# ╠═1a0f5f3a-48a3-49ee-ae7a-4d9d9e55a101
# ╟─b8cc375e-ea09-4529-8b57-df98ac14e102
# ╟─7011e609-68a5-4de9-a58b-f82068afe103
# ╠═6756e25d-9ca5-457e-9c9e-fc0e0e605104
# ╠═c5a43ea3-4e3d-4c59-90c1-c2ad6a060105
# ╠═e4e684aa-3900-4a44-95e2-f5ace6d63e40
# ╟─e64f422f-d4e0-4377-9622-6f8474e0c106
# ╠═f691ba87-7167-409f-82f5-5ea1c7176107
# ╠═b0f31923-bab3-40ea-8539-ebcae6eb5108
# ╟─e3c78175-29f0-4c60-8d3e-cfe2f0d22109
# ╠═dccf3bc7-c81b-4d3e-970d-7ec71df28c11
# ╠═82e4a09f-4271-4cce-85b5-07502ed20113
# ╟─0628a6a0-c657-43c4-a5d1-3ff51a85e114
# ╠═9a26d923-7564-4b81-9c9f-4fe6ca3bc115
# ╠═8ea65a3c-ad6e-43f5-a9bb-ff110069d116
# ╠═2f877939-7baf-47b0-9c12-49f0e5b7c117
# ╠═42184796-1c83-4276-b302-f7813e7f5118
# ╠═18192ca9-3b02-4c54-9e30-c1e4b6dce119
# ╠═902a5432-0bde-48ed-9eb6-f26e8c1c3119
# ╠═e7bc5417-07fd-4f83-bbaa-ee9f9cbdf120
