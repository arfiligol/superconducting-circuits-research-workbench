@testset "CircuitPlan stores authoring state" begin
    plan = CircuitPlan(; id="plan", metadata=Dict(:owner => "test"))
    @test plan.id == "plan"
    @test isempty(plan.components)
    @test plan.metadata[:owner] == "test"

    component = MinimalComponentLibrary.TestGroundedComponent("lc")
    register_component!(plan, component)
    @test haskey(plan.components, "lc")
    @test haskey(plan.parameters, :capacitance_f)

    relation = connect!(plan, pin(component, :signal), ground())
    @test relation isa NodeConnection
    @test length(plan.relations) == 1
end

@testset "duplicate component IDs are reported" begin
    plan = CircuitPlan("duplicates")
    register_component!(plan, MinimalComponentLibrary.TestGroundedComponent("lc"))
    register_component!(plan, MinimalComponentLibrary.TestGroundedComponent("lc"))
    report = validate_authoring(plan)
    @test has_errors(report)
    @test any(issue -> issue.code == :duplicate_component_id, errors(report))
end

