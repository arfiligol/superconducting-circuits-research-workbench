using Test
using SuperconductingCircuitsCore

include(
    joinpath(
        @__DIR__,
        "..",
        "..",
        "notebooks",
        "pluto",
        "D3 Intrinsic Purcell Filter Design",
        "d3_circuit_plans.jl",
    ),
)

const IDC_FIXTURE = (
    idc_filter_ground_capacitance_f=35.0e-15,
    idc_feedline_ground_capacitance_f=34.5e-15,
    idc_mutual_capacitance_f=38.0e-15,
)

@testset "D3 matched port regularizer V1" begin
    for built in (
        build_d3_intrinsic_purcell_equivalent_circuit_plan(; IDC_FIXTURE...),
        build_d3_linewidth_la_equivalent_circuit_plan(; IDC_FIXTURE...),
    )
        @test isempty(validate_authoring(built.plan).issues)
        @test built.feedline.regularizer_series_inductance_h == 1.0e-12
        @test built.feedline.regularizer_section_capacitance_f == 0.4e-15
        @test built.feedline.regularizer_characteristic_impedance_ohm == 50.0
        @test built.feedline.regularizer_section_length_m ==
              built.feedline.regularizer_series_inductance_h *
              built.feedline.regularizer_phase_velocity_m_per_s /
              built.feedline.regularizer_characteristic_impedance_ohm

        for section in (built.feedline.left, built.feedline.right)
            @test section.spec.n_sections == 1
            @test only(section.series_inductors).inductance == 1.0e-12
            @test all(
                capacitor -> capacitor.capacitance == 0.2e-15,
                section.shunt_capacitors,
            )
        end
    end

    @test_throws ArgumentError build_d3_intrinsic_purcell_equivalent_circuit_plan(
        ;
        IDC_FIXTURE...,
        port_resistance_ohm=75.0,
    )
    @test_throws ArgumentError build_d3_linewidth_la_equivalent_circuit_plan(
        ;
        IDC_FIXTURE...,
        port_resistance_ohm=75.0,
    )
end
