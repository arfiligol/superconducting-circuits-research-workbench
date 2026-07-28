@testset "Accepted intrinsic interferometric Purcell reusable components V1" begin
    idc_example = build_interdigitated_capacitor_example()
    idc = idc_example.component
    @test length(idc_example.plan.relations) == 3
    @test idc.c1g.at == idc.terminal_1
    @test idc.c2g.at == idc.terminal_2
    @test (idc.c12.from, idc.c12.to) == (idc.terminal_1, idc.terminal_2)
    @test_throws FrameworkValidationError build_interdigitated_capacitor_example(c1g_f=0.0)

    filter_example = build_intrinsic_interferometric_purcell_filter_example()
    filter = filter_example.component
    @test filter.window.coupling_orientation == :same_direction
    @test length(filter_example.plan.metadata[:transmission_line_ladders]) == 2
    @test length(filter_example.plan.metadata[:coupled_transmission_windows]) == 1
    @test filter.filter_resonator.line.tail == filter.feedline_capacitor.terminal_1
    @test filter.feedline_capacitor.terminal_2 == filter.feedline_attachment
    @test isempty(engineering_graph(filter_example.plan).ports)
    @test !any(
        component -> occursin("Feedline", string(component.component_type)),
        values(engineering_graph(filter_example.plan).components),
    )
    @test !has_errors(validate_compile_ready(filter_example.plan))
    @test !isempty(compile_to_josephson(filter_example.plan).netlist)
    @test_throws FrameworkValidationError build_intrinsic_interferometric_purcell_filter_example(
        coupling_orientation=:opposite_direction,
    )

    with_qubit_example = build_intrinsic_interferometric_purcell_filter_with_qubit_example()
    with_qubit = with_qubit_example.component
    @test !isnothing(with_qubit.c0r)
    @test isempty(engineering_graph(with_qubit_example.plan).ports)
    @test Set(keys(schematic_layout_intent(with_qubit_example.plan).terminals)) ==
          Set([:island_1, :island_2, :feedline_attachment])
    @test !has_errors(validate_compile_ready(with_qubit_example.plan))
    @test !isempty(compile_to_josephson(with_qubit_example.plan).netlist)

    without_c0r = build_intrinsic_interferometric_purcell_filter_with_qubit_example(c0r_f=0.0)
    @test isnothing(without_c0r.component.c0r)
    @test length(without_c0r.plan.relations) == length(with_qubit_example.plan.relations) - 1

    foreign_filter = build_intrinsic_interferometric_purcell_filter_example(id="foreign-filter")
    @test_throws FrameworkValidationError add_intrinsic_interferometric_purcell_filter_with_qubit!(
        filter_example.plan;
        id="foreign-filter-with-qubit",
        filter=foreign_filter.component,
        island_1=external_node("foreign_island_1"),
        island_2=external_node("foreign_island_2"),
        c0r_f=0.0,
        c01_f=65.0e-15,
        c02_f=64.0e-15,
        c12_f=12.0e-15,
        cr1_f=4.2e-15,
        cr2_f=3.8e-15,
        l_j_per_junction_h=24.0e-9,
    )
end
