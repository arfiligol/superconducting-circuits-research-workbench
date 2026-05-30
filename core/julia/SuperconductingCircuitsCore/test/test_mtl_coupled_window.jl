@testset "MTL coupled window generates primitive C12 and K relations" begin
    spec = TransmissionLineSpec(
        length_m=2.0mm,
        section_length_m=0.5mm,
        l_per_m_h=4.2e-7,
        c_per_m_f=1.7e-10,
    )
    plan = CircuitPlan("mtl-window")
    line1 = build_lc_ladder_line!(
        plan;
        id="line1",
        head=external_node("line1_head"),
        tail=external_node("line1_tail"),
        spec=spec,
    )
    line2 = build_lc_ladder_line!(
        plan;
        id="line2",
        head=external_node("line2_head"),
        tail=external_node("line2_tail"),
        spec=spec,
    )
    model = MTLCoupledWindowSpec(
        start1_m=0.5mm,
        start2_m=1.0mm,
        length_m=1.0mm,
        section_length_m=0.5mm,
        c12_per_m_f=1.0e-12,
        lm_per_m_h=0.5e-7,
        l1_per_m_h=4.2e-7,
        l2_per_m_h=4.2e-7,
        c1g_per_m_f=1.7e-10,
        c2g_per_m_f=1.7e-10,
    )

    window = couple_transmission_window!(
        plan;
        id="window",
        line1=line1,
        line2=line2,
        start1=0.5mm,
        start2=1.0mm,
        length=1.0mm,
        model=model,
    )

    @test window.section_range1 == 2:3
    @test window.section_range2 == 3:4
    @test length(window.capacitive_couplings) == 2
    @test length(window.inductive_couplings) == 2
    @test all(relation -> relation.capacitance ≈ 1.0e-12 * 0.5mm, window.capacitive_couplings)
    @test all(
        relation -> relation.mutual_inductance ≈ 0.5e-7 * 0.5mm &&
            relation.coupling_coefficient ≈ 0.5e-7 / 4.2e-7,
        window.inductive_couplings,
    )
    @test haskey(plan.metadata[:coupled_transmission_windows], :window)
    graph_window = only(filter(relation -> relation.id == :window, engineering_graph(plan).relations))
    @test graph_window.relation_type == :coupled_window
    @test graph_window.parameters[:section_count] == 2

    compiled = compile_to_josephson(plan)
    @test count(row -> startswith(row[1], "C_window_c12"), compiled.netlist) == 2
    @test count(row -> startswith(row[1], "K_window_m12"), compiled.netlist) == 2
    @test compiled.provenance[:relation_map]["window_m12_1"] isa Vector{Int}
end

@testset "MTL coupled window rejects non-aligned windows" begin
    spec = TransmissionLineSpec(
        length_m=2.0mm,
        section_length_m=0.5mm,
        l_per_m_h=4.2e-7,
        c_per_m_f=1.7e-10,
    )
    plan = CircuitPlan("bad-mtl-window")
    line1 = build_lc_ladder_line!(plan; id="line1", head=external_node("a"), tail=external_node("b"), spec=spec)
    line2 = build_lc_ladder_line!(plan; id="line2", head=external_node("c"), tail=external_node("d"), spec=spec)
    model = MTLCoupledWindowSpec(
        start1_m=0.25mm,
        start2_m=0.0,
        length_m=0.5mm,
        section_length_m=0.5mm,
        c12_per_m_f=1.0e-12,
        lm_per_m_h=0.5e-7,
        l1_per_m_h=4.2e-7,
        l2_per_m_h=4.2e-7,
        c1g_per_m_f=1.7e-10,
        c2g_per_m_f=1.7e-10,
    )
    @test_throws FrameworkValidationError couple_transmission_window!(
        plan;
        id="window",
        line1=line1,
        line2=line2,
        model=model,
    )

    @test_throws FrameworkValidationError MTLCoupledWindowSpec(
        start1_m=0.0,
        start2_m=0.0,
        length_m=0.75mm,
        section_length_m=0.5mm,
        c12_per_m_f=1.0e-12,
        lm_per_m_h=0.5e-7,
        l1_per_m_h=4.2e-7,
        l2_per_m_h=4.2e-7,
        c1g_per_m_f=1.7e-10,
        c2g_per_m_f=1.7e-10,
    )
end
