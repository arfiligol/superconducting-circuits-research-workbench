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
    @test window.coupling_orientation == :same_direction
    @test window.section_pairs == [(2, 3), (3, 4)]
    expected_boundary_node_pairs = [
        (line1.nodes[2], line2.nodes[3]),
        (line1.nodes[3], line2.nodes[4]),
        (line1.nodes[3], line2.nodes[4]),
        (line1.nodes[4], line2.nodes[5]),
    ]
    half_c12 = 1.0e-12 * 0.5mm / 2
    @test [record.section_pair for record in window.capacitive_boundary_records] == [(2, 3), (2, 3), (3, 4), (3, 4)]
    @test [record.boundary_side for record in window.capacitive_boundary_records] == [:start, :stop, :start, :stop]
    @test [record.node_pair for record in window.capacitive_boundary_records] == expected_boundary_node_pairs
    @test all(record -> record.capacitance ≈ half_c12, window.capacitive_boundary_records)
    @test window.inductive_orientation_sign == 1
    @test length(window.capacitive_couplings) == 4
    @test length(window.inductive_couplings) == 2
    @test line1.series_inductors[2].inductance ≈ 4.3e-7 * 0.5mm
    @test line2.series_inductors[3].inductance ≈ 4.4e-7 * 0.5mm
    base_capacitance = 1.7e-10 * 0.5mm
    line1_coupled_capacitance = 1.6e-10 * 0.5mm
    line2_coupled_capacitance = 1.65e-10 * 0.5mm
    expected_line1_node_capacitances = [
        base_capacitance / 2,
        (base_capacitance + line1_coupled_capacitance) / 2,
        line1_coupled_capacitance,
        (line1_coupled_capacitance + base_capacitance) / 2,
        base_capacitance / 2,
    ]
    expected_line2_node_capacitances = [
        base_capacitance / 2,
        base_capacitance,
        (base_capacitance + line2_coupled_capacitance) / 2,
        line2_coupled_capacitance,
        line2_coupled_capacitance / 2,
    ]
    graph_line1 = only(filter(relation -> relation.id == :line1_ladder, engineering_graph(plan).relations))
    graph_line2 = only(filter(relation -> relation.id == :line2_ladder, engineering_graph(plan).relations))
    @test graph_line1.parameters[:section_model] == :pi
    @test graph_line1.parameters[:node_shunt_capacitance_f] ≈ expected_line1_node_capacitances
    @test graph_line2.parameters[:node_shunt_capacitance_f] ≈ expected_line2_node_capacitances
    @test all(relation -> relation.capacitance ≈ half_c12, window.capacitive_couplings)
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
    @test graph_window.parameters[:coupling_orientation] == :same_direction
    @test graph_window.parameters[:section_pairs] == [(2, 3), (3, 4)]
    @test graph_window.parameters[:capacitive_boundary_records] == [
        (section_pair=(2, 3), boundary_side=:start, from="line1_node_1", to="line2_node_2", capacitance=half_c12),
        (section_pair=(2, 3), boundary_side=:stop, from="line1_node_2", to="line2_node_3", capacitance=half_c12),
        (section_pair=(3, 4), boundary_side=:start, from="line1_node_2", to="line2_node_3", capacitance=half_c12),
        (section_pair=(3, 4), boundary_side=:stop, from="line1_node_3", to="line2_tail", capacitance=half_c12),
    ]
    @test graph_window.parameters[:inductive_orientation_sign] == 1
    @test graph_window.parameters[:l1_per_m_h] ≈ 4.3e-7
    @test graph_window.parameters[:c12_per_m_f] ≈ 1.0e-12
    @test graph_window.parameters[:lm_per_m_h] ≈ 0.5e-7

    external_port!(
        plan;
        id=:line1_head_port,
        index=1,
        endpoint=line1.head,
        resistance=50.0,
        role=:line_head,
    )
    external_port!(
        plan;
        id=:line2_head_port,
        index=2,
        endpoint=line2.head,
        resistance=50.0,
        role=:line_head,
    )
    compiled = compile_to_josephson(plan)
    @test count(row -> startswith(row[1], "C_window_c12"), compiled.netlist) == 4
    @test count(row -> startswith(row[1], "K_window_m12"), compiled.netlist) == 2
    @test compiled.provenance[:relation_map]["window_m12_1"] isa Vector{Int}
end

@testset "MTL coupled window supports opposite spatial orientation" begin
    spec = RLGCSpec(
        length_m=2.0mm,
        section_length_m=0.5mm,
        l_per_m_h=4.2e-7,
        c_per_m_f=1.7e-10,
    )
    model = _test_mtl_model()
    plan = CircuitPlan("opposite-mtl-window")
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
        coupling_orientation=:opposite_direction,
    )

    @test window.section_range1 == 2:3
    @test window.section_range2 == 3:4
    @test window.coupling_orientation == :opposite_direction
    @test window.section_pairs == [(2, 4), (3, 3)]
    expected_boundary_node_pairs = [
        (line1.nodes[2], line2.nodes[5]),
        (line1.nodes[3], line2.nodes[4]),
        (line1.nodes[3], line2.nodes[4]),
        (line1.nodes[4], line2.nodes[3]),
    ]
    half_c12 = 1.0e-12 * 0.5mm / 2
    @test [record.section_pair for record in window.capacitive_boundary_records] == [(2, 4), (2, 4), (3, 3), (3, 3)]
    @test [record.boundary_side for record in window.capacitive_boundary_records] == [:start, :stop, :start, :stop]
    @test [record.node_pair for record in window.capacitive_boundary_records] == expected_boundary_node_pairs
    @test window.inductive_orientation_sign == -1
    @test all(relation -> relation.capacitance ≈ half_c12, window.capacitive_couplings)
    @test all(
        relation -> relation.mutual_inductance ≈ -0.5e-7 * 0.5mm &&
            relation.coupling_coefficient ≈ -0.5e-7 / sqrt(4.3e-7 * 4.4e-7),
        window.inductive_couplings,
    )

    graph_window = only(filter(relation -> relation.id == :window, engineering_graph(plan).relations))
    @test graph_window.parameters[:coupling_orientation] == :opposite_direction
    @test graph_window.parameters[:section_pairs] == [(2, 4), (3, 3)]
    @test graph_window.parameters[:capacitive_boundary_records] == [
        (section_pair=(2, 4), boundary_side=:start, from="line1_node_1", to="line2_tail", capacitance=half_c12),
        (section_pair=(2, 4), boundary_side=:stop, from="line1_node_2", to="line2_node_3", capacitance=half_c12),
        (section_pair=(3, 3), boundary_side=:start, from="line1_node_2", to="line2_node_3", capacitance=half_c12),
        (section_pair=(3, 3), boundary_side=:stop, from="line1_node_3", to="line2_node_2", capacitance=half_c12),
    ]
    @test graph_window.parameters[:inductive_orientation_sign] == -1
    @test graph_window.parameters[:lm_per_m_h] ≈ 0.5e-7

    external_port!(
        plan;
        id=:line1_head_port,
        index=1,
        endpoint=line1.head,
        resistance=50.0,
        role=:line_head,
    )
    external_port!(
        plan;
        id=:line2_head_port,
        index=2,
        endpoint=line2.head,
        resistance=50.0,
        role=:line_head,
    )
    compiled = compile_to_josephson(plan)
    first_c12_start = only(filter(row -> row[1] == "C_window_c12_1_start", compiled.netlist))
    first_c12_stop = only(filter(row -> row[1] == "C_window_c12_1_stop", compiled.netlist))
    second_c12_start = only(filter(row -> row[1] == "C_window_c12_2_start", compiled.netlist))
    second_c12_stop = only(filter(row -> row[1] == "C_window_c12_2_stop", compiled.netlist))
    first_k = only(filter(row -> row[1] == "K_window_m12_1", compiled.netlist))
    second_k = only(filter(row -> row[1] == "K_window_m12_2", compiled.netlist))

    @test first_c12_start[2:3] == ("ext_line1_node_1", "ext_line2_tail")
    @test first_c12_stop[2:3] == ("ext_line1_node_2", "ext_line2_node_3")
    @test second_c12_start[2:3] == ("ext_line1_node_2", "ext_line2_node_3")
    @test second_c12_stop[2:3] == ("ext_line1_node_3", "ext_line2_node_2")
    @test first_k[2:3] == ("L_line1_l_2", "L_line2_l_4")
    @test second_k[2:3] == ("L_line1_l_3", "L_line2_l_3")
    @test compiled.component_values[first_k[4]] < 0
    @test compiled.component_values[second_k[4]] < 0
end

@testset "MTL pi boundary topology matches same and opposite orientation drawings" begin
    spec = RLGCSpec(
        length_m=5.0mm,
        section_length_m=1.0mm,
        l_per_m_h=4.2e-7,
        c_per_m_f=1.7e-10,
    )
    model = _test_mtl_model(start1_m=2.0mm, start2_m=2.0mm, length_m=2.0mm, section_length_m=1.0mm)

    function build_window_for_orientation(orientation)
        plan = CircuitPlan("pi-topology-$(orientation)")
        line1 = build_lc_ladder_line!(
            plan;
            id="line1",
            head=external_node("line1_short"),
            tail=external_node("line1_port"),
            spec=spec,
            head_termination=:short,
            tail_termination=:external,
            breakpoints_m=[model.start1_m, model.start1_m + model.length_m],
            section_overrides=[coupled_line_section_override(model, 1)],
        )
        line2 = build_lc_ladder_line!(
            plan;
            id="line2",
            head=external_node("line2_short"),
            tail=external_node("line2_port"),
            spec=spec,
            head_termination=:short,
            tail_termination=:external,
            breakpoints_m=[model.start2_m, model.start2_m + model.length_m],
            section_overrides=[coupled_line_section_override(model, 2)],
        )

        window = couple_transmission_window!(
            plan;
            id="window",
            line1=line1,
            line2=line2,
            model=model,
            coupling_orientation=orientation,
        )
        return (plan=plan, line1=line1, line2=line2, window=window)
    end

    same = build_window_for_orientation(:same_direction)
    opposite = build_window_for_orientation(:opposite_direction)
    half_c12 = mutual_capacitance_per_m_f(model) * 1.0mm / 2

    @test same.window.section_range1 == 3:4
    @test same.window.section_range2 == 3:4
    @test same.window.section_pairs == [(3, 3), (4, 4)]
    @test [record.node_pair for record in same.window.capacitive_boundary_records] == [
        (same.line1.nodes[3], same.line2.nodes[3]),
        (same.line1.nodes[4], same.line2.nodes[4]),
        (same.line1.nodes[4], same.line2.nodes[4]),
        (same.line1.nodes[5], same.line2.nodes[5]),
    ]
    @test all(record -> record.capacitance ≈ half_c12, same.window.capacitive_boundary_records)
    @test all(relation -> relation.mutual_inductance > 0, same.window.inductive_couplings)

    @test opposite.window.section_range1 == 3:4
    @test opposite.window.section_range2 == 3:4
    @test opposite.window.section_pairs == [(3, 4), (4, 3)]
    @test [record.node_pair for record in opposite.window.capacitive_boundary_records] == [
        (opposite.line1.nodes[3], opposite.line2.nodes[5]),
        (opposite.line1.nodes[4], opposite.line2.nodes[4]),
        (opposite.line1.nodes[4], opposite.line2.nodes[4]),
        (opposite.line1.nodes[5], opposite.line2.nodes[3]),
    ]
    @test all(record -> record.capacitance ≈ half_c12, opposite.window.capacitive_boundary_records)
    @test all(relation -> relation.mutual_inductance < 0, opposite.window.inductive_couplings)

    same_line1_graph = only(filter(relation -> relation.id == :line1_ladder, engineering_graph(same.plan).relations))
    expected_pi_shunts = [
        0.0,
        1.7e-10 * 1.0mm,
        (1.7e-10 * 1.0mm + model.c_matrix_per_m_f[1, 1] * 1.0mm) / 2,
        model.c_matrix_per_m_f[1, 1] * 1.0mm,
        (model.c_matrix_per_m_f[1, 1] * 1.0mm + 1.7e-10 * 1.0mm) / 2,
        1.7e-10 * 1.0mm / 2,
    ]
    @test same_line1_graph.parameters[:section_model] == :pi
    @test same_line1_graph.parameters[:node_shunt_capacitance_f] ≈ expected_pi_shunts
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

    valid_model = _test_mtl_model(start1_m=0.0, start2_m=0.0, length_m=0.5mm, section_length_m=0.5mm)
    valid_plan = CircuitPlan("bad-orientation-window")
    valid_line1 = build_lc_ladder_line!(
        valid_plan;
        id="valid_line1",
        head=external_node("valid_a"),
        tail=external_node("valid_b"),
        spec=spec,
        breakpoints_m=[0.0, 0.5mm],
        section_overrides=[coupled_line_section_override(valid_model, 1)],
    )
    valid_line2 = build_lc_ladder_line!(
        valid_plan;
        id="valid_line2",
        head=external_node("valid_c"),
        tail=external_node("valid_d"),
        spec=spec,
        breakpoints_m=[0.0, 0.5mm],
        section_overrides=[coupled_line_section_override(valid_model, 2)],
    )
    @test_throws FrameworkValidationError couple_transmission_window!(
        valid_plan;
        id="bad_orientation_window",
        line1=valid_line1,
        line2=valid_line2,
        model=valid_model,
        coupling_orientation=:diagonal,
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
    @test length(window.capacitive_couplings) == 4
    @test all(relation -> relation.capacitance ≈ 1.0e-12 * 0.75mm / 2, window.capacitive_couplings)
    @test all(relation -> relation.mutual_inductance ≈ 0.5e-7 * 0.75mm, window.inductive_couplings)
end
