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

    floating = build_floating_lc_xy_line_example(;
        common_kwargs...,
        line_length_m=2.0mm,
        coupling_center_m=1.0mm,
        coupling_separation_m=1.0mm,
        section_length_m=1.0mm,
    )
    _assert_prepared_example(floating; expected_ports=2, min_relations=6)
    _assert_real_example_solve(floating)
    @test floating.line isa TransmissionLineLadder

    cpw = build_transmission_line_circuit_model_example(; common_kwargs..., length_m=2.0mm, section_length_m=1.0mm)
    _assert_prepared_example(cpw; expected_ports=2, min_relations=4)
    _assert_real_example_solve(cpw)
    @test cpw.line isa TransmissionLineLadder

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
