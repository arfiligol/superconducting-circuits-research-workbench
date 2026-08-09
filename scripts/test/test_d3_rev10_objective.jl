using Test

const WORKBENCH_ROOT = normpath(joinpath(@__DIR__, "..", ".."))
include(joinpath(
    WORKBENCH_ROOT,
    "notebooks",
    "pluto",
    "D3 Intrinsic Purcell Filter Design",
    "d3_rev10_objective.jl",
))

const TEST_SOURCE_IDENTITY = (
    source_profile_identity=(canonical_sha256=repeat("a", 64),),
    grid_identity=(canonical_sha256=repeat("b", 64),),
)

function objective_metrics(; slot_hz=5.6e9)
    return (
        contract_id="d3-rev10-targeted-schur-candidate-metrics.v3",
        model_family=:hybridized_distributed_lumped,
        source_profile_identity=TEST_SOURCE_IDENTITY.source_profile_identity,
        grid_identity=TEST_SOURCE_IDENTITY.grid_identity,
        fr_eff_complete_complement_rp_hz=slot_hz,
        fp_eff_complete_complement_rp_hz=slot_hz,
        J_eff_complete_complement_rp_coherent_hz=5.0e6,
        f_n_anchored_rp_transfer_zero_hz=5.0e9,
        kappa_sum_anchored_bare_rp_hz=20.0e6,
        effective_diagonal_frequency_extraction=
            :complete_complement_rp_anchored_bare_complex_diagonal_roots,
        effective_exchange_extraction=
            :complete_complement_rp_complex_midpoint_residue,
        notch_authority=:full_open_eom_anchored_r_to_p_transfer_cofactor_zero,
        linewidth_sum_extraction=:anchored_bare_diagonal_root_trace,
    )
end

@testset "D3 revision-10 five-term Objective" begin
    @test D3_REV10_TARGET_SLOT_FREQUENCIES_HZ ==
        (5.6e9, 5.7e9, 5.8e9, 5.9e9, 6.0e9, 6.1e9)
    @test D3_REV10_OBJECTIVE_AUTHORITY.target_contract_sha256 ==
        "b0a5bd3dcf721481171f3db88a83e23f5582cd184c3f598d7ecc91d45c56bac6"
    @test D3_REV10_OBJECTIVE_AUTHORITY.residual_multipliers == (
        r_r=100.0,
        r_p=100.0,
        r_n=100.0,
        r_J=10.0,
        r_kappa=10.0,
    )

    slot_hz = 5.6e9
    metrics = objective_metrics(; slot_hz=slot_hz)
    objective = d3_rev10_five_term_objective(
        metrics,
        slot_hz,
        D3_REV10_OBJECTIVE_AUTHORITY,
        TEST_SOURCE_IDENTITY,
    )
    @test objective.contract_id ==
        "d3-rev10-anchored-bare-five-term-cma-objective.v2"
    @test objective.cost == 0.0
    @test objective.source_identity == TEST_SOURCE_IDENTITY
    @test !hasproperty(objective, :stage_id)
    @test !hasproperty(objective, :target_gates)
    @test !hasproperty(objective, :target_diagnostics)
    @test !hasproperty(objective.normalized_residuals, :r_eta)

    perturbed = merge(metrics, (
        fr_eff_complete_complement_rp_hz=slot_hz * 1.01,
        fp_eff_complete_complement_rp_hz=slot_hz * 0.98,
        J_eff_complete_complement_rp_coherent_hz=7.5e6,
        f_n_anchored_rp_transfer_zero_hz=4.5e9,
        kappa_sum_anchored_bare_rp_hz=25.0e6,
    ))
    perturbed_objective = d3_rev10_five_term_objective(
        perturbed,
        slot_hz,
        D3_REV10_OBJECTIVE_AUTHORITY,
        TEST_SOURCE_IDENTITY,
    )
    expected_residuals = (
        r_r=0.01,
        r_p=-0.02,
        r_n=-0.1,
        r_J=0.5,
        r_kappa=0.25,
    )
    for name in keys(expected_residuals)
        @test getproperty(perturbed_objective.normalized_residuals, name) ≈
            getproperty(expected_residuals, name)
    end
    @test perturbed_objective.cost ≈ 136.25

    lossless = merge(metrics, (kappa_sum_anchored_bare_rp_hz=0.0,))
    @test isfinite(d3_rev10_five_term_objective(
        lossless,
        slot_hz,
        D3_REV10_OBJECTIVE_AUTHORITY,
        TEST_SOURCE_IDENTITY,
    ).cost)

    superseded = merge(metrics, (
        contract_id="d3-rev10-targeted-schur-candidate-metrics.v1",
    ))
    @test_throws ErrorException d3_rev10_five_term_objective(
        superseded,
        slot_hz,
        D3_REV10_OBJECTIVE_AUTHORITY,
        TEST_SOURCE_IDENTITY,
    )
    @test_throws ErrorException d3_rev10_five_term_objective(
        metrics,
        slot_hz,
        D3_REV10_OBJECTIVE_AUTHORITY,
        merge(TEST_SOURCE_IDENTITY, (
            grid_identity=(canonical_sha256=repeat("c", 64),),
        )),
    )
end
