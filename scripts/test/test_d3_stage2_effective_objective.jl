using Test

const WORKBENCH_ROOT = normpath(joinpath(@__DIR__, "..", ".."))
include(joinpath(
    WORKBENCH_ROOT,
    "notebooks",
    "pluto",
    "D3 Intrinsic Purcell Filter Design",
    "d3_stage_objectives.jl",
))

const TEST_MODEL_SHA256 = repeat("a", 64)
const TEST_MODEL_IDENTITY = (
    circuit_plan_sha256=TEST_MODEL_SHA256,
    capacitance_sha256=TEST_MODEL_SHA256,
    inverse_inductance_sha256=TEST_MODEL_SHA256,
    selector_sha256=TEST_MODEL_SHA256,
)

function objective_metrics(; slot_hz=6.0e9)
    return merge(
        TEST_MODEL_IDENTITY,
        (
            stage_id=:stage2_equivalent,
            model_family=:equivalent_exact_n,
            fr_eff_q_feedline_downfolded_qrp_on_ext_on_hz=slot_hz,
            fp_eff_q_feedline_downfolded_qrp_on_ext_on_hz=slot_hz,
            J_rp_eff_q_feedline_downfolded_coherent_hz=5.0e6,
            notch_rp_on_hz=4.5e9,
            kappa_sum_qrp_on_ext_on_hz=20.0e6,
            eta_r_qrp_on=0.5,
            eta_p_qrp_on=0.5,
            effective_diagonal_frequency_extraction=
                :q_feedline_downfolded_rp_complex_operator,
            effective_exchange_extraction=
                :q_feedline_downfolded_rp_complex_midpoint_residue,
            notch_authority=:rp_on,
            linewidth_pole_scope=:qrp_three,
            primary_linewidth_extraction=:L_C,
        ),
    )
end

@testset "D3 revision-7 effective objective" begin
    slot_hz = 6.0e9
    metrics = objective_metrics(; slot_hz=slot_hz)
    objective = d3_stage2_objective(
        metrics,
        slot_hz,
        D3_HUMAN_APPROVED_OBJECTIVE_AUTHORITY,
        TEST_MODEL_IDENTITY,
    )
    @test D3_HUMAN_APPROVED_OBJECTIVE_AUTHORITY.target_revision == 7
    @test D3_HUMAN_APPROVED_OBJECTIVE_AUTHORITY.target_contract_sha256 ==
        "2ec4014c5bd3ba5824c15d71c3ad1e03b2a0d1f7444a35dcd31b0a4fe99b7bf9"
    @test objective.cost == 0.0
    @test objective.target_gates_pass
    @test keys(objective.target_gates) == (
        :readout_effective_diagonal_within_tolerance,
        :filter_effective_diagonal_within_tolerance,
        :linewidth_participation,
    )

    detuned = merge(
        metrics,
        (
            fr_eff_q_feedline_downfolded_qrp_on_ext_on_hz=slot_hz - 0.6e6,
            fp_eff_q_feedline_downfolded_qrp_on_ext_on_hz=slot_hz + 0.6e6,
        ),
    )
    detuned_objective = d3_stage2_objective(
        detuned,
        slot_hz,
        D3_HUMAN_APPROVED_OBJECTIVE_AUTHORITY,
        TEST_MODEL_IDENTITY,
    )
    @test !detuned_objective.target_gates_pass
    @test detuned_objective.normalized_residuals.r_r ≈ -1.2
    @test detuned_objective.normalized_residuals.r_p ≈ 1.2

    legacy_metrics = merge(
        TEST_MODEL_IDENTITY,
        (
            stage_id=:stage2_equivalent,
            model_family=:equivalent_exact_n,
            fr_qrp_on_hz=slot_hz,
            fp_qrp_on_hz=slot_hz,
            J_qrp_on_hz=5.0e6,
            notch_rp_on_hz=4.5e9,
            kappa_sum_qrp_on_ext_on_hz=20.0e6,
            eta_r_qrp_on=0.5,
            eta_p_qrp_on=0.5,
            effective_diagonal_frequency_extraction=
                :q_feedline_downfolded_rp_complex_operator,
            effective_exchange_extraction=
                :q_feedline_downfolded_rp_complex_midpoint_residue,
            notch_authority=:rp_on,
            linewidth_pole_scope=:qrp_three,
            primary_linewidth_extraction=:L_C,
        ),
    )
    @test_throws ErrorException d3_stage2_objective(
        legacy_metrics,
        slot_hz,
        D3_HUMAN_APPROVED_OBJECTIVE_AUTHORITY,
        TEST_MODEL_IDENTITY,
    )
end
