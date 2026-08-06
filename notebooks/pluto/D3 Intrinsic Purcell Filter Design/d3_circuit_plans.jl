# D3 owns the complete research Circuit Plans. Julia Core owns only the
# reusable qubit/filter components that these builders compose.

using SuperconductingCircuitsCore

const D3_DEFAULT_FEEDLINE_L_PER_M_H = 404.313e-9
const D3_DEFAULT_FEEDLINE_C_PER_M_F = 179.86e-12
const D3_PORT_REGULARIZER_SERIES_INDUCTANCE_H = 1.0e-12
const D3_PORT_REGULARIZER_CHARACTERISTIC_IMPEDANCE_OHM = 50.0
const D3_PORT_REGULARIZER_PHASE_VELOCITY_M_PER_S =
    inv(sqrt(D3_DEFAULT_FEEDLINE_L_PER_M_H * D3_DEFAULT_FEEDLINE_C_PER_M_F))
const D3_PORT_REGULARIZER_SECTION_CAPACITANCE_F =
    D3_PORT_REGULARIZER_SERIES_INDUCTANCE_H /
    D3_PORT_REGULARIZER_CHARACTERISTIC_IMPEDANCE_OHM^2
const D3_PORT_REGULARIZER_SECTION_LENGTH_M =
    D3_PORT_REGULARIZER_SERIES_INDUCTANCE_H /
    (
        D3_PORT_REGULARIZER_CHARACTERISTIC_IMPEDANCE_OHM /
        D3_PORT_REGULARIZER_PHASE_VELOCITY_M_PER_S
    )
const D3_DEFAULT_MTL_L_MATRIX_PER_M_H = [
    410.86374 19.08527
    19.08527 410.85454
] .* 1e-9
const D3_DEFAULT_MTL_C_MATRIX_PER_M_F = [
    170.29805 -8.09678
    -8.09678 170.29538
] .* 1e-12

function _d3_line_spec(;
    length_m,
    section_length_m,
    l_per_m_h=D3_DEFAULT_FEEDLINE_L_PER_M_H,
    c_per_m_f=D3_DEFAULT_FEEDLINE_C_PER_M_F,
)
    return RLGCSpec(
        length_m=length_m,
        section_length_m=section_length_m,
        l_per_m_h=l_per_m_h,
        c_per_m_f=c_per_m_f,
    )
end

function _d3_mtl_window_breakpoints(start_m, length_m, section_length_m)
    count = ceil(Int, Float64(length_m) / Float64(section_length_m) - 1e-12)
    count > 0 || throw(ArgumentError("D3 MTL window requires at least one section."))
    dx = Float64(length_m) / count
    return [Float64(start_m) + index * dx for index in 0:count]
end

function _d3_exact_interval_breakpoints(start_m, length_m, count)
    count isa Integer && count > 0 || throw(ArgumentError(
        "D3 exact interval section count must be a positive integer.",
    ))
    start = Float64(start_m)
    length = Float64(length_m)
    isfinite(start) && start >= 0 && isfinite(length) && length > 0 ||
        throw(ArgumentError("D3 exact interval geometry must be finite and positive."))
    points = [start + length * index / count for index in 0:count]
    points[1] = start
    points[end] = start + length
    return points
end

function _d3_derived_section_count(length_m, reference_section_length_m)
    length = Float64(length_m)
    reference = Float64(reference_section_length_m)
    isfinite(length) && length > 0 && isfinite(reference) && reference > 0 ||
        throw(ArgumentError("D3 line length and reference section length must be finite and positive."))
    raw = length / reference
    nearest = round(Int, raw)
    return isapprox(raw, nearest; atol=1e-12, rtol=1e-9) ? nearest : ceil(Int, raw)
end

function _d3_refined_hybridized_line_breakpoints(
    head_length_m,
    window_length_m,
    tail_length_m,
    base_section_length_m,
    base_mtl_section_length_m,
    refinement_level,
)
    refinement_level isa Integer && refinement_level >= 0 || throw(ArgumentError(
        "D3 direct-Hybridized refinement_level must be a nonnegative integer.",
    ))
    factor = 1 << refinement_level
    head_count = _d3_derived_section_count(head_length_m, base_section_length_m) * factor
    mtl_count = _d3_derived_section_count(window_length_m, base_mtl_section_length_m) * factor
    tail_count = _d3_derived_section_count(tail_length_m, base_section_length_m) * factor
    head = _d3_exact_interval_breakpoints(0.0, head_length_m, head_count)
    window = _d3_exact_interval_breakpoints(head_length_m, window_length_m, mtl_count)
    tail = _d3_exact_interval_breakpoints(
        Float64(head_length_m) + Float64(window_length_m),
        tail_length_m,
        tail_count,
    )
    return (
        boundaries_m=vcat(head[1:(end - 1)], window[1:(end - 1)], tail),
        count=head_count + mtl_count + tail_count,
        mtl_count=mtl_count,
    )
end

function _d3_exact_breakpoint_reference(boundaries_m)
    boundaries = Float64.(collect(boundaries_m))
    length(boundaries) >= 2 || throw(ArgumentError(
        "D3 exact boundary array must contain at least two values.",
    ))
    all(isfinite, boundaries) && all(diff(boundaries) .> 0) || throw(ArgumentError(
        "D3 exact boundary array must be finite and strictly increasing.",
    ))
    return maximum(diff(boundaries)) * (1 + 8eps(Float64))
end

function _d3_engineering_relation_label(plan::CircuitPlan, relation_id)
    selected_id = Symbol(relation_id)
    for relation in engineering_graph(plan).relations
        relation.id == selected_id && return relation.label
    end
    throw(ArgumentError("Missing engineering relation label for '$(selected_id)'."))
end

_d3_port_label(port::EngineeringPort) = "\$P_$(port.port_index)\$"

function _d3_port_resistance_label(port::EngineeringPort)
    isapprox(port.resistance, 50.0) && return raw"$R_{50}$"
    return "\$R_{$(port.resistance)}\$"
end

function _d3_schematic_endpoint_ref(value)
    isnothing(value) && return nothing
    value isa PinEndpoint && return "$(value.component_id).$(value.pin)"
    value isa ProbeEndpoint && return "$(value.component_id).$(value.probe)"
    value isa LineTapEndpoint &&
        return "$(value.line_ref.component_id).$(value.line_ref.line)@$(value.at_m)"
    value isa LineSpanEndpoint &&
        return "$(value.line_ref.component_id).$(value.line_ref.line):$(value.from_m)-$(value.to_m)"
    value isa LoopEndpoint && return "$(value.component_id).$(value.loop)"
    value isa GroundEndpoint && return "ground"
    value isa ExternalNodeEndpoint && return value.name
    value isa Symbol && return string(value)
    value isa AbstractString && return String(value)
    return string(value)
end

function _d3_schemdraw_schematic!(
    plan::CircuitPlan;
    id,
    component_type,
    component_id,
    unit_length,
    labels,
    parameters,
    terminals,
    node_labels,
    node_bindings,
)
    serialized_bindings = Dict(
        Symbol(role) => _d3_schematic_endpoint_ref(endpoint)
        for (role, endpoint) in pairs(node_bindings)
    )
    label_roles = [Symbol(label.id) for label in node_labels]
    length(unique(label_roles)) == length(label_roles) ||
        throw(ArgumentError("Schematic physical-node label roles must be unique."))
    Set(keys(serialized_bindings)) == Set(label_roles) ||
        throw(ArgumentError("Schematic node_bindings must cover every physical-node label role exactly."))
    length(unique(values(serialized_bindings))) == length(serialized_bindings) ||
        throw(ArgumentError("Schematic node_bindings endpoints must be unique."))
    for label in node_labels
        role = Symbol(label.id)
        serialized_bindings[role] == _d3_schematic_endpoint_ref(label.target) ||
            throw(ArgumentError("Schematic node binding '$(role)' must match its physical-node label target."))
    end

    render_parameters = Dict{Symbol,Any}(:component_id => string(component_id))
    merge!(render_parameters, Dict{Symbol,Any}(parameters))
    return schematic!(
        plan;
        id=id,
        render_hints=Dict(
            :schemdraw => Dict{Symbol,Any}(
                :component_type => string(component_type),
                :unit_length => Float64(unit_length),
                :labels => Dict{Symbol,Any}(labels),
                :parameters => render_parameters,
                :node_bindings => serialized_bindings,
            ),
        ),
    ) do intent
        for terminal in terminals
            record_schematic_terminal!(
                intent;
                id=terminal.id,
                endpoint=terminal.endpoint,
                side=terminal.side,
                kind=terminal.kind,
                label=terminal.label,
            )
        end
        for label in node_labels
            record_schematic_node_label!(intent; label...)
        end
    end
end

function _d3_matched_port_regularizer!(
    plan::CircuitPlan;
    center=external_node("d3_design_target_fc"),
    port_resistance_ohm=50.0,
)
    resistance = Float64(port_resistance_ohm)
    isfinite(resistance) &&
        resistance == D3_PORT_REGULARIZER_CHARACTERISTIC_IMPEDANCE_OHM ||
        throw(ArgumentError(
            "D3 matched port regularizer requires both external ports to equal " *
            "$(D3_PORT_REGULARIZER_CHARACTERISTIC_IMPEDANCE_OHM) ohm.",
        ))
    input = external_node("d3_design_target_f1")
    output = external_node("d3_design_target_f2")
    l_per_m_h =
        D3_PORT_REGULARIZER_CHARACTERISTIC_IMPEDANCE_OHM /
        D3_PORT_REGULARIZER_PHASE_VELOCITY_M_PER_S
    c_per_m_f = inv(
        D3_PORT_REGULARIZER_CHARACTERISTIC_IMPEDANCE_OHM *
        D3_PORT_REGULARIZER_PHASE_VELOCITY_M_PER_S,
    )
    spec = _d3_line_spec(
        length_m=D3_PORT_REGULARIZER_SECTION_LENGTH_M,
        section_length_m=D3_PORT_REGULARIZER_SECTION_LENGTH_M,
        l_per_m_h=l_per_m_h,
        c_per_m_f=c_per_m_f,
    )
    left = transmission_line!(
        plan;
        id=:d3_design_target_port_regularizer_left,
        head=input,
        tail=center,
        spec=spec,
        head_termination=:external,
        tail_termination=:external,
    )
    right = transmission_line!(
        plan;
        id=:d3_design_target_port_regularizer_right,
        head=center,
        tail=output,
        spec=spec,
        head_termination=:external,
        tail_termination=:external,
    )
    external_port!(
        plan;
        id=:input_port,
        index=1,
        endpoint=input,
        resistance=resistance,
        role=:signal,
    )
    external_port!(
        plan;
        id=:output_port,
        index=2,
        endpoint=output,
        resistance=resistance,
        role=:readout,
    )
    return (;
        left,
        right,
        input,
        center,
        output,
        regularizer_series_inductance_h=D3_PORT_REGULARIZER_SERIES_INDUCTANCE_H,
        regularizer_section_capacitance_f=D3_PORT_REGULARIZER_SECTION_CAPACITANCE_F,
        regularizer_characteristic_impedance_ohm=
            D3_PORT_REGULARIZER_CHARACTERISTIC_IMPEDANCE_OHM,
        regularizer_phase_velocity_m_per_s=D3_PORT_REGULARIZER_PHASE_VELOCITY_M_PER_S,
        regularizer_section_length_m=D3_PORT_REGULARIZER_SECTION_LENGTH_M,
    )
end

function _d3_distributed_feedline!(
    plan::CircuitPlan;
    center=external_node("d3_design_target_fc"),
    length_m=1.0e-3,
    n_sections=20,
    l_per_m_h=D3_DEFAULT_FEEDLINE_L_PER_M_H,
    c_per_m_f=D3_DEFAULT_FEEDLINE_C_PER_M_F,
    port_resistance_ohm=50.0,
    left_breakpoints_m=nothing,
    right_breakpoints_m=nothing,
)
    n_sections isa Integer ||
        throw(ArgumentError("D3 split distributed feedline n_sections must be an integer."))
    n_sections >= 2 ||
        throw(ArgumentError("D3 split distributed feedline requires at least two sections."))
    iseven(n_sections) ||
        throw(ArgumentError("D3 split distributed feedline requires an even n_sections so both CPW halves use the same discretization."))
    input = external_node("d3_design_target_f1")
    output = external_node("d3_design_target_f2")
    left_center_terminal = external_node("d3_design_target_fc_left_terminal")
    right_center_terminal = external_node("d3_design_target_fc_right_terminal")
    half_length = Float64(length_m) / 2
    half_sections = n_sections ÷ 2
    exact_breakpoints = !isnothing(left_breakpoints_m) ||
        !isnothing(right_breakpoints_m)
    exact_breakpoints &&
        (isnothing(left_breakpoints_m) || isnothing(right_breakpoints_m)) &&
        throw(ArgumentError(
            "D3 split distributed feedline exact grid requires both left and right boundary arrays.",
        ))
    left_boundaries = exact_breakpoints ? Float64.(collect(left_breakpoints_m)) : nothing
    right_boundaries = exact_breakpoints ? Float64.(collect(right_breakpoints_m)) : nothing
    if exact_breakpoints
        for (label, boundaries) in (
            ("left", left_boundaries),
            ("right", right_boundaries),
        )
            first(boundaries) == 0.0 &&
                isapprox(last(boundaries), half_length; atol=1e-12, rtol=1e-9) ||
                throw(ArgumentError(
                    "D3 distributed feedline $(label) boundaries must span exactly one half of feedline_length_m.",
                ))
            length(boundaries) - 1 == half_sections || throw(ArgumentError(
                "D3 distributed feedline $(label) boundary count disagrees with n_sections.",
            ))
            _d3_exact_breakpoint_reference(boundaries)
        end
    end
    left = transmission_line!(
        plan;
        id=:d3_design_target_distributed_feedline_left,
        head=input,
        tail=left_center_terminal,
        spec=RLGCSpec(
            length_m=half_length,
            n_sections=exact_breakpoints ? nothing : half_sections,
            section_length_m=exact_breakpoints ?
                _d3_exact_breakpoint_reference(left_boundaries) : nothing,
            l_per_m_h=l_per_m_h,
            c_per_m_f=c_per_m_f,
        ),
        head_termination=:external,
        tail_termination=:external,
        breakpoints_m=left_boundaries,
    )
    right = transmission_line!(
        plan;
        id=:d3_design_target_distributed_feedline_right,
        head=right_center_terminal,
        tail=output,
        spec=RLGCSpec(
            length_m=half_length,
            n_sections=exact_breakpoints ? nothing : half_sections,
            section_length_m=exact_breakpoints ?
                _d3_exact_breakpoint_reference(right_boundaries) : nothing,
            l_per_m_h=l_per_m_h,
            c_per_m_f=c_per_m_f,
        ),
        head_termination=:external,
        tail_termination=:external,
        breakpoints_m=right_boundaries,
    )
    connect!(
        plan,
        left_center_terminal,
        center;
        role=:left_distributed_feedline_to_fc,
    )
    connect!(
        plan,
        right_center_terminal,
        center;
        role=:right_distributed_feedline_to_fc,
    )
    external_port!(
        plan;
        id=:input_port,
        index=1,
        endpoint=input,
        resistance=port_resistance_ohm,
        role=:signal,
    )
    external_port!(
        plan;
        id=:output_port,
        index=2,
        endpoint=output,
        resistance=port_resistance_ohm,
        role=:readout,
    )
    return (; left, right, input, center, output)
end

function _d3_plan_schematic!(
    plan,
    component,
    feedline;
    id,
    component_type,
    labels,
    readout_label_placement,
    readout_label_target,
    readout_label_loc,
    filter_node,
    filter_node_id,
    filter_label_placement,
    filter_label_target,
    feedline_model,
)
    graph = engineering_graph(plan)
    input_port = graph.ports[:input_port]
    output_port = graph.ports[:output_port]
    render_labels = Dict{Symbol,Any}(labels)
    merge!(
        render_labels,
        Dict(
            :input_port_label => _d3_port_label(input_port),
            :output_port_label => _d3_port_label(output_port),
            :input_port_resistance_label => _d3_port_resistance_label(input_port),
            :output_port_resistance_label => _d3_port_resistance_label(output_port),
        ),
    )
    _d3_schemdraw_schematic!(
        plan;
        id=id,
        component_type=component_type,
        component_id=component.id,
        unit_length=1.5,
        labels=render_labels,
        parameters=merge(
            Dict(
            :contains_feedline => true,
            :feedline_model => feedline_model,
            :feedline_coupling_kind => :interdigitated_three_branch,
            :idc_parameterization => :one_geometry_coordinate_derives_three_capacitances,
            :optimizer_parameterization => :three_branch_idc_mapping_only,
            :qubit_inductive_branch_kind =>
                engineering_graph(plan).components[Symbol(component.qubit.id)].parameters[:inductive_branch_kind],
            ),
            hasproperty(feedline, :regularizer_series_inductance_h) ? Dict(
                :regularizer_series_inductance_h =>
                    feedline.regularizer_series_inductance_h,
                :regularizer_section_capacitance_f =>
                    feedline.regularizer_section_capacitance_f,
                :regularizer_characteristic_impedance_ohm =>
                    feedline.regularizer_characteristic_impedance_ohm,
                :regularizer_phase_velocity_m_per_s =>
                    feedline.regularizer_phase_velocity_m_per_s,
                :regularizer_section_length_m =>
                    feedline.regularizer_section_length_m,
                :regularizer_physical_role => :numerical_port_node_regularization_only,
            ) : Dict{Symbol,Any}(),
        ),
        terminals=[
            (id=:input_port, endpoint=feedline.input, side=:left, kind=:port, label=raw"$P_1$"),
            (id=:output_port, endpoint=feedline.output, side=:right, kind=:port, label=raw"$P_2$"),
        ],
        node_labels=[
            (
                id=:readout_attachment,
                target=component.filter.readout_attachment,
                label=raw"$r$",
                hints=Dict(
                    :placement => readout_label_placement,
                    :placement_target => readout_label_target,
                    :loc => readout_label_loc,
                    :offset => 0.28,
                ),
            ),
            (
                id=filter_node_id,
                target=filter_node,
                label=raw"$p$",
                hints=Dict(
                    :placement => filter_label_placement,
                    :placement_target => filter_label_target,
                    :loc => :top,
                    :offset => (0.28, 0.5),
                ),
            ),
            (
                id=:island_1,
                target=component.qubit.island_1,
                label=raw"$q_1$",
                hints=Dict(
                    :placement => :marker,
                    :placement_target => :qubit_q1_terminal,
                    :loc => :top,
                    :offset => 0.28,
                ),
            ),
            (
                id=:island_2,
                target=component.qubit.island_2,
                label=raw"$q_0$",
                hints=Dict(
                    :placement => :marker,
                    :placement_target => :qubit_q2_terminal,
                    :loc => :bottom,
                    :offset => 0.28,
                ),
            ),
            (
                id=:feedline_attachment,
                target=component.filter.feedline_attachment,
                label=raw"$f_c$",
                hints=Dict(
                    :placement => :marker,
                    :placement_target => :feedline_center,
                    :loc => :top,
                    :offset => 0.28,
                ),
            ),
            (
                id=:feedline_left,
                target=feedline.input,
                label=raw"$f_1$",
                hints=Dict(
                    :placement => :bus_middle,
                    :placement_target => :feedline_left_inner_bus,
                    :loc => :top,
                    :offset => 0.28,
                ),
            ),
            (
                id=:feedline_right,
                target=feedline.output,
                label=raw"$f_2$",
                hints=Dict(
                    :placement => :bus_middle,
                    :placement_target => :feedline_right_inner_bus,
                    :loc => :top,
                    :offset => 0.28,
                ),
            ),
        ],
        node_bindings=Dict(
            :readout_attachment => component.filter.readout_attachment,
            filter_node_id => filter_node,
            :island_1 => component.qubit.island_1,
            :island_2 => component.qubit.island_2,
            :feedline_attachment => component.filter.feedline_attachment,
            :feedline_left => feedline.input,
            :feedline_right => feedline.output,
        ),
    )
    return nothing
end

"""
Build the D3 project-owned equivalent Circuit Plan. The IDC triplet is required
input because one geometry coordinate must derive all three branches.
"""
function build_d3_intrinsic_purcell_equivalent_circuit_plan(;
    id="d3-intrinsic-purcell-equivalent-circuit-plan",
    idc_filter_ground_capacitance_f,
    idc_feedline_ground_capacitance_f,
    idc_mutual_capacitance_f,
    readout_capacitance_f=500.0e-15,
    readout_inductance_h=1.40e-9,
    filter_capacitance_f=480.0e-15,
    filter_inductance_h=1.46e-9,
    bridge_capacitance_f=8.0e-15,
    bridge_inductance_h=35.0e-9,
    c0r_f=18.0e-15,
    c01_f=65.0e-15,
    c02_f=64.0e-15,
    c12_qubit_f=12.0e-15,
    cr1_f=4.2e-15,
    cr2_f=3.8e-15,
    l_j_per_junction_h=24.0e-9,
    port_resistance_ohm=50.0,
)
    plan = CircuitPlan(id)
    readout_attachment = external_node("readout_attachment")
    feedline_attachment = external_node("feedline_attachment")
    filter = add_intrinsic_interferometric_purcell_filter_equivalent!(
        plan;
        id="intrinsic_filter_equivalent",
        readout_attachment=readout_attachment,
        feedline_attachment=feedline_attachment,
        readout_capacitance_f=readout_capacitance_f,
        readout_inductance_h=readout_inductance_h,
        filter_capacitance_f=filter_capacitance_f,
        filter_inductance_h=filter_inductance_h,
        bridge_capacitance_f=bridge_capacitance_f,
        bridge_inductance_h=bridge_inductance_h,
        idc_filter_ground_capacitance_f=idc_filter_ground_capacitance_f,
        idc_feedline_ground_capacitance_f=idc_feedline_ground_capacitance_f,
        idc_mutual_capacitance_f=idc_mutual_capacitance_f,
        c0r_f=c0r_f,
    )
    island_1 = external_node("island_1")
    island_2 = external_node("island_2")
    component = add_intrinsic_interferometric_purcell_filter_equivalent_with_qubit!(
        plan;
        id="intrinsic_filter_equivalent_with_qubit",
        filter=filter,
        island_1=island_1,
        island_2=island_2,
        c0r_f=c0r_f,
        c01_f=c01_f,
        c02_f=c02_f,
        c12_f=c12_qubit_f,
        cr1_f=cr1_f,
        cr2_f=cr2_f,
        l_j_per_junction_h=l_j_per_junction_h,
    )
    feedline = _d3_matched_port_regularizer!(
        plan;
        center=component.filter.feedline_attachment,
        port_resistance_ohm=port_resistance_ohm,
    )
    labels = Dict(
        :cr_label => _d3_engineering_relation_label(plan, component.filter.readout_resonator.capacitor.id),
        :lr_label => _d3_engineering_relation_label(plan, component.filter.readout_resonator.inductor.id),
        :cp_label => _d3_engineering_relation_label(plan, component.filter.filter_resonator.capacitor.id),
        :lp_label => _d3_engineering_relation_label(plan, component.filter.filter_resonator.inductor.id),
        :cn_label => _d3_engineering_relation_label(plan, component.filter.bridge_capacitor.id),
        :ln_label => _d3_engineering_relation_label(plan, component.filter.bridge_inductor.id),
        :cpg_label => _d3_engineering_relation_label(plan, component.filter.feedline_capacitor.c1g.id),
        :cfcg_label => _d3_engineering_relation_label(plan, component.filter.feedline_capacitor.c2g.id),
        :cpfc_label => _d3_engineering_relation_label(plan, component.filter.feedline_capacitor.c12.id),
        :c01_label => _d3_engineering_relation_label(plan, component.qubit.c01.id),
        :c02_label => _d3_engineering_relation_label(plan, component.qubit.c02.id),
        :qubit_c12_label => _d3_engineering_relation_label(plan, component.qubit.c12.id),
        :cr1_label => _d3_engineering_relation_label(plan, component.qubit.cr1.id),
        :cr2_label => _d3_engineering_relation_label(plan, component.qubit.cr2.id),
        :lj1_label => _d3_engineering_relation_label(plan, component.qubit.lj1.id),
        :lj2_label => _d3_engineering_relation_label(plan, component.qubit.lj2.id),
        :feedline_regularizer_inductance_label => raw"$L_{\mathrm{sep}}$",
        :feedline_regularizer_half_capacitance_label => raw"$C_{\mathrm{sep}}/2$",
        :feedline_regularizer_center_capacitance_label => raw"$C_{\mathrm{sep}}$",
    )
    isnothing(component.c0r) ||
        (labels[:c0r_label] = _d3_engineering_relation_label(plan, component.c0r.id))
    _d3_plan_schematic!(
        plan,
        component,
        feedline;
        id=:d3_intrinsic_purcell_equivalent_circuit_plan,
        component_type=:D3IntrinsicPurcellEquivalentCircuitPlan,
        labels=labels,
        readout_label_placement=:bus_middle,
        readout_label_target=:readout_signal,
        readout_label_loc=:top,
        filter_node=component.filter.filter_resonator.node,
        filter_node_id=:filter,
        filter_label_placement=:bus_middle,
        filter_label_target=:filter_signal,
        feedline_model=:matched_port_regularizer_two_pi,
    )
    return (; plan=plan, graph=engineering_graph(plan), component=component, feedline=feedline)
end

"""
Build the D3 project-owned distributed/lumped Circuit Plan. The IDC triplet is
required input because one geometry coordinate must derive all three branches.
"""
function build_d3_intrinsic_purcell_hybridized_circuit_plan(;
    id="d3-intrinsic-purcell-hybridized-circuit-plan",
    idc_filter_ground_capacitance_f,
    idc_feedline_ground_capacitance_f,
    idc_mutual_capacitance_f,
    readout_length_m=6.0e-3,
    filter_length_m=6.0e-3,
    section_length_m=0.75e-3,
    mtl_section_length_m=section_length_m,
    readout_l_per_m_h=D3_DEFAULT_FEEDLINE_L_PER_M_H,
    readout_c_per_m_f=D3_DEFAULT_FEEDLINE_C_PER_M_F,
    filter_l_per_m_h=D3_DEFAULT_FEEDLINE_L_PER_M_H,
    filter_c_per_m_f=D3_DEFAULT_FEEDLINE_C_PER_M_F,
    window_start_readout_m=2.25e-3,
    window_start_filter_m=2.25e-3,
    window_length_m=1.5e-3,
    l_matrix_per_m_h=D3_DEFAULT_MTL_L_MATRIX_PER_M_H,
    c_matrix_per_m_f=D3_DEFAULT_MTL_C_MATRIX_PER_M_F,
    coupling_orientation=:same_direction,
    c0r_f=18.0e-15,
    c01_f=65.0e-15,
    c02_f=64.0e-15,
    c12_qubit_f=12.0e-15,
    cr1_f=4.2e-15,
    cr2_f=3.8e-15,
    l_j_per_junction_h=24.0e-9,
    feedline_length_m=1.0e-3,
    feedline_n_sections=20,
    feedline_l_per_m_h=D3_DEFAULT_FEEDLINE_L_PER_M_H,
    feedline_c_per_m_f=D3_DEFAULT_FEEDLINE_C_PER_M_F,
    port_resistance_ohm=50.0,
    readout_breakpoints_m=nothing,
    filter_breakpoints_m=nothing,
    feedline_left_breakpoints_m=nothing,
    feedline_right_breakpoints_m=nothing,
)
    exact_grid_values = (
        readout_breakpoints_m,
        filter_breakpoints_m,
        feedline_left_breakpoints_m,
        feedline_right_breakpoints_m,
    )
    any(value -> !isnothing(value), exact_grid_values) &&
        !all(value -> !isnothing(value), exact_grid_values) &&
        throw(ArgumentError(
            "D3 direct-Hybridized exact grid requires all four boundary arrays.",
        ))
    exact_grid = all(value -> !isnothing(value), exact_grid_values)
    readout_boundaries = exact_grid ? Float64.(collect(readout_breakpoints_m)) : nothing
    filter_boundaries = exact_grid ? Float64.(collect(filter_breakpoints_m)) : nothing
    plan = CircuitPlan(id)
    readout_attachment = external_node("readout_attachment")
    feedline_attachment = external_node("feedline_attachment")
    mtl_model = MTLCoupledRLGCSpec(
        start1_m=window_start_readout_m,
        start2_m=window_start_filter_m,
        length_m=window_length_m,
        section_length_m=mtl_section_length_m,
        l_matrix_per_m_h=l_matrix_per_m_h,
        c_matrix_per_m_f=c_matrix_per_m_f,
    )
    filter = add_intrinsic_interferometric_purcell_filter!(
        plan;
        id="intrinsic_filter",
        readout_attachment=readout_attachment,
        feedline_attachment=feedline_attachment,
        readout_spec=_d3_line_spec(
            length_m=readout_length_m,
            section_length_m=exact_grid ?
                _d3_exact_breakpoint_reference(readout_boundaries) :
                section_length_m,
            l_per_m_h=readout_l_per_m_h,
            c_per_m_f=readout_c_per_m_f,
        ),
        filter_spec=_d3_line_spec(
            length_m=filter_length_m,
            section_length_m=exact_grid ?
                _d3_exact_breakpoint_reference(filter_boundaries) :
                section_length_m,
            l_per_m_h=filter_l_per_m_h,
            c_per_m_f=filter_c_per_m_f,
        ),
        mtl_model=mtl_model,
        coupling_orientation=coupling_orientation,
        c1g_f=idc_filter_ground_capacitance_f,
        c2g_f=idc_feedline_ground_capacitance_f,
        c12_f=idc_mutual_capacitance_f,
        c0r_f=c0r_f,
        readout_breakpoints_m=readout_boundaries,
        filter_breakpoints_m=filter_boundaries,
    )
    island_1 = external_node("island_1")
    island_2 = external_node("island_2")
    component = add_intrinsic_interferometric_purcell_filter_with_qubit!(
        plan;
        id="intrinsic_filter_with_qubit",
        filter=filter,
        island_1=island_1,
        island_2=island_2,
        c0r_f=c0r_f,
        c01_f=c01_f,
        c02_f=c02_f,
        c12_f=c12_qubit_f,
        cr1_f=cr1_f,
        cr2_f=cr2_f,
        l_j_per_junction_h=l_j_per_junction_h,
    )
    feedline = _d3_distributed_feedline!(
        plan;
        center=component.filter.feedline_attachment,
        length_m=feedline_length_m,
        n_sections=feedline_n_sections,
        l_per_m_h=feedline_l_per_m_h,
        c_per_m_f=feedline_c_per_m_f,
        port_resistance_ohm=port_resistance_ohm,
        left_breakpoints_m=feedline_left_breakpoints_m,
        right_breakpoints_m=feedline_right_breakpoints_m,
    )
    labels = Dict(
        :readout_label => raw"$\lambda/4\ \mathrm{readout}$",
        :filter_label => raw"$\lambda/4\ \mathrm{filter}$",
        :capacitive_label => raw"$C_m$",
        :inductive_label => raw"$M$",
        :readout_head_label => raw"$\mathrm{CPW}\ \ell_r^s$",
        :readout_tail_label => raw"$\mathrm{CPW}\ \ell_r^o$",
        :filter_head_label => raw"$\mathrm{CPW}\ \ell_p^s$",
        :filter_tail_label => raw"$\mathrm{CPW}\ \ell_p^o$",
        :mtl_label => raw"$\mathrm{MTL}\ \ell_c$",
        :cpg_label => _d3_engineering_relation_label(plan, component.filter.feedline_capacitor.c1g.id),
        :cfcg_label => _d3_engineering_relation_label(plan, component.filter.feedline_capacitor.c2g.id),
        :cpfc_label => _d3_engineering_relation_label(plan, component.filter.feedline_capacitor.c12.id),
        :c01_label => _d3_engineering_relation_label(plan, component.qubit.c01.id),
        :c02_label => _d3_engineering_relation_label(plan, component.qubit.c02.id),
        :qubit_c12_label => _d3_engineering_relation_label(plan, component.qubit.c12.id),
        :cr1_label => _d3_engineering_relation_label(plan, component.qubit.cr1.id),
        :cr2_label => _d3_engineering_relation_label(plan, component.qubit.cr2.id),
        :lj1_label => _d3_engineering_relation_label(plan, component.qubit.lj1.id),
        :lj2_label => _d3_engineering_relation_label(plan, component.qubit.lj2.id),
        :feedline_left_label => raw"$\mathrm{CPW\ feedline}\ \ell_f/2$",
        :feedline_right_label => raw"$\mathrm{CPW\ feedline}\ \ell_f/2$",
    )
    isnothing(component.c0r) ||
        (labels[:c0r_label] = _d3_engineering_relation_label(plan, component.c0r.id))
    _d3_plan_schematic!(
        plan,
        component,
        feedline;
        id=:d3_intrinsic_purcell_hybridized_circuit_plan,
        component_type=:D3IntrinsicPurcellHybridizedCircuitPlan,
        labels=labels,
        readout_label_placement=:marker,
        readout_label_target=:readout_attachment,
        readout_label_loc=:left,
        filter_node=component.filter.filter_resonator.line.tail,
        filter_node_id=:filter_open_tail,
        filter_label_placement=:marker,
        filter_label_target=:filter_open_tail,
        feedline_model=:split_distributed_cpw,
    )
    return (;
        plan=plan,
        graph=engineering_graph(plan),
        component=component,
        feedline=feedline,
        mtl_model=mtl_model,
    )
end

function _d3_auxiliary_ports(plan, input, output, port_resistance_ohm)
    input_port = external_port!(
        plan;
        id=:input_port,
        index=1,
        endpoint=input,
        resistance=port_resistance_ohm,
        role=:input_probe,
    )
    output_port = external_port!(
        plan;
        id=:output_port,
        index=2,
        endpoint=output,
        resistance=port_resistance_ohm,
        role=:output_probe,
    )
    return (; input=input_port, output=output_port)
end

function _d3_auxiliary_port_labels(plan)
    graph = engineering_graph(plan)
    return Dict(
        :input_port_label => _d3_port_label(graph.ports[:input_port]),
        :output_port_label => _d3_port_label(graph.ports[:output_port]),
        :input_port_resistance_label =>
            _d3_port_resistance_label(graph.ports[:input_port]),
        :output_port_resistance_label =>
            _d3_port_resistance_label(graph.ports[:output_port]),
    )
end

"""
Build linewidth extraction L_A for the Equivalent family.

The readout coordinate and every r-p off-diagonal term are absent. The
filter-side diagonal contributions of Cp/Lp and Cn/Ln remain as two grounded
parallel LC components, while the full three-branch IDC, two fixed matched-TL
port-node regularizer sections, and both matched external ports remain
connected.
"""
function build_d3_linewidth_la_equivalent_circuit_plan(;
    id="d3-linewidth-la-equivalent-circuit-plan",
    idc_filter_ground_capacitance_f,
    idc_feedline_ground_capacitance_f,
    idc_mutual_capacitance_f,
    filter_capacitance_f=480.0e-15,
    filter_inductance_h=1.46e-9,
    bridge_capacitance_f=8.0e-15,
    bridge_inductance_h=35.0e-9,
    port_resistance_ohm=50.0,
)
    plan = CircuitPlan(id)
    filter_node = external_node("linewidth_la_filter")
    feedline_attachment = external_node("linewidth_la_feedline_attachment")
    filter_resonator = add_parallel_lc_resonator!(
        plan;
        id=:linewidth_la_filter_resonator,
        node=filter_node,
        capacitance=filter_capacitance_f,
        inductance=filter_inductance_h,
        capacitor_label=raw"$C_p$",
        inductor_label=raw"$L_p$",
    )
    diagonal_bridge_loading = add_parallel_lc_resonator!(
        plan;
        id=:linewidth_la_diagonal_bridge_loading,
        node=filter_node,
        capacitance=bridge_capacitance_f,
        inductance=bridge_inductance_h,
        capacitor_label=raw"$C_n^{\mathrm{diag}}$",
        inductor_label=raw"$L_n^{\mathrm{diag}}$",
    )
    feedline_capacitor = add_interdigitated_capacitor!(
        plan;
        id=:linewidth_la_feedline_idc,
        terminal_1=filter_node,
        terminal_2=feedline_attachment,
        c1g_f=idc_filter_ground_capacitance_f,
        c2g_f=idc_feedline_ground_capacitance_f,
        c12_f=idc_mutual_capacitance_f,
        c1g_label=raw"$C_{pG}^{\mathrm{IDC}}$",
        c2g_label=raw"$C_{f_cG}^{\mathrm{IDC}}$",
        c12_label=raw"$C_{pf_c}^{\mathrm{IDC}}$",
    )
    feedline = _d3_matched_port_regularizer!(
        plan;
        center=feedline_attachment,
        port_resistance_ohm=port_resistance_ohm,
    )
    component_id = :d3_linewidth_la_equivalent
    record_engineering_component!(
        plan;
        id=component_id,
        display_name="D3 linewidth L_A equivalent calibration",
        component_type=:D3LinewidthLAEquivalentCircuitPlan,
        role=:linewidth_loaded_bare_calibration,
        parameters=Dict(
            :internal_coupling_state => :off_diagonal_suppressed,
            :diagonal_loading => :retained,
            :external_coupling_state => :on,
            :feedline_model => :matched_port_regularizer_two_pi,
            :regularizer_series_inductance_h =>
                D3_PORT_REGULARIZER_SERIES_INDUCTANCE_H,
            :regularizer_section_capacitance_f =>
                D3_PORT_REGULARIZER_SECTION_CAPACITANCE_F,
            :regularizer_characteristic_impedance_ohm =>
                D3_PORT_REGULARIZER_CHARACTERISTIC_IMPEDANCE_OHM,
            :regularizer_section_length_m =>
                D3_PORT_REGULARIZER_SECTION_LENGTH_M,
            :regularizer_physical_role => :numerical_port_node_regularization_only,
        ),
        pins=[:filter, :feedline_attachment],
    )
    labels = merge(
        Dict(
            :cp_label => _d3_engineering_relation_label(plan, filter_resonator.capacitor.id),
            :lp_label => _d3_engineering_relation_label(plan, filter_resonator.inductor.id),
            :cn_diag_label =>
                _d3_engineering_relation_label(plan, diagonal_bridge_loading.capacitor.id),
            :ln_diag_label =>
                _d3_engineering_relation_label(plan, diagonal_bridge_loading.inductor.id),
            :cpg_label => _d3_engineering_relation_label(plan, feedline_capacitor.c1g.id),
            :cfcg_label => _d3_engineering_relation_label(plan, feedline_capacitor.c2g.id),
            :cpfc_label => _d3_engineering_relation_label(plan, feedline_capacitor.c12.id),
            :feedline_regularizer_inductance_label => raw"$L_{\mathrm{sep}}$",
            :feedline_regularizer_half_capacitance_label => raw"$C_{\mathrm{sep}}/2$",
            :feedline_regularizer_center_capacitance_label => raw"$C_{\mathrm{sep}}$",
        ),
        _d3_auxiliary_port_labels(plan),
    )
    _d3_schemdraw_schematic!(
        plan;
        id=:d3_linewidth_la_equivalent_circuit_plan,
        component_type=:D3LinewidthLAEquivalentCircuitPlan,
        component_id=component_id,
        unit_length=1.5,
        labels=labels,
        parameters=Dict(
            :extraction_id => :linewidth_la,
            :internal_coupling_state => :qrp_off,
            :external_coupling_state => :on,
            :feedline_model => :matched_port_regularizer_two_pi,
            :regularizer_series_inductance_h =>
                D3_PORT_REGULARIZER_SERIES_INDUCTANCE_H,
            :regularizer_section_capacitance_f =>
                D3_PORT_REGULARIZER_SECTION_CAPACITANCE_F,
            :regularizer_characteristic_impedance_ohm =>
                D3_PORT_REGULARIZER_CHARACTERISTIC_IMPEDANCE_OHM,
            :regularizer_section_length_m =>
                D3_PORT_REGULARIZER_SECTION_LENGTH_M,
            :regularizer_physical_role => :numerical_port_node_regularization_only,
        ),
        terminals=[
            (id=:input_port, endpoint=feedline.input, side=:left, kind=:port, label=raw"$P_1$"),
            (id=:output_port, endpoint=feedline.output, side=:right, kind=:port, label=raw"$P_2$"),
        ],
        node_labels=[
            (
                id=:filter,
                target=filter_node,
                label=raw"$p$",
                hints=Dict(:placement => :marker, :placement_target => :filter, :loc => :top, :offset => 0.28),
            ),
            (
                id=:feedline_attachment,
                target=feedline_attachment,
                label=raw"$f_c$",
                hints=Dict(:placement => :marker, :placement_target => :feedline_center, :loc => :bottom, :offset => (-0.48, -0.28)),
            ),
            (
                id=:feedline_left,
                target=feedline.input,
                label=raw"$f_1$",
                hints=Dict(:placement => :bus_middle, :placement_target => :feedline_left, :loc => :top, :offset => 0.28),
            ),
            (
                id=:feedline_right,
                target=feedline.output,
                label=raw"$f_2$",
                hints=Dict(:placement => :bus_middle, :placement_target => :feedline_right, :loc => :top, :offset => 0.28),
            ),
        ],
        node_bindings=Dict(
            :filter => filter_node,
            :feedline_attachment => feedline_attachment,
            :feedline_left => feedline.input,
            :feedline_right => feedline.output,
        ),
    )
    return (;
        plan=plan,
        graph=engineering_graph(plan),
        component=(;
            id=component_id,
            filter_node=filter_node,
            feedline_attachment=feedline_attachment,
            filter_resonator=filter_resonator,
            diagonal_bridge_loading=diagonal_bridge_loading,
            feedline_capacitor=feedline_capacitor,
        ),
        feedline=feedline,
    )
end

"""
Build linewidth extraction L_A for the Hybridized family.

The filter line keeps the uncoupled conductor's MTL diagonal RLGC section.
Mutual RLGC terms and the readout conductor are absent; the complete
three-branch IDC, the two distributed feedline halves joined at `f_c`, and
matched ports remain connected.
"""
function build_d3_linewidth_la_hybridized_circuit_plan(;
    id="d3-linewidth-la-hybridized-circuit-plan",
    idc_filter_ground_capacitance_f,
    idc_feedline_ground_capacitance_f,
    idc_mutual_capacitance_f,
    filter_length_m=6.0e-3,
    section_length_m=0.75e-3,
    mtl_section_length_m=section_length_m,
    filter_l_per_m_h=D3_DEFAULT_FEEDLINE_L_PER_M_H,
    filter_c_per_m_f=D3_DEFAULT_FEEDLINE_C_PER_M_F,
    window_start_filter_m=2.25e-3,
    window_length_m=1.5e-3,
    l_matrix_per_m_h=D3_DEFAULT_MTL_L_MATRIX_PER_M_H,
    c_matrix_per_m_f=D3_DEFAULT_MTL_C_MATRIX_PER_M_F,
    feedline_length_m=1.0e-3,
    feedline_n_sections=20,
    feedline_l_per_m_h=D3_DEFAULT_FEEDLINE_L_PER_M_H,
    feedline_c_per_m_f=D3_DEFAULT_FEEDLINE_C_PER_M_F,
    port_resistance_ohm=50.0,
)
    plan = CircuitPlan(id)
    filter_grounded_head = external_node("linewidth_la_filter_grounded_head")
    filter_open_tail = external_node("linewidth_la_filter_open_tail")
    feedline_attachment = external_node("linewidth_la_feedline_attachment")
    mtl_model = MTLCoupledRLGCSpec(
        start1_m=window_start_filter_m,
        start2_m=window_start_filter_m,
        length_m=window_length_m,
        section_length_m=mtl_section_length_m,
        l_matrix_per_m_h=l_matrix_per_m_h,
        c_matrix_per_m_f=c_matrix_per_m_f,
    )
    filter_resonator = add_quarter_wave_resonator!(
        plan;
        id=:linewidth_la_filter_resonator,
        grounded_head=filter_grounded_head,
        open_tail=filter_open_tail,
        spec=_d3_line_spec(
            length_m=filter_length_m,
            section_length_m=section_length_m,
            l_per_m_h=filter_l_per_m_h,
            c_per_m_f=filter_c_per_m_f,
        ),
        breakpoints_m=_d3_mtl_window_breakpoints(
            window_start_filter_m,
            window_length_m,
            mtl_section_length_m,
        ),
        section_overrides=[coupled_line_section_override(mtl_model, 2)],
    )
    feedline_capacitor = add_interdigitated_capacitor!(
        plan;
        id=:linewidth_la_feedline_idc,
        terminal_1=filter_open_tail,
        terminal_2=feedline_attachment,
        c1g_f=idc_filter_ground_capacitance_f,
        c2g_f=idc_feedline_ground_capacitance_f,
        c12_f=idc_mutual_capacitance_f,
        c1g_label=raw"$C_{pG}^{\mathrm{IDC}}$",
        c2g_label=raw"$C_{f_cG}^{\mathrm{IDC}}$",
        c12_label=raw"$C_{pf_c}^{\mathrm{IDC}}$",
    )
    feedline = _d3_distributed_feedline!(
        plan;
        center=feedline_attachment,
        length_m=feedline_length_m,
        n_sections=feedline_n_sections,
        l_per_m_h=feedline_l_per_m_h,
        c_per_m_f=feedline_c_per_m_f,
        port_resistance_ohm=port_resistance_ohm,
    )
    component_id = :d3_linewidth_la_hybridized
    record_engineering_component!(
        plan;
        id=component_id,
        display_name="D3 linewidth L_A hybridized calibration",
        component_type=:D3LinewidthLAHybridizedCircuitPlan,
        role=:linewidth_loaded_bare_calibration,
        parameters=Dict(
            :internal_coupling_state => :off_diagonal_suppressed,
            :diagonal_loading => :mtl_filter_conductor_retained,
            :external_coupling_state => :on,
            :feedline_model => :split_distributed_cpw,
        ),
        pins=[:filter_open_tail, :feedline_attachment],
    )
    labels = merge(
        Dict(
            :filter_head_label => raw"$\mathrm{CPW}\ \ell_p^s$",
            :filter_diagonal_label => raw"$\mathrm{MTL\ diagonal}\ \ell_c$",
            :filter_tail_label => raw"$\mathrm{CPW}\ \ell_p^o$",
            :cpg_label => _d3_engineering_relation_label(plan, feedline_capacitor.c1g.id),
            :cfcg_label => _d3_engineering_relation_label(plan, feedline_capacitor.c2g.id),
            :cpfc_label => _d3_engineering_relation_label(plan, feedline_capacitor.c12.id),
            :feedline_left_label => raw"$\mathrm{CPW\ feedline}\ \ell_f/2$",
            :feedline_right_label => raw"$\mathrm{CPW\ feedline}\ \ell_f/2$",
        ),
        _d3_auxiliary_port_labels(plan),
    )
    _d3_schemdraw_schematic!(
        plan;
        id=:d3_linewidth_la_hybridized_circuit_plan,
        component_type=:D3LinewidthLAHybridizedCircuitPlan,
        component_id=component_id,
        unit_length=1.5,
        labels=labels,
        parameters=Dict(
            :extraction_id => :linewidth_la,
            :internal_coupling_state => :qrp_off,
            :external_coupling_state => :on,
            :feedline_model => :split_distributed_cpw,
        ),
        terminals=[
            (id=:input_port, endpoint=feedline.input, side=:left, kind=:port, label=raw"$P_1$"),
            (id=:output_port, endpoint=feedline.output, side=:right, kind=:port, label=raw"$P_2$"),
        ],
        node_labels=[
            (
                id=:filter,
                target=filter_open_tail,
                label=raw"$p$",
                hints=Dict(:placement => :marker, :placement_target => :filter, :loc => :top, :offset => 0.28),
            ),
            (
                id=:feedline_attachment,
                target=feedline_attachment,
                label=raw"$f_c$",
                hints=Dict(:placement => :marker, :placement_target => :feedline_center, :loc => :bottom, :offset => 0.28),
            ),
            (
                id=:feedline_left,
                target=feedline.input,
                label=raw"$f_1$",
                hints=Dict(:placement => :bus_middle, :placement_target => :feedline_left, :loc => :top, :offset => 0.28),
            ),
            (
                id=:feedline_right,
                target=feedline.output,
                label=raw"$f_2$",
                hints=Dict(:placement => :bus_middle, :placement_target => :feedline_right, :loc => :top, :offset => 0.28),
            ),
        ],
        node_bindings=Dict(
            :filter => filter_open_tail,
            :feedline_attachment => feedline_attachment,
            :feedline_left => feedline.input,
            :feedline_right => feedline.output,
        ),
    )
    return (;
        plan=plan,
        graph=engineering_graph(plan),
        component=(;
            id=component_id,
            filter_open_tail=filter_open_tail,
            feedline_attachment=feedline_attachment,
            filter_resonator=filter_resonator,
            feedline_capacitor=feedline_capacitor,
        ),
        feedline=feedline,
        mtl_model=mtl_model,
    )
end

"""Build the Equivalent intrinsic-pair RP-on circuit for the Z21 notch."""
function build_d3_intrinsic_pair_notch_equivalent_circuit_plan(;
    id="d3-intrinsic-pair-notch-equivalent-circuit-plan",
    readout_capacitance_f=500.0e-15,
    readout_inductance_h=1.40e-9,
    filter_capacitance_f=480.0e-15,
    filter_inductance_h=1.46e-9,
    bridge_capacitance_f=8.0e-15,
    bridge_inductance_h=35.0e-9,
    port_resistance_ohm=50.0,
)
    plan = CircuitPlan(id)
    readout = external_node("intrinsic_pair_readout_open_tail")
    filter = external_node("intrinsic_pair_filter_open_tail")
    readout_resonator = add_parallel_lc_resonator!(
        plan;
        id=:intrinsic_pair_readout_resonator,
        node=readout,
        capacitance=readout_capacitance_f,
        inductance=readout_inductance_h,
        capacitor_label=raw"$C_r$",
        inductor_label=raw"$L_r$",
    )
    filter_resonator = add_parallel_lc_resonator!(
        plan;
        id=:intrinsic_pair_filter_resonator,
        node=filter,
        capacitance=filter_capacitance_f,
        inductance=filter_inductance_h,
        capacitor_label=raw"$C_p$",
        inductor_label=raw"$L_p$",
    )
    bridge_capacitor = couple_capacitive!(
        plan;
        id=:intrinsic_pair_bridge_capacitor,
        from=readout,
        to=filter,
        capacitance=bridge_capacitance_f,
        role=:intrinsic_pair_bridge_capacitance,
        label=raw"$C_n$",
    )
    bridge_inductor = series_inductor!(
        plan;
        id=:intrinsic_pair_bridge_inductor,
        from=readout,
        to=filter,
        inductance=bridge_inductance_h,
        role=:intrinsic_pair_bridge_inductance,
        label=raw"$L_n$",
    )
    _d3_auxiliary_ports(plan, readout, filter, port_resistance_ohm)
    component_id = :d3_intrinsic_pair_notch_equivalent
    record_engineering_component!(
        plan;
        id=component_id,
        display_name="D3 equivalent intrinsic-pair notch",
        component_type=:D3IntrinsicPairNotchEquivalentCircuitPlan,
        role=:intrinsic_pair_notch_extraction,
        parameters=Dict(
            :coupling_state => :rp_on,
            :excluded_subsystems => (:qubit, :c0r, :idc, :feedline),
            :observable => :z21,
        ),
        pins=[:readout_open_tail, :filter_open_tail],
    )
    labels = merge(
        Dict(
            :cr_label => _d3_engineering_relation_label(plan, readout_resonator.capacitor.id),
            :lr_label => _d3_engineering_relation_label(plan, readout_resonator.inductor.id),
            :cp_label => _d3_engineering_relation_label(plan, filter_resonator.capacitor.id),
            :lp_label => _d3_engineering_relation_label(plan, filter_resonator.inductor.id),
            :cn_label => _d3_engineering_relation_label(plan, bridge_capacitor.id),
            :ln_label => _d3_engineering_relation_label(plan, bridge_inductor.id),
        ),
        _d3_auxiliary_port_labels(plan),
    )
    _d3_schemdraw_schematic!(
        plan;
        id=:d3_intrinsic_pair_notch_equivalent_circuit_plan,
        component_type=:D3IntrinsicPairNotchEquivalentCircuitPlan,
        component_id=component_id,
        unit_length=1.5,
        labels=labels,
        parameters=Dict(
            :extraction_id => :intrinsic_pair_z21_zero,
            :coupling_state => :rp_on,
        ),
        terminals=[
            (id=:input_port, endpoint=readout, side=:left, kind=:port, label=raw"$P_r$"),
            (id=:output_port, endpoint=filter, side=:right, kind=:port, label=raw"$P_p$"),
        ],
        node_labels=[
            (
                id=:readout,
                target=readout,
                label=raw"$r$",
                hints=Dict(:placement => :marker, :placement_target => :readout, :loc => :top, :offset => 0.28),
            ),
            (
                id=:filter,
                target=filter,
                label=raw"$p$",
                hints=Dict(:placement => :marker, :placement_target => :filter, :loc => :top, :offset => 0.28),
            ),
        ],
        node_bindings=Dict(:readout => readout, :filter => filter),
    )
    return (;
        plan=plan,
        graph=engineering_graph(plan),
        component=(;
            id=component_id,
            readout=readout,
            filter=filter,
            readout_resonator=readout_resonator,
            filter_resonator=filter_resonator,
            bridge_capacitor=bridge_capacitor,
            bridge_inductor=bridge_inductor,
        ),
    )
end

"""Build the distributed intrinsic-pair RP-on circuit for the Z21 notch."""
function build_d3_intrinsic_pair_notch_hybridized_circuit_plan(;
    id="d3-intrinsic-pair-notch-hybridized-circuit-plan",
    readout_length_m=6.0e-3,
    filter_length_m=6.0e-3,
    section_length_m=0.75e-3,
    mtl_section_length_m=section_length_m,
    readout_l_per_m_h=D3_DEFAULT_FEEDLINE_L_PER_M_H,
    readout_c_per_m_f=D3_DEFAULT_FEEDLINE_C_PER_M_F,
    filter_l_per_m_h=D3_DEFAULT_FEEDLINE_L_PER_M_H,
    filter_c_per_m_f=D3_DEFAULT_FEEDLINE_C_PER_M_F,
    window_start_readout_m=2.25e-3,
    window_start_filter_m=2.25e-3,
    window_length_m=1.5e-3,
    l_matrix_per_m_h=D3_DEFAULT_MTL_L_MATRIX_PER_M_H,
    c_matrix_per_m_f=D3_DEFAULT_MTL_C_MATRIX_PER_M_F,
    coupling_orientation=:same_direction,
    port_resistance_ohm=50.0,
    readout_breakpoints_m=nothing,
    filter_breakpoints_m=nothing,
)
    exact_grid_values = (readout_breakpoints_m, filter_breakpoints_m)
    any(value -> !isnothing(value), exact_grid_values) &&
        !all(value -> !isnothing(value), exact_grid_values) &&
        throw(ArgumentError(
            "D3 Hybridized notch exact grid requires both resonator boundary arrays.",
        ))
    exact_grid = all(value -> !isnothing(value), exact_grid_values)
    readout_boundaries = exact_grid ? Float64.(collect(readout_breakpoints_m)) : nothing
    filter_boundaries = exact_grid ? Float64.(collect(filter_breakpoints_m)) : nothing
    plan = CircuitPlan(id)
    readout_grounded_head = external_node("intrinsic_pair_readout_grounded_head")
    readout_open_tail = external_node("intrinsic_pair_readout_open_tail")
    filter_grounded_head = external_node("intrinsic_pair_filter_grounded_head")
    filter_open_tail = external_node("intrinsic_pair_filter_open_tail")
    mtl_model = MTLCoupledRLGCSpec(
        start1_m=window_start_readout_m,
        start2_m=window_start_filter_m,
        length_m=window_length_m,
        section_length_m=mtl_section_length_m,
        l_matrix_per_m_h=l_matrix_per_m_h,
        c_matrix_per_m_f=c_matrix_per_m_f,
    )
    readout_resonator = add_quarter_wave_resonator!(
        plan;
        id=:intrinsic_pair_readout_resonator,
        grounded_head=readout_grounded_head,
        open_tail=readout_open_tail,
        spec=_d3_line_spec(
            length_m=readout_length_m,
            section_length_m=exact_grid ?
                _d3_exact_breakpoint_reference(readout_boundaries) :
                section_length_m,
            l_per_m_h=readout_l_per_m_h,
            c_per_m_f=readout_c_per_m_f,
        ),
        breakpoints_m=exact_grid ? readout_boundaries :
            _d3_mtl_window_breakpoints(
                window_start_readout_m,
                window_length_m,
                mtl_section_length_m,
            ),
        section_overrides=[coupled_line_section_override(mtl_model, 1)],
    )
    filter_resonator = add_quarter_wave_resonator!(
        plan;
        id=:intrinsic_pair_filter_resonator,
        grounded_head=filter_grounded_head,
        open_tail=filter_open_tail,
        spec=_d3_line_spec(
            length_m=filter_length_m,
            section_length_m=exact_grid ?
                _d3_exact_breakpoint_reference(filter_boundaries) :
                section_length_m,
            l_per_m_h=filter_l_per_m_h,
            c_per_m_f=filter_c_per_m_f,
        ),
        breakpoints_m=exact_grid ? filter_boundaries :
            _d3_mtl_window_breakpoints(
                window_start_filter_m,
                window_length_m,
                mtl_section_length_m,
            ),
        section_overrides=[coupled_line_section_override(mtl_model, 2)],
    )
    window = couple_transmission_window!(
        plan;
        id=:intrinsic_pair_mtl_window,
        line1=readout_resonator.line,
        line2=filter_resonator.line,
        start1=window_start_readout_m,
        start2=window_start_filter_m,
        length=window_length_m,
        model=mtl_model,
        coupling_orientation=coupling_orientation,
    )
    _d3_auxiliary_ports(
        plan,
        readout_open_tail,
        filter_open_tail,
        port_resistance_ohm,
    )
    component_id = :d3_intrinsic_pair_notch_hybridized
    record_engineering_component!(
        plan;
        id=component_id,
        display_name="D3 hybridized intrinsic-pair notch",
        component_type=:D3IntrinsicPairNotchHybridizedCircuitPlan,
        role=:intrinsic_pair_notch_extraction,
        parameters=Dict(
            :coupling_state => :rp_on,
            :coupling_orientation => coupling_orientation,
            :excluded_subsystems => (:qubit, :c0r, :idc, :feedline),
            :observable => :z21,
        ),
        pins=[:readout_open_tail, :filter_open_tail],
    )
    labels = merge(
        Dict(
            :readout_head_label => raw"$\mathrm{CPW}\ \ell_r^s$",
            :readout_tail_label => raw"$\mathrm{CPW}\ \ell_r^o$",
            :filter_head_label => raw"$\mathrm{CPW}\ \ell_p^s$",
            :filter_tail_label => raw"$\mathrm{CPW}\ \ell_p^o$",
            :mtl_label => raw"$\mathrm{MTL}\ \ell_c$",
        ),
        _d3_auxiliary_port_labels(plan),
    )
    _d3_schemdraw_schematic!(
        plan;
        id=:d3_intrinsic_pair_notch_hybridized_circuit_plan,
        component_type=:D3IntrinsicPairNotchHybridizedCircuitPlan,
        component_id=component_id,
        unit_length=1.5,
        labels=labels,
        parameters=Dict(
            :extraction_id => :intrinsic_pair_z21_zero,
            :coupling_state => :rp_on,
            :coupling_orientation => coupling_orientation,
        ),
        terminals=[
            (id=:input_port, endpoint=readout_open_tail, side=:right, kind=:port, label=raw"$P_r$"),
            (id=:output_port, endpoint=filter_open_tail, side=:right, kind=:port, label=raw"$P_p$"),
        ],
        node_labels=[
            (
                id=:readout,
                target=readout_open_tail,
                label=raw"$r$",
                hints=Dict(:placement => :marker, :placement_target => :readout, :loc => :top, :offset => 0.28),
            ),
            (
                id=:filter,
                target=filter_open_tail,
                label=raw"$p$",
                hints=Dict(:placement => :marker, :placement_target => :filter, :loc => :bottom, :offset => 0.28),
            ),
        ],
        node_bindings=Dict(
            :readout => readout_open_tail,
            :filter => filter_open_tail,
        ),
    )
    return (;
        plan=plan,
        graph=engineering_graph(plan),
        component=(;
            id=component_id,
            readout_open_tail=readout_open_tail,
            filter_open_tail=filter_open_tail,
            readout_resonator=readout_resonator,
            filter_resonator=filter_resonator,
            window=window,
        ),
        mtl_model=mtl_model,
    )
end
