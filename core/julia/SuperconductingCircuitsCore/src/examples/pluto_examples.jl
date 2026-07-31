# These public example builders expose thin notebook-facing Core workflows.
# Ideal parallel-LC physics and the raw/PTC/S observable distinction:
# https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/ideal-parallel-lc-resonator.qmd
# Their HB intent, mode, and evidence semantics are canonical at:
# https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/numerical-methods/harmonic-balance-periodic-steady-state.qmd
# Coupled-line examples implement the canonical matrix semantics documented at:
# https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/transmission-lines/multiconductor-rlgc-matrix-semantics.qmd

const DEFAULT_CPW_L_PER_M_H = 404.313e-9
const DEFAULT_CPW_C_PER_M_F = 179.86e-12
const DEFAULT_COUPLED_MTL_L_MATRIX_PER_M_H = [
    410.86374 19.08527
    19.08527 410.85454
] .* 1e-9
const DEFAULT_COUPLED_MTL_C_MATRIX_PER_M_F = [
    170.29805 -8.09678
    -8.09678 170.29538
] .* 1e-12
const DEFAULT_FLOATING_XY_C_G1_F = 102.4903555082012e-15
const DEFAULT_FLOATING_XY_C_G2_F = 101.8251170216874e-15
const DEFAULT_FLOATING_XY_C_Q_F = 58.12081132735904e-15
const DEFAULT_FLOATING_XY_C_XY1_F = 0.1742182638751523e-15
const DEFAULT_FLOATING_XY_C_XY2_F = 0.7451414067385129e-15
const DEFAULT_FLOATING_XY_C_XY_GROUND_F = 627.8043424559959e-15
const DEFAULT_FLOATING_XY_L_JUN_H = 24.0e-9

function _example_frequency_sweep(start_frequency, stop_frequency, point_count)
    point_count > 0 || _validation_error("point_count must be positive.")
    point_count == 1 && return [Float64(start_frequency)]
    return range(Float64(start_frequency), Float64(stop_frequency); length=Int(point_count))
end

function _port_hb_intent!(
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

function _prepare_example(
    plan::CircuitPlan;
    start_frequency,
    stop_frequency,
    point_count,
    pump_frequency,
    pump_current,
    optional_hb_kwargs,
)
    compiled = compile_to_josephson(plan)
    hb_problem = build_hb_problem(
        compiled,
        HBRunSpec(
            frequency_sweep=_example_frequency_sweep(start_frequency, stop_frequency, point_count),
            pump_frequencies=Dict(:pump => Float64(pump_frequency)),
            source_currents=Dict(:pump_in => Float64(pump_current)),
            optional_hb_kwargs=Dict{Symbol,Any}(optional_hb_kwargs),
        ),
    )
    return (
        plan=plan,
        graph=engineering_graph(plan),
        compiled=compiled,
        hb_problem=hb_problem,
        output_request_report=validate_output_request_configuration(compiled, hb_problem),
    )
end

function _default_line_spec(; length_m, section_length_m, l_per_m_h=DEFAULT_CPW_L_PER_M_H, c_per_m_f=DEFAULT_CPW_C_PER_M_F)
    return RLGCSpec(
        length_m=length_m,
        section_length_m=section_length_m,
        l_per_m_h=l_per_m_h,
        c_per_m_f=c_per_m_f,
    )
end

function _external_two_port!(plan::CircuitPlan; input, output, port_resistance)
    external_port!(plan; id=:input_port, index=1, endpoint=input, resistance=port_resistance, role=:signal)
    external_port!(plan; id=:output_port, index=2, endpoint=output, resistance=port_resistance, role=:readout)
    return nothing
end

function _engineering_relation_label(plan::CircuitPlan, relation_id)
    selected_id = Symbol(relation_id)
    for relation in engineering_graph(plan).relations
        relation.id == selected_id && return relation.label
    end
    _validation_error("Missing engineering relation label for '$(selected_id)'.")
end

function _port_label(port::EngineeringPort)
    return "\$P_$(port.port_index)\$"
end

function _port_resistance_label(port::EngineeringPort)
    isapprox(port.resistance, 50.0) && return raw"$R_{50}$"
    return "\$R_{$(port.resistance)}\$"
end

function _schemdraw_schematic!(
    plan::CircuitPlan;
    id,
    component_type,
    component_id,
    unit_length,
    labels,
    parameters=Dict{Symbol,Any}(),
    tracks=NamedTuple[],
    segments=NamedTuple[],
    coupled_spans=NamedTuple[],
    terminals=NamedTuple[],
    node_labels=NamedTuple[],
    node_bindings=nothing,
)
    render_parameters = Dict{Symbol,Any}(:component_id => string(component_id))
    merge!(render_parameters, Dict{Symbol,Any}(parameters))
    schemdraw_hints = Dict{Symbol,Any}(
        :component_type => string(component_type),
        :unit_length => Float64(unit_length),
        :labels => Dict{Symbol,Any}(labels),
        :parameters => render_parameters,
    )
    if !isnothing(node_bindings)
        serialized_bindings = Dict(
            _engineering_symbol(role) => _schematic_endpoint_ref(endpoint)
            for (role, endpoint) in pairs(node_bindings)
        )
        label_roles = [_engineering_symbol(label.id) for label in node_labels]
        length(unique(label_roles)) == length(label_roles) ||
            _validation_error("Schematic physical-node label roles must be unique.")
        Set(keys(serialized_bindings)) == Set(label_roles) ||
            _validation_error("Schematic node_bindings must cover every physical-node label role exactly.")
        length(unique(values(serialized_bindings))) == length(serialized_bindings) ||
            _validation_error("Schematic node_bindings endpoints must be unique.")
        for label in node_labels
            role = _engineering_symbol(label.id)
            serialized_bindings[role] == _schematic_endpoint_ref(label.target) ||
                _validation_error("Schematic node binding '$(role)' must match its physical-node label target.")
        end
        schemdraw_hints[:node_bindings] = serialized_bindings
    end
    return schematic!(
        plan;
        id=id,
        render_hints=Dict(:schemdraw => schemdraw_hints),
    ) do intent
        for track in tracks
            record_schematic_track!(intent; track...)
        end
        for segment in segments
            record_schematic_segment!(intent; segment...)
        end
        for span in coupled_spans
            record_schematic_coupled_span!(intent; span...)
        end
        for terminal in terminals
            record_schematic_terminal!(
                intent;
                id=terminal.id,
                endpoint=terminal.endpoint,
                side=terminal.side,
                kind=haskey(terminal, :kind) ? terminal.kind : :port,
                label=terminal.label,
            )
        end
        for label in node_labels
            record_schematic_node_label!(intent; label...)
        end
    end
end

"""
    build_parallel_lc_resonator_example(; kwargs...)

Build the executable one-port parallel-LC teaching example, including its
`CircuitPlan`, compiled JosephsonCircuits representation, and pump-off HB
problem. The external port compiler emits an explicit resistance shunt, so raw
Z/Y traces belong to the compiled port network rather than the isolated tank.
"""
function build_parallel_lc_resonator_example(;
    id="parallel-lc-resonator-example",
    capacitance=58.2e-15,
    inductance=21.5e-9,
    port_resistance=50.0,
    start_frequency=1.0e9,
    stop_frequency=10.0e9,
    point_count=1000,
    pump_frequency=8.0e9,
    pump_current=0.0,
    optional_hb_kwargs=Dict{Symbol,Any}(:nbatches => 1, :iterations => 120, :ftol => 1e-8),
)
    plan = CircuitPlan(id)
    signal = external_node("signal")
    signal_port = external_port!(plan; id=:signal_port, index=1, endpoint=signal, resistance=port_resistance, role=:mixed)
    resonator = add_parallel_lc_resonator!(
        plan;
        id="resonator",
        node=signal,
        capacitance=capacitance,
        inductance=inductance,
    )
    _schemdraw_schematic!(
        plan;
        id=:pluto_00_grounded_lc,
        component_type=:GroundedLCResonator,
        component_id=:resonator,
        unit_length=3.0,
        labels=Dict(
            :c_label => _engineering_relation_label(plan, resonator.capacitor.id),
            :l_label => _engineering_relation_label(plan, resonator.inductor.id),
            :port_label => _port_label(signal_port),
            :resistance_label => _port_resistance_label(signal_port),
        ),
        parameters=Dict(
            :inductive_branch_kind =>
                engineering_graph(plan).components[:resonator].parameters[:inductive_branch_kind],
            :port_resistance_ohm => signal_port.resistance,
        ),
        terminals=[
            (id=:signal_port_terminal, endpoint=signal, side=:left, label=_port_label(signal_port)),
        ],
        node_labels=[
            (id=:signal_node_label, target=signal, label="signal"),
        ],
    )
    _port_hb_intent!(plan; ports=[:signal_port])
    example = _prepare_example(
        plan;
        start_frequency=start_frequency,
        stop_frequency=stop_frequency,
        point_count=point_count,
        pump_frequency=pump_frequency,
        pump_current=pump_current,
        optional_hb_kwargs=optional_hb_kwargs,
    )
    return merge(example, (; resonator=resonator, f0_estimate_hz=1 / (2π * sqrt(inductance * capacitance))))
end

function build_reflective_jpa_capacitive_coupled_lc_example(;
    id="reflective-jpa-capacitive-coupled-lc-example",
    coupling_capacitance=16.0e-15,
    resonator_capacitance=90.0e-15,
    linear_inductance=nothing,
    josephson_inductance=7.5e-9,
    junction_capacitance=nothing,
    port_resistance=50.0,
    start_frequency=4.0e9,
    stop_frequency=9.0e9,
    point_count=1000,
    pump_frequency=12.0e9,
    pump_current=0.12e-6,
    optional_hb_kwargs=Dict{Symbol,Any}(:nbatches => 1, :iterations => 160, :ftol => 1e-8),
)
    plan = CircuitPlan(id)
    port_node = external_node("signal")
    resonator_node = external_node("jpa_resonator")
    signal_port = external_port!(plan; id=:signal_port, index=1, endpoint=port_node, resistance=port_resistance, role=:signal)
    jpa = add_reflective_jpa!(
        plan;
        id="jpa",
        port_node=port_node,
        resonator_node=resonator_node,
        coupling_capacitance=coupling_capacitance,
        resonator_capacitance=resonator_capacitance,
        josephson_inductance=josephson_inductance,
    )
    _schemdraw_schematic!(
        plan;
        id=:pluto_01_reflective_jpa,
        component_type=:CapacitivelyCoupledGroundedLCResonator,
        component_id=:jpa,
        unit_length=2.55,
        labels=Dict(
            :coupling_label => _engineering_relation_label(plan, jpa.coupling_capacitor.id),
            :c_label => _engineering_relation_label(plan, jpa.shunt_capacitor.id),
            :junction_label => _engineering_relation_label(plan, jpa.junction.id),
            :port_label => _port_label(signal_port),
            :resistance_label => _port_resistance_label(signal_port),
        ),
        parameters=Dict(
            :inductive_branch_kind =>
                engineering_graph(plan).components[:jpa].parameters[:inductive_branch_kind],
            :port_resistance_ohm => signal_port.resistance,
        ),
        terminals=[
            (id=:signal_port_terminal, endpoint=port_node, side=:right, label=_port_label(signal_port)),
        ],
        node_labels=[
            (id=:port_node_label, target=port_node, label="signal"),
            (id=:resonator_node_label, target=resonator_node, label="jpa_resonator"),
        ],
    )
    linear_inductor = isnothing(linear_inductance) ? nothing : shunt_inductor!(
        plan;
        id="jpa_linear_inductance",
        at=resonator_node,
        inductance=linear_inductance,
        role=:jpa_linear_shunt_inductance,
        label="JPA linear L",
    )
    junction_capacitor = isnothing(junction_capacitance) ? nothing : shunt_capacitor!(
        plan;
        id="jpa_junction_capacitance",
        at=resonator_node,
        capacitance=junction_capacitance,
        role=:jpa_junction_capacitance,
        label="JPA Cj",
    )
    _port_hb_intent!(
        plan;
        ports=[:signal_port],
        n_pump_harmonics=4,
        n_modulation_harmonics=2,
    )
    example = _prepare_example(
        plan;
        start_frequency=start_frequency,
        stop_frequency=stop_frequency,
        point_count=point_count,
        pump_frequency=pump_frequency,
        pump_current=pump_current,
        optional_hb_kwargs=optional_hb_kwargs,
    )
    return merge(
        example,
        (;
            jpa=jpa,
            jpa_resonator=(
                jpa=jpa,
                linear_inductor=linear_inductor,
                junction_capacitor=junction_capacitor,
            ),
        ),
    )
end

function build_floating_lc_xy_line_example(;
    id="floating-lc-xy-line-example",
    c_g1_f=DEFAULT_FLOATING_XY_C_G1_F,
    c_g2_f=DEFAULT_FLOATING_XY_C_G2_F,
    c_q_f=DEFAULT_FLOATING_XY_C_Q_F,
    c_xy1_f=DEFAULT_FLOATING_XY_C_XY1_F,
    c_xy2_f=DEFAULT_FLOATING_XY_C_XY2_F,
    c_xy_ground_f=DEFAULT_FLOATING_XY_C_XY_GROUND_F,
    l_jun_h=DEFAULT_FLOATING_XY_L_JUN_H,
    port_resistance=50.0,
    start_frequency=2.0e9,
    stop_frequency=12.0e9,
    point_count=1000,
    pump_frequency=12.0e9,
    pump_current=0.0,
    optional_hb_kwargs=Dict{Symbol,Any}(:nbatches => 1, :iterations => 120, :ftol => 1e-8),
)
    c_g1 = Float64(c_g1_f)
    c_g2 = Float64(c_g2_f)
    c_q = Float64(c_q_f)
    c_xy1 = Float64(c_xy1_f)
    c_xy2 = Float64(c_xy2_f)
    c_xy_ground = Float64(c_xy_ground_f)
    l_jun = Float64(l_jun_h)
    all(value -> value > 0, (c_g1, c_g2, c_q, c_xy1, c_xy2, l_jun)) ||
        _validation_error("floating XY capacitances and l_jun_h must be positive.")
    c_xy_ground >= 0 || _validation_error("c_xy_ground_f must be non-negative.")

    w1 = c_g1 + c_xy1
    w2 = c_g2 + c_xy2
    alpha = w1 / (w1 + w2)
    beta = w2 / (w1 + w2)
    c_d_xy = (c_g1 * c_xy2 - c_g2 * c_xy1) / (w1 + w2)
    c_eff_q = c_q + (c_g1 * c_g2) / (c_g1 + c_g2) + (c_xy1 * c_xy2) / (c_xy1 + c_xy2)
    l_eff = l_jun / 2
    f0_estimate = 1 / (2π * sqrt(l_eff * c_eff_q))

    plan = CircuitPlan(id)
    pad1 = external_node("pad1")
    pad2 = external_node("pad2")
    xy_node = external_node("xy_node")
    external_port!(plan; id=:pad1_port, index=1, endpoint=pad1, resistance=port_resistance, role=:probe)
    external_port!(plan; id=:pad2_port, index=2, endpoint=pad2, resistance=port_resistance, role=:probe)
    external_port!(plan; id=:xy_port, index=3, endpoint=xy_node, resistance=port_resistance, role=:xy_line)
    c_g1_relation = shunt_capacitor!(
        plan;
        id="floating_xy_c_g1",
        at=pad1,
        capacitance=c_g1,
        role=:floating_xy_pad_ground_capacitance,
        label=raw"$C_{01}$",
    )
    c_g2_relation = shunt_capacitor!(
        plan;
        id="floating_xy_c_g2",
        at=pad2,
        capacitance=c_g2,
        role=:floating_xy_pad_ground_capacitance,
        label=raw"$C_{02}$",
    )
    c_q_relation = couple_capacitive!(
        plan;
        id="floating_xy_c_q",
        from=pad1,
        to=pad2,
        capacitance=c_q,
        role=:floating_xy_qubit_capacitance,
        label=raw"$C_r$",
    )
    l_q1_relation = series_inductor!(
        plan;
        id="floating_xy_l_q1",
        from=pad1,
        to=pad2,
        inductance=l_jun,
        role=:floating_xy_qubit_inductance,
        label=raw"$L_{r,1}$",
    )
    l_q2_relation = series_inductor!(
        plan;
        id="floating_xy_l_q2",
        from=pad1,
        to=pad2,
        inductance=l_jun,
        role=:floating_xy_qubit_inductance,
        label=raw"$L_{r,2}$",
    )
    c_xy1_relation = couple_capacitive!(
        plan;
        id="floating_xy_c_xy1",
        from=pad1,
        to=xy_node,
        capacitance=c_xy1,
        role=:floating_xy_line_coupling,
        label=raw"$C_{xy,1}$",
    )
    c_xy2_relation = couple_capacitive!(
        plan;
        id="floating_xy_c_xy2",
        from=pad2,
        to=xy_node,
        capacitance=c_xy2,
        role=:floating_xy_line_coupling,
        label=raw"$C_{xy,2}$",
    )
    record_engineering_component!(
        plan;
        id=:floating_lc_xy,
        display_name="floating_lc_xy",
        component_type=:FloatingLCXYResonator,
        role=:resonator,
        parameters=Dict(
            :c_g1_f => c_g1,
            :c_g2_f => c_g2,
            :c_q_f => c_q,
            :c_xy1_f => c_xy1,
            :c_xy2_f => c_xy2,
            :l_jun_h => l_jun,
            :inductive_branch_kind => :linear,
        ),
        pins=[:pad1, :pad2, :xy],
    )
    pad1_port_record = engineering_graph(plan).ports[:pad1_port]
    pad2_port_record = engineering_graph(plan).ports[:pad2_port]
    xy_port_record = engineering_graph(plan).ports[:xy_port]
    _schemdraw_schematic!(
        plan;
        id=:pluto_02_floating_lc_xy,
        component_type=:FloatingLCXYResonator,
        component_id=:floating_lc_xy,
        unit_length=2.35,
        labels=Dict(
            :c_g1_label => _engineering_relation_label(plan, c_g1_relation.id),
            :c_g2_label => _engineering_relation_label(plan, c_g2_relation.id),
            :c_q_label => _engineering_relation_label(plan, c_q_relation.id),
            :l_q1_label => _engineering_relation_label(plan, l_q1_relation.id),
            :l_q2_label => _engineering_relation_label(plan, l_q2_relation.id),
            :c_xy1_label => _engineering_relation_label(plan, c_xy1_relation.id),
            :c_xy2_label => _engineering_relation_label(plan, c_xy2_relation.id),
            :pad1_label => _port_label(pad1_port_record),
            :pad2_label => _port_label(pad2_port_record),
            :xy_label => raw"$XY$",
        ),
        parameters=Dict(
            :inductive_branch_kind =>
                engineering_graph(plan).components[:floating_lc_xy].parameters[:inductive_branch_kind],
            :port_resistance_ohm => port_resistance,
        ),
        terminals=[
            (id=:pad1_terminal, endpoint=pad1, side=:left, label=_port_label(pad1_port_record)),
            (id=:pad2_terminal, endpoint=pad2, side=:left, label=_port_label(pad2_port_record)),
            (id=:xy_terminal, endpoint=xy_node, side=:right, label=raw"$XY$"),
        ],
        node_labels=[
            (id=:pad1_node_label, target=pad1, label="pad1"),
            (id=:pad2_node_label, target=pad2, label="pad2"),
            (id=:xy_node_label, target=xy_node, label="xy_node"),
        ],
    )
    _port_hb_intent!(plan; ports=[:pad1_port, :pad2_port, :xy_port])
    example = _prepare_example(
        plan;
        start_frequency=start_frequency,
        stop_frequency=stop_frequency,
        point_count=point_count,
        pump_frequency=pump_frequency,
        pump_current=pump_current,
        optional_hb_kwargs=optional_hb_kwargs,
    )
    return merge(
        example,
        (;
            pad1=pad1,
            pad2=pad2,
            xy_node=xy_node,
            floating_lc=(
                c_g1=c_g1_relation,
                c_g2=c_g2_relation,
                c_q=c_q_relation,
                c_xy1=c_xy1_relation,
                c_xy2=c_xy2_relation,
                l_q1=l_q1_relation,
                l_q2=l_q2_relation,
                pad1=pad1,
                pad2=pad2,
                xy_node=xy_node,
            ),
            c_g1=c_g1_relation,
            c_g2=c_g2_relation,
            c_q=c_q_relation,
            c_xy1=c_xy1_relation,
            c_xy2=c_xy2_relation,
            l_q1=l_q1_relation,
            l_q2=l_q2_relation,
            capacitance_summary=(
                c_g1_f=c_g1,
                c_g2_f=c_g2,
                c_q_f=c_q,
                c_xy1_f=c_xy1,
                c_xy2_f=c_xy2,
                c_xy_ground_f=c_xy_ground,
                w1_f=w1,
                w2_f=w2,
                alpha=alpha,
                beta=beta,
                c_d_xy_f=c_d_xy,
                c_eff_q_f=c_eff_q,
                l_jun_h=l_jun,
                l_eff_h=l_eff,
                f0_estimate_hz=f0_estimate,
            ),
        ),
    )
end

function build_transmission_line_circuit_model_example(;
    id="transmission-line-circuit-model-example",
    length_m=4.0e-3,
    section_length_m=0.5e-3,
    l_per_m_h=DEFAULT_CPW_L_PER_M_H,
    c_per_m_f=DEFAULT_CPW_C_PER_M_F,
    port_resistance=50.0,
    start_frequency=2.0e9,
    stop_frequency=8.0e9,
    point_count=1000,
    pump_frequency=10.0e9,
    pump_current=0.0,
    optional_hb_kwargs=Dict{Symbol,Any}(:nbatches => 1, :iterations => 120, :ftol => 1e-8),
)
    plan = CircuitPlan(id)
    input = external_node("input")
    output = external_node("output")
    _external_two_port!(plan; input=input, output=output, port_resistance=port_resistance)
    line = build_lc_ladder_line!(
        plan;
        id="cpw",
        head=input,
        tail=output,
        spec=_default_line_spec(
            length_m=length_m,
            section_length_m=section_length_m,
            l_per_m_h=l_per_m_h,
            c_per_m_f=c_per_m_f,
        ),
        head_termination=:external,
        tail_termination=:external,
    )
    _port_hb_intent!(plan; ports=[:input_port, :output_port])
    example = _prepare_example(
        plan;
        start_frequency=start_frequency,
        stop_frequency=stop_frequency,
        point_count=point_count,
        pump_frequency=pump_frequency,
        pump_current=pump_current,
        optional_hb_kwargs=optional_hb_kwargs,
    )
    return merge(example, (; line=line))
end

function build_readout_line_purcell_filter_example(;
    id="readout-line-purcell-filter-example",
    input_line_length_m=2.0e-3,
    filter_length_m=4.0e-3,
    resonator_length_m=nothing,
    output_line_length_m=2.0e-3,
    section_length_m=0.5e-3,
    l_per_m_h=DEFAULT_CPW_L_PER_M_H,
    c_per_m_f=DEFAULT_CPW_C_PER_M_F,
    input_coupling_f=2.0e-15,
    output_coupling_f=2.0e-15,
    port_resistance=50.0,
    start_frequency=2.0e9,
    stop_frequency=10.0e9,
    point_count=1000,
    pump_frequency=12.0e9,
    pump_current=0.0,
    optional_hb_kwargs=Dict{Symbol,Any}(:nbatches => 1, :iterations => 120, :ftol => 1e-8),
)
    selected_filter_length_m = isnothing(resonator_length_m) ? filter_length_m : resonator_length_m
    plan = CircuitPlan(id)
    input = external_node("input")
    output = external_node("output")
    _external_two_port!(plan; input=input, output=output, port_resistance=port_resistance)
    component = add_readout_line_with_purcell_filter!(
        plan;
        id="readout_purcell",
        input=input,
        output=output,
        input_line_spec=_default_line_spec(
            length_m=input_line_length_m,
            section_length_m=section_length_m,
            l_per_m_h=l_per_m_h,
            c_per_m_f=c_per_m_f,
        ),
        filter_spec=_default_line_spec(
            length_m=selected_filter_length_m,
            section_length_m=section_length_m,
            l_per_m_h=l_per_m_h,
            c_per_m_f=c_per_m_f,
        ),
        output_line_spec=_default_line_spec(
            length_m=output_line_length_m,
            section_length_m=section_length_m,
            l_per_m_h=l_per_m_h,
            c_per_m_f=c_per_m_f,
        ),
        input_coupling_f=input_coupling_f,
        output_coupling_f=output_coupling_f,
    )
    _port_hb_intent!(plan; ports=[:input_port, :output_port])
    example = _prepare_example(
        plan;
        start_frequency=start_frequency,
        stop_frequency=stop_frequency,
        point_count=point_count,
        pump_frequency=pump_frequency,
        pump_current=pump_current,
        optional_hb_kwargs=optional_hb_kwargs,
    )
    return merge(example, (; readout_purcell=component, filter=component.filter_line))
end

function build_readout_line_hanging_qwr_mtl_example(;
    id="readout-line-hanging-qwr-mtl-example",
    readout_length_m=6.0e-3,
    resonator_length_m=3.0e-3,
    section_length_m=0.75e-3,
    readout_l_per_m_h=DEFAULT_CPW_L_PER_M_H,
    readout_c_per_m_f=DEFAULT_CPW_C_PER_M_F,
    resonator_l_per_m_h=DEFAULT_CPW_L_PER_M_H,
    resonator_c_per_m_f=DEFAULT_CPW_C_PER_M_F,
    window_start_readout_m=2.25e-3,
    window_start_resonator_m=0.0,
    window_length_m=1.5e-3,
    l_matrix_per_m_h=DEFAULT_COUPLED_MTL_L_MATRIX_PER_M_H,
    c_matrix_per_m_f=DEFAULT_COUPLED_MTL_C_MATRIX_PER_M_F,
    port_resistance=50.0,
    start_frequency=6.0e9,
    stop_frequency=12.0e9,
    point_count=1000,
    pump_frequency=14.0e9,
    pump_current=0.0,
    optional_hb_kwargs=Dict{Symbol,Any}(:nbatches => 1, :iterations => 160, :ftol => 1e-8),
)
    plan = CircuitPlan(id)
    input = external_node("input")
    output = external_node("output")
    qwr_grounded_head = external_node("qwr_grounded_head")
    qwr_open_tail = external_node("qwr_open_tail")
    _external_two_port!(plan; input=input, output=output, port_resistance=port_resistance)
    window_model = MTLCoupledRLGCSpec(
        start1_m=window_start_readout_m,
        start2_m=window_start_resonator_m,
        length_m=window_length_m,
        section_length_m=section_length_m,
        l_matrix_per_m_h=l_matrix_per_m_h,
        c_matrix_per_m_f=c_matrix_per_m_f,
    )

    readout_line = build_lc_ladder_line!(
        plan;
        id="readout_line",
        head=input,
        tail=output,
        spec=_default_line_spec(
            length_m=readout_length_m,
            section_length_m=section_length_m,
            l_per_m_h=readout_l_per_m_h,
            c_per_m_f=readout_c_per_m_f,
        ),
        head_termination=:external,
        tail_termination=:external,
        breakpoints_m=[window_start_readout_m, window_start_readout_m + window_length_m],
        section_overrides=[coupled_line_section_override(window_model, 1)],
    )
    qwr = add_quarter_wave_resonator!(
        plan;
        id="qwr",
        grounded_head=qwr_grounded_head,
        open_tail=qwr_open_tail,
        spec=_default_line_spec(
            length_m=resonator_length_m,
            section_length_m=section_length_m,
            l_per_m_h=resonator_l_per_m_h,
            c_per_m_f=resonator_c_per_m_f,
        ),
        breakpoints_m=[window_start_resonator_m, window_start_resonator_m + window_length_m],
        section_overrides=[coupled_line_section_override(window_model, 2)],
    )
    window = couple_transmission_window!(
        plan;
        id="readout_qwr_mtl_window",
        line1=readout_line,
        line2=qwr.line,
        start1=window_start_readout_m,
        start2=window_start_resonator_m,
        length=window_length_m,
        model=window_model,
    )
    _port_hb_intent!(plan; ports=[:input_port, :output_port])
    example = _prepare_example(
        plan;
        start_frequency=start_frequency,
        stop_frequency=stop_frequency,
        point_count=point_count,
        pump_frequency=pump_frequency,
        pump_current=pump_current,
        optional_hb_kwargs=optional_hb_kwargs,
    )
    return merge(
        example,
        (;
            readout_line=readout_line,
            qwr=qwr.line,
            qwr_component=qwr,
            window=window,
            window_model=window_model,
        ),
    )
end

function build_readout_purcell_hanging_qwr_mtl_example(;
    id="readout-purcell-hanging-qwr-mtl-example",
    readout_length_m=nothing,
    input_line_length_m=2.0e-3,
    filter_length_m=6.0e-3,
    purcell_length_m=nothing,
    output_line_length_m=2.0e-3,
    qwr_length_m=3.0e-3,
    section_length_m=0.75e-3,
    l_per_m_h=DEFAULT_CPW_L_PER_M_H,
    readout_l_per_m_h=nothing,
    purcell_l_per_m_h=nothing,
    qwr_l_per_m_h=nothing,
    c_per_m_f=DEFAULT_CPW_C_PER_M_F,
    readout_c_per_m_f=nothing,
    purcell_c_per_m_f=nothing,
    qwr_c_per_m_f=nothing,
    input_coupling_f=2.0e-15,
    purcell_input_coupling_f=nothing,
    output_coupling_f=2.0e-15,
    purcell_output_coupling_f=nothing,
    window_start_filter_m=2.25e-3,
    window_start_readout_m=nothing,
    window_start_qwr_m=0.0,
    window_length_m=1.5e-3,
    l_matrix_per_m_h=DEFAULT_COUPLED_MTL_L_MATRIX_PER_M_H,
    c_matrix_per_m_f=DEFAULT_COUPLED_MTL_C_MATRIX_PER_M_F,
    port_resistance=50.0,
    start_frequency=6.0e9,
    stop_frequency=12.0e9,
    point_count=1000,
    pump_frequency=14.0e9,
    pump_current=0.0,
    optional_hb_kwargs=Dict{Symbol,Any}(:nbatches => 1, :iterations => 160, :ftol => 1e-8),
)
    if !isnothing(readout_length_m)
        input_line_length_m = Float64(readout_length_m) / 2
        output_line_length_m = Float64(readout_length_m) / 2
    end
    selected_filter_length_m = isnothing(purcell_length_m) ? filter_length_m : purcell_length_m
    selected_input_coupling = isnothing(purcell_input_coupling_f) ? input_coupling_f : purcell_input_coupling_f
    selected_output_coupling = isnothing(purcell_output_coupling_f) ? output_coupling_f : purcell_output_coupling_f
    selected_window_start_filter_m = isnothing(window_start_readout_m) ? window_start_filter_m : window_start_readout_m
    selected_readout_l = isnothing(readout_l_per_m_h) ? l_per_m_h : readout_l_per_m_h
    selected_purcell_l = isnothing(purcell_l_per_m_h) ? l_per_m_h : purcell_l_per_m_h
    selected_qwr_l = isnothing(qwr_l_per_m_h) ? l_per_m_h : qwr_l_per_m_h
    selected_readout_c = isnothing(readout_c_per_m_f) ? c_per_m_f : readout_c_per_m_f
    selected_purcell_c = isnothing(purcell_c_per_m_f) ? c_per_m_f : purcell_c_per_m_f
    selected_qwr_c = isnothing(qwr_c_per_m_f) ? c_per_m_f : qwr_c_per_m_f
    mtl_model = MTLCoupledRLGCSpec(
        start1_m=selected_window_start_filter_m,
        start2_m=window_start_qwr_m,
        length_m=window_length_m,
        section_length_m=section_length_m,
        l_matrix_per_m_h=l_matrix_per_m_h,
        c_matrix_per_m_f=c_matrix_per_m_f,
    )
    plan = CircuitPlan(id)
    input = external_node("input")
    output = external_node("output")
    qwr_grounded_head = external_node("qwr_grounded_head")
    qwr_open_tail = external_node("qwr_open_tail")
    _external_two_port!(plan; input=input, output=output, port_resistance=port_resistance)
    component = add_readout_purcell_qwr_mtl!(
        plan;
        id="readout_purcell_qwr",
        input=input,
        output=output,
        input_line_spec=_default_line_spec(
            length_m=input_line_length_m,
            section_length_m=section_length_m,
            l_per_m_h=selected_readout_l,
            c_per_m_f=selected_readout_c,
        ),
        filter_spec=_default_line_spec(
            length_m=selected_filter_length_m,
            section_length_m=section_length_m,
            l_per_m_h=selected_purcell_l,
            c_per_m_f=selected_purcell_c,
        ),
        output_line_spec=_default_line_spec(
            length_m=output_line_length_m,
            section_length_m=section_length_m,
            l_per_m_h=selected_readout_l,
            c_per_m_f=selected_readout_c,
        ),
        qwr_spec=_default_line_spec(
            length_m=qwr_length_m,
            section_length_m=section_length_m,
            l_per_m_h=selected_qwr_l,
            c_per_m_f=selected_qwr_c,
        ),
        input_coupling_f=selected_input_coupling,
        output_coupling_f=selected_output_coupling,
        qwr_grounded_head=qwr_grounded_head,
        qwr_open_tail=qwr_open_tail,
        mtl_model=mtl_model,
    )
    _port_hb_intent!(plan; ports=[:input_port, :output_port])
    example = _prepare_example(
        plan;
        start_frequency=start_frequency,
        stop_frequency=stop_frequency,
        point_count=point_count,
        pump_frequency=pump_frequency,
        pump_current=pump_current,
        optional_hb_kwargs=optional_hb_kwargs,
    )
    return merge(
        example,
        (;
            component=component,
            readout_purcell=component.readout_filter,
            readout_line=component.readout_filter.input_line,
            purcell_filter=component.readout_filter.filter_line,
            qwr=component.qwr.line,
            window=component.window,
            window_model=mtl_model,
        ),
    )
end

"""
    build_interdigitated_capacitor_example(; kwargs...)

Build the renderer/export-facing three-branch IDC equivalent without adding a
feedline, external port, or simulation intent.
"""
function build_interdigitated_capacitor_example(;
    id="interdigitated-capacitor-example",
    c1g_f=35.0e-15,
    c2g_f=34.5e-15,
    c12_f=38.0e-15,
)
    plan = CircuitPlan(id)
    terminal_1 = external_node("terminal_1")
    terminal_2 = external_node("terminal_2")
    component = add_interdigitated_capacitor!(
        plan;
        id="feedline_idc",
        terminal_1=terminal_1,
        terminal_2=terminal_2,
        c1g_f=c1g_f,
        c2g_f=c2g_f,
        c12_f=c12_f,
    )
    _schemdraw_schematic!(
        plan;
        id=:reusable_interdigitated_capacitor,
        component_type=:InterdigitatedCapacitor,
        component_id=component.id,
        unit_length=2.2,
        labels=Dict(
            :c1g_label => _engineering_relation_label(plan, component.c1g.id),
            :c2g_label => _engineering_relation_label(plan, component.c2g.id),
            :c12_label => _engineering_relation_label(plan, component.c12.id),
            :terminal_1_label => raw"$1$",
            :terminal_2_label => raw"$2$",
        ),
        terminals=[
            (id=:terminal_1, endpoint=terminal_1, side=:left, label=raw"$1$"),
            (id=:terminal_2, endpoint=terminal_2, side=:right, label=raw"$2$"),
        ],
        node_labels=[
            (id=:terminal_1_node, target=terminal_1, label="terminal_1"),
            (id=:terminal_2_node, target=terminal_2, label="terminal_2"),
        ],
    )
    return (; plan=plan, graph=engineering_graph(plan), component=component)
end

"""
    build_intrinsic_interferometric_purcell_filter_example(; kwargs...)

Build the reusable filter candidate and its schematic-export intent. The
feedline attachment remains an exposed node; no feedline or port is added.
`C0r` belongs to the filter and defaults to an omitted zero-valued branch.
"""
function build_intrinsic_interferometric_purcell_filter_example(;
    id="intrinsic-interferometric-purcell-filter-example",
    readout_length_m=6.0e-3,
    filter_length_m=6.0e-3,
    section_length_m=0.75e-3,
    readout_l_per_m_h=DEFAULT_CPW_L_PER_M_H,
    readout_c_per_m_f=DEFAULT_CPW_C_PER_M_F,
    filter_l_per_m_h=DEFAULT_CPW_L_PER_M_H,
    filter_c_per_m_f=DEFAULT_CPW_C_PER_M_F,
    window_start_readout_m=2.25e-3,
    window_start_filter_m=2.25e-3,
    window_length_m=1.5e-3,
    l_matrix_per_m_h=DEFAULT_COUPLED_MTL_L_MATRIX_PER_M_H,
    c_matrix_per_m_f=DEFAULT_COUPLED_MTL_C_MATRIX_PER_M_F,
    coupling_orientation=:same_direction,
    c1g_f=35.0e-15,
    c2g_f=34.5e-15,
    c12_f=38.0e-15,
    c0r_f=0.0,
)
    plan = CircuitPlan(id)
    readout_attachment = external_node("readout_attachment")
    feedline_attachment = external_node("feedline_attachment")
    mtl_model = MTLCoupledRLGCSpec(
        start1_m=window_start_readout_m,
        start2_m=window_start_filter_m,
        length_m=window_length_m,
        section_length_m=section_length_m,
        l_matrix_per_m_h=l_matrix_per_m_h,
        c_matrix_per_m_f=c_matrix_per_m_f,
    )
    component = add_intrinsic_interferometric_purcell_filter!(
        plan;
        id="intrinsic_filter",
        readout_attachment=readout_attachment,
        feedline_attachment=feedline_attachment,
        readout_spec=_default_line_spec(
            length_m=readout_length_m,
            section_length_m=section_length_m,
            l_per_m_h=readout_l_per_m_h,
            c_per_m_f=readout_c_per_m_f,
        ),
        filter_spec=_default_line_spec(
            length_m=filter_length_m,
            section_length_m=section_length_m,
            l_per_m_h=filter_l_per_m_h,
            c_per_m_f=filter_c_per_m_f,
        ),
        mtl_model=mtl_model,
        coupling_orientation=coupling_orientation,
        c1g_f=c1g_f,
        c2g_f=c2g_f,
        c12_f=c12_f,
        c0r_f=c0r_f,
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
        :c1g_label => _engineering_relation_label(plan, component.feedline_capacitor.c1g.id),
        :c2g_label => _engineering_relation_label(plan, component.feedline_capacitor.c2g.id),
        :c12_label => _engineering_relation_label(plan, component.feedline_capacitor.c12.id),
    )
    isnothing(component.c0r) ||
        (labels[:c0r_label] = _engineering_relation_label(plan, component.c0r.id))
    _schemdraw_schematic!(
        plan;
        id=:reusable_intrinsic_interferometric_purcell_filter,
        component_type=:IntrinsicInterferometricPurcellFilter,
        component_id=component.id,
        unit_length=1.7,
        labels=labels,
        parameters=Dict(
            :coupling_orientation => component.window.coupling_orientation,
            :c0r_f => c0r_f,
            :contains_feedline => false,
        ),
        tracks=[
            (
                id=:readout,
                line=component.readout_resonator.line.id,
                orientation=:left_to_right,
                relative_order=:top,
                role=:quarter_wave_resonator,
                label="readout",
            ),
            (
                id=:filter,
                line=component.filter_resonator.line.id,
                orientation=:left_to_right,
                relative_order=:bottom,
                role=:quarter_wave_resonator,
                label="filter",
            ),
        ],
        segments=[
            (
                id=:readout_head_cpw,
                track=:readout,
                from=0.0,
                to=mtl_model.start1_m,
                role=:plain_cpw,
                label=labels[:readout_head_label],
            ),
            (
                id=:readout_tail_cpw,
                track=:readout,
                from=mtl_model.start1_m + mtl_model.length_m,
                to=component.readout_resonator.line.spec.length_m,
                role=:plain_cpw,
                label=labels[:readout_tail_label],
            ),
            (
                id=:filter_head_cpw,
                track=:filter,
                from=0.0,
                to=mtl_model.start2_m,
                role=:plain_cpw,
                label=labels[:filter_head_label],
            ),
            (
                id=:filter_tail_cpw,
                track=:filter,
                from=mtl_model.start2_m + mtl_model.length_m,
                to=component.filter_resonator.line.spec.length_m,
                role=:plain_cpw,
                label=labels[:filter_tail_label],
            ),
        ],
        coupled_spans=[
            (
                id=:mtl_window,
                relation=component.window.id,
                track1=:readout,
                track2=:filter,
                from1=mtl_model.start1_m,
                to1=mtl_model.start1_m + mtl_model.length_m,
                from2=mtl_model.start2_m,
                to2=mtl_model.start2_m + mtl_model.length_m,
                align=:start_and_end,
                label=labels[:mtl_label],
                render=:coupled_cpw_transmission_line,
                hints=Dict(
                    :coupling_orientation => component.window.coupling_orientation,
                ),
            ),
        ],
        terminals=[
            (
                id=:readout_attachment,
                endpoint=component.readout_attachment,
                side=:right,
                kind=:attachment,
                label="",
            ),
            (
                id=:feedline_attachment,
                endpoint=component.feedline_attachment,
                side=:right,
                kind=:attachment,
                label="",
            ),
        ],
        node_labels=[
            (
                id=:readout_attachment,
                target=component.readout_attachment,
                label=raw"$r$",
                hints=Dict(
                    :placement => :terminal,
                    :placement_target => :readout_attachment,
                    :loc => :right,
                    :offset => 0.28,
                ),
            ),
            (
                id=:filter_open_tail,
                target=component.filter_resonator.line.tail,
                label=raw"$p$",
                hints=Dict(
                    :placement => :marker,
                    :placement_target => :filter_open_tail,
                    :loc => :top,
                    :offset => (0.28, 0.5),
                ),
            ),
            (
                id=:feedline_attachment,
                target=component.feedline_attachment,
                label=raw"$f_c$",
                hints=Dict(
                    :placement => :terminal,
                    :placement_target => :feedline_attachment,
                    :loc => :right,
                    :offset => 0.28,
                ),
            ),
        ],
        node_bindings=Dict(
            :readout_attachment => component.readout_attachment,
            :filter_open_tail => component.filter_resonator.line.tail,
            :feedline_attachment => component.feedline_attachment,
        ),
    )
    return (;
        plan=plan,
        graph=engineering_graph(plan),
        component=component,
        mtl_model=mtl_model,
    )
end

"""
    build_intrinsic_interferometric_purcell_filter_with_qubit_example(; kwargs...)

Build the filter candidate and compose its readout attachment with the
linearized floating-qubit component. `C0r` remains filter-owned.
"""
function build_intrinsic_interferometric_purcell_filter_with_qubit_example(;
    id="intrinsic-interferometric-purcell-filter-with-qubit-example",
    c0r_f=18.0e-15,
    c01_f=65.0e-15,
    c02_f=64.0e-15,
    c12_qubit_f=12.0e-15,
    cr1_f=4.2e-15,
    cr2_f=3.8e-15,
    l_j_per_junction_h=24.0e-9,
    filter_kwargs...,
)
    filter_example = build_intrinsic_interferometric_purcell_filter_example(;
        id=id,
        c0r_f=c0r_f,
        filter_kwargs...,
    )
    plan = filter_example.plan
    delete!(schematic_layout_intent(plan).terminals, :readout_attachment)
    island_1 = external_node("island_1")
    island_2 = external_node("island_2")
    component = add_intrinsic_interferometric_purcell_filter_with_qubit!(
        plan;
        id="intrinsic_filter_with_qubit",
        filter=filter_example.component,
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
        :c1g_label => _engineering_relation_label(plan, component.filter.feedline_capacitor.c1g.id),
        :c2g_label => _engineering_relation_label(plan, component.filter.feedline_capacitor.c2g.id),
        :c12_label => _engineering_relation_label(plan, component.filter.feedline_capacitor.c12.id),
        :c01_label => _engineering_relation_label(plan, component.qubit.c01.id),
        :c02_label => _engineering_relation_label(plan, component.qubit.c02.id),
        :qubit_c12_label => _engineering_relation_label(plan, component.qubit.c12.id),
        :cr1_label => _engineering_relation_label(plan, component.qubit.cr1.id),
        :cr2_label => _engineering_relation_label(plan, component.qubit.cr2.id),
        :lj1_label => _engineering_relation_label(plan, component.qubit.lj1.id),
        :lj2_label => _engineering_relation_label(plan, component.qubit.lj2.id),
    )
    isnothing(component.c0r) ||
        (labels[:c0r_label] = _engineering_relation_label(plan, component.c0r.id))
    _schemdraw_schematic!(
        plan;
        id=:reusable_intrinsic_interferometric_purcell_filter_with_qubit,
        component_type=:IntrinsicInterferometricPurcellFilterWithQubit,
        component_id=component.id,
        unit_length=1.55,
        labels=labels,
        parameters=Dict(
            :coupling_orientation => component.filter.window.coupling_orientation,
            :contains_feedline => false,
            :c0r_f => c0r_f,
            :qubit_inductive_branch_kind =>
                engineering_graph(plan).components[Symbol(component.qubit.id)].parameters[:inductive_branch_kind],
        ),
        terminals=[
            (id=:island_1, endpoint=island_1, side=:top, kind=:attachment, label=""),
            (id=:island_2, endpoint=island_2, side=:top, kind=:attachment, label=""),
            (
                id=:feedline_attachment,
                endpoint=component.filter.feedline_attachment,
                side=:right,
                kind=:attachment,
                label="",
            ),
        ],
        node_labels=[
            (
                id=:readout_attachment,
                target=component.filter.readout_attachment,
                label=raw"$r$",
                hints=Dict(
                    :placement => :marker,
                    :placement_target => :readout_attachment,
                    :loc => :left,
                    :offset => 0.28,
                ),
            ),
            (
                id=:filter_open_tail,
                target=component.filter.filter_resonator.line.tail,
                label=raw"$p$",
                hints=Dict(
                    :placement => :marker,
                    :placement_target => :filter_open_tail,
                    :loc => :top,
                    :offset => (0.28, 0.5),
                ),
            ),
            (
                id=:island_1,
                target=island_1,
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
                target=island_2,
                label=raw"$q_2$",
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
                    :placement => :terminal,
                    :placement_target => :feedline_attachment,
                    :loc => :right,
                    :offset => 0.28,
                ),
            ),
        ],
        node_bindings=Dict(
            :readout_attachment => component.filter.readout_attachment,
            :filter_open_tail => component.filter.filter_resonator.line.tail,
            :island_1 => island_1,
            :island_2 => island_2,
            :feedline_attachment => component.filter.feedline_attachment,
        ),
    )
    return (;
        plan=plan,
        graph=engineering_graph(plan),
        component=component,
        mtl_model=filter_example.mtl_model,
    )
end

"""
    build_intrinsic_interferometric_purcell_filter_equivalent_example(; kwargs...)

Build the response-matched lumped intrinsic-filter equivalent with the
complete three-branch feedline IDC and no feedline or port.
"""
function build_intrinsic_interferometric_purcell_filter_equivalent_example(;
    id="intrinsic-interferometric-purcell-filter-equivalent-example",
    readout_capacitance_f=500.0e-15,
    readout_inductance_h=1.40e-9,
    filter_capacitance_f=480.0e-15,
    filter_inductance_h=1.46e-9,
    bridge_capacitance_f=8.0e-15,
    bridge_inductance_h=35.0e-9,
    idc_filter_ground_capacitance_f=35.0e-15,
    idc_feedline_ground_capacitance_f=34.5e-15,
    idc_mutual_capacitance_f=38.0e-15,
    c0r_f=0.0,
)
    plan = CircuitPlan(id)
    readout_attachment = external_node("readout_attachment")
    feedline_attachment = external_node("feedline_attachment")
    component = add_intrinsic_interferometric_purcell_filter_equivalent!(
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
    labels = Dict(
        :cr_label => _engineering_relation_label(plan, component.readout_resonator.capacitor.id),
        :lr_label => _engineering_relation_label(plan, component.readout_resonator.inductor.id),
        :cp_label => _engineering_relation_label(plan, component.filter_resonator.capacitor.id),
        :lp_label => _engineering_relation_label(plan, component.filter_resonator.inductor.id),
        :cn_label => _engineering_relation_label(plan, component.bridge_capacitor.id),
        :ln_label => _engineering_relation_label(plan, component.bridge_inductor.id),
        :cpg_label => _engineering_relation_label(plan, component.feedline_capacitor.c1g.id),
        :cfcg_label => _engineering_relation_label(plan, component.feedline_capacitor.c2g.id),
        :cpfc_label => _engineering_relation_label(plan, component.feedline_capacitor.c12.id),
    )
    isnothing(component.c0r) ||
        (labels[:c0r_label] = _engineering_relation_label(plan, component.c0r.id))
    _schemdraw_schematic!(
        plan;
        id=:reusable_intrinsic_interferometric_purcell_filter_equivalent,
        component_type=:IntrinsicInterferometricPurcellFilterEquivalent,
        component_id=component.id,
        unit_length=1.7,
        labels=labels,
        parameters=Dict(
            :model_family => :response_matched_parallel_lc_bridge,
            :c0r_f => c0r_f,
            :contains_feedline => false,
            :feedline_coupling_kind => :interdigitated_three_branch,
        ),
        terminals=[
            (
                id=:readout_attachment,
                endpoint=component.readout_attachment,
                side=:left,
                kind=:attachment,
                label="",
            ),
            (
                id=:feedline_attachment,
                endpoint=component.feedline_attachment,
                side=:right,
                kind=:attachment,
                label="",
            ),
        ],
        node_labels=[
            (
                id=:readout_attachment,
                target=component.readout_attachment,
                label=raw"$r$",
                hints=Dict(
                    :placement => :bus_middle,
                    :placement_target => :readout_signal,
                    :loc => :top,
                    :offset => 0.28,
                ),
            ),
            (
                id=:filter,
                target=component.filter_resonator.node,
                label=raw"$p$",
                hints=Dict(
                    :placement => :bus_middle,
                    :placement_target => :filter_signal,
                    :loc => :top,
                    :offset => (0.28, 0.5),
                ),
            ),
            (
                id=:feedline_attachment,
                target=component.feedline_attachment,
                label=raw"$f_c$",
                hints=Dict(
                    :placement => :terminal,
                    :placement_target => :feedline_attachment,
                    :loc => :right,
                    :offset => 0.28,
                ),
            ),
        ],
        node_bindings=Dict(
            :readout_attachment => component.readout_attachment,
            :filter => component.filter_resonator.node,
            :feedline_attachment => component.feedline_attachment,
        ),
    )
    return (; plan=plan, graph=engineering_graph(plan), component=component)
end

"""
    build_intrinsic_interferometric_purcell_filter_equivalent_with_qubit_example(; kwargs...)

Compose the response-matched lumped intrinsic-filter equivalent with the
linearized floating qubit. `C0r` remains equivalent-filter-owned.
"""
function build_intrinsic_interferometric_purcell_filter_equivalent_with_qubit_example(;
    id="intrinsic-interferometric-purcell-filter-equivalent-with-qubit-example",
    c0r_f=18.0e-15,
    c01_f=65.0e-15,
    c02_f=64.0e-15,
    c12_qubit_f=12.0e-15,
    cr1_f=4.2e-15,
    cr2_f=3.8e-15,
    l_j_per_junction_h=24.0e-9,
    filter_kwargs...,
)
    filter_example = build_intrinsic_interferometric_purcell_filter_equivalent_example(;
        id=id,
        c0r_f=c0r_f,
        filter_kwargs...,
    )
    plan = filter_example.plan
    delete!(schematic_layout_intent(plan).terminals, :readout_attachment)
    island_1 = external_node("island_1")
    island_2 = external_node("island_2")
    component = add_intrinsic_interferometric_purcell_filter_equivalent_with_qubit!(
        plan;
        id="intrinsic_filter_equivalent_with_qubit",
        filter=filter_example.component,
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
    labels = Dict(
        :cr_label => _engineering_relation_label(plan, component.filter.readout_resonator.capacitor.id),
        :lr_label => _engineering_relation_label(plan, component.filter.readout_resonator.inductor.id),
        :cp_label => _engineering_relation_label(plan, component.filter.filter_resonator.capacitor.id),
        :lp_label => _engineering_relation_label(plan, component.filter.filter_resonator.inductor.id),
        :cn_label => _engineering_relation_label(plan, component.filter.bridge_capacitor.id),
        :ln_label => _engineering_relation_label(plan, component.filter.bridge_inductor.id),
        :cpg_label => _engineering_relation_label(plan, component.filter.feedline_capacitor.c1g.id),
        :cfcg_label => _engineering_relation_label(plan, component.filter.feedline_capacitor.c2g.id),
        :cpfc_label => _engineering_relation_label(plan, component.filter.feedline_capacitor.c12.id),
        :c01_label => _engineering_relation_label(plan, component.qubit.c01.id),
        :c02_label => _engineering_relation_label(plan, component.qubit.c02.id),
        :qubit_c12_label => _engineering_relation_label(plan, component.qubit.c12.id),
        :cr1_label => _engineering_relation_label(plan, component.qubit.cr1.id),
        :cr2_label => _engineering_relation_label(plan, component.qubit.cr2.id),
        :lj1_label => _engineering_relation_label(plan, component.qubit.lj1.id),
        :lj2_label => _engineering_relation_label(plan, component.qubit.lj2.id),
    )
    isnothing(component.c0r) ||
        (labels[:c0r_label] = _engineering_relation_label(plan, component.c0r.id))
    _schemdraw_schematic!(
        plan;
        id=:reusable_intrinsic_interferometric_purcell_filter_equivalent_with_qubit,
        component_type=:IntrinsicInterferometricPurcellFilterEquivalentWithQubit,
        component_id=component.id,
        unit_length=1.55,
        labels=labels,
        parameters=Dict(
            :model_family => :response_matched_parallel_lc_bridge,
            :c0r_f => c0r_f,
            :contains_feedline => false,
            :feedline_coupling_kind => :interdigitated_three_branch,
            :qubit_inductive_branch_kind =>
                engineering_graph(plan).components[Symbol(component.qubit.id)].parameters[:inductive_branch_kind],
        ),
        terminals=[
            (id=:island_1, endpoint=island_1, side=:top, kind=:attachment, label=""),
            (id=:island_2, endpoint=island_2, side=:top, kind=:attachment, label=""),
            (
                id=:feedline_attachment,
                endpoint=component.filter.feedline_attachment,
                side=:right,
                kind=:attachment,
                label="",
            ),
        ],
        node_labels=[
            (
                id=:readout_attachment,
                target=component.filter.readout_attachment,
                label=raw"$r$",
                hints=Dict(
                    :placement => :bus_middle,
                    :placement_target => :readout_signal,
                    :loc => :top,
                    :offset => 0.28,
                ),
            ),
            (
                id=:filter,
                target=component.filter.filter_resonator.node,
                label=raw"$p$",
                hints=Dict(
                    :placement => :bus_middle,
                    :placement_target => :filter_signal,
                    :loc => :top,
                    :offset => (0.28, 0.5),
                ),
            ),
            (
                id=:island_1,
                target=island_1,
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
                target=island_2,
                label=raw"$q_2$",
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
                    :placement => :terminal,
                    :placement_target => :feedline_attachment,
                    :loc => :right,
                    :offset => 0.28,
                ),
            ),
        ],
        node_bindings=Dict(
            :readout_attachment => component.filter.readout_attachment,
            :filter => component.filter.filter_resonator.node,
            :island_1 => island_1,
            :island_2 => island_2,
            :feedline_attachment => component.filter.feedline_attachment,
        ),
    )
    return (; plan=plan, graph=engineering_graph(plan), component=component)
end
