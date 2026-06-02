@testset "RLGCSpec validation" begin
    @test_throws FrameworkValidationError RLGCSpec(length_m=-1.0, n_sections=2, l_per_m_h=1.0, c_per_m_f=1.0)
end

@testset "section_values correctness" begin
    values = section_values(base_line_spec(length_m=2.0mm, n_sections=4))
    @test values.dx_m ≈ 0.5mm
    @test values.l_h ≈ 4.2e-7 * 0.5mm
    @test values.c_f ≈ 1.7e-10 * 0.5mm
end

@testset "coupled_window_section_values validation" begin
    invalid = CoupledWindowSpec(
        length_m=0.1mm,
        n_sections=2,
        l11_per_m_h=4.2e-7,
        l22_per_m_h=4.2e-7,
        lm_per_m_h=10.0,
        c1g_per_m_f=1.7e-10,
        c2g_per_m_f=1.7e-10,
        cm_per_m_f=1.0e-12,
    )
    @test_throws FrameworkValidationError coupled_window_section_values(invalid)
end

@testset "coupled_window_section_values correctness" begin
    values = coupled_window_section_values(base_window_spec(length_m=0.2mm))
    @test values.dx_m ≈ 0.1mm
    @test values.line_a.l_h ≈ 4.2e-7 * 0.1mm
    @test values.line_b.c_f ≈ 1.7e-10 * 0.1mm
    @test values.cm_f ≈ 1.0e-12 * 0.1mm
end

@testset "_emit_distributed_segment! row count" begin
    circuit = Tuple{String,String,String,Any}[]
    SuperconductingCircuitsCore._emit_distributed_segment!(
        circuit;
        prefix="tl",
        start_node="a",
        spec=base_line_spec(n_sections=2),
        final_node="b",
    )
    @test length(circuit) == 4
end

@testset "_emit_coupled_window! row count" begin
    circuit = Tuple{String,String,String,Any}[]
    SuperconductingCircuitsCore._emit_coupled_window!(
        circuit;
        prefix="window",
        left_node_a="a0",
        right_node_a="a1",
        left_node_b="b0",
        right_node_b="b1",
        spec=base_window_spec(n_sections=2),
    )
    @test length(circuit) == 12
    @test count(row -> startswith(row[1], "K_window"), circuit) == 2
end
