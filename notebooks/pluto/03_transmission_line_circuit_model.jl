### A Pluto.jl notebook ###
# v1.0.1

#> [frontmatter]
#> title = "03 Transmission Line Circuit Model"
#> tags = ["julia-core", "pluto", "transmission-line", "lc-ladder", "two-port"]
#> description = "Canonical Pluto notebook for a two-port transmission line lowered to an LC ladder."

using Markdown
using InteractiveUtils

# ╔═╡ e732a416-ddff-5e11-9e02-29e983c6c1c9
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

# ╔═╡ bac37c6d-60ec-5d01-bb47-57c78c70348d
TableOfContents()

# ╔═╡ 39d52e10-b669-5036-b690-4684b3095397
md"""
# 03 Transmission Line Circuit Model

This notebook introduces the distributed line convention used by later readout and resonator examples.

## Purpose

Map an `RLGCSpec` to a Core LC ladder, inspect the primitive line object, inspect `CircuitPlan` / `EngineeringGraph` / compiled rows, run the explicit HB solve, and plot real two-port traces.
"""

# ╔═╡ 7a7b9afc-18ac-5ac0-ae2d-938d6fa095eb
md"""
## Owns

- Two-port through-line LC ladder tutorial.
- `RLGCSpec` section-count and section-value conventions.
- Combined `S11` / `S21` magnitude figure for the transmission line baseline.
"""

# ╔═╡ 8faace08-2771-58cb-9029-5878ac44d698
LocalResource(joinpath(@__DIR__, "..", "..", "docs", "assets", "pluto-03-transmission-line-circuit-model.svg"))

# ╔═╡ 7e5c3939-6d03-592a-ad2d-d945bfef789a
md"""
## LaTeX Physics

For a low-loss line,

```math
Z_0 \approx \sqrt{\frac{L'}{C'}}, \qquad v_p \approx \frac{1}{\sqrt{L'C'}}.
```

Each ladder section of length ``\Delta x`` contributes

```math
L_{\mathrm{sec}}=L'\Delta x, \qquad C_{\mathrm{sec}}=C'\Delta x.
```
"""

# ╔═╡ 18299c1a-77ac-548e-9aa1-817fca113650
md"""
## Modeling Conventions

- Head and tail are external ports.
- Core derives the actual section length from the physical length and requested reference section length.
- The notebook uses the Core line builder and does not construct a second notebook-only ladder path.
"""

# ╔═╡ 55802de0-5e03-531a-8b3a-402668b861fd
begin
    line_length_m = 4.0e-3
    section_length_m = 0.5e-3
    l_per_m_h = 404.313e-9
    c_per_m_f = 179.86e-12
    port_resistance = 50.0

    start_frequency = 1.0e9
    stop_frequency = 30.0e9
    point_count = 1000

    pump_frequency = 10.0e9
    pump_current = 0.0

    optional_hb_kwargs = Dict{Symbol,Any}(
        :nbatches => 1,
        :iterations => 120,
        :ftol => 1e-8,
    )
end

# ╔═╡ 2d017161-e4ea-5b6a-9f37-bb4350b9928d
line_model = RLGCSpec(
    length_m=line_length_m,
    section_length_m=section_length_m,
    l_per_m_h=l_per_m_h,
    c_per_m_f=c_per_m_f,
)

# ╔═╡ ebfb04be-49e5-52f0-a78f-2bd310375faf
(
    length_m=line_model.length_m,
    reference_section_length_m=line_model.reference_section_length_m,
    actual_section_length_m=line_model.section_length_m,
    n_sections=line_model.n_sections,
    l_section_h=section_values(line_model).l_h,
    c_section_f=section_values(line_model).c_f,
    phase_velocity_m_per_s=phase_velocity(line_model),
)

# ╔═╡ 181f8f11-7609-5da9-82cc-9bcd0f4585a6
md"""
## Primitive-Built Component And Core Authoring

The model starts from `RLGCSpec`, then Core expands it into series inductors and shunt capacitors with head/tail ordering preserved. The local tutorial builder below calls the ladder primitive directly so the generated node and section mapping can be inspected before solving.
"""

# ╔═╡ 77099ab5-5be5-596a-a39f-b256fe8dd84f
begin
    function frequency_sweep_tutorial(start_frequency, stop_frequency, point_count)
        point_count > 0 || throw(ArgumentError("point_count must be positive."))
        point_count == 1 && return [Float64(start_frequency)]
        return range(Float64(start_frequency), Float64(stop_frequency); length=Int(point_count))
    end

    function port_hb_intent_tutorial!(
        plan::CircuitPlan;
        ports,
        pump_frequency_parameter=:pump_frequency,
        pump_current_parameter=:pump_current,
        pump_slot=:pump_in,
        input_port=first(ports),
        n_pump_harmonics=1,
        n_modulation_harmonics=1,
    )
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
                    frequency_parameter=pump_frequency_parameter,
                ),
            ],
            source_slots=[
                HBSourceSlot(
                    id=pump_slot,
                    role=:pump,
                    port=input_port,
                    mode=(1,),
                    current_parameter=pump_current_parameter,
                ),
            ],
            observables=observables,
            default_solver_controls=HBSolverControls(
                n_pump_harmonics=n_pump_harmonics,
                n_modulation_harmonics=n_modulation_harmonics,
                returnS=true,
                returnZ=true,
                returnQE=true,
                returnCM=true,
                keyedarrays=false,
            ),
        )
    end

    function add_through_cpw_line_tutorial!(
        plan::CircuitPlan;
        id,
        input,
        output,
        spec::RLGCSpec,
    )
        return build_lc_ladder_line!(
            plan;
            id=id,
            head=input,
            tail=output,
            spec=spec,
            head_termination=:external,
            tail_termination=:external,
        )
    end

    function build_through_cpw_line_plan_tutorial(;
        id="transmission-line-circuit-model-tutorial",
        line_model,
        port_resistance,
    )
        plan = CircuitPlan(id)
        input = external_node("input")
        output = external_node("output")
        external_port!(plan; id=:input_port, index=1, endpoint=input, resistance=port_resistance, role=:signal)
        external_port!(plan; id=:output_port, index=2, endpoint=output, resistance=port_resistance, role=:readout)
        add_through_cpw_line_tutorial!(
            plan;
            id="cpw",
            input=input,
            output=output,
            spec=line_model,
        )
        port_hb_intent_tutorial!(plan; ports=[:input_port, :output_port])
        return plan
    end

    function hb_run_spec_tutorial(;
        start_frequency,
        stop_frequency,
        point_count,
        pump_frequency,
        pump_current,
        optional_hb_kwargs,
    )
        return HBRunSpec(
            frequency_sweep=frequency_sweep_tutorial(start_frequency, stop_frequency, point_count),
            pump_frequencies=Dict(:pump => Float64(pump_frequency)),
            source_currents=Dict(:pump_in => Float64(pump_current)),
            optional_hb_kwargs=Dict{Symbol,Any}(optional_hb_kwargs),
        )
    end
end

# ╔═╡ 65e97c66-6248-5a6f-bd7d-7214d096004d
circuit_plan = build_through_cpw_line_plan_tutorial(
    line_model=line_model,
    port_resistance=port_resistance,
)

# ╔═╡ e8e3e629-83fd-52b6-b957-095c315c13cf
engineering_graph = SuperconductingCircuitsCore.engineering_graph(circuit_plan)

# ╔═╡ 040be686-55ec-510b-9bdd-95c0c611d3c0
compiled_circuit = compile_to_josephson(circuit_plan)

# ╔═╡ 95fea1db-ad47-56aa-8657-eb3594f75089
primitive_component = circuit_plan.metadata[:transmission_line_ladders][:cpw]

# ╔═╡ 9e70be9c-692d-521d-a7a5-6ea07a7b6cee
(
    head=primitive_component.head,
    tail=primitive_component.tail,
    node_count=length(primitive_component.nodes),
    section_count=length(primitive_component.series_inductors),
    node_at_1mm=node_at_distance(primitive_component, 1.0e-3),
    section_at_1mm=section_index_at_distance(primitive_component, 1.0e-3),
)

# ╔═╡ 7c26a0af-6d54-5146-a6b8-59ebcc6cfa6d
(
    plan_id=circuit_plan.id,
    relation_count=length(circuit_plan.relations),
    parameter_count=length(circuit_plan.parameters),
    port_ids=sort(collect(keys(engineering_graph.ports))),
)

# ╔═╡ 69a5660b-5ee6-50b7-86b8-56ad1faf1ddc
engineering_graph.relations

# ╔═╡ 3ed6b943-848d-53e7-b740-bb96c91032c7
compiled_circuit.netlist

# ╔═╡ 049e9014-dcfe-5bbc-a445-b989736fc9c5
compiled_circuit.component_values

# ╔═╡ ee46277b-c8fa-5ce8-8afe-b35df7809e7a
md"""
## HBProblemSpec And Real Solver Output

The notebook keeps the solve boundary visible. `hb_problem` is inspectable before execution, and the next cell is intentionally the explicit solver call used by all canonical Pluto notebooks.
"""

# ╔═╡ fa9dbdea-e3f1-5193-b1d8-5e29cfbaff4a
hb_problem = build_hb_problem(
    compiled_circuit,
    hb_run_spec_tutorial(
        start_frequency=start_frequency,
        stop_frequency=stop_frequency,
        point_count=point_count,
        pump_frequency=pump_frequency,
        pump_current=pump_current,
        optional_hb_kwargs=optional_hb_kwargs,
    ),
)

# ╔═╡ 975be4b0-b8ae-5ee3-b830-bbda6eff2fb9
(
    frequency_points=length(hb_problem.frequencies_hz),
    pump_axes=hb_problem.wp,
    sources=hb_problem.sources,
    controls=hb_problem.controls,
)

# ╔═╡ 4d30da85-9cc5-5840-ab5a-8de451f8ee4e
result = run_hb_problem(hb_problem)

# ╔═╡ 3c1eb3cb-9b7a-53c1-ac5c-3d39b61f102f
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

# ╔═╡ ed27f416-19a7-57fa-b64f-7eb78632a513
begin
    frequencies_ghz = result.frequencies_hz ./ 1e9
    s11 = zero_mode_s(result, 1, 1)
    s21 = zero_mode_s(result, 2, 1)
    z11 = zero_mode_z(result, 1, 1)
    z21 = zero_mode_z(result, 2, 1)
end

# ╔═╡ e129926c-d881-52ef-9336-c045d1123498
sanity = (
    point_count_matches=length(result.frequencies_hz) == point_count,
    s11_points=length(s11),
    s21_points=length(s21),
    finite_s_traces=all(isfinite, real.(s11)) && all(isfinite, imag.(s11)) && all(isfinite, real.(s21)) && all(isfinite, imag.(s21)),
    s21_phase_delay_deg=phase_deg(s21)[end] - phase_deg(s21)[1],
)

# ╔═╡ 539e5d27-382a-5f1c-87b0-a6286f40d50e
sanity

# ╔═╡ 33f2d55a-49bf-59c9-a7a9-d36bffd1a965
begin
    s_parameter_db_magnitude_figure(
        result.frequencies_hz,
        [
            "S11" => s11,
            "S21" => s21,
        ];
        title="Transmission Line S-Parameter Magnitudes",
        config=figure_config,
    )
end |> wide_figure_cell

# ╔═╡ 8502c791-7d99-59df-9e61-fd6f08388903
begin
    s_parameter_abs_magnitude_figure(
        result.frequencies_hz,
        [
            "S11" => s11,
            "S21" => s21,
        ];
        title="Transmission Line S-Parameter Linear Magnitudes",
        config=figure_config,
    )
end |> wide_figure_cell

# ╔═╡ fdb1f785-69c3-53dd-bbcf-9354b3c88ba2
begin
    s_parameter_phase_figure(
        result.frequencies_hz,
        [
            "S11" => s11,
            "S21" => s21,
        ];
        title="Transmission Line Phase",
        config=figure_config,
    )
end |> wide_figure_cell

# ╔═╡ adeadaa6-c4cd-58b8-acd5-69bd53ae069b
begin
    z_trace_figure(
        result.frequencies_hz,
        [
            "Z11" => z11,
            "Z21" => z21,
        ];
        title="Transmission Line Z Parameters",
        config=figure_config,
    )
end |> wide_figure_cell

# ╔═╡ Cell order:
# ╠═e732a416-ddff-5e11-9e02-29e983c6c1c9
# ╠═bac37c6d-60ec-5d01-bb47-57c78c70348d
# ╟─39d52e10-b669-5036-b690-4684b3095397
# ╟─7a7b9afc-18ac-5ac0-ae2d-938d6fa095eb
# ╠═8faace08-2771-58cb-9029-5878ac44d698
# ╟─7e5c3939-6d03-592a-ad2d-d945bfef789a
# ╟─18299c1a-77ac-548e-9aa1-817fca113650
# ╠═55802de0-5e03-531a-8b3a-402668b861fd
# ╠═2d017161-e4ea-5b6a-9f37-bb4350b9928d
# ╠═ebfb04be-49e5-52f0-a78f-2bd310375faf
# ╟─181f8f11-7609-5da9-82cc-9bcd0f4585a6
# ╠═77099ab5-5be5-596a-a39f-b256fe8dd84f
# ╠═65e97c66-6248-5a6f-bd7d-7214d096004d
# ╠═e8e3e629-83fd-52b6-b957-095c315c13cf
# ╠═040be686-55ec-510b-9bdd-95c0c611d3c0
# ╠═95fea1db-ad47-56aa-8657-eb3594f75089
# ╠═9e70be9c-692d-521d-a7a5-6ea07a7b6cee
# ╠═7c26a0af-6d54-5146-a6b8-59ebcc6cfa6d
# ╠═69a5660b-5ee6-50b7-86b8-56ad1faf1ddc
# ╠═3ed6b943-848d-53e7-b740-bb96c91032c7
# ╠═049e9014-dcfe-5bbc-a445-b989736fc9c5
# ╟─ee46277b-c8fa-5ce8-8afe-b35df7809e7a
# ╠═fa9dbdea-e3f1-5193-b1d8-5e29cfbaff4a
# ╠═975be4b0-b8ae-5ee3-b830-bbda6eff2fb9
# ╠═4d30da85-9cc5-5840-ab5a-8de451f8ee4e
# ╠═3c1eb3cb-9b7a-53c1-ac5c-3d39b61f102f
# ╠═ed27f416-19a7-57fa-b64f-7eb78632a513
# ╠═e129926c-d881-52ef-9336-c045d1123498
# ╠═539e5d27-382a-5f1c-87b0-a6286f40d50e
# ╠═33f2d55a-49bf-59c9-a7a9-d36bffd1a965
# ╠═8502c791-7d99-59df-9e61-fd6f08388903
# ╠═fdb1f785-69c3-53dd-bbcf-9354b3c88ba2
# ╠═adeadaa6-c4cd-58b8-acd5-69bd53ae069b
