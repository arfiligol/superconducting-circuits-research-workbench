function _example_frequency_sweep(start_frequency, stop_frequency, point_count)
    point_count > 0 || _validation_error("point_count must be positive.")
    point_count == 1 && return [Float64(start_frequency)]
    return range(Float64(start_frequency), Float64(stop_frequency); length=Int(point_count))
end

function _passive_hb_intent!(
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

function _solve_example(plan::CircuitPlan; start_frequency, stop_frequency, point_count, pump_frequency, pump_current, optional_hb_kwargs)
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
        result=run_hb_problem(hb_problem),
    )
end

function build_lc_resonator_example(;
    id="lc-resonator-example",
    capacitance=80.0e-15,
    inductance=10.0e-9,
    port_resistance=50.0,
    start_frequency=1.0e9,
    stop_frequency=10.0e9,
    point_count=101,
    pump_frequency=8.0e9,
    pump_current=0.0,
    optional_hb_kwargs=Dict{Symbol,Any}(:nbatches => 1, :iterations => 120, :ftol => 1e-8),
)
    plan = CircuitPlan(id)
    signal = external_node("signal")
    external_port!(
        plan;
        id=:signal_port,
        index=1,
        endpoint=signal,
        resistance=port_resistance,
        role=:mixed,
    )
    shunt_capacitor!(
        plan;
        id="resonator_capacitance",
        at=signal,
        capacitance=capacitance,
        role=:resonator_capacitance,
        label="C to ground",
    )
    shunt_inductor!(
        plan;
        id="resonator_inductance",
        at=signal,
        inductance=inductance,
        role=:resonator_inductance,
        label="L to ground",
    )
    _passive_hb_intent!(plan; ports=[:signal_port])
    example = _solve_example(
        plan;
        start_frequency=start_frequency,
        stop_frequency=stop_frequency,
        point_count=point_count,
        pump_frequency=pump_frequency,
        pump_current=pump_current,
        optional_hb_kwargs=optional_hb_kwargs,
    )
    return merge(example, (; f0_estimate_hz=1 / (2π * sqrt(inductance * capacitance))))
end

function _default_line_spec(; length_m, section_length_m, l_per_m_h=4.2e-7, c_per_m_f=1.7e-10)
    return TransmissionLineSpec(
        length_m=length_m,
        section_length_m=section_length_m,
        l_per_m_h=l_per_m_h,
        c_per_m_f=c_per_m_f,
    )
end

function _two_port_line_plan(;
    id,
    line_id,
    length_m,
    section_length_m,
    l_per_m_h,
    c_per_m_f,
    port_resistance,
    tail_termination=:external,
)
    plan = CircuitPlan(id)
    input = external_node("input")
    output = external_node("output")
    external_port!(
        plan;
        id=:input_port,
        index=1,
        endpoint=input,
        resistance=port_resistance,
        role=:signal,
    )
    external_port!(
        plan;
        id=:output_port,
        index=2,
        endpoint=output,
        resistance=port_resistance,
        role=:readout,
    )
    line = build_lc_ladder_line!(
        plan;
        id=line_id,
        head=input,
        tail=output,
        spec=_default_line_spec(
            length_m=length_m,
            section_length_m=section_length_m,
            l_per_m_h=l_per_m_h,
            c_per_m_f=c_per_m_f,
        ),
        head_termination=:external,
        tail_termination=tail_termination,
    )
    _passive_hb_intent!(plan; ports=[:input_port, :output_port])
    return plan, line
end

function build_cpw_ladder_example(;
    id="cpw-ladder-example",
    length_m=4.0e-3,
    section_length_m=0.5e-3,
    l_per_m_h=4.2e-7,
    c_per_m_f=1.7e-10,
    port_resistance=50.0,
    start_frequency=2.0e9,
    stop_frequency=8.0e9,
    point_count=81,
    pump_frequency=10.0e9,
    pump_current=0.0,
    optional_hb_kwargs=Dict{Symbol,Any}(:nbatches => 1, :iterations => 120, :ftol => 1e-8),
)
    plan, line = _two_port_line_plan(
        id=id,
        line_id="cpw",
        length_m=length_m,
        section_length_m=section_length_m,
        l_per_m_h=l_per_m_h,
        c_per_m_f=c_per_m_f,
        port_resistance=port_resistance,
        tail_termination=:external,
    )
    example = _solve_example(
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

function build_purcell_filter_mvp_example(;
    id="purcell-filter-mvp-example",
    resonator_length_m=4.0e-3,
    section_length_m=0.5e-3,
    l_per_m_h=4.2e-7,
    c_per_m_f=1.7e-10,
    input_coupling_f=2.0e-15,
    output_coupling_f=2.0e-15,
    port_resistance=50.0,
    start_frequency=2.0e9,
    stop_frequency=10.0e9,
    point_count=81,
    pump_frequency=12.0e9,
    pump_current=0.0,
    optional_hb_kwargs=Dict{Symbol,Any}(:nbatches => 1, :iterations => 120, :ftol => 1e-8),
)
    plan = CircuitPlan(id)
    input = external_node("input")
    output = external_node("output")
    filter_head = external_node("purcell_filter_head")
    filter_tail = external_node("purcell_filter_tail")
    external_port!(plan; id=:input_port, index=1, endpoint=input, resistance=port_resistance, role=:signal)
    external_port!(plan; id=:output_port, index=2, endpoint=output, resistance=port_resistance, role=:readout)
    filter = build_lc_ladder_line!(
        plan;
        id="purcell_filter",
        head=filter_head,
        tail=filter_tail,
        spec=_default_line_spec(
            length_m=resonator_length_m,
            section_length_m=section_length_m,
            l_per_m_h=l_per_m_h,
            c_per_m_f=c_per_m_f,
        ),
        head_termination=:open,
        tail_termination=:open,
    )
    couple_capacitive!(
        plan;
        id="input_point_coupling",
        from=input,
        to=filter_head,
        capacitance=input_coupling_f,
        role=:point_capacitive_coupling,
        label="input Cc",
    )
    couple_capacitive!(
        plan;
        id="output_point_coupling",
        from=filter_tail,
        to=output,
        capacitance=output_coupling_f,
        role=:point_capacitive_coupling,
        label="output Cc",
    )
    _passive_hb_intent!(plan; ports=[:input_port, :output_port])
    example = _solve_example(
        plan;
        start_frequency=start_frequency,
        stop_frequency=stop_frequency,
        point_count=point_count,
        pump_frequency=pump_frequency,
        pump_current=pump_current,
        optional_hb_kwargs=optional_hb_kwargs,
    )
    return merge(example, (; filter=filter))
end

function build_long_readout_line_example(;
    id="long-readout-line-example",
    length_m=8.0e-3,
    section_length_m=0.5e-3,
    l_per_m_h=4.2e-7,
    c_per_m_f=1.7e-10,
    port_resistance=50.0,
    start_frequency=2.0e9,
    stop_frequency=10.0e9,
    point_count=81,
    pump_frequency=12.0e9,
    pump_current=0.0,
    optional_hb_kwargs=Dict{Symbol,Any}(:nbatches => 1, :iterations => 120, :ftol => 1e-8),
)
    plan, line = _two_port_line_plan(
        id=id,
        line_id="long_readout",
        length_m=length_m,
        section_length_m=section_length_m,
        l_per_m_h=l_per_m_h,
        c_per_m_f=c_per_m_f,
        port_resistance=port_resistance,
        tail_termination=:external,
    )
    example = _solve_example(
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

function build_hanging_qwr_mtl_example(;
    id="hanging-qwr-mtl-example",
    readout_length_m=6.0e-3,
    resonator_length_m=3.0e-3,
    section_length_m=0.75e-3,
    readout_l_per_m_h=4.2e-7,
    readout_c_per_m_f=1.7e-10,
    resonator_l_per_m_h=4.2e-7,
    resonator_c_per_m_f=1.7e-10,
    window_start_readout_m=2.25e-3,
    window_start_resonator_m=0.0,
    window_length_m=1.5e-3,
    c12_per_m_f=4.0e-12,
    lm_per_m_h=0.5e-7,
    port_resistance=50.0,
    start_frequency=6.0e9,
    stop_frequency=12.0e9,
    point_count=81,
    pump_frequency=14.0e9,
    pump_current=0.0,
    optional_hb_kwargs=Dict{Symbol,Any}(:nbatches => 1, :iterations => 160, :ftol => 1e-8),
)
    plan = CircuitPlan(id)
    input = external_node("input")
    output = external_node("output")
    qwr_head = external_node("qwr_head")
    qwr_ground = external_node("qwr_ground")
    external_port!(plan; id=:input_port, index=1, endpoint=input, resistance=port_resistance, role=:signal)
    external_port!(plan; id=:output_port, index=2, endpoint=output, resistance=port_resistance, role=:readout)

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
    )
    qwr = build_lc_ladder_line!(
        plan;
        id="qwr",
        head=qwr_head,
        tail=qwr_ground,
        spec=_default_line_spec(
            length_m=resonator_length_m,
            section_length_m=section_length_m,
            l_per_m_h=resonator_l_per_m_h,
            c_per_m_f=resonator_c_per_m_f,
        ),
        head_termination=:open,
        tail_termination=:short,
    )
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
    window = couple_transmission_window!(
        plan;
        id="readout_qwr_mtl_window",
        line1=readout_line,
        line2=qwr,
        start1=window_start_readout_m,
        start2=window_start_resonator_m,
        length=window_length_m,
        model=window_model,
    )
    _passive_hb_intent!(plan; ports=[:input_port, :output_port])
    example = _solve_example(
        plan;
        start_frequency=start_frequency,
        stop_frequency=stop_frequency,
        point_count=point_count,
        pump_frequency=pump_frequency,
        pump_current=pump_current,
        optional_hb_kwargs=optional_hb_kwargs,
    )
    return merge(example, (; readout_line=readout_line, qwr=qwr, window=window, window_model=window_model))
end
