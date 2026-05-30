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
    series_inductor!(
        plan;
        id="readout_series_l",
        from=line_tap(readout; at_m=0.1mm),
        to=external_node("readout_mid"),
        inductance=1.2e-9,
    )
    series_resistor!(
        plan;
        id="readout_series_r",
        from=external_node("readout_mid"),
        to=external_node("readout_out"),
        resistance=2.5,
        parameters=[
            ParameterMetadata(
                name=:readout_series_resistance,
                role=NumericParameter(),
                owner="readout_series_r",
                targets=[:resistance],
                units="ohm",
            ),
        ],
    )
    josephson_junction!(
        plan;
        id="jpa_junction",
        from=pin(lc, :signal),
        to=ground(),
        josephson_inductance=7.5e-9,
        parameters=[
            ParameterMetadata(
                name=:jpa_lj,
                role=NumericParameter(),
                owner="jpa_junction",
                targets=[:josephson_inductance],
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

    @test length(plan.relations) == 9
    @test haskey(plan.parameters, :coupling_capacitance)
    @test haskey(plan.parameters, :readout_shunt_inductance)
    @test haskey(plan.parameters, :readout_series_resistance)
    @test haskey(plan.parameters, :jpa_lj)
    @test any(relation -> relation isa ShuntCapacitor, plan.relations)
    @test any(relation -> relation isa ShuntInductor, plan.relations)
    @test any(relation -> relation isa SeriesInductor, plan.relations)
    @test any(relation -> relation isa SeriesResistor, plan.relations)
    @test any(relation -> relation isa JosephsonJunction, plan.relations)
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
            relation.id == :readout_series_l &&
                relation.relation_type == :series &&
                relation.through == :inductance,
        graph_relations,
    )
    @test any(
        relation ->
            relation.id == :readout_series_r &&
                relation.relation_type == :series &&
                relation.through == :resistance,
        graph_relations,
    )
    @test any(
        relation ->
            relation.id == :jpa_junction &&
                relation.relation_type == :josephson_junction,
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
    @test_throws FrameworkValidationError series_inductor!(
        plan;
        id="bad_series_inductor",
        from=line_span(qwr; from_m=0.1mm, to_m=0.2mm),
        to=ground(),
        inductance=1.0e-9,
    )
    @test_throws FrameworkValidationError series_resistor!(
        plan;
        id="bad_series_resistor",
        from=line_span(qwr; from_m=0.1mm, to_m=0.2mm),
        to=ground(),
        resistance=50.0,
    )
    @test_throws FrameworkValidationError josephson_junction!(
        plan;
        id="bad_jj",
        from=line_span(qwr; from_m=0.1mm, to_m=0.2mm),
        to=ground(),
        josephson_inductance=7.0e-9,
    )
end
