### A Pluto.jl notebook ###
# v1.0.1

#> [frontmatter]
#> title = "04 Readout Line Purcell Filter"
#> tags = ["julia-core", "pluto", "readout-line", "purcell-filter", "two-port"]
#> description = "Canonical Pluto notebook for a point-capacitively coupled readout-line Purcell filter."

using Markdown
using InteractiveUtils

# ╔═╡ 4ac36288-845e-5eb6-9916-ba0782f46c52
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

# ╔═╡ 3f6f5dcf-2767-5250-bbbf-9d57313a155f
TableOfContents()

# ╔═╡ 505ff436-ca73-598f-b0c8-fa5768d19b54
md"""
# 04 Readout Line / Purcell Filter

This notebook models a half-wave Purcell filter coupled between two readout ports with lumped endpoint capacitors.

## Purpose

Show the point-coupled filter convention, inspect the filter ladder primitive, preserve explicit Core compile and HB cells, and plot real two-port `S11` / `S21` traces in magnitude figures.
"""

# ╔═╡ a308caf5-d3ea-5a84-81bc-2d934b60317e
md"""
## Owns

- Point-capacitively coupled half-wave Purcell filter.
- Readout-line two-port trace display.
- Boundary between point coupling here and finite MTL coupling in Notebook 05.
"""

# ╔═╡ e82c2c28-ddb5-5470-9561-aee5e54a9c89
LocalResource(joinpath(@__DIR__, "..", "..", "docs", "assets", "pluto-04-readout-line-purcell-filter.svg"))

# ╔═╡ bdca6df1-b8e7-5598-ba64-a58a980103f0
md"""
## LaTeX Physics

A filter modifies the electromagnetic environment seen through the readout line. In a simplified admittance view,

```math
\Gamma(\omega) = \frac{Y_0 - Y_{in}(\omega)}{Y_0 + Y_{in}(\omega)},
```

while transmission notches appear in ``S_{21}(\omega)`` near coupled resonant modes. The plotted curves below come only from the HB result.
"""

# ╔═╡ 48f8c8a4-8816-5d9d-829b-36e67d82a8ca
md"""
## Modeling Conventions

- The Purcell filter is an open-open ladder.
- Input and output coupling are localized lumped capacitors.
- Notebook 05 introduces finite distributed coupling after this point-coupled filter convention is clear.
"""

# ╔═╡ 0ac7c636-c48c-5a47-b707-25cf5d8dcaf4
begin
    input_line_length_m = 2.0e-3
    filter_length_m = 8.0e-3
    output_line_length_m = 2.0e-3
    section_length_m = 0.5e-3
    l_per_m_h = 404.313e-9
    c_per_m_f = 179.86e-12

    input_coupling_f = 2.0e-15
    output_coupling_f = 2.0e-15
    port_resistance = 50.0

    start_frequency = 2.0e9
    stop_frequency = 30.0e9
    point_count = 1000

    pump_frequency = 12.0e9
    pump_current = 0.0

    optional_hb_kwargs = Dict{Symbol,Any}(
        :nbatches => 1,
        :iterations => 120,
        :ftol => 1e-8,
    )
end

# ╔═╡ 32d227d2-bf1b-5a76-9028-6fbcc94facbe
begin
    input_line_model = RLGCSpec(
        length_m=input_line_length_m,
        section_length_m=section_length_m,
        l_per_m_h=l_per_m_h,
        c_per_m_f=c_per_m_f,
    )
    filter_model = RLGCSpec(
        length_m=filter_length_m,
        section_length_m=section_length_m,
        l_per_m_h=l_per_m_h,
        c_per_m_f=c_per_m_f,
    )
    output_line_model = RLGCSpec(
        length_m=output_line_length_m,
        section_length_m=section_length_m,
        l_per_m_h=l_per_m_h,
        c_per_m_f=c_per_m_f,
    )
end

# ╔═╡ 3e48e080-0ef9-51d7-b512-3bacdb9f77e7
(
    input_sections=input_line_model.n_sections,
    filter_sections=filter_model.n_sections,
    output_sections=output_line_model.n_sections,
    filter_actual_section_length_m=filter_model.section_length_m,
    input_coupling_fF=input_coupling_f * 1e15,
    output_coupling_fF=output_coupling_f * 1e15,
)

# ╔═╡ 3ed8cbfc-cc07-556a-a8e0-b4462336c9ad
md"""
## Primitive-Built Component And Core Authoring

The topology is three CPW ladders connected by two localized coupling capacitors. The local tutorial function below keeps the filter ladder and point-coupling relations available for inspection before the solve.
"""

# ╔═╡ b1c72e4b-e768-5e64-a6ad-bc67a14be5ad
begin
    function frequency_sweep_tutorial(start_frequency, stop_frequency, point_count)
        point_count > 0 || throw(ArgumentError("point_count must be positive."))
        point_count == 1 && return [Float64(start_frequency)]
        return range(Float64(start_frequency), Float64(stop_frequency); length=Int(point_count))
    end

    function external_two_port_tutorial!(plan; input, output, port_resistance)
        external_port!(plan; id=:input_port, index=1, endpoint=input, resistance=port_resistance, role=:signal)
        external_port!(plan; id=:output_port, index=2, endpoint=output, resistance=port_resistance, role=:readout)
        return nothing
    end

    function add_hb_intent_tutorial!(plan; ports)
        observables = Any[]
        for output_port in ports
            for source_port in ports
                push!(
                    observables,
                    SParameterRequest(
                        id=Symbol(:s, output_port, :_, source_port),
                        outputmode=(0,),
                        outputport=output_port,
                        inputmode=(0,),
                        inputport=source_port,
                    ),
                )
            end
        end

        return hb_intent!(
            plan;
            pump_axes=[
                PumpAxis(
                    id=:pump,
                    frequency_parameter=:pump_frequency,
                ),
            ],
            source_slots=[
                HBSourceSlot(
                    id=:pump_in,
                    role=:pump,
                    port=first(ports),
                    mode=(1,),
                    current_parameter=:pump_current,
                ),
            ],
            observables=observables,
            default_solver_controls=HBSolverControls(
                n_pump_harmonics=1,
                n_modulation_harmonics=1,
                returnS=true,
                returnZ=true,
                returnQE=true,
                returnCM=true,
                keyedarrays=false,
            ),
        )
    end

    function add_readout_purcell_filter_tutorial!(
        plan;
        id,
        input,
        output,
        input_line_spec::RLGCSpec,
        filter_spec::RLGCSpec,
        output_line_spec::RLGCSpec,
        input_coupling_f,
        output_coupling_f,
    )
        input_tail = external_node(string(id, "_input_tail"))
        filter_head = external_node(string(id, "_filter_head"))
        filter_tail = external_node(string(id, "_filter_tail"))
        output_head = external_node(string(id, "_output_head"))

        input_line = build_lc_ladder_line!(
            plan;
            id=string(id, "_input_line"),
            head=input,
            tail=input_tail,
            spec=input_line_spec,
            head_termination=:external,
            tail_termination=:open,
        )
        filter_line = build_lc_ladder_line!(
            plan;
            id=string(id, "_purcell_filter"),
            head=filter_head,
            tail=filter_tail,
            spec=filter_spec,
            head_termination=:open,
            tail_termination=:open,
        )
        output_line = build_lc_ladder_line!(
            plan;
            id=string(id, "_output_line"),
            head=output_head,
            tail=output,
            spec=output_line_spec,
            head_termination=:open,
            tail_termination=:external,
        )
        input_coupling = couple_capacitive!(
            plan;
            id=string(id, "_input_point_coupling"),
            from=input_tail,
            to=filter_head,
            capacitance=input_coupling_f,
            role=:purcell_filter_point_coupling,
            label=string(id, " input Cc"),
        )
        output_coupling = couple_capacitive!(
            plan;
            id=string(id, "_output_point_coupling"),
            from=filter_tail,
            to=output_head,
            capacitance=output_coupling_f,
            role=:purcell_filter_point_coupling,
            label=string(id, " output Cc"),
        )

        return (
            id=string(id),
            input_line=input_line,
            filter_line=filter_line,
            output_line=output_line,
            input_coupling=input_coupling,
            output_coupling=output_coupling,
            input_node=input,
            output_node=output,
            filter_head=filter_head,
            filter_tail=filter_tail,
        )
    end

    tutorial_circuit = let
        plan = CircuitPlan("readout-line-purcell-filter-tutorial")
        input = external_node("input")
        output = external_node("output")
        external_two_port_tutorial!(plan; input=input, output=output, port_resistance=port_resistance)
        component = add_readout_purcell_filter_tutorial!(
            plan;
            id="readout_purcell",
            input=input,
            output=output,
            input_line_spec=input_line_model,
            filter_spec=filter_model,
            output_line_spec=output_line_model,
            input_coupling_f=input_coupling_f,
            output_coupling_f=output_coupling_f,
        )
        add_hb_intent_tutorial!(plan; ports=[:input_port, :output_port])
        (plan=plan, component=component)
    end
end

# ╔═╡ 52b50448-bec0-5669-9f38-8e65f245aec6
circuit_plan = tutorial_circuit.plan

# ╔═╡ 065c255e-5328-5165-a1ea-7927ac56910a
engineering_graph = SuperconductingCircuitsCore.engineering_graph(circuit_plan)

# ╔═╡ ad4cc808-acd0-5286-adc1-9b3b28eb8693
compiled_circuit = compile_to_josephson(circuit_plan)

# ╔═╡ 53bf7ab0-2a2b-5c6d-b496-96834ccdb462
primitive_component = tutorial_circuit.component

# ╔═╡ 5f438872-bb8b-566d-be96-52de20602cdf
(
    filter_head=primitive_component.filter_line.head,
    filter_tail=primitive_component.filter_line.tail,
    head_termination=primitive_component.filter_line.head_termination,
    tail_termination=primitive_component.filter_line.tail_termination,
    section_count=length(primitive_component.filter_line.series_inductors),
    point_couplings=count(relation -> relation isa CapacitiveCoupling, circuit_plan.relations),
)

# ╔═╡ 131aa8da-7843-5987-a7a1-c511c723858f
(
    plan_id=circuit_plan.id,
    relation_count=length(circuit_plan.relations),
    parameter_count=length(circuit_plan.parameters),
    port_ids=sort(collect(keys(engineering_graph.ports))),
)

# ╔═╡ b6aa2db6-8580-5295-9040-0c8050f60b28
engineering_graph.relations

# ╔═╡ 7002a61c-27cf-52d0-a49c-bf09af78a719
compiled_circuit.netlist

# ╔═╡ b73512e6-e84f-5862-afaa-674679fc0f92
compiled_circuit.component_values

# ╔═╡ 373ab3a7-dfec-56bb-81e5-f32f79be85c4
md"""
## HBProblemSpec And Real Solver Output

The notebook keeps the solve boundary visible. `hb_problem` is inspectable before execution, and the next cell is intentionally the explicit solver call used by all canonical Pluto notebooks.
"""

# ╔═╡ 139032c1-21d4-572e-a8e5-4b05f282e83a
hb_problem = build_hb_problem(
    compiled_circuit,
    HBRunSpec(
        frequency_sweep=frequency_sweep_tutorial(start_frequency, stop_frequency, point_count),
        pump_frequencies=Dict(:pump => Float64(pump_frequency)),
        source_currents=Dict(:pump_in => Float64(pump_current)),
        optional_hb_kwargs=Dict{Symbol,Any}(optional_hb_kwargs),
    ),
)

# ╔═╡ 9ddeb728-26cf-53df-94e4-1ff5756b19b3
(
    frequency_points=length(hb_problem.frequencies_hz),
    pump_axes=hb_problem.wp,
    sources=hb_problem.sources,
    controls=hb_problem.controls,
)

# ╔═╡ 6cb8f15b-00f5-53f7-beaf-b86606e08fea
result = run_hb_problem(hb_problem)

# ╔═╡ 6d5b7788-69be-5e50-a0c1-a34bef58891a
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

# ╔═╡ 64634f93-5262-5ed8-972c-5243db7e3d60
begin
    frequencies_ghz = result.frequencies_hz ./ 1e9
    s11 = zero_mode_s(result, 1, 1)
    s21 = zero_mode_s(result, 2, 1)
    z11 = zero_mode_z(result, 1, 1)
    z21 = zero_mode_z(result, 2, 1)
end

# ╔═╡ 9104ba98-175f-5a06-a824-d8740d58658e
sanity = (
    point_count_matches=length(result.frequencies_hz) == point_count,
    s11_points=length(s11),
    s21_points=length(s21),
    finite_s_traces=all(isfinite, real.(s11)) && all(isfinite, imag.(s11)) && all(isfinite, real.(s21)) && all(isfinite, imag.(s21)),
    s21_feature_frequency_ghz=frequencies_ghz[argmin(db20(s21))],
)

# ╔═╡ e7d18aa4-5a6c-5cea-bf35-c112d073a629
sanity

# ╔═╡ dbfb7174-055e-5aff-8e4a-c4e35a1dc99a
begin
    s_parameter_db_magnitude_figure(
        result.frequencies_hz,
        [
            "S11" => s11,
            "S21" => s21,
        ];
        title="Purcell Filter S-Parameter Magnitudes",
        config=figure_config,
    )
end |> wide_figure_cell

# ╔═╡ 815908ef-18bd-534d-88e2-cb2086f54504
begin
    s_parameter_abs_magnitude_figure(
        result.frequencies_hz,
        [
            "S11" => s11,
            "S21" => s21,
        ];
        title="Purcell Filter S-Parameter Linear Magnitudes",
        config=figure_config,
    )
end |> wide_figure_cell

# ╔═╡ 64d26a74-2220-55dd-9569-f2a4f46bbfda
begin
    s_parameter_phase_figure(
        result.frequencies_hz,
        [
            "S11" => s11,
            "S21" => s21,
        ];
        title="Purcell Filter Phase",
        config=figure_config,
    )
end |> wide_figure_cell

# ╔═╡ c230a4a1-9cff-5cd0-8a5e-d63dc20b4024
begin
    z_trace_figure(
        result.frequencies_hz,
        [
            "Z11" => z11,
            "Z21" => z21,
        ];
        title="Purcell Filter Z Parameters",
        config=figure_config,
    )
end |> wide_figure_cell

# ╔═╡ Cell order:
# ╠═4ac36288-845e-5eb6-9916-ba0782f46c52
# ╠═3f6f5dcf-2767-5250-bbbf-9d57313a155f
# ╟─505ff436-ca73-598f-b0c8-fa5768d19b54
# ╟─a308caf5-d3ea-5a84-81bc-2d934b60317e
# ╠═e82c2c28-ddb5-5470-9561-aee5e54a9c89
# ╟─bdca6df1-b8e7-5598-ba64-a58a980103f0
# ╟─48f8c8a4-8816-5d9d-829b-36e67d82a8ca
# ╠═0ac7c636-c48c-5a47-b707-25cf5d8dcaf4
# ╠═32d227d2-bf1b-5a76-9028-6fbcc94facbe
# ╠═3e48e080-0ef9-51d7-b512-3bacdb9f77e7
# ╟─3ed8cbfc-cc07-556a-a8e0-b4462336c9ad
# ╠═b1c72e4b-e768-5e64-a6ad-bc67a14be5ad
# ╠═52b50448-bec0-5669-9f38-8e65f245aec6
# ╠═065c255e-5328-5165-a1ea-7927ac56910a
# ╠═ad4cc808-acd0-5286-adc1-9b3b28eb8693
# ╠═53bf7ab0-2a2b-5c6d-b496-96834ccdb462
# ╠═5f438872-bb8b-566d-be96-52de20602cdf
# ╠═131aa8da-7843-5987-a7a1-c511c723858f
# ╠═b6aa2db6-8580-5295-9040-0c8050f60b28
# ╠═7002a61c-27cf-52d0-a49c-bf09af78a719
# ╠═b73512e6-e84f-5862-afaa-674679fc0f92
# ╟─373ab3a7-dfec-56bb-81e5-f32f79be85c4
# ╠═139032c1-21d4-572e-a8e5-4b05f282e83a
# ╠═9ddeb728-26cf-53df-94e4-1ff5756b19b3
# ╠═6cb8f15b-00f5-53f7-beaf-b86606e08fea
# ╠═6d5b7788-69be-5e50-a0c1-a34bef58891a
# ╠═64634f93-5262-5ed8-972c-5243db7e3d60
# ╠═9104ba98-175f-5a06-a824-d8740d58658e
# ╠═e7d18aa4-5a6c-5cea-bf35-c112d073a629
# ╠═dbfb7174-055e-5aff-8e4a-c4e35a1dc99a
# ╠═815908ef-18bd-534d-88e2-cb2086f54504
# ╠═64d26a74-2220-55dd-9569-f2a4f46bbfda
# ╠═c230a4a1-9cff-5cd0-8a5e-d63dc20b4024
