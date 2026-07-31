using LinearAlgebra
using Test

const WORKBENCH_ROOT = normpath(joinpath(@__DIR__, "..", ".."))
include(joinpath(
    WORKBENCH_ROOT,
    "notebooks",
    "pluto",
    "D3 Intrinsic Purcell Filter Design",
    "d3_exact_n_response.jl",
))

function synthetic_d3_model(; q_coupling_rad_s=0.0, direct_exchange_hz=5.0e6)
    coordinate_order = [:q, :r, :p, :f1, :fc, :f2]
    frequency_hz = [8.0e9, 5.0e9, 6.0e9, 11.0e9, 13.0e9, 15.0e9]
    angular_frequency = 2π .* frequency_hz
    capacitance = Matrix{Float64}(I, 6, 6)
    stiffness = Matrix(Diagonal(angular_frequency .^ 2))
    direct_exchange_rad_s = 2π * direct_exchange_hz
    stiffness[2, 3] = stiffness[3, 2] =
        2 * sqrt(angular_frequency[2] * angular_frequency[3]) *
        direct_exchange_rad_s
    if !iszero(q_coupling_rad_s)
        stiffness[1, 2] = stiffness[2, 1] =
            2 * sqrt(angular_frequency[1] * angular_frequency[2]) *
            q_coupling_rad_s
        stiffness[1, 3] = stiffness[3, 1] =
            2 * sqrt(angular_frequency[1] * angular_frequency[3]) *
            q_coupling_rad_s
    end
    selector = zeros(Float64, 6, 2)
    selector[4, 1] = 1.0
    selector[6, 2] = 1.0
    digest = repeat("0", 64)
    return (
        capacitance=capacitance,
        inverse_inductance=stiffness,
        selector=selector,
        reference_impedance_ohm=[50.0, 50.0],
        coordinate_order=coordinate_order,
        provenance=(
            circuit_plan_sha256=digest,
            capacitance_sha256=digest,
            inverse_inductance_sha256=digest,
            selector_sha256=digest,
        ),
    )
end

const TEST_GATE_POLICY = (
    maximum_elimination_condition_number=1.0e12,
    maximum_relative_elimination_solve_residual=1.0e-11,
    maximum_relative_reciprocity_error=1.0e-12,
    maximum_relative_passivity_violation=1.0e-12,
    maximum_relative_root_residual=1.0e-10,
    maximum_root_growth_rate_hz=1.0e-3,
    minimum_normalized_residue_slope=1.0e-4,
    maximum_relative_coupling_spread=1.0e-8,
    maximum_relative_determinant_closure_error=1.0e-10,
)

@testset "D3 q+feedline-downfolded RP operator" begin
    model = synthetic_d3_model()
    receipt = d3_q_feedline_downfolded_rp_metrics(
        model;
        readout_root_band_hz=(4.9e9, 5.1e9),
        filter_root_band_hz=(5.9e9, 6.1e9),
        gate_policy=TEST_GATE_POLICY,
    )
    @test receipt.retained_coordinates == [:r, :p]
    @test receipt.eliminated_coordinates == [:q, :f1, :fc, :f2]
    @test receipt.readout.frequency_hz ≈ 5.0e9 rtol=1.0e-12
    @test receipt.filter.frequency_hz ≈ 6.0e9 rtol=1.0e-12
    @test receipt.coherent_exchange_hz ≈ 5.0e6 rtol=1.0e-12
    @test receipt.total_exchange_hz ≈ 5.0e6 rtol=1.0e-12
    @test abs(receipt.dissipative_cross_coupling_hz) <= 1.0e-6
    @test receipt.relative_coupling_spread <= 1.0e-12
    @test receipt.determinant_closure.relative_error <= 1.0e-12

    legacy = d3_feedline_downfolded_loaded_bare_roots(
        model,
        (4.9e9, 6.1e9),
    )
    @test receipt.readout.root_hz ≈ legacy.readout.root_hz rtol=1.0e-12
    @test receipt.filter.root_hz ≈ legacy.filter.root_hz rtol=1.0e-12

    context =
        _d3_q_feedline_downfolded_rp_context(model, TEST_GATE_POLICY)
    sample_omega = receipt.midpoint_angular_frequency_rad_s
    sample =
        _d3_q_feedline_downfolded_rp_operator(context, sample_omega)
    derivative_step = 1.0e-5 * real(sample_omega)
    lower = _d3_q_feedline_downfolded_rp_operator(
        context,
        sample_omega - derivative_step,
    )
    upper = _d3_q_feedline_downfolded_rp_operator(
        context,
        sample_omega + derivative_step,
    )
    finite_difference =
        (upper.effective_dynamic_stiffness -
         lower.effective_dynamic_stiffness) /
        (2 * derivative_step)
    @test sample.effective_dynamic_stiffness_derivative ≈
        finite_difference rtol=2.0e-10
end

@testset "D3 q-mediated exchange and fail-closed gates" begin
    mediated_model = synthetic_d3_model(
        q_coupling_rad_s=2π * 30.0e6,
        direct_exchange_hz=0.0,
    )
    relaxed_spread_policy = merge(
        TEST_GATE_POLICY,
        (maximum_relative_coupling_spread=10.0,),
    )
    receipt = d3_q_feedline_downfolded_rp_metrics(
        mediated_model;
        readout_root_band_hz=(4.9e9, 5.1e9),
        filter_root_band_hz=(5.9e9, 6.1e9),
        gate_policy=relaxed_spread_policy,
    )
    @test receipt.coherent_exchange_hz > 0
    @test iszero(
        d3_stage2_matrix_metrics(mediated_model).
        J_circuit_h_rp_pre_downfold_report_only_hz,
    )

    @test_throws ErrorException d3_q_feedline_downfolded_rp_metrics(
        synthetic_d3_model();
        readout_root_band_hz=(4.0e9, 9.0e9),
        filter_root_band_hz=(5.9e9, 6.1e9),
        gate_policy=TEST_GATE_POLICY,
    )
    asymmetric = synthetic_d3_model()
    asymmetric.inverse_inductance[2, 3] *= 1.01
    @test_throws ErrorException d3_q_feedline_downfolded_rp_metrics(
        asymmetric;
        readout_root_band_hz=(4.9e9, 5.1e9),
        filter_root_band_hz=(5.9e9, 6.1e9),
        gate_policy=TEST_GATE_POLICY,
    )
    @test_throws ErrorException d3_q_feedline_downfolded_rp_metrics(
        mediated_model;
        readout_root_band_hz=(4.9e9, 5.1e9),
        filter_root_band_hz=(5.9e9, 6.1e9),
        gate_policy=merge(
            TEST_GATE_POLICY,
            (maximum_relative_coupling_spread=0.0,),
        ),
    )
end
