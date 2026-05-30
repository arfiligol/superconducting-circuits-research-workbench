struct ParallelLCResonator
    id::String
    node::AbstractNodeEndpoint
    capacitor::ShuntCapacitor
    inductor::ShuntInductor
end

struct ReflectiveJPA
    id::String
    port_node::AbstractNodeEndpoint
    resonator_node::AbstractNodeEndpoint
    coupling_capacitor::CapacitiveCoupling
    shunt_capacitor::ShuntCapacitor
    junction::JosephsonJunction
end

struct HalfWaveResonator
    id::String
    line::TransmissionLineLadder
end

struct QuarterWaveResonator
    id::String
    line::TransmissionLineLadder
end

struct ReadoutLineWithPurcellFilter
    id::String
    input_line::TransmissionLineLadder
    filter_line::TransmissionLineLadder
    output_line::TransmissionLineLadder
    input_coupling::CapacitiveCoupling
    output_coupling::CapacitiveCoupling
    input_node::AbstractNodeEndpoint
    output_node::AbstractNodeEndpoint
    filter_head::AbstractNodeEndpoint
    filter_tail::AbstractNodeEndpoint
end

struct ReadoutPurcellQWRMTL
    id::String
    readout_filter::ReadoutLineWithPurcellFilter
    qwr::QuarterWaveResonator
    window::CoupledTransmissionWindow
end

function _component_node(id, name)
    return external_node("$(id)_$(name)")
end

function add_parallel_lc_resonator!(
    plan::CircuitPlan;
    id,
    node,
    capacitance,
    inductance,
)
    node isa AbstractNodeEndpoint || _validation_error("add_parallel_lc_resonator! requires node to be a NodeEndpoint.")
    capacitor = shunt_capacitor!(
        plan;
        id="$(id)_capacitance",
        at=node,
        capacitance=capacitance,
        role=:parallel_lc_capacitance,
        label="$(id) C",
    )
    inductor = shunt_inductor!(
        plan;
        id="$(id)_inductance",
        at=node,
        inductance=inductance,
        role=:parallel_lc_inductance,
        label="$(id) L",
    )
    return ParallelLCResonator(string(id), node, capacitor, inductor)
end

function add_reflective_jpa!(
    plan::CircuitPlan;
    id,
    port_node,
    resonator_node,
    coupling_capacitance,
    resonator_capacitance,
    josephson_inductance,
)
    port_node isa AbstractNodeEndpoint ||
        _validation_error("add_reflective_jpa! requires port_node to be a NodeEndpoint.")
    resonator_node isa AbstractNodeEndpoint ||
        _validation_error("add_reflective_jpa! requires resonator_node to be a NodeEndpoint.")
    coupling = couple_capacitive!(
        plan;
        id="$(id)_coupling_capacitance",
        from=port_node,
        to=resonator_node,
        capacitance=coupling_capacitance,
        role=:jpa_coupling_capacitance,
        label="$(id) Cc",
    )
    capacitance = shunt_capacitor!(
        plan;
        id="$(id)_shunt_capacitance",
        at=resonator_node,
        capacitance=resonator_capacitance,
        role=:jpa_resonator_capacitance,
        label="$(id) C",
    )
    junction = josephson_junction!(
        plan;
        id="$(id)_junction",
        from=resonator_node,
        to=ground(),
        josephson_inductance=josephson_inductance,
        role=:jpa_josephson_junction,
        label="$(id) JJ",
    )
    return ReflectiveJPA(string(id), port_node, resonator_node, coupling, capacitance, junction)
end

function add_half_wave_resonator!(
    plan::CircuitPlan;
    id,
    head,
    tail,
    spec::RLGCSpec,
    breakpoints_m=nothing,
)
    line = build_lc_ladder_line!(
        plan;
        id=id,
        head=head,
        tail=tail,
        spec=spec,
        head_termination=:open,
        tail_termination=:open,
        breakpoints_m=breakpoints_m,
    )
    return HalfWaveResonator(string(id), line)
end

function add_quarter_wave_resonator!(
    plan::CircuitPlan;
    id,
    grounded_head,
    open_tail,
    spec::RLGCSpec,
    breakpoints_m=nothing,
)
    grounded_head isa AbstractNodeEndpoint ||
        _validation_error("add_quarter_wave_resonator! requires grounded_head to be a NodeEndpoint.")
    open_tail isa AbstractNodeEndpoint ||
        _validation_error("add_quarter_wave_resonator! requires open_tail to be a NodeEndpoint.")
    line = build_lc_ladder_line!(
        plan;
        id=id,
        head=grounded_head,
        tail=open_tail,
        spec=spec,
        head_termination=:short,
        tail_termination=:open,
        breakpoints_m=breakpoints_m,
    )
    return QuarterWaveResonator(string(id), line)
end

function add_readout_line_with_purcell_filter!(
    plan::CircuitPlan;
    id,
    input,
    output,
    input_line_spec::RLGCSpec,
    filter_spec::RLGCSpec,
    output_line_spec::RLGCSpec,
    input_coupling_f,
    output_coupling_f,
    filter_breakpoints_m=nothing,
)
    input isa AbstractNodeEndpoint ||
        _validation_error("add_readout_line_with_purcell_filter! requires input to be a NodeEndpoint.")
    output isa AbstractNodeEndpoint ||
        _validation_error("add_readout_line_with_purcell_filter! requires output to be a NodeEndpoint.")
    input_tail = _component_node(id, "input_tail")
    filter_head = _component_node(id, "filter_head")
    filter_tail = _component_node(id, "filter_tail")
    output_head = _component_node(id, "output_head")

    input_line = build_lc_ladder_line!(
        plan;
        id="$(id)_input_line",
        head=input,
        tail=input_tail,
        spec=input_line_spec,
        head_termination=:external,
        tail_termination=:open,
    )
    filter_line = build_lc_ladder_line!(
        plan;
        id="$(id)_purcell_filter",
        head=filter_head,
        tail=filter_tail,
        spec=filter_spec,
        head_termination=:open,
        tail_termination=:open,
        breakpoints_m=filter_breakpoints_m,
    )
    output_line = build_lc_ladder_line!(
        plan;
        id="$(id)_output_line",
        head=output_head,
        tail=output,
        spec=output_line_spec,
        head_termination=:open,
        tail_termination=:external,
    )
    input_coupling = couple_capacitive!(
        plan;
        id="$(id)_input_point_coupling",
        from=input_tail,
        to=filter_head,
        capacitance=input_coupling_f,
        role=:purcell_filter_point_coupling,
        label="$(id) input Cc",
    )
    output_coupling = couple_capacitive!(
        plan;
        id="$(id)_output_point_coupling",
        from=filter_tail,
        to=output_head,
        capacitance=output_coupling_f,
        role=:purcell_filter_point_coupling,
        label="$(id) output Cc",
    )
    return ReadoutLineWithPurcellFilter(
        string(id),
        input_line,
        filter_line,
        output_line,
        input_coupling,
        output_coupling,
        input,
        output,
        filter_head,
        filter_tail,
    )
end

function add_readout_purcell_qwr_mtl!(
    plan::CircuitPlan;
    id,
    input,
    output,
    input_line_spec::RLGCSpec,
    filter_spec::RLGCSpec,
    output_line_spec::RLGCSpec,
    qwr_spec::RLGCSpec,
    input_coupling_f,
    output_coupling_f,
    qwr_grounded_head,
    qwr_open_tail,
    window_start_filter_m,
    window_start_qwr_m,
    window_length_m,
    c12_per_m_f,
    lm_per_m_h,
)
    filter_breakpoints = [window_start_filter_m, Float64(window_start_filter_m) + Float64(window_length_m)]
    qwr_breakpoints = [window_start_qwr_m, Float64(window_start_qwr_m) + Float64(window_length_m)]
    readout_filter = add_readout_line_with_purcell_filter!(
        plan;
        id="$(id)_readout_filter",
        input=input,
        output=output,
        input_line_spec=input_line_spec,
        filter_spec=filter_spec,
        output_line_spec=output_line_spec,
        input_coupling_f=input_coupling_f,
        output_coupling_f=output_coupling_f,
        filter_breakpoints_m=filter_breakpoints,
    )
    qwr = add_quarter_wave_resonator!(
        plan;
        id="$(id)_qwr",
        grounded_head=qwr_grounded_head,
        open_tail=qwr_open_tail,
        spec=qwr_spec,
        breakpoints_m=qwr_breakpoints,
    )
    model = MTLCoupledWindowSpec(
        start1_m=window_start_filter_m,
        start2_m=window_start_qwr_m,
        length_m=window_length_m,
        section_length_m=min(filter_spec.reference_section_length_m, qwr_spec.reference_section_length_m),
        c12_per_m_f=c12_per_m_f,
        lm_per_m_h=lm_per_m_h,
    )
    window = couple_transmission_window!(
        plan;
        id="$(id)_filter_qwr_mtl_window",
        line1=readout_filter.filter_line,
        line2=qwr.line,
        start1=window_start_filter_m,
        start2=window_start_qwr_m,
        length=window_length_m,
        model=model,
    )
    return ReadoutPurcellQWRMTL(string(id), readout_filter, qwr, window)
end
