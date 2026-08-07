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
        "891a50bfc4c85889b82d0f64fe03b527ac68cb870e6d5542f99c849b80a304b6"

    perturbed = merge(metrics, (
        fr_eff_complete_complement_rp_hz=slot_hz * 1.01,
        fp_eff_complete_complement_rp_hz=slot_hz * 0.98,
        J_eff_complete_complement_rp_coherent_hz=7.5e6,
        notch_distributed_rp_on_hz=4.5e9,
        kappa_sum_local_hybrid_rp_hz=25.0e6,
        linewidth_fraction_min_local_hybrid_rp=0.4,
        linewidth_fraction_max_local_hybrid_rp=0.6,
    ))
    perturbed_objective = d3_stage2_objective(
        perturbed,
        slot_hz,
        D3_HUMAN_APPROVED_OBJECTIVE_AUTHORITY,
        TEST_SOURCE_IDENTITY,
    )
    expected_residuals = (
        r_r=0.01,
        r_p=-0.02,
        r_J=0.5,
        r_n=-0.1,
        r_kappa=0.25,
        r_eta=-0.2,
    )
    for name in keys(expected_residuals)
        @test getproperty(perturbed_objective.normalized_residuals, name) ≈
            getproperty(expected_residuals, name)
    end
    @test perturbed_objective.cost ≈ sum(abs2, values(expected_residuals))
    @test !perturbed_objective.target_diagnostics.readout_effective_diagonal_within_tolerance
    @test !perturbed_objective.target_diagnostics.filter_effective_diagonal_within_tolerance
    @test perturbed_objective.target_diagnostics.linewidth_participation
    @test perturbed_objective.promotion_gate_status == :not_evaluated
    @test !perturbed_objective.promotion_eligible

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
