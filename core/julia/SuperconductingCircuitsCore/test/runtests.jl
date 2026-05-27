using Test
using SuperconductingCircuitsCore

const mm = 1e-3

function base_line_spec(; length_m=1.0mm, n_sections=4)
    return RLGCSpec(
        length_m=length_m,
        n_sections=n_sections,
        l_per_m_h=4.2e-7,
        c_per_m_f=1.7e-10,
    )
end

function base_window_spec(; length_m=0.1mm)
    return CoupledWindowSpec(
        length_m=length_m,
        n_sections=2,
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

@testset "LineSpan validation" begin
    @test span_length(LineSpan(0.1mm, 0.2mm)) ≈ 0.1mm
    @test_throws FrameworkValidationError LineSpan(-0.1mm, 0.2mm)
    @test_throws FrameworkValidationError LineSpan(0.2mm, 0.2mm)
end

@testset "add_distributed_segment! row count" begin
    circuit = Tuple{String,String,String,Any}[]
    add_distributed_segment!(
        circuit;
        prefix="tl",
        start_node="a",
        spec=base_line_spec(n_sections=2),
        final_node="b",
    )
    @test length(circuit) == 4
end

@testset "CircuitDraft can add components" begin
    draft = CircuitDraft("component-test")
    add_component!(draft; name="C1", node1="a", node2="0", value=1e-15)
    @test length(draft.lumped_components) == 1
end

@testset "connect! collapses pins during finalization" begin
    draft = CircuitDraft("connect-test")
    left = add_readout_line_component!(draft; id="left", line_spec=base_line_spec())
    right = add_readout_line_component!(draft; id="right", line_spec=base_line_spec())
    connect!(draft, left, :right, right, :left)
    connect!(draft, left, :left, "input")
    connect!(draft, right, :right, "output")
    netlist = finalize_to_josephson_netlist(draft)

    all_nodes = vcat([row[2] for row in netlist], [row[3] for row in netlist])
    @test all(node -> !contains(node, "__pin__"), all_nodes)
end

@testset "apply_series_chain! creates expected symbolic connections" begin
    draft = CircuitDraft("chain-test")
    first = add_readout_line_component!(draft; id="first", line_spec=base_line_spec())
    second = add_readout_line_component!(draft; id="second", line_spec=base_line_spec())
    connections = apply_series_chain!(draft, first, second)
    @test length(connections) == 1
    @test length(draft.node_connections) == 1
end

@testset "apply_coupled_window! rejects invalid spans" begin
    draft = CircuitDraft("coupled-invalid")
    line_a = add_transmission_line!(
        draft;
        id="line_a",
        start_node="a0",
        end_node="a1",
        spec=base_line_spec(),
    )
    line_b = add_transmission_line!(
        draft;
        id="line_b",
        start_node="b0",
        end_node="b1",
        spec=base_line_spec(),
    )

    @test_throws FrameworkValidationError apply_coupled_window!(
        draft;
        prefix="bad",
        line_a=line_a,
        span_a=LineSpan(0.1mm, 0.2mm),
        line_b=line_b,
        span_b=LineSpan(0.1mm, 0.3mm),
        spec=base_window_spec(length_m=0.1mm),
    )
end

@testset "finalize_to_josephson_netlist returns flat tuple rows" begin
    draft = CircuitDraft("flat-test")
    add_transmission_line!(
        draft;
        id="line",
        start_node="a",
        end_node="b",
        spec=base_line_spec(n_sections=2),
    )
    netlist = finalize_to_josephson_netlist(draft)
    @test !isempty(netlist)
    @test all(row -> row isa Tuple{String,String,String,Any}, netlist)
end

@testset "simple reusable component design finalizes" begin
    draft = CircuitDraft("component-finalize")
    readout = add_readout_line_component!(draft; id="readout", line_spec=base_line_spec())
    resonator = add_hanging_quarter_wave_resonator_component!(
        draft;
        id="resonator",
        line_spec=base_line_spec(length_m=1.2mm),
    )
    apply_coupled_window!(
        draft;
        prefix="window",
        line_a=readout,
        span_a=LineSpan(0.2mm, 0.3mm),
        line_b=resonator,
        span_b=LineSpan(0.4mm, 0.5mm),
        spec=base_window_spec(),
    )
    netlist = finalize_to_josephson_netlist(draft)
    @test any(row -> startswith(row[1], "K_window"), netlist)
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
