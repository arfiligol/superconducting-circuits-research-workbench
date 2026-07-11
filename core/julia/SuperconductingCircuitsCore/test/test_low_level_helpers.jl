@testset "RLGCSpec validation" begin
    @test_throws FrameworkValidationError RLGCSpec(length_m=-1.0, n_sections=2, l_per_m_h=1.0, c_per_m_f=1.0)
end

@testset "section_values correctness" begin
    values = section_values(base_line_spec(length_m=2.0mm, n_sections=4))
    @test values.dx_m ≈ 0.5mm
    @test values.l_h ≈ 4.2e-7 * 0.5mm
    @test values.c_f ≈ 1.7e-10 * 0.5mm
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
