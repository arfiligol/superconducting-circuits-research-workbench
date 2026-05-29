import JosephsonCircuits: hbsolve

struct HBRunnerRecordingNetlist
    calls::Vector{Any}
end

struct HBRunnerMockLinearized
    modes::Vector{Tuple{Int}}
    portnumbers::Vector{Int}
    S::Array{ComplexF64,3}
    Z::Array{ComplexF64,3}
    QE::Array{Float64,3}
    QEideal::Array{Float64,3}
    CM::Array{Float64,2}
end

struct HBRunnerMockSolution
    linearized::HBRunnerMockLinearized
end

function hbsolve(
    ws,
    wp::NTuple{N,Number},
    sources::Vector,
    n_modulation::NTuple{M,Int},
    n_pump::NTuple{N,Int},
    netlist::HBRunnerRecordingNetlist,
    component_values::Dict;
    kwargs...,
) where {N,M}
    push!(
        netlist.calls,
        (
            ws=collect(ws),
            wp=wp,
            sources=sources,
            n_modulation=n_modulation,
            n_pump=n_pump,
            component_values=Dict(component_values),
            kwargs=Dict(kwargs),
        ),
    )
    s = reshape(ComplexF64[1 + 0im, 2 + 0im], 1, 1, 2)
    z = reshape(ComplexF64[3 + 0im, 4 + 0im], 1, 1, 2)
    qe = reshape(Float64[5, 6], 1, 1, 2)
    qeideal = reshape(Float64[7, 8], 1, 1, 2)
    cm = reshape(Float64[1, 1], 1, 2)
    return HBRunnerMockSolution(HBRunnerMockLinearized([(0,)], [1], s, z, qe, qeideal, cm))
end

@testset "run_hbsolve forwards normalized hbsolve call arguments once" begin
    calls = Any[]
    netlist = HBRunnerRecordingNetlist(calls)
    sources = [(mode=(1,), port=1, current=0.0)]

    result = run_hbsolve(
        netlist,
        Dict(:L_res => 8.0e-9),
        [4.0e9, 5.0e9];
        pump_frequencies_hz=(8.0e9,),
        sources=sources,
        n_modulation_harmonics=(8,),
        n_pump_harmonics=(16,),
        port_indices=[1],
        dc=true,
        returnZ=false,
        switchofflinesearchtol=0.1,
    )

    @test result isa HBSolveResult
    @test result.frequencies_hz == [4.0e9, 5.0e9]
    @test length(calls) == 1

    call = only(calls)
    @test call.ws == 2π .* [4.0e9, 5.0e9]
    @test call.wp == (2π * 8.0e9,)
    @test call.sources == sources
    @test call.n_modulation == (8,)
    @test call.n_pump == (16,)
    @test call.component_values == Dict(:L_res => 8.0e-9)
    @test call.kwargs[:dc]
    @test call.kwargs[:returnS]
    @test !call.kwargs[:returnZ]
    @test call.kwargs[:switchofflinesearchtol] == 0.1
    @test result.traces[:zero_mode_s]["S11"] == ComplexF64[1 + 0im, 2 + 0im]
end

@testset "HBProblemSpec normalized frequencies are the solver-facing values" begin
    plan = CircuitPlan("hb-normalized-frequency-payload")
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

    problem = build_hb_problem(
        compile_to_josephson(plan),
        HBRunSpec(
            frequency_sweep=[4.0e9, 5.0e9],
            pump_frequencies=Dict(:pump => 8.0e9),
            source_currents=Dict(:pump_in => 0.0),
        ),
    )

    @test problem.ws == 2π .* [4.0e9, 5.0e9]
    @test problem.wp == (2π * 8.0e9,)
end

@testset "run_hb_problem executes JosephsonCircuits for pump-off lumped plan" begin
    plan = CircuitPlan("hb-real-run")
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
    shunt_capacitor!(
        plan;
        id="res_c",
        at=pin(component, :signal),
        capacitance=80e-15,
    )
    shunt_inductor!(
        plan;
        id="res_l",
        at=pin(component, :signal),
        inductance=10e-9,
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
            n_pump_harmonics=1,
            n_modulation_harmonics=1,
            returnS=true,
            returnZ=true,
            returnQE=true,
            returnCM=true,
            keyedarrays=false,
        ),
    )

    problem = build_hb_problem(
        compile_to_josephson(plan),
        HBRunSpec(
            frequency_sweep=[4.0e9, 5.0e9],
            pump_frequencies=Dict(:pump => 8.0e9),
            source_currents=Dict(:pump_in => 0.0),
            optional_hb_kwargs=Dict(:nbatches => 1),
        ),
    )
    result = run_hb_problem(problem)

    @test result isa HBSolveResult
    @test result.frequencies_hz == [4.0e9, 5.0e9]
    @test haskey(result.traces, :s_parameter_mode)
    @test haskey(result.traces, :z_parameter_mode)
    @test haskey(result.traces, :qe_mode)
    @test haskey(result.traces, :qeideal_mode)
    @test haskey(result.traces, :cm_mode)
    @test result.traces[:zero_mode_s]["S11"] isa Vector{ComplexF64}
end
