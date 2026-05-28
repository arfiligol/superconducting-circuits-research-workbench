function build_sweep_plan(params)
    plan = CircuitPlan("sweep")
    qwr = register_component!(plan, MinimalComponentLibrary.TestLineComponent("qwr", [:main], :main))
    lc = register_component!(plan, MinimalComponentLibrary.TestGroundedComponent("lc"))
    position = get(params, :tap_m, 0.1mm)
    couple_capacitive!(
        plan;
        id="coupling",
        from=pin(lc, :signal),
        to=line_tap(qwr; at_m=position),
        capacitance=get(params, :coupling_f, 1.0e-15),
    )
    return plan
end

@testset "SweepSpec and preflight estimates" begin
    numeric = SweepSpec(axes=(coupling_f=NumericAxis([1.0e-15, 2.0e-15]),), compile_policy=CompileOnce())
    numeric_plan = preflight_sweep(build_sweep_plan, numeric)
    @test numeric_plan isa SweepExecutionPlan
    @test numeric_plan.estimated_compiles == 1
    @test numeric_plan.estimated_simulations == 2

    structural = SweepSpec(axes=(tap_m=StructuralAxis([0.1mm, 0.2mm]),), compile_policy=CompileEveryPoint())
    structural_plan = preflight_sweep(build_sweep_plan, structural)
    @test structural_plan.estimated_compiles == 2

    grouped = SweepSpec(
        axes=(tap_m=StructuralAxis([0.1mm, 0.1mm, 0.2mm]), coupling_f=NumericAxis([1.0e-15])),
        compile_policy=CompileByTopologyKey(),
    )
    grouped_plan = preflight_sweep(build_sweep_plan, grouped)
    @test grouped_plan.estimated_compiles == 2
end

@testset "run_parameter_sweep preserves point order" begin
    sweep = SweepSpec(
        axes=(coupling_f=NumericAxis([1.0, 2.0, 3.0]),),
        compile_policy=CompileOnce(),
        executor=ThreadedExecutor(),
    )
    result = run_parameter_sweep(build_sweep_plan, sweep; simulate=(_compiled, point) -> point[:coupling_f])
    @test result isa SweepResult
    @test result.point_results == Any[1.0, 2.0, 3.0]
    @test all(==(:success), result.point_statuses)
    @test result.execution_plan.estimated_compiles == 1
end

