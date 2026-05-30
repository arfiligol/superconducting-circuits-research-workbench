function _test_mtl_model(; start1_m=0.5mm, start2_m=1.0mm, length_m=1.0mm, section_length_m=0.5mm)
    return MTLCoupledRLGCSpec(
        start1_m=start1_m,
        start2_m=start2_m,
        length_m=length_m,
        section_length_m=section_length_m,
        l_matrix_per_m_h=[
            4.3e-7 0.5e-7
            0.5e-7 4.4e-7
        ],
        c_matrix_per_m_f=[
            1.6e-10 -1.0e-12
            -1.0e-12 1.65e-10
        ],
    )
end

@testset "MTLCoupledRLGCSpec validates matrix convention and conversion" begin
    model = _test_mtl_model()

    @test mutual_capacitance_per_m_f(model) ≈ 1.0e-12
    @test mutual_inductance_per_m_h(model) ≈ 0.5e-7
    @test coupled_line_section_override(model, 1).values.l_per_m_h ≈ 4.3e-7
    @test coupled_line_section_override(model, 2).values.c_per_m_f ≈ 1.65e-10

    @test_throws FrameworkValidationError MTLCoupledRLGCSpec(
        start1_m=0.0,
        start2_m=0.0,
        length_m=1.0mm,
        section_length_m=0.5mm,
        l_matrix_per_m_h=[1.0 0.1; 0.1 1.0],
        c_matrix_per_m_f=[1.0 0.1; 0.1 1.0],
    )
    @test_throws FrameworkValidationError MTLCoupledRLGCSpec(
        start1_m=0.0,
        start2_m=0.0,
        length_m=1.0mm,
        section_length_m=0.5mm,
        l_matrix_per_m_h=[1.0 0.1 0.0; 0.1 1.0 0.0],
        c_matrix_per_m_f=[1.0 -0.1; -0.1 1.0],
    )

    even_odd = MTLCoupledRLGCSpec(
        start1_m=0.0,
        start2_m=0.0,
        length_m=1.0mm,
        section_length_m=0.5mm,
        z_even_ohm=60.0,
        z_odd_ohm=40.0,
        phase_velocity_even_m_per_s=1.2e8,
        phase_velocity_odd_m_per_s=1.0e8,
    )
    @test even_odd.l_matrix_per_m_h[1, 1] > 0
    @test even_odd.c_matrix_per_m_f[1, 2] <= 0
end

@testset "MTL coupled window uses coupled self terms and generates primitive C12 and K relations" begin
    spec = RLGCSpec(
        length_m=2.0mm,
        section_length_m=0.5mm,
        l_per_m_h=4.2e-7,
        c_per_m_f=1.7e-10,
    )
    model = _test_mtl_model()
    plan = CircuitPlan("mtl-window")
    line1 = build_lc_ladder_line!(
        plan;
        id="line1",
        head=external_node("line1_head"),
        tail=external_node("line1_tail"),
        spec=spec,
        breakpoints_m=[model.start1_m, model.start1_m + model.length_m],
        section_overrides=[coupled_line_section_override(model, 1)],
    )
    line2 = build_lc_ladder_line!(
        plan;
        id="line2",
        head=external_node("line2_head"),
        tail=external_node("line2_tail"),
        spec=spec,
        breakpoints_m=[model.start2_m, model.start2_m + model.length_m],
        section_overrides=[coupled_line_section_override(model, 2)],
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
    @test line1.series_inductors[2].inductance ≈ 4.3e-7 * 0.5mm
    @test line2.series_inductors[3].inductance ≈ 4.4e-7 * 0.5mm
    @test line1.shunt_capacitors[2].capacitance ≈ 1.6e-10 * 0.5mm
    @test line2.shunt_capacitors[3].capacitance ≈ 1.65e-10 * 0.5mm
    @test all(relation -> relation.capacitance ≈ 1.0e-12 * 0.5mm, window.capacitive_couplings)
    @test all(
        relation -> relation.mutual_inductance ≈ 0.5e-7 * 0.5mm &&
            relation.coupling_coefficient ≈ 0.5e-7 / sqrt(4.3e-7 * 4.4e-7),
        window.inductive_couplings,
    )
    @test haskey(plan.metadata[:coupled_transmission_windows], :window)
    graph_window = only(filter(relation -> relation.id == :window, engineering_graph(plan).relations))
    @test graph_window.relation_type == :coupled_window
    @test graph_window.parameters[:section_count] == 2
    @test graph_window.parameters[:section_lengths_m] ≈ [0.5mm, 0.5mm]
    @test graph_window.parameters[:l1_per_m_h] ≈ 4.3e-7
    @test graph_window.parameters[:c12_per_m_f] ≈ 1.0e-12

    compiled = compile_to_josephson(plan)
    @test count(row -> startswith(row[1], "C_window_c12"), compiled.netlist) == 2
    @test count(row -> startswith(row[1], "K_window_m12"), compiled.netlist) == 2
    @test compiled.provenance[:relation_map]["window_m12_1"] isa Vector{Int}
end

@testset "MTL coupled window rejects non-aligned windows and missing coupled self overrides" begin
    spec = RLGCSpec(
        length_m=2.0mm,
        section_length_m=0.5mm,
        l_per_m_h=4.2e-7,
        c_per_m_f=1.7e-10,
    )
    plan = CircuitPlan("bad-mtl-window")
    line1 = build_lc_ladder_line!(plan; id="line1", head=external_node("a"), tail=external_node("b"), spec=spec)
    line2 = build_lc_ladder_line!(plan; id="line2", head=external_node("c"), tail=external_node("d"), spec=spec)
    model = _test_mtl_model(start1_m=0.25mm, start2_m=0.0, length_m=0.5mm, section_length_m=0.5mm)
    @test_throws FrameworkValidationError couple_transmission_window!(
        plan;
        id="window",
        line1=line1,
        line2=line2,
        model=model,
    )

    aligned_model = _test_mtl_model(start1_m=0.0, start2_m=0.0, length_m=0.5mm, section_length_m=0.5mm)
    @test_throws FrameworkValidationError couple_transmission_window!(
        plan;
        id="missing_override_window",
        line1=line1,
        line2=line2,
        model=aligned_model,
    )

    bad_length_model = _test_mtl_model(start1_m=0.0, start2_m=0.0, length_m=0.75mm, section_length_m=0.5mm)
    @test_throws FrameworkValidationError couple_transmission_window!(
        plan;
        id="bad_length_window",
        line1=line1,
        line2=line2,
        model=bad_length_model,
    )
end

@testset "MTL coupled window uses semantic breakpoints and actual dx" begin
    reference_dx = 0.75mm
    line1_spec = RLGCSpec(
        length_m=9.0mm,
        section_length_m=reference_dx,
        l_per_m_h=4.2e-7,
        c_per_m_f=1.7e-10,
    )
    line2_spec = RLGCSpec(
        length_m=5.28371mm,
        section_length_m=reference_dx,
        l_per_m_h=4.2e-7,
        c_per_m_f=1.7e-10,
    )
    model = _test_mtl_model(start1_m=2.25mm, start2_m=0.0, length_m=1.5mm, section_length_m=reference_dx)
    plan = CircuitPlan("segmented-mtl-window")
    line1 = build_lc_ladder_line!(
        plan;
        id="line1",
        head=external_node("a"),
        tail=external_node("b"),
        spec=line1_spec,
        breakpoints_m=[2.25mm, 3.75mm],
        section_overrides=[coupled_line_section_override(model, 1)],
    )
    line2 = build_lc_ladder_line!(
        plan;
        id="line2",
        head=external_node("c"),
        tail=external_node("d"),
        spec=line2_spec,
        breakpoints_m=[0.0, 1.5mm],
        section_overrides=[coupled_line_section_override(model, 2)],
    )

    window = couple_transmission_window!(
        plan;
        id="window",
        line1=line1,
        line2=line2,
        model=model,
    )

    @test window.section_range1 == 4:5
    @test window.section_range2 == 1:2
    @test line2.spec.n_sections == 8
    @test line2.section_boundaries_m[end] ≈ 5.28371mm
    @test all(relation -> relation.capacitance ≈ 1.0e-12 * 0.75mm, window.capacitive_couplings)
    @test all(relation -> relation.mutual_inductance ≈ 0.5e-7 * 0.75mm, window.inductive_couplings)
end
