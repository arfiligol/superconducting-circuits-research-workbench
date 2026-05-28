@testset "inspection helpers return summaries" begin
    plan = build_sweep_plan(Dict{Symbol,Any}(:coupling_f => 1.0e-15))
    compiled = compile_to_josephson(plan)
    sweep = SweepSpec(axes=(coupling_f=NumericAxis([1.0e-15]),))
    preflight = preflight_sweep(build_sweep_plan, sweep)
    result = run_parameter_sweep(build_sweep_plan, sweep)

    @test inspect_plan(plan).component_count == 2
    @test !isempty(inspect_parameters(plan))
    @test !isempty(inspect_endpoints(plan))
    @test !isempty(inspect_topology_key(compiled).digest)
    @test inspect_sweep_preflight(preflight).estimated_simulations == 1
    @test summarize_sweep_result(result).point_count == 1

    df = sweep_result_dataframe(result)
    @test :point_index in propertynames(df)
    @test :success in propertynames(df)
end

