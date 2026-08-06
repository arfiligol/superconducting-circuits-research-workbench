# D3 Stage-2 and Stage-3 objective scalarization. Stage 1 defines the
# Finite-Order Port-Response Model quantities but owns no numerical objective.
# Each physical stage must extract all six operands from its own complete
# CircuitPlan candidate before calling the corresponding objective below.

const D3_STAGE_OBJECTIVE_CONTRACT_ID =
    "d3-stage2-stage3-full-qrp-objective.v2"
const D3_TARGET_SLOT_FREQUENCIES_HZ = (5.6e9, 5.7e9, 5.8e9, 5.9e9, 6.0e9)
const D3_INTERFERENCE_NOTCH_TARGET_HZ = 5.0e9

const D3_HUMAN_APPROVED_OBJECTIVE_AUTHORITY = (
    approval_status=:human_approved,
    target_id="d3-same-face-resonators-opposite-face-qubit-j5-k20-gap8",
    target_revision=10,
    target_contract_sha256=
        "2853586e4c82e9912d5ef9cf178a22d45c534d70b6352da06aee13c2777ef3a9",
    notch_authority=:rp_on,
    effective_diagonal_frequency_extraction=
        :q_feedline_downfolded_rp_complex_operator,
    effective_exchange_extraction=
        :q_feedline_downfolded_rp_complex_midpoint_residue,
    linewidth_pole_scope=:qrp_three,
    primary_linewidth_extraction=:L_C,
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

function _d3_objective_model_identity(source, label)
    fields = (
        :circuit_plan_sha256,
        :capacitance_sha256,
        :inverse_inductance_sha256,
        :selector_sha256,
    )
    values = map(fields) do name
        hasproperty(source, name) || error("$(label) must bind $(name).")
        value = lowercase(strip(String(getproperty(source, name))))
        occursin(r"^[0-9a-f]{64}$", value) || error(
            "$(label) $(name) must contain 64 lowercase hexadecimal characters.",
        )
        value
    end
    return NamedTuple{fields}(Tuple(values))
end

function _d3_validate_metric_source(
    stage_id,
    model_family,
    metrics,
    expected_model_identity,
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
    model_identity = _d3_objective_model_identity(metrics, "D3 stage metrics")
    expected_identity = _d3_objective_model_identity(
        expected_model_identity,
        "D3 expected model identity",
    )
    model_identity == expected_identity || error(
        "D3 stage metrics do not match the model identity bound by the Run.",
    )
    return model_identity
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
        (:linewidth_pole_scope, authority.linewidth_pole_scope),
        (:primary_linewidth_extraction, authority.primary_linewidth_extraction),
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
        :fr_eff_q_feedline_downfolded_qrp_on_ext_on_hz,
        label,
    )
    fp = _d3_objective_finite(
        metrics,
        :fp_eff_q_feedline_downfolded_qrp_on_ext_on_hz,
        label,
    )
    notch = _d3_objective_finite(metrics, :notch_rp_on_hz, label)
    exchange = _d3_objective_finite(
        metrics,
        :J_rp_eff_q_feedline_downfolded_coherent_hz,
        label,
    )
    total_linewidth = _d3_objective_finite(
        metrics,
        :kappa_sum_qrp_on_ext_on_hz,
        label,
    )
    eta_r = _d3_objective_finite(metrics, :eta_r_qrp_on, label)
    eta_p = _d3_objective_finite(metrics, :eta_p_qrp_on, label)
    all(value -> 0 <= value <= 1, (eta_r, eta_p)) ||
        error("D3 resonator linewidth shares must lie in [0, 1].")
    abs((eta_r + eta_p) - 1.0) <= 1.0e-9 ||
        error("D3 resonator linewidth shares must sum to one.")

    residuals = (
        r_r=(fr - slot) / 0.5e6,
        r_p=(fp - slot) / 0.5e6,
        r_J=(exchange - 5.0e6) / 2.0e6,
        r_n=(notch - D3_INTERFERENCE_NOTCH_TARGET_HZ) / 10.0e6,
        r_kappa=(total_linewidth - 20.0e6) / 1.0e6,
        r_eta=(min(eta_r, eta_p) - 0.5) / 0.2,
    )
    target_gates = (
        readout_effective_diagonal_within_tolerance=
            abs(fr - slot) <= 0.5e6,
        filter_effective_diagonal_within_tolerance=
            abs(fp - slot) <= 0.5e6,
        linewidth_participation=
            0.3 <= eta_r <= 0.7 && 0.3 <= eta_p <= 0.7,
    )
    return residuals, target_gates
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
    d3_stage2_objective(metrics, slot_hz, authority, expected_model_identity)

Evaluate the single revision-10 Stage-2 Equivalent objective. Matrix-space and
open-response entries are provenance groups within one residual vector, not
separate costs or optimizer stages.
"""
function d3_stage2_objective(metrics, slot_hz, authority, expected_model_identity)
    approved = _d3_objective_authority(authority)
    model_identity = _d3_validate_metric_source(
        :stage2_equivalent,
        :equivalent_exact_n,
        metrics,
        expected_model_identity,
    )
    _d3_validate_response_authority(metrics, approved, "D3 Stage-2 metrics")
    residuals, target_gates = _d3_objective_residuals(
        metrics,
        slot_hz,
        "D3 Stage-2 metrics",
    )
    return (
        contract_id=D3_STAGE_OBJECTIVE_CONTRACT_ID,
        stage_id=:stage2_equivalent,
        model_family=:equivalent_exact_n,
        authority=approved,
        model_identity=model_identity,
        cost=sum(abs2, values(residuals)),
        provenance_groups=_d3_objective_provenance_groups(
            residuals,
            :q_feedline_downfolded_rp_complex_operator,
            :direct_equivalent_open_response,
        ),
        normalized_residuals=residuals,
        target_gates=target_gates,
        target_gates_pass=all(values(target_gates)),
        promotion_gate_status=:not_evaluated,
        promotion_eligible=false,
    )
end

"""
    d3_stage3_objective(metrics, slot_hz, authority, expected_model_identity)

Evaluate the independent revision-10 Stage-3 Hybridized objective. Every
operand must be recomputed from the same complete distributed/lumped candidate.
"""
function d3_stage3_objective(metrics, slot_hz, authority, expected_model_identity)
    approved = _d3_objective_authority(authority)
    model_identity = _d3_validate_metric_source(
        :stage3_hybridized,
        :hybridized_distributed_lumped,
        metrics,
        expected_model_identity,
    )
    _d3_validate_response_authority(metrics, approved, "D3 Stage-3 metrics")
    residuals, target_gates = _d3_objective_residuals(
        metrics,
        slot_hz,
        "D3 Stage-3 metrics",
    )
    return (
        contract_id=D3_STAGE_OBJECTIVE_CONTRACT_ID,
        stage_id=:stage3_hybridized,
        model_family=:hybridized_distributed_lumped,
        authority=approved,
        model_identity=model_identity,
        cost=sum(abs2, values(residuals)),
        provenance_groups=_d3_objective_provenance_groups(
            residuals,
            :hybridized_coupling_on_number_conserving_matrix,
            :independent_hybridized_distributed_lumped_response,
        ),
        normalized_residuals=residuals,
        target_gates=target_gates,
        target_gates_pass=all(values(target_gates)),
        promotion_gate_status=:not_evaluated,
        promotion_eligible=false,
    )
end
