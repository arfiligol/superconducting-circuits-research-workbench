### A Pluto.jl notebook ###
# v1.0.1

#> [frontmatter]
#> title = "02 Floating LC XY Line"
#> tags = ["julia-core", "pluto", "hb", "floating-lc", "post-processing"]
#> description = "Macro DSL tutorial for a floating LC coupled to an XY node with explicit matrix post-processing."

using Markdown
using InteractiveUtils

# ╔═╡ d4c2e4d2-0702-5c47-9ad1-9e96d27575d2
begin
    import Pkg
    Pkg.activate(joinpath(first(DEPOT_PATH), "environments", "v1.12"); io=devnull)

    using LinearAlgebra
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
    include(joinpath(@__DIR__, "includes", "port_matrix_post_processing.jl"))
    using .HBExampleHelpers: zero_mode_z
    using .PortMatrixPostProcessing: zero_mode_y_matrix_stack,
        compiled_port_shunt_evidence,
        apply_port_termination_compensation,
        common_differential_transform,
        apply_coordinate_transform,
        kron_reduce
end

# ╔═╡ f68a000d-9f5b-5760-9156-34d44e8790cc
TableOfContents()

# ╔═╡ 925798a9-8155-52d2-b5d1-389df52b1eb1
md"""
# 02 Floating LC Coupled To XY Node

This notebook models a floating LC resonator with two islands and one XY environment node. The circuit has three physical ports: Pad1, Pad2, and XY.

Reusable harmonic-balance theory and periodic-steady-state evidence gates are canonical in [Harmonic Balance: Periodic Steady State and Mode Semantics](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/numerical-methods/harmonic-balance-periodic-steady-state.qmd); this notebook owns only the circuit-specific executable workflow and evidence.
"""

# ╔═╡ 76da6a39-f791-5aac-948e-deaf925a2b7d
md"""
## Owns

- Three-node floating LC plus XY coupling capacitances.
- Explicit probe-port loading and visible post-processing.
- PTC, weighted common/differential transform, and Kron reduction from real solver output.

Canonical semantics:

- [Network Trace Views](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/network-trace-views.qmd)
- [Port Reference Impedance](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/simulation/port-reference-impedance-semantics.qmd)
- [Port-Termination Compensation](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/simulation/port-termination-compensation.qmd)
- [Admittance Coordinate Transforms](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/admittance-coordinate-transforms.qmd)
- [Schur Complement and Kron Reduction](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/numerical-methods/schur-complement-kron-reduction.qmd)

Implementation boundary: the two resonator branches below are ordinary `series_inductor!` relations. This notebook contains no `JosephsonJunction` or SQUID model; `compile_to_josephson` names the target compiler, not the branch physics.
"""

# ╔═╡ 8d7c8662-893f-5808-8b36-c33c37ab49b9
LocalResource(joinpath(@__DIR__, "..", "..", "docs", "assets", "circuit_draw", "pluto_examples", "floating_lc_xy_line", "diagram.light.svg"))

# ╔═╡ 7caa12c4-973b-50a0-a872-d378f92808f5
md"""
## Physics

The floating mode is not the same as either island voltage alone. The useful qubit coordinate is a differential coordinate after accounting for unequal capacitance weights.

The raw circuit contains two island nodes and one XY node. The post-processing below transforms the solver's raw port matrix; it does not change circuit topology.
"""

# ╔═╡ e7dc2fd9-d595-5d38-8371-9cef9d32bbdb
begin
    c_g1_f = 102.4903555082012e-15
    c_g2_f = 101.8251170216874e-15
    c_q_f = 58.12081132735904e-15
    c_xy1_f = 0.1742182638751523e-15
    c_xy2_f = 0.7451414067385129e-15
    c_xy_ground_f = 627.8043424559959e-15
    l_branch_h = 24.0e-9
    port_resistance = 50.0

    start_frequency = 2.0e9
    stop_frequency = 12.0e9
    point_count = 1000

    pump_frequency = 12.0e9
    pump_current = 0.0

    optional_hb_kwargs = Dict{Symbol,Any}(
        :nbatches => 1,
        :iterations => 120,
        :ftol => 1e-8,
    )
end

# ╔═╡ 30456352-a3c6-5a50-9be7-0f7f7492b340
begin
    w1_f = c_g1_f + c_xy1_f
    w2_f = c_g2_f + c_xy2_f
    alpha = w1_f / (w1_f + w2_f)
    beta = w2_f / (w1_f + w2_f)
    c_d_xy_f = (c_g1_f * c_xy2_f - c_g2_f * c_xy1_f) / (w1_f + w2_f)
    c_eff_q_f = c_q_f + (c_g1_f * c_g2_f) / (c_g1_f + c_g2_f) + (c_xy1_f * c_xy2_f) / (c_xy1_f + c_xy2_f)
    l_eff_h = l_branch_h / 2
    f0_estimate = 1 / (2π * sqrt(l_eff_h * c_eff_q_f))
end

# ╔═╡ 2178e3b2-7e54-5d3c-b302-3bdc8b9c96ed
parameter_table = [
    (name="Cg1", value=c_g1_f, unit="F", meaning="Pad1 to ground"),
    (name="Cg2", value=c_g2_f, unit="F", meaning="Pad2 to ground"),
    (name="Cq", value=c_q_f, unit="F", meaning="Pad1 to Pad2"),
    (name="Cxy1", value=c_xy1_f, unit="F", meaning="Pad1 to XY node"),
    (name="Cxy2", value=c_xy2_f, unit="F", meaning="Pad2 to XY node"),
    (name="Cxy_ground", value=c_xy_ground_f, unit="F", meaning="diagnostic only; not inserted as a shunt"),
    (name="Lbranch", value=l_branch_h, unit="H", meaning="each parallel linear-inductor branch"),
]

# ╔═╡ b5d445b9-fb30-583a-9701-6159eefd565b
md"""
## Reusable Component

The component exposes three pins: two floating pads and the XY node. Ports 1
and 2 are compiled probe ports with explicit 50 ohm adapter shunts. For this
declared floating-mode observable those two shunts are solver scaffold; their
compiled rows and values are proven below before an explicit matrix operation
removes them. Port 3's compiled adapter shunt is retained as declared XY-port
loading for this workflow; whether that loading represents the physical
environment remains a Human/model decision.
"""

# ╔═╡ 9b3d4f31-e0dc-5fde-8041-10d693fc2503
floating_lc_xy! = @circuit_component "floating_lc_xy" begin
    pin :pad1
    pin :pad2
    pin :xy_node

    parameter(:c_g1_f; unit="F")
    parameter(:c_g2_f; unit="F")
    parameter(:c_q_f; unit="F")
    parameter(:c_xy1_f; unit="F")
    parameter(:c_xy2_f; unit="F")
    parameter(:l_branch_h; unit="H")

    shunt_capacitor!(id=:c_g1, at=pin(:pad1), capacitance=c_g1_f, role=:pad_ground_capacitance, label="Cg1")
    shunt_capacitor!(id=:c_g2, at=pin(:pad2), capacitance=c_g2_f, role=:pad_ground_capacitance, label="Cg2")
    couple_capacitive!(id=:c_q, from=pin(:pad1), to=pin(:pad2), capacitance=c_q_f, role=:floating_capacitance, label="Cq")
    series_inductor!(id=:l_q1, from=pin(:pad1), to=pin(:pad2), inductance=l_branch_h, role=:floating_inductance, label="Lq1")
    series_inductor!(id=:l_q2, from=pin(:pad1), to=pin(:pad2), inductance=l_branch_h, role=:floating_inductance, label="Lq2")
    couple_capacitive!(id=:c_xy1, from=pin(:pad1), to=pin(:xy_node), capacitance=c_xy1_f, role=:xy_coupling_capacitance, label="Cxy1")
    couple_capacitive!(id=:c_xy2, from=pin(:pad2), to=pin(:xy_node), capacitance=c_xy2_f, role=:xy_coupling_capacitance, label="Cxy2")
end

# ╔═╡ 1e2f2386-50bf-5722-9dba-cbe7c2aa4984
begin
    circuit_plan = @circuit "floating-lc-xy-line" begin
        pad1 = external_node("pad1")
        pad2 = external_node("pad2")
        xy_node = external_node("xy_node")

        floating = floating_lc_xy!(
            id=:floating,
            pad1=pad1,
            pad2=pad2,
            xy_node=xy_node,
            c_g1_f=c_g1_f,
            c_g2_f=c_g2_f,
            c_q_f=c_q_f,
            c_xy1_f=c_xy1_f,
            c_xy2_f=c_xy2_f,
            l_branch_h=l_branch_h,
        )

        port(:pad1_port) do
            index = 1
            endpoint = pin(floating, :pad1)
            resistance = port_resistance
            role = :probe
        end
        port(:pad2_port) do
            index = 2
            endpoint = pin(floating, :pad2)
            resistance = port_resistance
            role = :probe
        end
        port(:xy_port) do
            index = 3
            endpoint = pin(floating, :xy_node)
            resistance = port_resistance
            role = :xy_drive
        end

        group(:floating_xy_system) do
            label = "Floating LC with XY node"
            role = :floating_qubit_xy_coupling
            members = [:floating, :pad1_port, :pad2_port, :xy_port]
        end

        schematic!(:notebook_view) do
            terminal(:pad1_terminal) do
                endpoint = pad1
                side = :left
                kind = :port
                label = "1"
            end
            terminal(:pad2_terminal) do
                endpoint = pad2
                side = :left
                kind = :port
                label = "2"
            end
            terminal(:xy_terminal) do
                endpoint = xy_node
                side = :right
                kind = :port
                label = "3"
            end
            node_label(:pad1_label) do
                target = pad1
                label = "Pad1"
            end
            node_label(:pad2_label) do
                target = pad2
                label = "Pad2"
            end
            node_label(:xy_label) do
                target = xy_node
                label = "XY"
            end
        end
    end


    @hbintent circuit_plan begin
        pump_axis(:pump; frequency_parameter=:pump_frequency)
        source_slot(:pump_in) do
            role = :pump
            port = :xy_port
            mode = (1,)
            current_parameter = :pump_current
        end
        sparameter(:s11) do
            outputmode = (0,)
            outputport = :pad1_port
            inputmode = (0,)
            inputport = :pad1_port
        end
        sparameter(:s22) do
            outputmode = (0,)
            outputport = :pad2_port
            inputmode = (0,)
            inputport = :pad2_port
        end
        sparameter(:s33) do
            outputmode = (0,)
            outputport = :xy_port
            inputmode = (0,)
            inputport = :xy_port
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
# ╔═╡ 4151f9bb-28e6-5250-8c44-701bc1068353
md"""
## Inspect Core Representations
"""

# ╔═╡ b75739bd-143f-5cc6-8416-72304b9b9265
hb_validation_report = validate_hb_intent(circuit_plan)

# ╔═╡ 23e723e3-8086-5730-861d-779e180531ff
graph = engineering_graph(circuit_plan)

# ╔═╡ 5194adce-52fc-5214-a5df-612ecef4cf1d
layout = schematic_layout_intent(circuit_plan)

# ╔═╡ aca33251-8167-5dcd-a2a2-18fd88dbdf70
schematic_export = to_schematic_export_spec(circuit_plan)

# ╔═╡ 60b82228-ceaa-5d31-a198-8aac6a6f88e8
graph_summary = (
    components=sort(collect(keys(graph.components)); by=string),
    ports=sort(collect(keys(graph.ports)); by=string),
    groups=sort(collect(keys(graph.groups)); by=string),
    relation_count=length(graph.relations),
)

# ╔═╡ 10230843-6370-515d-9452-65dac72deeab
layout_summary = (
    tracks=sort(collect(keys(layout.tracks)); by=string),
    segments=sort(collect(keys(layout.segments)); by=string),
    coupled_spans=sort(collect(keys(layout.coupled_spans)); by=string),
    terminals=sort(collect(keys(layout.terminals)); by=string),
    node_labels=sort(collect(keys(layout.node_labels)); by=string),
)

# ╔═╡ c211d7cc-51a8-57f5-b094-890e1d5df2ad
export_summary = (
    components=length(schematic_export.components),
    relations=length(schematic_export.relations),
    ports=length(schematic_export.ports),
    tracks=length(schematic_export.tracks),
    terminals=length(schematic_export.terminals),
)

# ╔═╡ 1169429d-cb3f-5a17-b85c-feae545c0c28
compiled_circuit = compile_to_josephson(circuit_plan)

# ╔═╡ 1dfe47cf-2fa9-5514-91c3-de42761694bf
begin
    compiled_port_rows = filter(
        row -> startswith(string(first(row)), "P") || startswith(string(first(row)), "R_port_"),
        compiled_circuit.netlist,
    )
    compiled_probe_shunt_evidence = compiled_port_shunt_evidence(
        compiled_circuit;
        port_indices=(1, 2),
    )
    retained_xy_load_evidence = compiled_port_shunt_evidence(
        compiled_circuit;
        port_indices=(3,),
    )[3]

    compiled_summary = (
        netlist_rows=length(compiled_circuit.netlist),
        port_ids=sort(collect(keys(compiled_circuit.port_map)); by=string),
        port_rows=compiled_port_rows,
        probe_shunt_evidence=compiled_probe_shunt_evidence,
        ptc_removal_intent=:floating_mode_probe_scaffold,
        retained_xy_load=(
            role=:retained_xy_port_shunt,
            retention_intent=:declared_xy_port_loading_for_this_workflow,
            evidence=retained_xy_load_evidence,
        ),
        warning_count=length(compiled_circuit.warnings),
    )
end

# ╔═╡ 4fb75516-ee94-5a91-ba8b-460cc2e4f500
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

# ╔═╡ 92bc547e-51cd-5670-a808-daaa21cb0ae8
output_request_report = validate_output_request_configuration(compiled_circuit, hb_problem)

# ╔═╡ 6df62bc9-1715-5ee2-aaae-6f5bb880c0a9
result = run_hb_problem(hb_problem)

# ╔═╡ 73175506-6f68-525c-98b9-dead7e23e4d2
trace_families = sort(collect(keys(result.traces)); by=string)

# ╔═╡ b7547da3-66be-5c3e-a60b-4868823a73d2
md"""
## Post-Processing: Port-Termination Compensation

Ports 1 and 2 are declared island probes. Their explicit compiled adapter
shunts are part of the raw solved network. The canonical
[Port-Termination Compensation](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/simulation/port-termination-compensation.qmd)
node owns the operation and evidence gates. Here the local removal intent is
`floating_mode_probe_scaffold`; the declared port-3 adapter shunt remains in the
matrix before the coordinate transform and Kron reduction. Whether it models
the physical XY environment remains a Human/model decision.
"""

# ╔═╡ 907d69fb-ef1b-58cf-8c28-210852c89786
md"""
## Post-Processing: Weighted Common/Differential Coordinates

This workflow uses the local capacitance-derived weights below and defines the
differential voltage as ``V_{dm}=V_1-V_2``:

```math
V_{cm}=\alpha V_1+\beta V_2, \qquad V_{dm}=V_1-V_2,
```

```math
\alpha = \frac{C_{g1}+C_{xy1}}{C_{g1}+C_{xy1}+C_{g2}+C_{xy2}}, \qquad
\beta = 1-\alpha.
```

The exact voltage and power-conjugate current transforms used by this run are
published in `coordinate_contract`. The canonical coordinate-transform page
linked above owns the reusable derivation.
"""

# ╔═╡ 8d937c1c-1b72-523c-8b16-781ebd08447c
md"""
## Post-Processing: Kron Reduction

This run keeps transformed index 2 (`differential`) and eliminates indices 1
and 3 (`common`, `xy`) with zero external current injection at those eliminated
coordinates. The compiled port-3 resistor remains inside the supplied
admittance as declared XY-port loading for this workflow; it is not claimed as
a proven physical environment. The canonical Kron page linked above owns the
generic derivation.
"""

# ╔═╡ 4cece3fe-1e36-50b0-b7de-00f2db701e28
raw_y_stack = zero_mode_y_matrix_stack(result; ports=[1, 2, 3])

# ╔═╡ 2fb7f994-4f0a-5e6b-9fae-9b9e163c0440
compensated_y_stack = apply_port_termination_compensation(
    raw_y_stack,
    compiled_circuit;
    compensate_port_indices=(1, 2),
    removal_intent=compiled_summary.ptc_removal_intent,
)

# ╔═╡ df3fb84a-4ef0-5d6b-8b09-e862a3d8cba9
coordinate_transform = common_differential_transform(
    3,
    1,
    2;
    alpha=alpha,
    beta=beta,
)

# ╔═╡ 0ca42d23-ad1b-5bb5-b226-9a50028723f7
begin
    transformed_y_stack = apply_coordinate_transform(
        compensated_y_stack,
        coordinate_transform;
        labels=["common", "differential", "xy"],
    )
    coordinate_contract = (
        alpha=alpha,
        beta=beta,
        voltage_transform_A=copy(coordinate_transform),
        current_transform_A_inverse_transpose=ComplexF64[
            1 1 0
            beta -alpha 0
            0 0 1
        ],
        voltage_convention=(
            common="V_common = alpha * V_pad1 + beta * V_pad2",
            differential="V_differential = V_pad1 - V_pad2",
            xy="V_xy = V_xy_port",
        ),
        current_convention=(
            common="I_common = I_pad1 + I_pad2",
            differential="I_differential = beta * I_pad1 - alpha * I_pad2",
            xy="I_xy = I_xy_port",
        ),
        quantity_lineage=(
            raw=raw_y_stack.quantity_kind,
            compensated=compensated_y_stack.quantity_kind,
            transformed=transformed_y_stack.quantity_kind,
        ),
        source_lineage=(
            raw=raw_y_stack.source_kind,
            compensated=compensated_y_stack.source_kind,
            transformed=transformed_y_stack.source_kind,
        ),
        input_labels=copy(compensated_y_stack.labels),
        output_labels=copy(transformed_y_stack.labels),
    )
end

# ╔═╡ f9ddfebd-390b-5de8-9e94-838d3fcfca89
begin
    kron_keep_indices = [2]
    kron_drop_indices = [1, 3]
    kron_boundary = (
        keep_indices=copy(kron_keep_indices),
        keep_labels=transformed_y_stack.labels[kron_keep_indices],
        drop_indices=copy(kron_drop_indices),
        drop_labels=transformed_y_stack.labels[kron_drop_indices],
        eliminated_external_current=:zero,
        retained_load=compiled_summary.retained_xy_load,
    )
    reduced_y_stack = kron_reduce(transformed_y_stack; keep_indices=kron_keep_indices)
    kron_boundary
end

# ╔═╡ 419e2dbf-09da-5a0f-a4bf-ce46aa06f245
begin
    y_eff = vec(reduced_y_stack.values[1, 1, :])
    eliminated_current_residuals = Float64[]
    retained_response_residuals = Float64[]
    y_dd_condition_numbers = Float64[]
    unit_retained_voltage = ComplexF64[1]
    for frequency_index in axes(transformed_y_stack.values, 3)
        y = transformed_y_stack.values[:, :, frequency_index]
        y_kk = y[kron_keep_indices, kron_keep_indices]
        y_kd = y[kron_keep_indices, kron_drop_indices]
        y_dk = y[kron_drop_indices, kron_keep_indices]
        y_dd = y[kron_drop_indices, kron_drop_indices]
        eliminated_voltage = -(y_dd \ (y_dk * unit_retained_voltage))
        eliminated_current = y_dk * unit_retained_voltage + y_dd * eliminated_voltage
        retained_current = y_kk * unit_retained_voltage + y_kd * eliminated_voltage
        reduced_current = reduced_y_stack.values[:, :, frequency_index] * unit_retained_voltage
        push!(
            eliminated_current_residuals,
            norm(eliminated_current) /
            max(norm(y_dk * unit_retained_voltage), norm(y_dd * eliminated_voltage), eps(Float64)),
        )
        push!(
            retained_response_residuals,
            norm(retained_current - reduced_current) /
            max(norm(retained_current), norm(reduced_current), eps(Float64)),
        )
        push!(y_dd_condition_numbers, cond(y_dd))
    end
    worst_condition_index = argmax(y_dd_condition_numbers)
    kron_reconstruction_evidence = (
        frequency_point_count=length(y_dd_condition_numbers),
        condition_number_definition=:spectral_2_norm,
        numeric_type=ComplexF64,
        eliminated_basis_labels=copy(kron_boundary.drop_labels),
        y_dd_condition_numbers=y_dd_condition_numbers,
        y_dd_condition_range=(
            minimum=minimum(y_dd_condition_numbers),
            maximum=maximum(y_dd_condition_numbers),
        ),
        worst_condition_frequency_hz=transformed_y_stack.frequencies_hz[worst_condition_index],
        conditioning_decision=:human_review_required,
        normalized_eliminated_current_residuals=eliminated_current_residuals,
        maximum_normalized_eliminated_current_residual=maximum(eliminated_current_residuals),
        normalized_retained_response_residuals=retained_response_residuals,
        maximum_normalized_retained_response_residual=maximum(retained_response_residuals),
    )
end

# ╔═╡ c359fd3b-5c32-5d28-b9f9-724c4b2e02a1
begin
    residual_tolerance = sqrt(eps(Float64))
    sanity = (
        point_count_matches=length(result.frequencies_hz) == point_count,
        finite_y_eff=all(isfinite, real.(y_eff)) && all(isfinite, imag.(y_eff)),
        resonance_in_span=start_frequency <= f0_estimate <= stop_frequency,
        hb_intent_ok=!has_errors(hb_validation_report),
        quantity_contract_ok=coordinate_contract.quantity_lineage == (
            raw=:admittance,
            compensated=:admittance,
            transformed=:admittance,
        ) && reduced_y_stack.quantity_kind == :admittance,
        coordinate_labels_ok=coordinate_contract.input_labels == ["1", "2", "3"] &&
            coordinate_contract.output_labels == ["common", "differential", "xy"] &&
            kron_boundary.keep_labels == ["differential"] &&
            kron_boundary.drop_labels == ["common", "xy"],
        source_lineage_ok=coordinate_contract.source_lineage == (
            raw=:z_inverse,
            compensated=:ptc_z_inverse,
            transformed=:coordinate_transform_ptc_z_inverse,
        ) && reduced_y_stack.source_kind == :kron_reduction_coordinate_transform_ptc_z_inverse,
        real_transform_ok=all(isreal, coordinate_contract.voltage_transform_A) &&
            all(isreal, coordinate_contract.current_transform_A_inverse_transpose),
        current_transform_ok=coordinate_contract.current_transform_A_inverse_transpose ≈
            transpose(
                coordinate_contract.voltage_transform_A \
                Matrix{ComplexF64}(I, size(coordinate_contract.voltage_transform_A)...),
            ),
        alpha_beta_ok=isapprox(coordinate_contract.alpha + coordinate_contract.beta, 1.0; atol=eps(Float64), rtol=0.0),
        retained_port3_evidence_ok=compiled_summary.retained_xy_load.role == :retained_xy_port_shunt &&
            compiled_summary.retained_xy_load.retention_intent == :declared_xy_port_loading_for_this_workflow &&
            compiled_summary.retained_xy_load.evidence.port_id == :xy_port &&
            compiled_summary.retained_xy_load.evidence.port_index == 3 &&
            compiled_summary.retained_xy_load.evidence.resistor_id == "R_port_3" &&
            compiled_summary.retained_xy_load.evidence.resistance_ohm == port_resistance,
        condition_evidence_finite=all(isfinite, kron_reconstruction_evidence.y_dd_condition_numbers) &&
            kron_reconstruction_evidence.conditioning_decision == :human_review_required,
        zero_injection_residual_ok=kron_reconstruction_evidence.maximum_normalized_eliminated_current_residual <= residual_tolerance,
        retained_response_residual_ok=kron_reconstruction_evidence.maximum_normalized_retained_response_residual <= residual_tolerance,
    )
end

# ╔═╡ 10af70df-bab0-58dc-8399-665fc4b7ad07
sanity

# ╔═╡ 938c6ab9-6b59-5b4a-84a1-65350178c76d
begin
    y_trace_figure(
        result.frequencies_hz,
        ["Yeff" => y_eff];
        title="Floating LC Differential-Mode Admittance",
        config=figure_config,
    )
end |> wide_figure_cell

# ╔═╡ Cell order:
# ╠═d4c2e4d2-0702-5c47-9ad1-9e96d27575d2
# ╠═f68a000d-9f5b-5760-9156-34d44e8790cc
# ╟─925798a9-8155-52d2-b5d1-389df52b1eb1
# ╟─76da6a39-f791-5aac-948e-deaf925a2b7d
# ╠═8d7c8662-893f-5808-8b36-c33c37ab49b9
# ╟─7caa12c4-973b-50a0-a872-d378f92808f5
# ╠═e7dc2fd9-d595-5d38-8371-9cef9d32bbdb
# ╠═30456352-a3c6-5a50-9be7-0f7f7492b340
# ╠═2178e3b2-7e54-5d3c-b302-3bdc8b9c96ed
# ╟─b5d445b9-fb30-583a-9701-6159eefd565b
# ╠═9b3d4f31-e0dc-5fde-8041-10d693fc2503
# ╠═1e2f2386-50bf-5722-9dba-cbe7c2aa4984
# ╟─4151f9bb-28e6-5250-8c44-701bc1068353
# ╠═b75739bd-143f-5cc6-8416-72304b9b9265
# ╠═23e723e3-8086-5730-861d-779e180531ff
# ╠═5194adce-52fc-5214-a5df-612ecef4cf1d
# ╠═aca33251-8167-5dcd-a2a2-18fd88dbdf70
# ╠═60b82228-ceaa-5d31-a198-8aac6a6f88e8
# ╠═10230843-6370-515d-9452-65dac72deeab
# ╠═c211d7cc-51a8-57f5-b094-890e1d5df2ad
# ╠═1169429d-cb3f-5a17-b85c-feae545c0c28
# ╠═1dfe47cf-2fa9-5514-91c3-de42761694bf
# ╠═4fb75516-ee94-5a91-ba8b-460cc2e4f500
# ╠═92bc547e-51cd-5670-a808-daaa21cb0ae8
# ╠═6df62bc9-1715-5ee2-aaae-6f5bb880c0a9
# ╠═73175506-6f68-525c-98b9-dead7e23e4d2
# ╟─b7547da3-66be-5c3e-a60b-4868823a73d2
# ╟─907d69fb-ef1b-58cf-8c28-210852c89786
# ╟─8d937c1c-1b72-523c-8b16-781ebd08447c
# ╠═4cece3fe-1e36-50b0-b7de-00f2db701e28
# ╠═2fb7f994-4f0a-5e6b-9fae-9b9e163c0440
# ╠═df3fb84a-4ef0-5d6b-8b09-e862a3d8cba9
# ╠═0ca42d23-ad1b-5bb5-b226-9a50028723f7
# ╠═f9ddfebd-390b-5de8-9e94-838d3fcfca89
# ╠═419e2dbf-09da-5a0f-a4bf-ce46aa06f245
# ╠═c359fd3b-5c32-5d28-b9f9-724c4b2e02a1
# ╠═10af70df-bab0-58dc-8399-665fc4b7ad07
# ╠═938c6ab9-6b59-5b4a-84a1-65350178c76d
