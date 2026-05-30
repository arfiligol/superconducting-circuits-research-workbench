### A Pluto.jl notebook ###
# v1.0.1

#> [frontmatter]
#> title = "02 Floating LC XY Line"
#> tags = ["julia-core", "pluto", "floating-lc", "xy-line", "three-port"]
#> description = "Floating-qubit XY-line notebook using the thesis three-node Pad1/Pad2/XY capacitance model."

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

This notebook analyzes the thesis floating-qubit XY-line circuit: two floating qubit pads and one XY environment node.

## Purpose

Show the raw Core solve first, then apply notebook-side port-matrix post-processing: probe-port termination compensation, weighted common/differential coordinate transform, and Kron reduction to the qubit differential mode.
"""

# ╔═╡ 4fcc1ac4-5803-594a-9dc9-fd654f146700
md"""
## Owns

- Three-node floating XY-line circuit: Pad1, Pad2, and XY node.
- Q3D capacitance naming for `Cg1`, `Cg2`, `Cq`, `Cxy1`, and `Cxy2`.
- PTC, weighted common/differential transform, and Kron reduction from real solver traces.
"""

# ╔═╡ a717b102-1313-5de7-8881-86aadd9c8e27
LocalResource(joinpath(@__DIR__, "..", "..", "docs", "assets", "pluto-02-floating-lc-xy-line.svg"))

# ╔═╡ 41c9c683-71bc-5d69-a94c-261efb7e464a
md"""
## LaTeX Physics

The floating qubit pads are first described in the node basis. The Q3D Maxwell off-diagonal entries become positive branch capacitances:

```math
C_{ij} = -C^{\mathrm{Maxwell}}_{ij}.
```

The XY-line problem is then read through the weighted floating coordinates

```math
\Phi_{\mathrm{cm}} = \alpha\Phi_1 + \beta\Phi_2,\qquad
\Phi_{\mathrm{dm}} = \Phi_1 - \Phi_2,
```

where

```math
\alpha = \frac{C_{g1}+C_{xy1}}{C_{g1}+C_{xy1}+C_{g2}+C_{xy2}},\qquad
\beta = 1-\alpha.
```

The differential-mode coupling and reduced qubit capacitance are

```math
C_{d,xy} = \frac{C_{g1}C_{xy2}-C_{g2}C_{xy1}}
{C_{g1}+C_{xy1}+C_{g2}+C_{xy2}},
```

```math
C_{\mathrm{eff},q}
= C_q + \frac{C_{g1}C_{g2}}{C_{g1}+C_{g2}}
+ \frac{C_{xy1}C_{xy2}}{C_{xy1}+C_{xy2}}.
```
"""

# ╔═╡ a1d16a5e-a140-555d-b58b-69e9790212ff
md"""
## Modeling Conventions

- Ports 1 and 2 are qubit-pad probe ports. Their artificial 50 ohm shunts are removed by PTC.
- Port 3 is the physical XY environment. Its 50 ohm termination remains in the reduced admittance.
- `Cxy_ground` is retained as a Q3D diagnostic value, but is not inserted as a shunt in this Core circuit to avoid double-counting the XY-line environment.
"""

# ╔═╡ 973aee0b-0062-5eb5-9411-05ade9edcecd
begin
    c_g1_f = 102.4903555082012e-15
    c_g2_f = 101.8251170216874e-15
    c_q_f = 58.12081132735904e-15
    c_xy1_f = 0.1742182638751523e-15
    c_xy2_f = 0.7451414067385129e-15
    c_xy_ground_f = 627.8043424559959e-15
    l_jun_h = 24.0e-9
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
begin
    w1_f = c_g1_f + c_xy1_f
    w2_f = c_g2_f + c_xy2_f
    alpha = w1_f / (w1_f + w2_f)
    beta = w2_f / (w1_f + w2_f)
    c_d_xy_f = (c_g1_f * c_xy2_f - c_g2_f * c_xy1_f) / (w1_f + w2_f)
    c_eff_q_f = c_q_f + (c_g1_f * c_g2_f) / (c_g1_f + c_g2_f) + (c_xy1_f * c_xy2_f) / (c_xy1_f + c_xy2_f)
    l_eff_h = l_jun_h / 2
    floating_f0_estimate = 1 / (2π * sqrt(l_eff_h * c_eff_q_f))
end

# ╔═╡ ee2e6985-d950-5e3c-8811-0f33591160d3
q3d_source = "sandbox/thesis_pf6fq_external_coupling_analysis/raw/Q0/Q0_XY_Q3D_C_Matrix.m"

# ╔═╡ 5e47b9f1-5e14-5ce2-8538-0a8f3ee57584
(
    q3d_source=q3d_source,
    c_g1_fF=c_g1_f * 1e15,
    c_g2_fF=c_g2_f * 1e15,
    c_q_fF=c_q_f * 1e15,
    c_xy1_fF=c_xy1_f * 1e15,
    c_xy2_fF=c_xy2_f * 1e15,
    c_xy_ground_diagnostic_fF=c_xy_ground_f * 1e15,
    alpha=alpha,
    beta=beta,
    c_d_xy_fF=c_d_xy_f * 1e15,
    c_eff_q_fF=c_eff_q_f * 1e15,
    floating_f0_estimate_ghz=floating_f0_estimate / 1e9,
)

# ╔═╡ e2a3b4ae-5787-5fe0-8c43-66f6f79c81a7
md"""
## Primitive-Built Component And Core Authoring

The component is the thesis reduced circuit: two qubit pads, one XY node, five capacitance branches, and two equal inductive branches between the pads. The local tutorial builder below creates those primitive relations directly and leaves the compile and solve boundaries visible.
"""

# ╔═╡ 3cfd3e81-07d6-5bdd-82f9-f5e1a8425a0a
begin
    function frequency_sweep_tutorial(start_frequency, stop_frequency, point_count)
        point_count > 0 || throw(ArgumentError("point_count must be positive."))
        point_count == 1 && return [Float64(start_frequency)]
        return range(Float64(start_frequency), Float64(stop_frequency); length=Int(point_count))
    end

    function relation_by_id_tutorial(plan::CircuitPlan, id)
        matches = filter(relation -> hasproperty(relation, :id) && relation.id == string(id), plan.relations)
        length(matches) == 1 || throw(ArgumentError("expected exactly one relation with id $(id), found $(length(matches))."))
        return only(matches)
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

    function add_floating_lc_xy_tutorial!(
        plan::CircuitPlan;
        pad1,
        pad2,
        xy_node,
        c_g1_f,
        c_g2_f,
        c_q_f,
        c_xy1_f,
        c_xy2_f,
        l_jun_h,
    )
        c_g1 = shunt_capacitor!(
            plan;
            id="floating_xy_c_g1",
            at=pad1,
            capacitance=c_g1_f,
            role=:floating_xy_pad_ground_capacitance,
            label="floating XY Cg1",
        )
        c_g2 = shunt_capacitor!(
            plan;
            id="floating_xy_c_g2",
            at=pad2,
            capacitance=c_g2_f,
            role=:floating_xy_pad_ground_capacitance,
            label="floating XY Cg2",
        )
        c_q = couple_capacitive!(
            plan;
            id="floating_xy_c_q",
            from=pad1,
            to=pad2,
            capacitance=c_q_f,
            role=:floating_xy_qubit_capacitance,
            label="floating XY Cq",
        )
        c_xy1 = couple_capacitive!(
            plan;
            id="floating_xy_c_xy1",
            from=pad1,
            to=xy_node,
            capacitance=c_xy1_f,
            role=:floating_xy_line_coupling,
            label="floating XY Cxy1",
        )
        c_xy2 = couple_capacitive!(
            plan;
            id="floating_xy_c_xy2",
            from=pad2,
            to=xy_node,
            capacitance=c_xy2_f,
            role=:floating_xy_line_coupling,
            label="floating XY Cxy2",
        )
        l_q1 = series_inductor!(
            plan;
            id="floating_xy_l_q1",
            from=pad1,
            to=pad2,
            inductance=l_jun_h,
            role=:floating_xy_qubit_inductance,
            label="floating XY Lq1",
        )
        l_q2 = series_inductor!(
            plan;
            id="floating_xy_l_q2",
            from=pad1,
            to=pad2,
            inductance=l_jun_h,
            role=:floating_xy_qubit_inductance,
            label="floating XY Lq2",
        )
        return (
            c_g1=c_g1,
            c_g2=c_g2,
            c_q=c_q,
            c_xy1=c_xy1,
            c_xy2=c_xy2,
            l_q1=l_q1,
            l_q2=l_q2,
        )
    end

    function build_floating_lc_xy_plan_tutorial(;
        id="floating-lc-xy-line-tutorial",
        c_g1_f,
        c_g2_f,
        c_q_f,
        c_xy1_f,
        c_xy2_f,
        c_xy_ground_f,
        l_jun_h,
        port_resistance,
    )
        values = Float64.((c_g1_f, c_g2_f, c_q_f, c_xy1_f, c_xy2_f, l_jun_h))
        all(value -> value > 0, values) ||
            throw(ArgumentError("floating XY capacitances and l_jun_h must be positive."))
        Float64(c_xy_ground_f) >= 0 ||
            throw(ArgumentError("c_xy_ground_f must be non-negative."))

        plan = CircuitPlan(id)
        pad1 = external_node("pad1")
        pad2 = external_node("pad2")
        xy_node = external_node("xy_node")
        external_port!(plan; id=:pad1_port, index=1, endpoint=pad1, resistance=port_resistance, role=:probe)
        external_port!(plan; id=:pad2_port, index=2, endpoint=pad2, resistance=port_resistance, role=:probe)
        external_port!(plan; id=:xy_port, index=3, endpoint=xy_node, resistance=port_resistance, role=:xy_line)
        add_floating_lc_xy_tutorial!(
            plan;
            pad1=pad1,
            pad2=pad2,
            xy_node=xy_node,
            c_g1_f=Float64(c_g1_f),
            c_g2_f=Float64(c_g2_f),
            c_q_f=Float64(c_q_f),
            c_xy1_f=Float64(c_xy1_f),
            c_xy2_f=Float64(c_xy2_f),
            l_jun_h=Float64(l_jun_h),
        )
        port_hb_intent_tutorial!(plan; ports=[:pad1_port, :pad2_port, :xy_port])
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

# ╔═╡ d949456d-2760-5e42-92ee-e412c83587c5
circuit_plan = build_floating_lc_xy_plan_tutorial(
    c_g1_f=c_g1_f,
    c_g2_f=c_g2_f,
    c_q_f=c_q_f,
    c_xy1_f=c_xy1_f,
    c_xy2_f=c_xy2_f,
    c_xy_ground_f=c_xy_ground_f,
    l_jun_h=l_jun_h,
    port_resistance=port_resistance,
)

# ╔═╡ 613e431b-dcce-58a9-9df7-ff763690c4e9
engineering_graph = SuperconductingCircuitsCore.engineering_graph(circuit_plan)

# ╔═╡ be11e7b0-7f07-5e18-be95-dac21d35fbc4
compiled_circuit = compile_to_josephson(circuit_plan)

# ╔═╡ 1a3a9e91-9ed4-5204-be6d-9a7d583b36b2
primitive_component = (
    pad1=external_node("pad1"),
    pad2=external_node("pad2"),
    xy_node=external_node("xy_node"),
    c_g1=relation_by_id_tutorial(circuit_plan, "floating_xy_c_g1"),
    c_g2=relation_by_id_tutorial(circuit_plan, "floating_xy_c_g2"),
    c_q=relation_by_id_tutorial(circuit_plan, "floating_xy_c_q"),
    c_xy1=relation_by_id_tutorial(circuit_plan, "floating_xy_c_xy1"),
    c_xy2=relation_by_id_tutorial(circuit_plan, "floating_xy_c_xy2"),
    l_q1=relation_by_id_tutorial(circuit_plan, "floating_xy_l_q1"),
    l_q2=relation_by_id_tutorial(circuit_plan, "floating_xy_l_q2"),
    capacitance_summary=(
        c_g1_f=c_g1_f,
        c_g2_f=c_g2_f,
        c_q_f=c_q_f,
        c_xy1_f=c_xy1_f,
        c_xy2_f=c_xy2_f,
        c_xy_ground_f=c_xy_ground_f,
        w1_f=w1_f,
        w2_f=w2_f,
        alpha=alpha,
        beta=beta,
        c_d_xy_f=c_d_xy_f,
        c_eff_q_f=c_eff_q_f,
        l_jun_h=l_jun_h,
        l_eff_h=l_eff_h,
        f0_estimate_hz=floating_f0_estimate,
    ),
)

# ╔═╡ 45567dac-133c-5806-86f7-d5d358ee8014
primitive_component

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

# ╔═╡ 45eb022b-7573-43e0-aa80-9d67c07b38d7
md"""
## Port-Matrix Post-Processing

The raw solve includes the artificial probe-port terminations. Probe termination compensation removes the 50 ohm shunts from the qubit pads while leaving the physical XY environment termination in place:

```math
Y^{\mathrm{PTC}}_{ii}(\omega) = Y^{\mathrm{raw}}_{ii}(\omega) - \frac{1}{Z_0}, \qquad i\in\{1,2\}.
```
"""

# ╔═╡ 509d9cdb-690b-4120-a724-a790bdb80824
md"""
The floating pad variables are then rewritten into weighted common and differential coordinates:

```math
\Phi_{\mathrm{cm}} = \alpha\Phi_1 + \beta\Phi_2,\qquad
\Phi_{\mathrm{dm}} = \Phi_1 - \Phi_2.
```

For the Q0 capacitance data,

```math
\alpha = \frac{C_{g1}+C_{xy1}}{(C_{g1}+C_{xy1})+(C_{g2}+C_{xy2})},\qquad
\beta = \frac{C_{g2}+C_{xy2}}{(C_{g1}+C_{xy1})+(C_{g2}+C_{xy2})}.
```
"""

# ╔═╡ f0cfb74f-aa04-49b1-bb09-606ac3de6d76
md"""
Kron reduction keeps the qubit differential mode and eliminates the common and XY coordinates:

```math
Y_{\mathrm{eff}} = Y_{aa} - Y_{ab}Y_{bb}^{-1}Y_{ba}.
```

Here `a` is the kept differential coordinate, and `b` contains the eliminated modes.
"""

# ╔═╡ f939dd9a-40ae-50bc-bf81-380299e6eb7c
begin
    frequencies_ghz = result.frequencies_hz ./ 1e9
    raw_y_stack = zero_mode_y_matrix_stack(result; ports=[1, 2, 3])
end

# ╔═╡ 2eeaf4f8-e51f-4c55-841d-5d97f7a3a1db
begin
    deembedded_y_stack = apply_port_termination_compensation(
        raw_y_stack;
        resistance_ohm_by_port=Dict(1 => port_resistance, 2 => port_resistance),
    )
    common_differential_matrix = common_differential_transform(3, 1, 2; alpha=alpha, beta=beta)
    cd_y_stack = apply_coordinate_transform(
        deembedded_y_stack,
        common_differential_matrix;
        labels=["common", "differential", "xy"],
    )
    differential_y_stack = kron_reduce(cd_y_stack; keep_indices=[2])
    y_eff_trace = vec(differential_y_stack.values[1, 1, :])
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
    y_eff_points=length(y_eff_trace),
    finite_y_eff=all(isfinite, real.(y_eff_trace)) && all(isfinite, imag.(y_eff_trace)),
    floating_resonance_in_span=start_frequency <= floating_f0_estimate <= stop_frequency,
)

# ╔═╡ 3bf216fd-6f55-5344-98c6-213167ab49c5
sanity

# ╔═╡ ec574764-5b0d-5d25-bd69-3c505aea2b22
begin
    y_trace_figure(
        result.frequencies_hz,
        ["Yeff" => y_eff_trace];
        title="Floating XY Reduced Differential Admittance",
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
# ╟─45eb022b-7573-43e0-aa80-9d67c07b38d7
# ╟─509d9cdb-690b-4120-a724-a790bdb80824
# ╟─f0cfb74f-aa04-49b1-bb09-606ac3de6d76
# ╠═f939dd9a-40ae-50bc-bf81-380299e6eb7c
# ╠═2eeaf4f8-e51f-4c55-841d-5d97f7a3a1db
# ╠═6b15f9b2-5654-48e4-a563-1c15b2f01667
# ╠═16f1deb4-ec16-50f9-86d5-24d581dbda5d
# ╠═3bf216fd-6f55-5344-98c6-213167ab49c5
# ╠═ec574764-5b0d-5d25-bd69-3c505aea2b22
