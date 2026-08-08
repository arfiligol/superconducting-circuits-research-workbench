# D3 revision-10 direct-Hybridized Stage-2 objective scalarization. Stage 1
# defines the operators and quantities but owns no numerical optimizer. Every
# operand comes from the same complete distributed/lumped CircuitPlan candidate.

const D3_STAGE_OBJECTIVE_CONTRACT_ID =
    "d3-stage2-direct-hybridized-targeted-schur-objective.v1"
const D3_TARGET_SLOT_FREQUENCIES_HZ = (5.6e9, 5.7e9, 5.8e9, 5.9e9, 6.0e9)
const D3_INTERFERENCE_NOTCH_TARGET_HZ = 5.0e9

const D3_HUMAN_APPROVED_OBJECTIVE_AUTHORITY = (
    approval_status=:human_approved,
    target_id="d3-same-face-resonators-opposite-face-qubit-j5-k20-gap8",
    target_revision=10,
    target_contract_sha256=
        "501645c18e9348546edd749bc566f6313906eec662cacad8577ac83a6034e77a",
    notch_authority=:distributed_rp_on,
    effective_diagonal_frequency_extraction=
        :complete_complement_rp_anchored_bare_complex_diagonal_roots,
    effective_exchange_extraction=
        :complete_complement_rp_complex_midpoint_residue,
    linewidth_sum_extraction=:anchored_bare_diagonal_root_trace,
    linewidth_participation_extraction=
        :residue_normalized_local_2x2_eigendiagonalization,
    residual_multipliers=(
        r_r=100.0,
        r_p=100.0,
        r_J=10.0,
        r_n=100.0,
        r_kappa=10.0,
        r_eta=1.0,
    ),
)

function _d3_objective_finite(metrics, name, label)
    hasproperty(metrics, name) || error("$(label) is missing $(name).")
    raw = getproperty(metrics, name)
    raw isa Real || error("$(label) $(name) must be real.")
    value = Float64(raw)
    isfinite(value) || error("$(label) $(name) must be finite.")
    return value
end

function _d3_objective_authority(authority)
    authority == D3_HUMAN_APPROVED_OBJECTIVE_AUTHORITY || error(
        "D3 objective authority does not equal the Human-accepted revision-10 target contract.",
    )
    return D3_HUMAN_APPROVED_OBJECTIVE_AUTHORITY
end

function _d3_validate_metric_source(
    stage_id,
    model_family,
    metrics,
    expected_source_identity,
)
    metric_stage = hasproperty(metrics, :stage_id) ?
        Symbol(metrics.stage_id) : error("D3 stage metrics must declare stage_id.")
    metric_family = hasproperty(metrics, :model_family) ?
        Symbol(metrics.model_family) :
        error("D3 stage metrics must declare model_family.")
    metric_stage == stage_id || error(
        "D3 objective received metrics from $(metric_stage), expected $(stage_id).",
    )
    metric_family == model_family || error(
        "D3 objective received $(metric_family) metrics, expected $(model_family).",
    )
    for name in (:source_profile_identity, :grid_identity)
        hasproperty(metrics, name) || error("D3 stage metrics must bind $(name).")
        hasproperty(expected_source_identity, name) || error(
            "D3 expected source identity must bind $(name).",
        )
        getproperty(metrics, name) == getproperty(expected_source_identity, name) || error(
            "D3 stage metrics $(name) does not match the targeted-Schur evaluation identity.",
        )
    end
    contract_id = hasproperty(metrics, :contract_id) ? String(metrics.contract_id) :
        error("D3 stage metrics must declare contract_id.")
    contract_id == "d3-stage2-targeted-schur-anchored-bare-candidate-metrics.v1" || error(
        "D3 stage metrics contract is not the targeted-Schur metrics authority.",
    )
    return (
        source_profile_identity=metrics.source_profile_identity,
        grid_identity=metrics.grid_identity,
    )
end

function _d3_objective_slot(slot_hz)
    slot = Float64(slot_hz)
    slot in D3_TARGET_SLOT_FREQUENCIES_HZ || error(
        "D3 objective Slot must be one of $(D3_TARGET_SLOT_FREQUENCIES_HZ) Hz.",
    )
    return slot
end

function _d3_validate_response_authority(metrics, authority, label)
    for (name, expected) in (
        (
            :effective_diagonal_frequency_extraction,
            authority.effective_diagonal_frequency_extraction,
        ),
        (
            :effective_exchange_extraction,
            authority.effective_exchange_extraction,
        ),
        (:notch_authority, authority.notch_authority),
        (:linewidth_sum_extraction, authority.linewidth_sum_extraction),
        (
            :linewidth_participation_extraction,
            authority.linewidth_participation_extraction,
        ),
    )
        hasproperty(metrics, name) ||
            error("$(label) is missing $(name).")
        Symbol(getproperty(metrics, name)) == expected || error(
            "$(label) $(name) disagrees with the revision-10 authority.",
        )
    end
    return nothing
end

function _d3_objective_residuals(metrics, slot_hz, label)
    slot = _d3_objective_slot(slot_hz)
    fr = _d3_objective_finite(
        metrics,
        :fr_eff_complete_complement_rp_hz,
        label,
    )
    fp = _d3_objective_finite(
        metrics,
        :fp_eff_complete_complement_rp_hz,
        label,
    )
    notch = _d3_objective_finite(metrics, :notch_distributed_rp_on_hz, label)
    exchange = _d3_objective_finite(
        metrics,
        :J_eff_complete_complement_rp_coherent_hz,
        label,
    )
    total_linewidth = _d3_objective_finite(
        metrics,
        :kappa_sum_anchored_bare_rp_hz,
        label,
    )
    fraction_min = _d3_objective_finite(
        metrics,
        :linewidth_fraction_min_local_2x2_rp,
        label,
    )
    0 <= fraction_min <= 0.5 || error(
        "D3 local 2x2 RP minimum linewidth fraction must be in [0, 0.5].",
    )

    residuals = (
        r_r=(fr - slot) / slot,
        r_p=(fp - slot) / slot,
        r_J=(exchange - 5.0e6) / 5.0e6,
        r_n=(notch - D3_INTERFERENCE_NOTCH_TARGET_HZ) /
            D3_INTERFERENCE_NOTCH_TARGET_HZ,
        r_kappa=(total_linewidth - 20.0e6) / 20.0e6,
        r_eta=(fraction_min - 0.5) / 0.5,
    )
    target_diagnostics = (
        readout_effective_diagonal_within_tolerance=
            abs(fr - slot) <= 0.5e6,
        filter_effective_diagonal_within_tolerance=
            abs(fp - slot) <= 0.5e6,
        linewidth_participation=fraction_min >= 0.3,
    )
    return residuals, target_diagnostics
end

function _d3_objective_provenance_groups(residuals, matrix_authority, response_authority)
    return (
        matrix_space=(
            operand_authority=matrix_authority,
            normalized_residuals=(
                r_r=residuals.r_r,
                r_p=residuals.r_p,
                r_J=residuals.r_J,
            ),
        ),
        open_response=(
            operand_authority=response_authority,
            normalized_residuals=(
                r_n=residuals.r_n,
                r_kappa=residuals.r_kappa,
                r_eta=residuals.r_eta,
            ),
        ),
    )
end

"""
    d3_stage2_objective(metrics, slot_hz, authority, expected_source_identity)

Evaluate the single revision-10 direct-Hybridized Stage-2 objective. Operator and
open-response entries are provenance groups within one residual vector, not
separate costs or optimizer stages.
"""
function d3_stage2_objective(metrics, slot_hz, authority, expected_source_identity)
    approved = _d3_objective_authority(authority)
    source_identity = _d3_validate_metric_source(
        :stage2_direct_hybridized,
        :hybridized_distributed_lumped,
        metrics,
        expected_source_identity,
    )
    _d3_validate_response_authority(metrics, approved, "D3 Stage-2 metrics")
    residuals, target_diagnostics = _d3_objective_residuals(
        metrics,
        slot_hz,
        "D3 Stage-2 metrics",
    )
    return (
        contract_id=D3_STAGE_OBJECTIVE_CONTRACT_ID,
        stage_id=:stage2_direct_hybridized,
        model_family=:hybridized_distributed_lumped,
        authority=approved,
        source_identity=source_identity,
        cost=sum(
            name -> abs2(
                getproperty(residuals, name) *
                getproperty(approved.residual_multipliers, name),
            ),
            keys(residuals),
        ),
        provenance_groups=_d3_objective_provenance_groups(
            residuals,
            :complete_complement_rp_anchored_bare_complex_diagonal_roots,
            (
                notch=:distributed_rp_on,
                linewidth_sum=:anchored_bare_diagonal_root_trace,
                linewidth_participation=
                    :residue_normalized_local_2x2_eigendiagonalization,
            ),
        ),
        normalized_residuals=residuals,
        target_diagnostics=target_diagnostics,
        promotion_gate_status=:not_evaluated,
        promotion_eligible=false,
    )
end

function d3_stage3_objective(args...)
    error(
        "The independent Stage-3 Circuit Model objective is superseded; Stage 3 is Layout/EM only.",
    )
end
