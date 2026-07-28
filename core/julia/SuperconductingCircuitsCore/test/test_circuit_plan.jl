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

@testset "linearized floating qubit reusable component" begin
    plan = CircuitPlan("linearized-floating-qubit")
    island_1 = external_node("island_1")
    island_2 = external_node("island_2")
    readout = external_node("readout")
    qubit = add_linearized_floating_qubit!(
        plan;
        id="q01",
        island_1=island_1,
        island_2=island_2,
        readout_attachment=readout,
        c01_f=60e-15,
        c02_f=61e-15,
        c12_f=40e-15,
        cr1_f=5e-15,
        cr2_f=6e-15,
        l_j_per_junction_h=21.5e-9,
    )

    @test qubit isa LinearizedFloatingQubit
    @test length(plan.relations) == 7
    @test count(relation -> relation isa ShuntCapacitor, plan.relations) == 2
    @test count(relation -> relation isa CapacitiveCoupling, plan.relations) == 3
    @test count(relation -> relation isa SeriesInductor, plan.relations) == 2
    @test engineering_graph(plan).components[:q01].component_type == :LinearizedFloatingQubit
    @test engineering_graph(plan).components[:q01].parameters[:inductive_branch_kind] ==
          :linearized_josephson
    compiled = compile_to_josephson(plan)
    inductive_rows = filter(row -> startswith(row[1], "L_"), compiled.netlist)
    @test Set(row[1] for row in inductive_rows) == Set(["L_q01_lj1", "L_q01_lj2"])
    @test !any(row -> startswith(row[1], "Lj"), compiled.netlist)
    @test_throws FrameworkValidationError add_linearized_floating_qubit!(
        CircuitPlan("invalid-linearized-floating-qubit");
        id="q01",
        island_1=island_1,
        island_2=island_2,
        readout_attachment=readout,
        c01_f=0.0,
        c02_f=61e-15,
        c12_f=40e-15,
        cr1_f=5e-15,
        cr2_f=6e-15,
        l_j_per_junction_h=21.5e-9,
    )
end
