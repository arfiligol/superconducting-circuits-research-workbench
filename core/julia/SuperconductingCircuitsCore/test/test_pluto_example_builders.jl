function _assert_executable_example(example; expected_ports, min_relations)
    @test !isempty(example.compiled.netlist)
    @test length(example.compiled.port_map) == expected_ports
    @test length(example.plan.relations) >= min_relations
    @test example.hb_problem isa HBProblemSpec
    @test example.result isa HBSolveResult
    @test haskey(example.result.traces, :zero_mode_s)
    @test haskey(example.result.traces, :s_parameter_mode)
    @test haskey(example.result.traces, :z_parameter_mode)
    @test haskey(example.result.traces, :qe_mode)
    @test haskey(example.result.traces, :qeideal_mode)
    @test haskey(example.result.traces, :cm_mode)
end

@testset "notebook-equivalent example builders execute real HB solves" begin
    common_kwargs = (
        point_count=1,
        optional_hb_kwargs=Dict{Symbol,Any}(:nbatches => 1, :iterations => 80, :ftol => 1e-8),
    )

    lc = build_lc_resonator_example(; common_kwargs...)
    _assert_executable_example(lc; expected_ports=1, min_relations=3)
    @test lc.f0_estimate_hz > 0

    cpw = build_cpw_ladder_example(; common_kwargs..., length_m=2.0mm, section_length_m=1.0mm)
    _assert_executable_example(cpw; expected_ports=2, min_relations=4)
    @test cpw.line isa TransmissionLineLadder

    purcell = build_purcell_filter_mvp_example(;
        common_kwargs...,
        resonator_length_m=2.0mm,
        section_length_m=1.0mm,
    )
    _assert_executable_example(purcell; expected_ports=2, min_relations=4)
    @test purcell.filter.head_termination == :open
    @test purcell.filter.tail_termination == :open

    readout = build_long_readout_line_example(; common_kwargs..., length_m=2.0mm, section_length_m=1.0mm)
    _assert_executable_example(readout; expected_ports=2, min_relations=4)
    @test readout.line.spec.n_sections == 2

    mtl = build_hanging_qwr_mtl_example(;
        common_kwargs...,
        readout_length_m=3.0mm,
        resonator_length_m=2.0mm,
        section_length_m=1.0mm,
        window_start_readout_m=1.0mm,
        window_start_resonator_m=0.0,
        window_length_m=1.0mm,
    )
    _assert_executable_example(mtl; expected_ports=2, min_relations=6)
    @test mtl.window isa CoupledTransmissionWindow
    @test any(relation -> relation.relation_type == :coupled_window, mtl.graph.relations)
end
