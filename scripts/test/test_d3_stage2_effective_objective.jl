using Test

const WORKBENCH_ROOT = normpath(joinpath(@__DIR__, "..", ".."))
include(joinpath(
    WORKBENCH_ROOT,
    "notebooks",
    "pluto",
    "D3 Intrinsic Purcell Filter Design",
    "d3_stage_objectives.jl",
))

const TEST_SOURCE_IDENTITY = (
    source_profile_identity=(canonical_sha256=repeat("a", 64),),
    grid_identity=(canonical_sha256=repeat("b", 64),),
)

function objective_metrics(; slot_hz=5.6e9)
    return (
        contract_id="d3-stage2-targeted-schur-candidate-metrics.v1",
        stage_id=:stage2_direct_hybridized,
        model_family=:hybridized_distributed_lumped,
        source_profile_identity=TEST_SOURCE_IDENTITY.source_profile_identity,
        grid_identity=TEST_SOURCE_IDENTITY.grid_identity,
        fr_eff_complete_complement_rp_hz=slot_hz,
        fp_eff_complete_complement_rp_hz=slot_hz,
        J_eff_complete_complement_rp_coherent_hz=5.0e6,
        notch_distributed_rp_on_hz=5.0e9,
        kappa_sum_local_hybrid_rp_hz=20.0e6,
        linewidth_fraction_min_local_hybrid_rp=0.5,
        linewidth_fraction_max_local_hybrid_rp=0.5,
        effective_diagonal_frequency_extraction=
            :complete_complement_rp_complex_operator,
        effective_exchange_extraction=
            :complete_complement_rp_complex_midpoint_residue,
        notch_authority=:distributed_rp_on,
        linewidth_pole_scope=:complete_complement_rp_local_hybrid_two_pole,
        primary_linewidth_extraction=:targeted_schur_determinant_poles,
    )
end

@testset "D3 revision-10 targeted-Schur objective" begin
    slot_hz = 5.6e9
    metrics = objective_metrics(; slot_hz=slot_hz)
    objective = d3_stage2_objective(
        metrics,
        slot_hz,
        D3_HUMAN_APPROVED_OBJECTIVE_AUTHORITY,
        TEST_SOURCE_IDENTITY,
    )
    @test objective.contract_id ==
        "d3-stage2-direct-hybridized-targeted-schur-objective.v1"
    @test objective.cost == 0.0
    @test objective.source_identity == TEST_SOURCE_IDENTITY
    @test keys(objective.target_diagnostics) == (
        :readout_effective_diagonal_within_tolerance,
        :filter_effective_diagonal_within_tolerance,
        :linewidth_participation,
    )
    @test !hasproperty(objective, :target_gates)
    @test !hasproperty(objective, :target_gates_pass)
    @test D3_HUMAN_APPROVED_OBJECTIVE_AUTHORITY.linewidth_pole_scope ==
        :complete_complement_rp_local_hybrid_two_pole
    @test D3_HUMAN_APPROVED_OBJECTIVE_AUTHORITY.primary_linewidth_extraction ==
        :targeted_schur_determinant_poles
    @test D3_HUMAN_APPROVED_OBJECTIVE_AUTHORITY.target_contract_sha256 ==
        "5a1b35d96d25f3888c4bf6d4bc8ee2f4eceb6fd91e0a097abe9ee5490258acdf"

    detuned = merge(metrics, (
        fr_eff_complete_complement_rp_hz=slot_hz - 0.6e6,
        fp_eff_complete_complement_rp_hz=slot_hz + 0.6e6,
    ))
    detuned_objective = d3_stage2_objective(
        detuned,
        slot_hz,
        D3_HUMAN_APPROVED_OBJECTIVE_AUTHORITY,
        TEST_SOURCE_IDENTITY,
    )
    @test detuned_objective.normalized_residuals.r_r ≈ -1.2
    @test detuned_objective.normalized_residuals.r_p ≈ 1.2

    legacy = merge(metrics, (
        contract_id="d3-stage2-direct-hybridized-candidate-metrics.v1",
        kappa_sum_unordered_rp_subspace_hz=20.0e6,
    ))
    @test_throws ErrorException d3_stage2_objective(
        legacy,
        slot_hz,
        D3_HUMAN_APPROVED_OBJECTIVE_AUTHORITY,
        TEST_SOURCE_IDENTITY,
    )
    @test_throws ErrorException d3_stage2_objective(
        metrics,
        slot_hz,
        D3_HUMAN_APPROVED_OBJECTIVE_AUTHORITY,
        merge(TEST_SOURCE_IDENTITY, (
            grid_identity=(canonical_sha256=repeat("c", 64),),
        )),
    )
end
