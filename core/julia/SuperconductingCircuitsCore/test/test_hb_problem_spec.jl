@testset "HBIntent pure linear no-pump problem spec" begin
    plan = CircuitPlan("pure-linear")
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
        pump_axes=PumpAxis[],
        source_slots=HBSourceSlot[],
        observables=[
            SParameterRequest(
                id=:s11_signal,
                outputmode=(),
                outputport=:signal_port,
                inputmode=(),
                inputport=:signal_port,
            ),
        ],
        default_solver_controls=HBSolverControls(
            n_modulation_harmonics=0,
            returnS=true,
            returnZ=true,
            returnQE=true,
            returnCM=true,
        ),
    )

    compiled = compile_to_josephson(plan)
    run_spec = HBRunSpec(
        frequency_sweep=range(4e9, 6e9; length=3),
        pump_frequencies=Dict{Symbol,Float64}(),
        source_currents=Dict{Symbol,Float64}(),
    )
    problem = build_hb_problem(compiled, run_spec)

    @test problem.wp == ()
    @test isempty(problem.sources)
    @test problem.Npumpharmonics == ()
    @test problem.Nmodulationharmonics == (0,)
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
    @test_throws FrameworkValidationError run_hb_problem(problem)
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
        source_slots=HBSourceSlot[],
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
            source_currents=Dict{Symbol,Float64}(),
        ),
    )

    @test problem.Npumpharmonics == (8, 10)
    @test problem.Nmodulationharmonics == (6,)
end
