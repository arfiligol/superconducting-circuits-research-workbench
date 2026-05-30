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

function _default_line_spec(; length_m, section_length_m, l_per_m_h=4.2e-7, c_per_m_f=1.7e-10)
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
    capacitance=80.0e-15,
    inductance=10.0e-9,
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
    line_length_m=5.0e-3,
    xy_line_length_m=nothing,
    coupling_separation_m=0.5e-3,
    coupling_center_m=2.5e-3,
    section_length_m=0.5e-3,
    l_per_m_h=4.2e-7,
    xy_l_per_m_h=nothing,
    c_per_m_f=1.7e-10,
    xy_c_per_m_f=nothing,
    resonator_capacitance=65.0e-15,
    floating_capacitance=nothing,
    resonator_inductance=11.0e-9,
    floating_inductance=nothing,
    coupling_capacitance=3.0e-15,
    xy_coupling_capacitance=nothing,
    port_resistance=50.0,
    start_frequency=2.0e9,
    stop_frequency=10.0e9,
    point_count=1000,
    pump_frequency=12.0e9,
    pump_current=0.0,
    optional_hb_kwargs=Dict{Symbol,Any}(:nbatches => 1, :iterations => 120, :ftol => 1e-8),
)
    selected_line_length_m = isnothing(xy_line_length_m) ? line_length_m : xy_line_length_m
    selected_l_per_m_h = isnothing(xy_l_per_m_h) ? l_per_m_h : xy_l_per_m_h
    selected_c_per_m_f = isnothing(xy_c_per_m_f) ? c_per_m_f : xy_c_per_m_f
    selected_capacitance = isnothing(floating_capacitance) ? resonator_capacitance : floating_capacitance
    selected_inductance = isnothing(floating_inductance) ? resonator_inductance : floating_inductance
    selected_coupling = isnothing(xy_coupling_capacitance) ? coupling_capacitance : xy_coupling_capacitance
    left_coupling_m = Float64(coupling_center_m) - Float64(coupling_separation_m) / 2
    right_coupling_m = Float64(coupling_center_m) + Float64(coupling_separation_m) / 2
    plan = CircuitPlan(id)
    input = external_node("xy_input")
    output = external_node("xy_output")
    _external_two_port!(plan; input=input, output=output, port_resistance=port_resistance)
    line = build_lc_ladder_line!(
        plan;
        id="xy_line",
        head=input,
        tail=output,
        spec=_default_line_spec(
            length_m=selected_line_length_m,
            section_length_m=section_length_m,
            l_per_m_h=selected_l_per_m_h,
            c_per_m_f=selected_c_per_m_f,
        ),
        head_termination=:external,
        tail_termination=:external,
        breakpoints_m=[left_coupling_m, right_coupling_m],
    )
    positive = external_node("floating_lc_positive")
    negative = external_node("floating_lc_negative")
    resonator_cap = couple_capacitive!(
        plan;
        id="floating_lc_capacitance",
        from=positive,
        to=negative,
        capacitance=selected_capacitance,
        role=:floating_lc_capacitance,
        label="floating LC C",
    )
    resonator_ind = series_inductor!(
        plan;
        id="floating_lc_inductance",
        from=positive,
        to=negative,
        inductance=selected_inductance,
        role=:floating_lc_inductance,
        label="floating LC L",
    )
    left_coupling = couple_capacitive!(
        plan;
        id="floating_lc_left_coupling",
        from=node_at_distance(line, left_coupling_m),
        to=positive,
        capacitance=selected_coupling,
        role=:floating_lc_xy_coupling,
        label="left Cc",
    )
    right_coupling = couple_capacitive!(
        plan;
        id="floating_lc_right_coupling",
        from=node_at_distance(line, right_coupling_m),
        to=negative,
        capacitance=selected_coupling,
        role=:floating_lc_xy_coupling,
        label="right Cc",
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
            line=line,
            xy_line=line,
            floating_lc=(capacitance=resonator_cap, inductance=resonator_ind, positive=positive, negative=negative),
            xy_coupling=(left=left_coupling, right=right_coupling),
            resonator_cap=resonator_cap,
            resonator_ind=resonator_ind,
            left_coupling=left_coupling,
            right_coupling=right_coupling,
        ),
    )
end

function build_transmission_line_circuit_model_example(;
    id="transmission-line-circuit-model-example",
    length_m=4.0e-3,
    section_length_m=0.5e-3,
    l_per_m_h=4.2e-7,
    c_per_m_f=1.7e-10,
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
    l_per_m_h=4.2e-7,
    c_per_m_f=1.7e-10,
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
    )
    window_model = MTLCoupledWindowSpec(
        start1_m=window_start_readout_m,
        start2_m=window_start_resonator_m,
        length_m=window_length_m,
        section_length_m=section_length_m,
        c12_per_m_f=c12_per_m_f,
        lm_per_m_h=lm_per_m_h,
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
    l_per_m_h=4.2e-7,
    readout_l_per_m_h=nothing,
    purcell_l_per_m_h=nothing,
    qwr_l_per_m_h=nothing,
    c_per_m_f=1.7e-10,
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
    c12_per_m_f=4.0e-12,
    lm_per_m_h=0.5e-7,
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
        window_start_filter_m=selected_window_start_filter_m,
        window_start_qwr_m=window_start_qwr_m,
        window_length_m=window_length_m,
        c12_per_m_f=c12_per_m_f,
        lm_per_m_h=lm_per_m_h,
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
        ),
    )
end
