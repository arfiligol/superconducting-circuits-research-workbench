@testset "TransmissionLineSpec construction and LC ladder generation" begin
    spec = TransmissionLineSpec(
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
    @test length(ladder.shunt_capacitors) == 4
    @test isempty(ladder.termination_relations)
    @test node_at_distance(ladder, 0.5mm) == ladder.nodes[3]
    @test section_index_at_distance(ladder, 0.5mm) == 3
    @test section_range_from_window(ladder, 0.25mm, 0.5mm) == 2:3
    @test haskey(plan.metadata[:transmission_line_ladders], :line)
    @test any(relation -> relation.relation_type == :transmission_line_ladder, engineering_graph(plan).relations)

    compiled = compile_to_josephson(plan)
    @test length(compiled.netlist) == 8
    @test ("L_line_l_1", "ext_head", "ext_line_node_1", :L_line_l_1) in compiled.netlist
    @test ("C_line_c_4", "ext_tail", "0", :C_line_c_4) in compiled.netlist
end

@testset "Transmission-line short termination maps terminal node to ground" begin
    spec = TransmissionLineSpec(
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
    @test length(ladder.shunt_capacitors) == 1
    @test length(ladder.termination_relations) == 1
    @test ladder.tail_termination == :short

    compiled = compile_to_josephson(plan)
    @test compiled.node_map[ladder.tail] == "0"
    @test !any(row -> row[1] == "C_shorted_c_2" && row[2] == "0" && row[3] == "0", compiled.netlist)
end
