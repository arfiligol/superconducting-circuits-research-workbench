# D3 revision-10 five-quantity objective. Every operand comes from one
# fixed-node direct C/K/G targeted-Schur evaluation of the same physical
# candidate. Participation, Equivalent, HB, and fit quantities are absent.

const D3_REV10_OBJECTIVE_CONTRACT_ID =
    "d3-rev10-anchored-bare-five-term-cma-objective.v2"
const D3_REV10_TARGET_SLOT_FREQUENCIES_HZ =
    (5.6e9, 5.7e9, 5.8e9, 5.9e9, 6.0e9, 6.1e9)
const D3_REV10_INTERFERENCE_NOTCH_TARGET_HZ = 5.0e9

const D3_REV10_OBJECTIVE_AUTHORITY = (
    approval_status=:human_approved,
    target_id="d3-same-face-resonators-opposite-face-qubit-j5-k20-gap8",
    target_revision=10,
    target_contract_sha256=
        "b0a5bd3dcf721481171f3db88a83e23f5582cd184c3f598d7ecc91d45c56bac6",
    notch_authority=:full_open_eom_anchored_r_to_p_transfer_cofactor_zero,
    effective_diagonal_frequency_extraction=
        :complete_complement_rp_anchored_bare_complex_diagonal_roots,
    effective_exchange_extraction=
        :complete_complement_rp_complex_midpoint_residue,
    linewidth_sum_extraction=:anchored_bare_diagonal_root_trace,
    residual_multipliers=(
        r_r=100.0,
        r_p=100.0,
        r_n=100.0,
        r_J=10.0,
        r_kappa=10.0,
    ),
)

function _d3_objective_finite(metrics, name)
    hasproperty(metrics, name) || error("D3 objective metrics are missing $(name).")
    raw = getproperty(metrics, name)
    raw isa Real || error("D3 objective metric $(name) must be real.")
    value = Float64(raw)
    isfinite(value) || error("D3 objective metric $(name) must be finite.")
    return value
end

function _d3_objective_authority(authority)
    authority == D3_REV10_OBJECTIVE_AUTHORITY || error(
        "D3 objective authority does not equal the Human-accepted revision-10 target contract.",
    )
    return D3_REV10_OBJECTIVE_AUTHORITY
end

function _d3_validate_metric_source(metrics, expected_source_identity)
    hasproperty(metrics, :model_family) ||
        error("D3 objective metrics must declare model_family.")
    Symbol(metrics.model_family) == :hybridized_distributed_lumped || error(
        "D3 objective requires hybridized_distributed_lumped metrics.",
    )
    for name in (:source_profile_identity, :grid_identity)
        hasproperty(metrics, name) || error("D3 objective metrics must bind $(name).")
        hasproperty(expected_source_identity, name) || error(
            "D3 expected source identity must bind $(name).",
        )
        getproperty(metrics, name) == getproperty(expected_source_identity, name) || error(
            "D3 objective metric $(name) does not match the targeted-Schur evaluation identity.",
        )
    end
    hasproperty(metrics, :contract_id) ||
        error("D3 objective metrics must declare contract_id.")
    String(metrics.contract_id) == "d3-rev10-targeted-schur-candidate-metrics.v3" ||
        error("D3 objective metrics contract is not the current targeted-Schur authority.")
    return (
        source_profile_identity=metrics.source_profile_identity,
        grid_identity=metrics.grid_identity,
    )
end

function _d3_objective_slot(slot_hz)
    slot = Float64(slot_hz)
    slot in D3_REV10_TARGET_SLOT_FREQUENCIES_HZ || error(
        "D3 objective slot must be one of $(D3_REV10_TARGET_SLOT_FREQUENCIES_HZ) Hz.",
    )
    return slot
end

function _d3_validate_response_authority(metrics, authority)
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
    )
        hasproperty(metrics, name) ||
            error("D3 objective metrics are missing $(name).")
        Symbol(getproperty(metrics, name)) == expected || error(
            "D3 objective metric $(name) disagrees with the revision-10 authority.",
        )
    end
    return nothing
end

function _d3_objective_residuals(metrics, slot_hz)
    slot = _d3_objective_slot(slot_hz)
    fr = _d3_objective_finite(metrics, :fr_eff_complete_complement_rp_hz)
    fp = _d3_objective_finite(metrics, :fp_eff_complete_complement_rp_hz)
    notch = _d3_objective_finite(metrics, :f_n_anchored_rp_transfer_zero_hz)
    exchange = _d3_objective_finite(
        metrics,
        :J_eff_complete_complement_rp_coherent_hz,
    )
    total_linewidth = _d3_objective_finite(
        metrics,
        :kappa_sum_anchored_bare_rp_hz,
    )
    return (
        r_r=(fr - slot) / slot,
        r_p=(fp - slot) / slot,
        r_n=(notch - D3_REV10_INTERFERENCE_NOTCH_TARGET_HZ) /
            D3_REV10_INTERFERENCE_NOTCH_TARGET_HZ,
        r_J=(exchange - 5.0e6) / 5.0e6,
        r_kappa=(total_linewidth - 20.0e6) / 20.0e6,
    )
end

"""
    d3_rev10_five_term_objective(
        metrics,
        slot_hz,
        authority,
        expected_source_identity,
    )

Evaluate the sole revision-10 current Objective: signed relative residuals for
`f_r`, `f_p`, `f_n`, `J`, and `kappa_sum`, weighted 100/100/100/10/10.
"""
function d3_rev10_five_term_objective(
    metrics,
    slot_hz,
    authority,
    expected_source_identity,
)
    approved = _d3_objective_authority(authority)
    source_identity = _d3_validate_metric_source(
        metrics,
        expected_source_identity,
    )
    _d3_validate_response_authority(metrics, approved)
    residuals = _d3_objective_residuals(metrics, slot_hz)
    return (
        contract_id=D3_REV10_OBJECTIVE_CONTRACT_ID,
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
        normalized_residuals=residuals,
        residual_multipliers=approved.residual_multipliers,
    )
end
