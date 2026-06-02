function _assert_prepared_example(example; expected_ports, min_relations)
    @test !isempty(example.compiled.netlist)
    @test length(example.compiled.port_map) == expected_ports
    @test length(example.plan.relations) >= min_relations
    @test example.hb_problem isa HBProblemSpec
    @test example.output_request_report isa OutputRequestConfigurationReport
end

function _assert_real_example_solve(example)
    result = run_hb_problem(example.hb_problem)
    @test result isa HBSolveResult
    @test haskey(result.traces, :zero_mode_s)
    @test haskey(result.traces, :s_parameter_mode)
    @test haskey(result.traces, :z_parameter_mode)
    @test haskey(result.traces, :qe_mode)
    @test haskey(result.traces, :qeideal_mode)
    @test haskey(result.traces, :cm_mode)
    return result
end

@testset "notebook-equivalent example builders prepare explicit HB solves" begin
    common_kwargs = (
        point_count=1,
        optional_hb_kwargs=Dict{Symbol,Any}(:nbatches => 1, :iterations => 80, :ftol => 1e-8),
    )

    lc = build_parallel_lc_resonator_example(; common_kwargs...)
    _assert_prepared_example(lc; expected_ports=1, min_relations=2)
    _assert_real_example_solve(lc)
    @test lc.f0_estimate_hz > 0

    jpa = build_reflective_jpa_capacitive_coupled_lc_example(;
        common_kwargs...,
        pump_current=0.0,
        optional_hb_kwargs=Dict{Symbol,Any}(:nbatches => 1, :iterations => 80, :ftol => 1e-8),
    )
    _assert_prepared_example(jpa; expected_ports=1, min_relations=3)
    _assert_real_example_solve(jpa)
    @test any(row -> startswith(string(row[1]), "Lj"), jpa.compiled.netlist)

    floating = build_floating_lc_xy_line_example(; common_kwargs...)
    _assert_prepared_example(floating; expected_ports=3, min_relations=7)
    floating_result = _assert_real_example_solve(floating)
    @test floating.pad1 isa AbstractNodeEndpoint
    @test floating.pad2 isa AbstractNodeEndpoint
    @test floating.xy_node isa AbstractNodeEndpoint
    @test floating.capacitance_summary.alpha ≈
        (102.4903555082012e-15 + 0.1742182638751523e-15) /
        (102.4903555082012e-15 + 0.1742182638751523e-15 + 101.8251170216874e-15 + 0.7451414067385129e-15)
    @test floating.capacitance_summary.beta ≈ 1 - floating.capacitance_summary.alpha
    @test floating.capacitance_summary.c_d_xy_f ≈
        (102.4903555082012e-15 * 0.7451414067385129e-15 -
         101.8251170216874e-15 * 0.1742182638751523e-15) /
        (102.4903555082012e-15 + 0.1742182638751523e-15 + 101.8251170216874e-15 + 0.7451414067385129e-15)
    @test floating.capacitance_summary.c_eff_q_f ≈
        58.12081132735904e-15 +
        (102.4903555082012e-15 * 101.8251170216874e-15) /
        (102.4903555082012e-15 + 101.8251170216874e-15) +
        (0.1742182638751523e-15 * 0.7451414067385129e-15) /
        (0.1742182638751523e-15 + 0.7451414067385129e-15)
    for row_name in (
        "C_floating_xy_c_g1",
        "C_floating_xy_c_g2",
        "C_floating_xy_c_q",
        "C_floating_xy_c_xy1",
        "C_floating_xy_c_xy2",
        "L_floating_xy_l_q1",
        "L_floating_xy_l_q2",
    )
        @test any(row -> row[1] == row_name, floating.compiled.netlist)
    end
    @test length(floating_result.traces[:portnumbers]) == 3

    cpw = build_transmission_line_circuit_model_example(; common_kwargs..., length_m=2.0mm, section_length_m=1.0mm)
    _assert_prepared_example(cpw; expected_ports=2, min_relations=4)
    _assert_real_example_solve(cpw)
    @test cpw.line isa TransmissionLineLadder
    @test cpw.line.spec.l_per_m_h ≈ 404.313e-9
    @test cpw.line.spec.c_per_m_f ≈ 179.86e-12

    purcell = build_readout_line_purcell_filter_example(;
        common_kwargs...,
        input_line_length_m=1.0mm,
        filter_length_m=2.0mm,
        output_line_length_m=1.0mm,
        section_length_m=1.0mm,
    )
    _assert_prepared_example(purcell; expected_ports=2, min_relations=6)
    _assert_real_example_solve(purcell)
    @test purcell.filter.head_termination == :open
    @test purcell.filter.tail_termination == :open

    mtl = build_readout_line_hanging_qwr_mtl_example(;
        common_kwargs...,
        readout_length_m=3.0mm,
        resonator_length_m=2.0mm,
        section_length_m=1.0mm,
        window_start_readout_m=1.0mm,
        window_start_resonator_m=0.0,
        window_length_m=1.0mm,
    )
    _assert_prepared_example(mtl; expected_ports=2, min_relations=6)
    _assert_real_example_solve(mtl)
    @test mtl.window isa CoupledTransmissionWindow
    @test mtl.qwr.head_termination == :short
    @test mtl.qwr.tail_termination == :open
    @test mtl.readout_line.section_rlgc_per_m[mtl.window.section_range1.start].l_per_m_h ≈ 410.86374e-9
    @test mtl.qwr.section_rlgc_per_m[mtl.window.section_range2.start].c_per_m_f ≈ 170.29538e-12
    @test any(relation -> relation.relation_type == :coupled_window, mtl.graph.relations)

    exact_length_mtl = build_readout_line_hanging_qwr_mtl_example(;
        common_kwargs...,
        readout_length_m=9.0mm,
        resonator_length_m=5.28371mm,
        section_length_m=0.75mm,
        window_start_readout_m=2.25mm,
        window_start_resonator_m=0.0,
        window_length_m=1.5mm,
    )
    _assert_prepared_example(exact_length_mtl; expected_ports=2, min_relations=6)
    _assert_real_example_solve(exact_length_mtl)
    @test exact_length_mtl.qwr.section_boundaries_m[end] ≈ 5.28371mm
    @test exact_length_mtl.window.section_range2 == 1:2

    purcell_qwr = build_readout_purcell_hanging_qwr_mtl_example(;
        common_kwargs...,
        input_line_length_m=1.0mm,
        filter_length_m=3.0mm,
        output_line_length_m=1.0mm,
        qwr_length_m=2.0mm,
        section_length_m=1.0mm,
        window_start_filter_m=1.0mm,
        window_start_qwr_m=0.0,
        window_length_m=1.0mm,
    )
    _assert_prepared_example(purcell_qwr; expected_ports=2, min_relations=8)
    _assert_real_example_solve(purcell_qwr)
    @test purcell_qwr.window isa CoupledTransmissionWindow
    @test purcell_qwr.qwr.head_termination == :short
    @test purcell_qwr.qwr.tail_termination == :open
end
