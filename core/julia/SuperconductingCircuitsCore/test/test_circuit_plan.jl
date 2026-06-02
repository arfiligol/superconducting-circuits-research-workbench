@testset "CircuitPlan stores authoring state" begin
    plan = CircuitPlan(; id="plan", metadata=Dict(:owner => "test"))
    @test plan.id == "plan"
    @test isempty(plan.components)
    @test plan.metadata[:owner] == "test"

    component = MinimalComponentLibrary.TestGroundedComponent("lc")
    register_component!(plan, component)
    @test haskey(plan.components, "lc")
    @test haskey(plan.parameters, :capacitance)

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

@testset "external ports use formal declarations" begin
    plan = CircuitPlan("formal-port")
    component = register_component!(plan, MinimalComponentLibrary.TestGroundedComponent("lc"))
    port = external_port!(
        plan;
        id=:signal_port,
        index=1,
        endpoint=pin(component, :signal),
        resistance=50.0,
        role=:mixed,
    )
    shunt_capacitor!(
        plan;
        id="lc_shunt",
        at=pin(component, :signal),
        capacitance=80.0e-15,
    )

    @test port isa EngineeringPort
    @test plan.metadata[:external_ports][:signal_port] isa ExternalPort

    compiled = compile_to_josephson(plan)

    @test ("P1", "ext_signal_port", "0", 1) in compiled.netlist
    @test ("R_port_1", "ext_signal_port", "0", :R_port_1) in compiled.netlist
    @test compiled.port_map[:signal_port] == (index=1,)
end

@testset "legacy external port metadata is rejected" begin
    legacy_specs = Any[
        ["port_1"],
        [:port_1],
        [(name="port_1", index=1, resistance_ohm=50.0)],
    ]

    for spec in legacy_specs
        plan = CircuitPlan(; id="legacy-port", metadata=Dict{Symbol,Any}(:external_ports => spec))
        @test_throws FrameworkValidationError compile_to_josephson(plan)
    end
end
