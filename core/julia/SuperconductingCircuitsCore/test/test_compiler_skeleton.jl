@testset "compiler skeleton returns compiled circuit" begin
    plan = CircuitPlan("empty")
    compiled = compile_to_josephson(plan)
    @test compiled isa JosephsonCompiledCircuit
    @test isempty(compiled.netlist)
    @test topology_key(compiled) isa TopologyKey
    @test !isempty(compiled.warnings)
end

@testset "topology key excludes numeric metadata and includes topology" begin
    plan_a = CircuitPlan("same")
    plan_b = CircuitPlan("same")
    register_component!(plan_a, MinimalComponentLibrary.TestGroundedComponent("lc"))
    register_component!(plan_b, MinimalComponentLibrary.TestGroundedComponent("lc"))

    register_parameter!(
        plan_a,
        ParameterMetadata(name=:c, role=NumericParameter(), owner="lc", valid_domain=(1.0, 2.0)),
    )
    register_parameter!(
        plan_b,
        ParameterMetadata(name=:c, role=NumericParameter(), owner="lc", valid_domain=(10.0, 20.0)),
    )
    @test topology_key(plan_a).digest == topology_key(plan_b).digest

    register_parameter!(
        plan_b,
        ParameterMetadata(name=:n_sections, role=StructuralParameter(), owner="lc", targets=[:n_sections]),
    )
    @test topology_key(plan_a).digest != topology_key(plan_b).digest

    connect!(plan_a, pin("lc", :signal), ground())
    @test topology_key(plan_a).digest != topology_key(CircuitPlan("same")).digest
end

@testset "topology key excludes plan identity" begin
    plan_a = CircuitPlan("plan-a")
    plan_b = CircuitPlan("plan-b")
    register_component!(plan_a, MinimalComponentLibrary.TestGroundedComponent("lc"))
    register_component!(plan_b, MinimalComponentLibrary.TestGroundedComponent("lc"))
    connect!(plan_a, pin("lc", :signal), ground())
    connect!(plan_b, pin("lc", :signal), ground())

    @test topology_key(plan_a).digest == topology_key(plan_b).digest
    @test topology_key(plan_a).summary[:plan_id] == "plan-a"
end

@testset "compile validation rejects unresolved endpoints" begin
    plan = CircuitPlan("bad")
    connect!(plan, pin("missing", :signal), ground())
    @test_throws FrameworkValidationError compile_to_josephson(plan)
end
