function _framework_validation_message(f)
    try
        f()
    catch err
        @test err isa FrameworkValidationError
        return sprint(showerror, err)
    end
    @test false
    return ""
end

function _output_request_problem(;
    controls=HBSolverControls(
        n_pump_harmonics=1,
        n_modulation_harmonics=1,
    ),
    observables=nothing,
)
    plan = CircuitPlan("output-request")
    component = register_component!(
        plan,
        MinimalComponentLibrary.TestGroundedComponent("res");
        display_name=:res,
        role=:resonator,
    )
    external_port!(
        plan;
        id=:signal_port,
        index=1,
        endpoint=pin(component, :signal),
        resistance=50.0,
        role=:mixed,
    )
    hb_intent!(
        plan;
        pump_axes=[
            PumpAxis(id=:pump, frequency_parameter=:pump_frequency),
        ],
        source_slots=[
            HBSourceSlot(
                id=:pump_in,
                role=:pump,
                port=:signal_port,
                mode=(1,),
                current_parameter=:pump_current,
            ),
        ],
        observables=isnothing(observables) ? [
            SParameterRequest(
                id=:s11_signal,
                outputmode=(0,),
                outputport=:signal_port,
                inputmode=(0,),
                inputport=:signal_port,
            ),
        ] : observables,
        default_solver_controls=controls,
    )
    compiled = compile_to_josephson(plan)
    problem = build_hb_problem(
        compiled,
        HBRunSpec(
            frequency_sweep=[4.0e9],
            pump_frequencies=Dict(:pump => 8.0e9),
            source_currents=Dict(:pump_in => 0.0),
        ),
    )
    return compiled, problem
end

@testset "output request configuration validation is explicit" begin
    @test isdefined(SuperconductingCircuitsCore, :validate_output_request_configuration)
    @test :validate_output_request_configuration in names(SuperconductingCircuitsCore)
    @test isdefined(SuperconductingCircuitsCore, :OutputRequestConfigurationReport)
    @test :OutputRequestConfigurationReport in names(SuperconductingCircuitsCore)
    removed_function = Symbol("validate_" * "output_capabilities")
    @test !isdefined(SuperconductingCircuitsCore, removed_function)
    @test !(removed_function in names(SuperconductingCircuitsCore))

    compiled, problem = _output_request_problem()
    report = validate_output_request_configuration(compiled, problem)
    @test report isa OutputRequestConfigurationReport
    @test report.S
    @test report.Z
    @test report.QE
    @test report.QEideal
    @test report.CM

    compiled_disabled, problem_disabled = _output_request_problem(
        observables=Any[Dict(:id => :z11_signal, :family => :Z)],
        controls=HBSolverControls(
            n_pump_harmonics=1,
            n_modulation_harmonics=1,
            returnS=true,
            returnZ=false,
            returnQE=true,
            returnCM=true,
        ),
    )
    disabled_message = _framework_validation_message() do
        validate_output_request_configuration(compiled_disabled, problem_disabled)
    end
    @test occursin("z11_signal", disabled_message)
    @test occursin("disables", disabled_message)
    @test occursin("Z", disabled_message)

    compiled_unknown, problem_unknown = _output_request_problem(
        observables=Any[Dict(:id => :unknown_family_probe, :family => :UnknownThing)],
    )
    unknown_message = _framework_validation_message() do
        validate_output_request_configuration(compiled_unknown, problem_unknown)
    end
    @test occursin("unknown_family_probe", unknown_message)
    @test occursin("unknown", lowercase(unknown_message))
    @test occursin("UnknownThing", unknown_message)
    @test occursin("S", unknown_message)
    @test occursin("Z", unknown_message)
    @test occursin("QE", unknown_message)
    @test occursin("QEideal", unknown_message)
    @test occursin("CM", unknown_message)

    compiled_keyed, problem_keyed = _output_request_problem(
        controls=HBSolverControls(
            n_pump_harmonics=1,
            n_modulation_harmonics=1,
            keyedarrays=true,
        ),
    )
    keyed_message = _framework_validation_message() do
        validate_output_request_configuration(compiled_keyed, problem_keyed)
    end
    @test occursin("keyedarrays=false", keyed_message)
end

@testset "HBProblemSpec pump-off problem keeps pump axis and source slot" begin
    plan = CircuitPlan("pump-off")
    component = register_component!(
        plan,
        MinimalComponentLibrary.TestGroundedComponent("res");
        display_name=:res,
        role=:resonator,
    )
    external_port!(
        plan;
        id=:signal_port,
        index=1,
        endpoint=pin(component, :signal),
        resistance=50.0,
        role=:mixed,
    )
    hb_intent!(
        plan;
        pump_axes=[
            PumpAxis(id=:pump, frequency_parameter=:pump_frequency),
        ],
        source_slots=[
            HBSourceSlot(
                id=:pump_in,
                role=:pump,
                port=:signal_port,
                mode=(1,),
                current_parameter=:pump_current,
            ),
        ],
        observables=[
            SParameterRequest(
                id=:s11_signal,
                outputmode=(0,),
                outputport=:signal_port,
                inputmode=(0,),
                inputport=:signal_port,
            ),
        ],
        default_solver_controls=HBSolverControls(
            n_pump_harmonics=16,
            n_modulation_harmonics=(8,),
            returnS=true,
            returnZ=true,
            returnQE=true,
            returnCM=true,
        ),
    )

    compiled = compile_to_josephson(plan)
    run_spec = HBRunSpec(
        frequency_sweep=range(4e9, 6e9; length=3),
        pump_frequencies=Dict(:pump => 8.0e9),
        source_currents=Dict(:pump_in => 0.0),
    )
    problem = build_hb_problem(compiled, run_spec)

    @test problem.ws == collect(2π .* Float64.(run_spec.frequency_sweep))
    @test problem.wp == (2π * 8.0e9,)
    @test problem.sources == [(mode=(1,), port=1, current=0.0)]
    @test problem.Npumpharmonics == (16,)
    @test problem.Nmodulationharmonics == (8,)
    @test problem.controls.returnS
    @test problem.controls.returnZ
    @test problem.controls.returnQE
    @test problem.controls.returnCM
end

@testset "HBProblemSpec pumped source accepts zero current" begin
    plan = CircuitPlan("pumped")
    component = register_component!(
        plan,
        MinimalComponentLibrary.TestGroundedComponent("res");
        display_name=:res,
        role=:resonator,
    )
    external_port!(
        plan;
        id=:signal_port,
        index=1,
        endpoint=pin(component, :signal),
        resistance=50.0,
        role=:mixed,
    )
    hb_intent!(
        plan;
        pump_axes=[
            PumpAxis(id=:pump, frequency_parameter=:pump_frequency),
        ],
        source_slots=[
            HBSourceSlot(
                id=:pump_in,
                role=:pump,
                port=:signal_port,
                mode=(1,),
                current_parameter=:pump_current,
            ),
        ],
        observables=[
            SParameterRequest(
                id=:s11_signal,
                outputmode=(0,),
                outputport=:signal_port,
                inputmode=(0,),
                inputport=:signal_port,
            ),
        ],
        default_solver_controls=HBSolverControls(
            n_pump_harmonics=16,
            n_modulation_harmonics=8,
        ),
    )

    compiled = compile_to_josephson(plan)
    run_spec = HBRunSpec(
        frequency_sweep=[4.0e9, 5.0e9],
        pump_frequencies=Dict(:pump => 8.0e9),
        source_currents=Dict(:pump_in => 0.0),
    )
    problem = build_hb_problem(compiled, run_spec)

    @test problem.wp == (2π * 8.0e9,)
    @test problem.sources == [(mode=(1,), port=1, current=0.0)]
    @test problem.Npumpharmonics == (16,)
    @test problem.Nmodulationharmonics == (8,)
    @test problem.compiled === compiled
end

@testset "HBProblemSpec carries compiled execution payload for supported plans" begin
    plan = CircuitPlan("hb-execution-payload")
    component = register_component!(
        plan,
        MinimalComponentLibrary.TestGroundedComponent("res");
        display_name=:res,
        role=:resonator,
    )
    external_port!(
        plan;
        id=:signal_port,
        index=1,
        endpoint=pin(component, :signal),
        resistance=50.0,
        role=:mixed,
    )
    hb_intent!(
        plan;
        pump_axes=[
            PumpAxis(id=:pump, frequency_parameter=:pump_frequency),
        ],
        source_slots=[
            HBSourceSlot(
                id=:pump_in,
                role=:pump,
                port=:signal_port,
                mode=(1,),
                current_parameter=:pump_current,
            ),
        ],
        observables=[
            SParameterRequest(
                id=:s11_signal,
                outputmode=(0,),
                outputport=:signal_port,
                inputmode=(0,),
                inputport=:signal_port,
            ),
        ],
        default_solver_controls=HBSolverControls(
            n_pump_harmonics=16,
            n_modulation_harmonics=(8,),
        ),
    )

    compiled = compile_to_josephson(plan)
    @test !isempty(compiled.netlist)
    @test !isempty(compiled.component_values)

    problem = build_hb_problem(
        compiled,
        HBRunSpec(
            frequency_sweep=[4.0e9, 5.0e9],
            pump_frequencies=Dict(:pump => 8.0e9),
            source_currents=Dict(:pump_in => 0.0),
        ),
    )

    @test problem.compiled === compiled
    @test problem.frequencies_hz == [4.0e9, 5.0e9]
    @test !isempty(problem.compiled.netlist)
    @test !isempty(problem.compiled.component_values)
end

@testset "modulation harmonics are independent from pump-axis count" begin
    plan = CircuitPlan("double-pump")
    component = register_component!(
        plan,
        MinimalComponentLibrary.TestGroundedComponent("res");
        display_name=:res,
        role=:resonator,
    )
    external_port!(
        plan;
        id=:signal_port,
        index=1,
        endpoint=pin(component, :signal),
        resistance=50.0,
        role=:mixed,
    )
    hb_intent!(
        plan;
        pump_axes=[
            PumpAxis(id=:pump_1, frequency_parameter=:pump_1_frequency),
            PumpAxis(id=:pump_2, frequency_parameter=:pump_2_frequency),
        ],
        source_slots=[
            HBSourceSlot(
                id=:pump_1_in,
                role=:pump,
                port=:signal_port,
                mode=(1, 0),
                current_parameter=:pump_1_current,
            ),
            HBSourceSlot(
                id=:pump_2_in,
                role=:pump,
                port=:signal_port,
                mode=(0, 1),
                current_parameter=:pump_2_current,
            ),
        ],
        observables=[
            SParameterRequest(
                id=:s11_signal,
                outputmode=(0, 0),
                outputport=:signal_port,
                inputmode=(0, 0),
                inputport=:signal_port,
            ),
        ],
        default_solver_controls=HBSolverControls(
            n_pump_harmonics=Dict(:pump_1 => 8, :pump_2 => 10),
            n_modulation_harmonics=(6,),
        ),
    )

    compiled = compile_to_josephson(plan)
    problem = build_hb_problem(
        compiled,
        HBRunSpec(
            frequency_sweep=[5.0e9],
            pump_frequencies=Dict(:pump_1 => 8.0e9, :pump_2 => 9.0e9),
            source_currents=Dict(:pump_1_in => 0.0, :pump_2_in => 0.0),
        ),
    )

    @test problem.sources == [
        (mode=(1, 0), port=1, current=0.0),
        (mode=(0, 1), port=1, current=0.0),
    ]
    @test problem.Npumpharmonics == (8, 10)
    @test problem.Nmodulationharmonics == (6,)
end

@testset "HBProblemSpec DC bias source uses source_currents binding" begin
    plan = CircuitPlan("dc-bias-source")
    component = register_component!(
        plan,
        MinimalComponentLibrary.TestGroundedComponent("res");
        display_name=:res,
        role=:resonator,
    )
    external_port!(
        plan;
        id=:pump_port,
        index=1,
        endpoint=pin(component, :signal),
        resistance=50.0,
        role=:mixed,
    )
    hb_intent!(
        plan;
        pump_axes=[
            PumpAxis(id=:pump, frequency_parameter=:pump_frequency),
        ],
        source_slots=[
            HBSourceSlot(
                id=:dc_bias,
                role=:dc_bias,
                port=:pump_port,
                mode=(0,),
                current_parameter=:dc_current,
            ),
            HBSourceSlot(
                id=:pump_in,
                role=:pump,
                port=:pump_port,
                mode=(1,),
                current_parameter=:pump_current,
            ),
        ],
        observables=[
            SParameterRequest(
                id=:s11_signal,
                outputmode=(0,),
                outputport=:pump_port,
                inputmode=(0,),
                inputport=:pump_port,
            ),
        ],
        default_solver_controls=HBSolverControls(
            n_pump_harmonics=16,
            n_modulation_harmonics=(8,),
            dc=true,
            threewavemixing=true,
            fourwavemixing=true,
        ),
    )

    compiled = compile_to_josephson(plan)
    problem = build_hb_problem(
        compiled,
        HBRunSpec(
            frequency_sweep=[4.0e9, 5.0e9],
            pump_frequencies=Dict(:pump => 8.0e9),
            source_currents=Dict(:dc_bias => 0.0, :pump_in => 1.0e-6),
        ),
    )

    @test problem.sources == [
        (mode=(0,), port=1, current=0.0),
        (mode=(1,), port=1, current=1.0e-6),
    ]
    @test problem.controls.dc
    @test problem.Nmodulationharmonics == (8,)

    message = _framework_validation_message() do
        build_hb_problem(
            compiled,
            HBRunSpec(
                frequency_sweep=[4.0e9],
                pump_frequencies=Dict(:pump => 8.0e9),
                source_currents=Dict(:pump_in => 1.0e-6),
            ),
        )
    end
    @test occursin("missing source current binding", message)
    @test occursin("dc_bias", message)
end

@testset "HBIntent validates DC bias source declarations" begin
    plan_wrong_mode = CircuitPlan("dc-wrong-mode")
    component_wrong_mode = register_component!(
        plan_wrong_mode,
        MinimalComponentLibrary.TestGroundedComponent("res");
        display_name=:res,
        role=:resonator,
    )
    external_port!(
        plan_wrong_mode;
        id=:pump_port,
        index=1,
        endpoint=pin(component_wrong_mode, :signal),
        resistance=50.0,
        role=:mixed,
    )
    hb_intent!(
        plan_wrong_mode;
        pump_axes=[
            PumpAxis(id=:pump, frequency_parameter=:pump_frequency),
        ],
        source_slots=[
            HBSourceSlot(
                id=:dc_bias,
                role=:dc_bias,
                port=:pump_port,
                mode=(1,),
                current_parameter=:dc_current,
            ),
        ],
        default_solver_controls=HBSolverControls(dc=true),
    )

    wrong_mode_message = _framework_validation_message() do
        compile_to_josephson(plan_wrong_mode)
    end
    @test occursin("DC bias source slot 'dc_bias' must use mode (0,).", wrong_mode_message)

    plan_dc_disabled = CircuitPlan("dc-disabled")
    component_dc_disabled = register_component!(
        plan_dc_disabled,
        MinimalComponentLibrary.TestGroundedComponent("res");
        display_name=:res,
        role=:resonator,
    )
    external_port!(
        plan_dc_disabled;
        id=:pump_port,
        index=1,
        endpoint=pin(component_dc_disabled, :signal),
        resistance=50.0,
        role=:mixed,
    )
    hb_intent!(
        plan_dc_disabled;
        pump_axes=[
            PumpAxis(id=:pump, frequency_parameter=:pump_frequency),
        ],
        source_slots=[
            HBSourceSlot(
                id=:dc_bias,
                role=:dc_bias,
                port=:pump_port,
                mode=(0,),
                current_parameter=:dc_current,
            ),
        ],
        default_solver_controls=HBSolverControls(dc=false),
    )

    dc_disabled_message = _framework_validation_message() do
        compile_to_josephson(plan_dc_disabled)
    end
    @test occursin("DC bias source slot 'dc_bias' requires HBSolverControls(dc=true).", dc_disabled_message)
end

@testset "HBSolverControls product output family defaults" begin
    controls = HBSolverControls()

    @test controls.returnS
    @test controls.returnZ
    @test controls.returnQE
    @test controls.returnCM
end
