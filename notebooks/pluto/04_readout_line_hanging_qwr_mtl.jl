### A Pluto.jl notebook ###
# v1.0.1

#> [frontmatter]
#> title = "04 Readout Line Hanging QWR MTL"
#> tags = ["julia-core", "readout", "quarter-wave-resonator", "mtl-coupling", "coupled-window"]
#> description = "Self-contained Julia Core Pluto tutorial for readout CPW plus grounded QWR using a finite MTL coupled window and real HBSolveResult plots."

using Markdown
using InteractiveUtils

# ╔═╡ 509a0ea2-c111-4e8d-9dfc-03b78b041201
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
    using .HBExampleHelpers: db20, phase_deg, zero_mode_s
end

# ╔═╡ 3eb4069a-4087-4934-a59c-94488f2b1202
md"""
# 04 Readout Line + Hanging QWR With MTL Coupling

This is the distributed coupling example:

```text
input -> readout CPW ladder -> output
              ||
              || finite MTL coupled window
              ||
        open/coupled end of QWR ladder -> shorted grounded end
```

This notebook does not use a single `Cc` to pretend there is an MTL coupling window.
"""

# ╔═╡ e08b53fb-b3ec-465d-a319-82232ccf1203
md"""
## Physics And Modeling Convention

The readout CPW and the quarter-wave resonator are both LC ladders with the same section length in the coupled region.

Quarter-wave boundary:

```text
head: open/coupled end
tail: shorted / grounded end
```

Coupling-window convention:

```text
start1 = distance from readout-line head
start2 = distance from resonator head
length = finite coupled length
```

For each coupled section, Julia Core adds `C12` between corresponding nodes and `M12` / `K` between corresponding series inductors.
"""

# ╔═╡ cff8096c-2583-48fa-99a2-789d8bc61204
begin
    readout_length_m = 6.0e-3
    resonator_length_m = 3.0e-3
    section_length_m = 0.75e-3

    readout_l_per_m_h = 4.2e-7
    readout_c_per_m_f = 1.7e-10
    resonator_l_per_m_h = 4.2e-7
    resonator_c_per_m_f = 1.7e-10

    window_start_readout_m = 2.25e-3
    window_start_resonator_m = 0.0
    window_length_m = 1.5e-3
    c12_per_m_f = 4.0e-12
    lm_per_m_h = 0.5e-7

    port_resistance = 50.0

    start_frequency = 6.0e9
    stop_frequency = 12.0e9
    point_count = 81

    pump_frequency = 14.0e9
    pump_current = 0.0

    optional_hb_kwargs = Dict{Symbol,Any}(
        :nbatches => 1,
        :iterations => 160,
        :ftol => 1e-8,
    )
end

# ╔═╡ b3d3654b-4714-42dc-b6e5-2d4b4d811205
window_model = MTLCoupledWindowSpec(
    start1_m=window_start_readout_m,
    start2_m=window_start_resonator_m,
    length_m=window_length_m,
    section_length_m=section_length_m,
    c12_per_m_f=c12_per_m_f,
    lm_per_m_h=lm_per_m_h,
    l1_per_m_h=readout_l_per_m_h,
    l2_per_m_h=resonator_l_per_m_h,
    c1g_per_m_f=readout_c_per_m_f,
    c2g_per_m_f=resonator_c_per_m_f,
)

# ╔═╡ 23e086e2-d27b-426d-9d37-9d609d411206
(
    readout_sections=TransmissionLineSpec(
        length_m=readout_length_m,
        section_length_m=section_length_m,
        l_per_m_h=readout_l_per_m_h,
        c_per_m_f=readout_c_per_m_f,
    ).n_sections,
    resonator_sections=TransmissionLineSpec(
        length_m=resonator_length_m,
        section_length_m=section_length_m,
        l_per_m_h=resonator_l_per_m_h,
        c_per_m_f=resonator_c_per_m_f,
    ).n_sections,
    coupled_sections=Int(window_model.length_m / window_model.section_length_m),
    mutual_k_per_section=window_model.lm_per_m_h / sqrt(window_model.l1_per_m_h * window_model.l2_per_m_h),
)

# ╔═╡ 94c0698a-19bd-4497-8f34-4e32bc2e1207
md"""
## Julia Core Authoring

`build_hanging_qwr_mtl_example` uses:

```julia
build_lc_ladder_line!(...)
couple_transmission_window!(...)
```

The coupled-window helper validates section alignment and records an EngineeringGraph relation of type `:coupled_window`.
"""

# ╔═╡ df9d0241-0418-48f9-abf5-54f7fb251208
example = build_hanging_qwr_mtl_example(
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

# ╔═╡ b2053a44-edfb-472c-a17e-a344a04a1209
(
    readout_window_sections=example.window.section_range1,
    resonator_window_sections=example.window.section_range2,
    generated_c12_relations=length(example.window.capacitive_couplings),
    generated_m12_relations=length(example.window.inductive_couplings),
    qwr_tail_termination=example.qwr.tail_termination,
)

# ╔═╡ 10ac4d47-6655-4d5c-ac83-cc0cad3c1210
filter(relation -> relation.relation_type == :coupled_window, example.graph.relations)

# ╔═╡ 02d7b3b0-dcfe-41cf-bf7c-95dba98f1211
md"""
## Compiled Solver Representation

The compiled netlist contains ordinary line `L`/`C` rows plus generated `C_window...` and `K_window...` rows for the MTL coupled sections.
"""

# ╔═╡ a8e8e7bd-72d8-49cb-b8e7-df3a5d0d1212
example.compiled.netlist

# ╔═╡ 47326f97-52a9-4a2d-aa2f-48fc53671213
(
    c12_rows=count(row -> startswith(row[1], "C_readout_qwr_mtl_window"), example.compiled.netlist),
    k_rows=count(row -> startswith(row[1], "K_readout_qwr_mtl_window"), example.compiled.netlist),
)

# ╔═╡ bdc03e7b-5641-448f-bd83-a40355f41214
md"""
## HBProblemSpec And Real Solver Output
"""

# ╔═╡ 1848f062-b625-4c6e-b2cc-bbb2d3101215
hb_problem = example.hb_problem

# ╔═╡ 8204b6a8-54a3-44de-b142-ed56e1bd1216
result = run_hb_problem(hb_problem)

# ╔═╡ c87dc3a0-5097-4e15-ab58-f6b36e9f1217
weaker_window_example = build_hanging_qwr_mtl_example(
    readout_length_m=readout_length_m,
    resonator_length_m=resonator_length_m,
    section_length_m=section_length_m,
    readout_l_per_m_h=readout_l_per_m_h,
    readout_c_per_m_f=readout_c_per_m_f,
    resonator_l_per_m_h=resonator_l_per_m_h,
    resonator_c_per_m_f=resonator_c_per_m_f,
    window_start_readout_m=window_start_readout_m,
    window_start_resonator_m=window_start_resonator_m,
    window_length_m=section_length_m,
    c12_per_m_f=c12_per_m_f / 2,
    lm_per_m_h=lm_per_m_h / 2,
    port_resistance=port_resistance,
    start_frequency=start_frequency,
    stop_frequency=stop_frequency,
    point_count=point_count,
    pump_frequency=pump_frequency,
    pump_current=pump_current,
    optional_hb_kwargs=optional_hb_kwargs,
)

# ╔═╡ 14fb1fa4-6c05-4919-8d25-8be5e2161218
weak_result = weaker_window_example.result

# ╔═╡ 423a6f64-c7f8-45b0-b8db-d1c7febf1219
begin
    frequencies_ghz = result.frequencies_hz ./ 1e9
    s11 = zero_mode_s(result, 1, 1)
    s21 = zero_mode_s(result, 2, 1)
    weak_s21 = zero_mode_s(weak_result, 2, 1)
end

# ╔═╡ 9f465f7c-f9a6-47c2-9962-36c2b7bf1220
(
    s21_notch_frequency_ghz=frequencies_ghz[argmin(db20(s21))],
    s21_notch_db=minimum(db20(s21)),
    weaker_window_notch_db=minimum(db20(weak_s21)),
)

# ╔═╡ dc688fe1-6c8c-49d5-91f2-f41beb621221
s_parameter_magnitude_figure(
    result.frequencies_hz,
    [
        "base MTL window S21" => s21,
        "shorter/weaker MTL window S21" => weak_s21,
    ];
    title="Readout + Hanging QWR Transmission",
    config=figure_config,
)

# ╔═╡ 612ff652-08d5-4972-b3d2-e21fb77b1222
s_parameter_magnitude_figure(
    result.frequencies_hz,
    ["S11" => s11];
    title="Readout + Hanging QWR Reflection",
    config=figure_config,
)

# ╔═╡ Cell order:
# ╠═509a0ea2-c111-4e8d-9dfc-03b78b041201
# ╟─3eb4069a-4087-4934-a59c-94488f2b1202
# ╟─e08b53fb-b3ec-465d-a319-82232ccf1203
# ╠═cff8096c-2583-48fa-99a2-789d8bc61204
# ╠═b3d3654b-4714-42dc-b6e5-2d4b4d811205
# ╠═23e086e2-d27b-426d-9d37-9d609d411206
# ╟─94c0698a-19bd-4497-8f34-4e32bc2e1207
# ╠═df9d0241-0418-48f9-abf5-54f7fb251208
# ╠═b2053a44-edfb-472c-a17e-a344a04a1209
# ╠═10ac4d47-6655-4d5c-ac83-cc0cad3c1210
# ╟─02d7b3b0-dcfe-41cf-bf7c-95dba98f1211
# ╠═a8e8e7bd-72d8-49cb-b8e7-df3a5d0d1212
# ╠═47326f97-52a9-4a2d-aa2f-48fc53671213
# ╟─bdc03e7b-5641-448f-bd83-a40355f41214
# ╠═1848f062-b625-4c6e-b2cc-bbb2d3101215
# ╠═8204b6a8-54a3-44de-b142-ed56e1bd1216
# ╠═c87dc3a0-5097-4e15-ab58-f6b36e9f1217
# ╠═14fb1fa4-6c05-4919-8d25-8be5e2161218
# ╠═423a6f64-c7f8-45b0-b8db-d1c7febf1219
# ╠═9f465f7c-f9a6-47c2-9962-36c2b7bf1220
# ╠═dc688fe1-6c8c-49d5-91f2-f41beb621221
# ╠═612ff652-08d5-4972-b3d2-e21fb77b1222
