@testset "relations and coupling constraints" begin
    plan = CircuitPlan("relations")
    lc = register_component!(plan, MinimalComponentLibrary.TestGroundedComponent("lc"))
    qwr = register_component!(plan, MinimalComponentLibrary.TestLineComponent("qwr", [:main], :main))
    readout = register_component!(plan, MinimalComponentLibrary.TestLineComponent("readout", [:main], :main))

    connect!(plan, pin(lc, :signal), external_node("drive"))
    couple_capacitive!(
        plan;
        id="lc_to_qwr",
        from=pin(lc, :signal),
        to=line_tap(qwr; at_m=0.2mm),
        capacitance=3.0e-15,
        parameters=[
            ParameterMetadata(
                name=:coupling_capacitance,
                role=NumericParameter(),
                owner="lc_to_qwr",
                targets=[:capacitance],
                units="F",
            ),
        ],
    )
    shunt_capacitor!(plan; id="shunt", at=line_tap(readout; at_m=0.1mm), capacitance=20.0e-15)
    shunt_inductor!(
        plan;
        id="readout_shunt_l",
        at=line_tap(readout; at_m=0.1mm),
        inductance=8.0e-9,
        parameters=[
            ParameterMetadata(
                name=:readout_shunt_inductance,
                role=NumericParameter(),
                owner="readout_shunt_l",
                targets=[:inductance],
                units="H",
            ),
        ],
    )
    couple_window!(
        plan;
        id="window",
        line_a=line_span(qwr; from_m=0.1mm, to_m=0.2mm),
        line_b=line_span(readout; from_m=0.1mm, to_m=0.2mm),
        spec=(kind=:test_window,),
    )
    couple_inductive!(
        plan;
        id="flux",
        from=line_tap(readout; at_m=0.15mm),
        to=loop_endpoint(lc, :loop),
        mutual_inductance=3.0e-12,
    )

    @test length(plan.relations) == 6
    @test haskey(plan.parameters, :coupling_capacitance)
    @test haskey(plan.parameters, :readout_shunt_inductance)
    @test any(relation -> relation isa ShuntCapacitor, plan.relations)
    @test any(relation -> relation isa ShuntInductor, plan.relations)
    @test validate_authoring(plan).issues == ValidationIssue[]

    graph_relations = engineering_graph(plan).relations
    @test length(graph_relations) == length(plan.relations)
    @test any(
        relation ->
            relation.id == :connect_1 &&
                relation.relation_type == :connect &&
                relation.role == :node_connection,
        graph_relations,
    )
    @test any(
        relation ->
            relation.id == :lc_to_qwr &&
                relation.relation_type == :couple &&
                relation.role == :capacitive_coupling,
        graph_relations,
    )
    @test any(
        relation ->
            relation.id == :shunt &&
                relation.relation_type == :terminates &&
                relation.through == :capacitance,
        graph_relations,
    )
    @test any(
        relation ->
            relation.id == :readout_shunt_l &&
                relation.relation_type == :terminates &&
                relation.through == :inductance,
        graph_relations,
    )
    @test any(
        relation ->
            relation.id == :window &&
                relation.relation_type == :couple &&
                relation.through == :coupled_window,
        graph_relations,
    )

    @test_throws FrameworkValidationError connect!(plan, line_span(qwr; from_m=0.1mm, to_m=0.2mm), ground())
    @test_throws FrameworkValidationError couple_capacitive!(
        plan;
        id="bad",
        from=line_span(qwr; from_m=0.1mm, to_m=0.2mm),
        to=ground(),
        capacitance=1.0e-15,
    )
    @test_throws FrameworkValidationError shunt_inductor!(
        plan;
        id="bad_inductor",
        at=line_span(qwr; from_m=0.1mm, to_m=0.2mm),
        inductance=1.0e-9,
    )
end
