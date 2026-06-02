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
    external_port!(plan; id=:signal_port, index=1, endpoint=signal, resistance=port_resistance, role=:mixed)
    resonator = add_parallel_lc_resonator!(
        plan;
        id="resonator",
        node=signal,
        capacitance=capacitance,
        inductance=inductance,
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
    external_port!(plan; id=:signal_port, index=1, endpoint=port_node, resistance=port_resistance, role=:signal)
    jpa = add_reflective_jpa!(
        plan;
        id="jpa",
        port_node=port_node,
        resonator_node=resonator_node,
        coupling_capacitance=coupling_capacitance,
        resonator_capacitance=resonator_capacitance,
        josephson_inductance=josephson_inductance,
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
        label="floating XY Cg1",
    )
    c_g2_relation = shunt_capacitor!(
        plan;
        id="floating_xy_c_g2",
        at=pad2,
        capacitance=c_g2,
        role=:floating_xy_pad_ground_capacitance,
        label="floating XY Cg2",
    )
    c_q_relation = couple_capacitive!(
        plan;
        id="floating_xy_c_q",
        from=pad1,
        to=pad2,
        capacitance=c_q,
        role=:floating_xy_qubit_capacitance,
        label="floating XY Cq",
    )
    l_q1_relation = series_inductor!(
        plan;
        id="floating_xy_l_q1",
        from=pad1,
        to=pad2,
        inductance=l_jun,
        role=:floating_xy_qubit_inductance,
        label="floating XY Lq1",
    )
    l_q2_relation = series_inductor!(
        plan;
        id="floating_xy_l_q2",
        from=pad1,
        to=pad2,
        inductance=l_jun,
        role=:floating_xy_qubit_inductance,
        label="floating XY Lq2",
    )
    c_xy1_relation = couple_capacitive!(
        plan;
        id="floating_xy_c_xy1",
        from=pad1,
        to=xy_node,
        capacitance=c_xy1,
        role=:floating_xy_line_coupling,
        label="floating XY Cxy1",
    )
    c_xy2_relation = couple_capacitive!(
        plan;
        id="floating_xy_c_xy2",
        from=pad2,
        to=xy_node,
        capacitance=c_xy2,
        role=:floating_xy_line_coupling,
        label="floating XY Cxy2",
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
