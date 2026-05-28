using SuperconductingCircuitsCore
using Test

const mm = 1e-3

function base_line_spec(; length_m=1.0mm, n_sections=4)
    return RLGCSpec(
        length_m=length_m,
        n_sections=n_sections,
        l_per_m_h=4.2e-7,
        c_per_m_f=1.7e-10,
    )
end

function base_window_spec(; length_m=0.1mm, n_sections=2)
    return CoupledWindowSpec(
        length_m=length_m,
        n_sections=n_sections,
        l11_per_m_h=4.2e-7,
        l22_per_m_h=4.2e-7,
        lm_per_m_h=0.5e-7,
        c1g_per_m_f=1.7e-10,
        c2g_per_m_f=1.7e-10,
        cm_per_m_f=1.0e-12,
    )
end

@testset "RLGCSpec validation" begin
    invalid = RLGCSpec(length_m=-1.0, n_sections=2, l_per_m_h=1.0, c_per_m_f=1.0)
    @test_throws FrameworkValidationError section_values(invalid)
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

@testset "sweep runner creates Cartesian product points" begin
    sweep = SweepSpec([
        SweepAxis("length_mm", [1.0, 2.0]),
        SweepAxis("cap_fF", [5.0, 10.0, 15.0]),
    ])
    result = run_design_sweep(params -> params["length_mm"] + params["cap_fF"], sweep; threaded=false)
    @test length(result.points) == 6
    @test all(point -> point.success, result.points)
end

@testset "sweep runner preserves failed point information" begin
    sweep = SweepSpec([SweepAxis("value", [1.0, 2.0])])
    result = run_design_sweep(
        params -> begin
            params["value"] == 2.0 && error("intentional failure")
            return params["value"]
        end,
        sweep;
        threaded=false,
    )

    @test count(point -> point.success, result.points) == 1
    failed = only(filter(point -> !point.success, result.points))
    @test contains(failed.error_message, "intentional failure")
end

@testset "sweep_result_dataframe flattens sweep axes" begin
    sweep = SweepSpec([
        SweepAxis("a", [1.0, 2.0]),
        SweepAxis("b", [10.0]),
    ])
    result = run_design_sweep(params -> params["a"] + params["b"], sweep; threaded=false)
    df = sweep_result_dataframe(result)
    @test :a in propertynames(df)
    @test :b in propertynames(df)
    @test :parameters ∉ propertynames(df)
end
