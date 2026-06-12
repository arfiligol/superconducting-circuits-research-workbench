@testset "RLGCSpec construction and LC ladder generation" begin
    spec = RLGCSpec(
        length_m=1.0mm,
        section_length_m=0.25mm,
        l_per_m_h=4.2e-7,
        c_per_m_f=1.7e-10,
    )
    @test spec.n_sections == 4
    @test spec.section_length_m ≈ 0.25mm
    values = section_values(spec)
    @test values.l_h ≈ 4.2e-7 * 0.25mm
    @test values.c_f ≈ 1.7e-10 * 0.25mm

    plan = CircuitPlan("tl-ladder")
    head = external_node("head")
    tail = external_node("tail")
    ladder = build_lc_ladder_line!(
        plan;
        id="line",
        head=head,
        tail=tail,
        spec=spec,
        head_termination=:external,
        tail_termination=:open,
    )

    @test ladder.id == "line"
    @test ladder.head == head
    @test ladder.tail == tail
    @test ladder.nodes[1] == head
    @test ladder.nodes[end] == tail
    @test length(ladder.nodes) == 5
    @test length(ladder.series_inductors) == 4
    section_capacitance = 1.7e-10 * 0.25mm
    expected_node_capacitances = [
        section_capacitance / 2,
        section_capacitance,
        section_capacitance,
        section_capacitance,
        section_capacitance / 2,
    ]
    @test length(ladder.shunt_capacitors) == 5
    @test [capacitor.capacitance for capacitor in ladder.shunt_capacitors] ≈ expected_node_capacitances
    @test ladder.section_lengths_m == fill(0.25mm, 4)
    @test ladder.section_boundaries_m ≈ [0.0, 0.25mm, 0.5mm, 0.75mm, 1.0mm]
    @test isempty(ladder.termination_relations)
    @test node_at_distance(ladder, 0.5mm) == ladder.nodes[3]
    @test section_index_at_distance(ladder, 0.5mm) == 3
    @test section_range_from_window(ladder, 0.25mm, 0.5mm) == 2:3
    @test haskey(plan.metadata[:transmission_line_ladders], :line)
    graph_ladder = only(filter(relation -> relation.relation_type == :transmission_line_ladder, engineering_graph(plan).relations))
    @test graph_ladder.parameters[:section_model] == :pi
    @test graph_ladder.parameters[:node_shunt_positions_m] ≈ [0.0, 0.25mm, 0.5mm, 0.75mm, 1.0mm]
    @test graph_ladder.parameters[:node_shunt_capacitance_f] ≈ expected_node_capacitances

    external_port!(
        plan;
        id=:head_port,
        index=1,
        endpoint=head,
        resistance=50.0,
        role=:line_head,
    )
    compiled = compile_to_josephson(plan)
    @test count(row -> startswith(row[1], "C_line_c_node"), compiled.netlist) == 5
    @test ("L_line_l_1", "ext_head", "ext_line_node_1", :L_line_l_1) in compiled.netlist
    @test ("C_line_c_node_0", "ext_head", "0", :C_line_c_node_0) in compiled.netlist
    @test ("C_line_c_node_4", "ext_tail", "0", :C_line_c_node_4) in compiled.netlist
end

@testset "RLGCSpec derives section count from reference length" begin
    spec = RLGCSpec(
        length_m=5.28371mm,
        section_length_m=0.75mm,
        l_per_m_h=4.2e-7,
        c_per_m_f=1.7e-10,
    )

    @test spec.n_sections == 8
    @test spec.reference_section_length_m ≈ 0.75mm
    @test spec.section_length_m ≈ 5.28371mm / 8

    values = section_values(spec)
    @test values.dx_m ≈ spec.section_length_m
    @test values.l_h ≈ 4.2e-7 * spec.section_length_m
    @test values.c_f ≈ 1.7e-10 * spec.section_length_m
end

@testset "Transmission-line section overrides replace per-section RLGC values" begin
    spec = RLGCSpec(
        length_m=2.0mm,
        section_length_m=0.5mm,
        l_per_m_h=4.2e-7,
        c_per_m_f=1.7e-10,
    )
    override = TransmissionLineSectionOverride(
        start_m=0.5mm,
        length_m=1.0mm,
        l_per_m_h=4.1e-7,
        c_per_m_f=1.8e-10,
        tag=:coupled_section,
    )
    plan = CircuitPlan("section-override")
    ladder = build_lc_ladder_line!(
        plan;
        id="line",
        head=external_node("head"),
        tail=external_node("tail"),
        spec=spec,
        section_overrides=[override],
    )

    @test ladder.section_boundaries_m ≈ [0.0, 0.5mm, 1.0mm, 1.5mm, 2.0mm]
    @test ladder.section_rlgc_per_m[1].l_per_m_h ≈ 4.2e-7
    @test ladder.section_rlgc_per_m[2].l_per_m_h ≈ 4.1e-7
    @test ladder.series_inductors[2].inductance ≈ 4.1e-7 * 0.5mm
    base_capacitance = 1.7e-10 * 0.5mm
    override_capacitance = 1.8e-10 * 0.5mm
    expected_node_capacitances = [
        base_capacitance / 2,
        (base_capacitance + override_capacitance) / 2,
        override_capacitance,
        (override_capacitance + base_capacitance) / 2,
        base_capacitance / 2,
    ]
    @test [capacitor.capacitance for capacitor in ladder.shunt_capacitors] ≈ expected_node_capacitances
    graph_ladder = only(filter(relation -> relation.relation_type == :transmission_line_ladder, engineering_graph(plan).relations))
    @test graph_ladder.parameters[:section_rlgc_per_m][2].c_per_m_f ≈ 1.8e-10
    @test graph_ladder.parameters[:node_shunt_capacitance_f] ≈ expected_node_capacitances
end

@testset "Quarter-wave reusable builder uses grounded head and open tail" begin
    spec = RLGCSpec(
        length_m=1.5mm,
        section_length_m=0.5mm,
        l_per_m_h=4.2e-7,
        c_per_m_f=1.7e-10,
    )
    plan = CircuitPlan("qwr-builder")
    qwr = add_quarter_wave_resonator!(
        plan;
        id="qwr",
        grounded_head=external_node("qwr_head"),
        open_tail=external_node("qwr_tail"),
        spec=spec,
    )

    @test qwr.line.head_termination == :short
    @test qwr.line.tail_termination == :open
    @test length(qwr.line.termination_relations) == 1
    compiled = compile_to_josephson(plan)
    @test compiled.node_map[qwr.line.head] == "0"
    @test compiled.node_map[qwr.line.tail] != "0"
end

@testset "Transmission-line short termination maps terminal node to ground" begin
    spec = RLGCSpec(
        length_m=1.0mm,
        n_sections=2,
        l_per_m_h=4.2e-7,
        c_per_m_f=1.7e-10,
    )
    plan = CircuitPlan("shorted-line")
    ladder = build_lc_ladder_line!(
        plan;
        id="shorted",
        head=external_node("head"),
        tail=external_node("tail"),
        spec=spec,
        head_termination=:external,
        tail_termination=:short,
    )

    @test length(ladder.series_inductors) == 2
    section_capacitance = 1.7e-10 * 0.5mm
    right_short_node_capacitances = [section_capacitance / 2, section_capacitance]
    @test length(ladder.shunt_capacitors) == 2
    @test [capacitor.capacitance for capacitor in ladder.shunt_capacitors] ≈ right_short_node_capacitances
    @test length(ladder.termination_relations) == 1
    @test ladder.tail_termination == :short

    external_port!(
        plan;
        id=:head_port,
        index=1,
        endpoint=ladder.head,
        resistance=50.0,
        role=:line_head,
    )
    compiled = compile_to_josephson(plan)
    @test compiled.node_map[ladder.tail] == "0"
    @test !any(row -> row[1] == "C_shorted_c_node_2" && row[2] == "0" && row[3] == "0", compiled.netlist)

    left_plan = CircuitPlan("left-shorted-line")
    left_ladder = build_lc_ladder_line!(
        left_plan;
        id="left_shorted",
        head=external_node("left_head"),
        tail=external_node("left_tail"),
        spec=spec,
        head_termination=:short,
        tail_termination=:external,
    )
    left_short_node_capacitances = [section_capacitance, section_capacitance / 2]
    @test length(left_ladder.shunt_capacitors) == 2
    @test [capacitor.capacitance for capacitor in left_ladder.shunt_capacitors] ≈ left_short_node_capacitances
    external_port!(
        left_plan;
        id=:left_tail_port,
        index=1,
        endpoint=left_ladder.tail,
        resistance=50.0,
        role=:line_tail,
    )
    left_compiled = compile_to_josephson(left_plan)
    @test left_compiled.node_map[left_ladder.head] == "0"
    @test !any(row -> row[1] == "C_left_shorted_c_node_0" && row[2] == "0" && row[3] == "0", left_compiled.netlist)
end

@testset "External line terminations require enclosing connections" begin
    spec = RLGCSpec(
        length_m=1.0mm,
        n_sections=2,
        l_per_m_h=4.2e-7,
        c_per_m_f=1.7e-10,
    )
    plan = CircuitPlan("dangling-external")
    build_lc_ladder_line!(
        plan;
        id="line",
        head=external_node("head"),
        tail=external_node("tail"),
        spec=spec,
        head_termination=:external,
        tail_termination=:open,
    )

    report = validate_authoring(plan)
    @test has_errors(report)
    @test any(issue -> issue.code == :dangling_external_endpoint, errors(report))

    open_plan = CircuitPlan("intentional-open")
    build_lc_ladder_line!(
        open_plan;
        id="line",
        head=external_node("head"),
        tail=external_node("tail"),
        spec=spec,
        head_termination=:open,
        tail_termination=:open,
    )
    @test !any(issue -> issue.code == :dangling_external_endpoint, validate_authoring(open_plan).issues)
end
