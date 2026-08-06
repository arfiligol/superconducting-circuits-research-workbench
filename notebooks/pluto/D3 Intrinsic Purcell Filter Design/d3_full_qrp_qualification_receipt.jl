# Candidate-specific qualification of the already-defined Stage-2 Full-QRP
# cared outputs. This module binds successful upstream extractors; it does not
# redefine objective operands, targets, costs, circuit equations, or topology.

isdefined(@__MODULE__, :D3SemanticHash) ||
    include(joinpath(@__DIR__, "d3_semantic_hash.jl"))
isdefined(@__MODULE__, :D3LCQualificationReceipt) ||
    include(joinpath(@__DIR__, "d3_lc_qualification_receipt.jl"))

module D3FullQRPQualificationReceipt

using SHA
using SuperconductingCircuitsCore
using ..D3SemanticHash: SEMANTIC_HASH_FRAMING, semantic_value_sha256
using ..D3LCQualificationReceipt: D3AuthorizedStage2LC,
    d3_lc_qualification_receipt_identity,
    validate_d3_stage2_lc_authorization_match

const JSON3 = SuperconductingCircuitsCore.JSON3
const D3_FULL_QRP_QUALIFICATION_SCHEMA =
    "d3-stage2-full-qrp-cared-output-qualification.v1"
const D3_FULL_QRP_QUALIFICATION_CONTRACT =
    "d3-rev10-exact-candidate-full-qrp-qualification.v1"
const D3_FULL_QRP_QUALIFICATION_POLICY_ID =
    "d3-rev10-full-qrp-existing-extractor-policy.v1"
const _MODEL_IDENTITY_FIELDS = (
    :circuit_plan_sha256,
    :capacitance_sha256,
    :inverse_inductance_sha256,
    :selector_sha256,
)
const _CANDIDATE_FIELDS =
    (:lr_open_m, :lr_short_m, :lc_m, :lp_open_m, :lp_short_m, :u_IDC)
const _METRIC_FIELDS = (
    :fr_eff_q_feedline_downfolded_qrp_on_ext_on_hz,
    :fp_eff_q_feedline_downfolded_qrp_on_ext_on_hz,
    :J_rp_eff_q_feedline_downfolded_coherent_hz,
    :notch_rp_on_hz,
    :kappa_sum_qrp_on_ext_on_hz,
    :eta_r_qrp_on,
    :eta_p_qrp_on,
)
const _AUTHORITY_FIELDS = (
    :effective_diagonal_frequency_extraction,
    :effective_exchange_extraction,
    :notch_authority,
    :linewidth_pole_scope,
    :primary_linewidth_extraction,
)
const _GATE_POLICY_FIELDS = (
    :maximum_elimination_condition_number,
    :maximum_relative_elimination_solve_residual,
    :maximum_relative_reciprocity_error,
    :maximum_relative_passivity_violation,
    :maximum_relative_root_residual,
    :maximum_root_growth_rate_hz,
    :minimum_normalized_residue_slope,
    :maximum_relative_coupling_spread,
    :maximum_relative_determinant_closure_error,
)

const _POLICY_PAYLOAD = Dict(
    "schema_version" => D3_FULL_QRP_QUALIFICATION_SCHEMA,
    "contract_id" => D3_FULL_QRP_QUALIFICATION_CONTRACT,
    "policy_id" => D3_FULL_QRP_QUALIFICATION_POLICY_ID,
    "semantic_hash_framing" => SEMANTIC_HASH_FRAMING,
    "authority_mode" => "exact_candidate_receipt_only",
    "accepted_envelope" => nothing,
    "objective_target_gate_role" => "not_evaluated_by_qualification",
    "cared_outputs" => String.(_METRIC_FIELDS),
    "required_extractions" => [
        "q_feedline_downfolded_rp_effective_operator",
        "intrinsic_rp_on_notch",
        "exact_open_qrp_identity_continuation",
        "identity_continued_lc_linewidth_and_participation",
    ],
)
const D3_FULL_QRP_QUALIFICATION_POLICY_SHA256 =
    semantic_value_sha256(_POLICY_PAYLOAD)

export D3FullQRPReceiptNotEvaluable,
    D3FullQRPQualificationReceipt,
    D3AuthorizedStage2FullQRP,
    D3_FULL_QRP_QUALIFICATION_CONTRACT,
    D3_FULL_QRP_QUALIFICATION_POLICY_ID,
    D3_FULL_QRP_QUALIFICATION_POLICY_SHA256,
    D3_FULL_QRP_QUALIFICATION_SCHEMA,
    authorize_d3_stage2_full_qrp_receipt,
    d3_full_qrp_qualification_policy,
    d3_full_qrp_qualification_receipt_identity,
    evaluate_d3_stage2_objective_with_evidence,
    load_d3_full_qrp_qualification_receipt,
    produce_d3_full_qrp_qualification_evidence,
    revalidate_d3_stage2_full_qrp_receipt,
    validate_d3_full_qrp_qualification_receipt_identity,
    validate_d3_full_qrp_qualification_policy,
    validate_d3_stage2_full_qrp_authorization_match,
    write_d3_full_qrp_qualification_receipt

struct D3FullQRPReceiptNotEvaluable <: Exception
    code::String
    reason::String
    details
end

Base.showerror(io::IO, exception::D3FullQRPReceiptNotEvaluable) = print(
    io,
    "D3 Full-QRP receipt NOT_EVALUABLE [",
    exception.code,
    "]: ",
    exception.reason,
)

struct D3FullQRPQualificationReceipt{T}
    path::String
    sha256::String
    normalized::T
end

struct D3AuthorizedStage2FullQRP{R,C,L,M}
    receipt::R
    candidate::C
    lc_qualification::L
    model_identity::M
end

_fail(code, reason, details=nothing) =
    throw(D3FullQRPReceiptNotEvaluable(String(code), String(reason), details))

function _sha(value, label)
    value isa AbstractString ||
        _fail("full_qrp_receipt.malformed", "$(label) must be text.")
    parsed = strip(String(value))
    parsed == lowercase(parsed) && occursin(r"^[0-9a-f]{64}$", parsed) ||
        _fail("full_qrp_receipt.malformed", "$(label) must be lowercase SHA-256.")
    return parsed
end

function _real(value, label; positive=false, nonnegative=false)
    value isa Real && !(value isa Bool) ||
        _fail("full_qrp_receipt.malformed", "$(label) must be numeric.")
    parsed = Float64(value)
    isfinite(parsed) ||
        _fail("full_qrp_receipt.malformed", "$(label) must be finite.")
    positive && parsed <= 0 &&
        _fail("full_qrp_receipt.malformed", "$(label) must be positive.")
    nonnegative && parsed < 0 &&
        _fail("full_qrp_receipt.malformed", "$(label) must be nonnegative.")
    return parsed
end

function _candidate(candidate)
    Set(propertynames(candidate)) == Set(_CANDIDATE_FIELDS) || _fail(
        "full_qrp_receipt.candidate_mismatch",
        "Full-QRP candidate fields do not equal the six Rev10 coordinates.",
    )
    return NamedTuple{_CANDIDATE_FIELDS}(Tuple(
        _real(getproperty(candidate, name), "candidate.$(name)"; positive=true)
        for name in _CANDIDATE_FIELDS
    ))
end

function _candidate_dict(candidate)
    return Dict(String(name) => getproperty(candidate, name) for name in _CANDIDATE_FIELDS)
end

function _model_identity(source, label)
    all(name -> hasproperty(source, name), _MODEL_IDENTITY_FIELDS) ||
        _fail("full_qrp_receipt.model_mismatch", "$(label) omits model identity fields.")
    return NamedTuple{_MODEL_IDENTITY_FIELDS}(Tuple(
        _sha(getproperty(source, name), "$(label).$(name)") for name in _MODEL_IDENTITY_FIELDS
    ))
end

function _json_safe(value)
    value isa Symbol && return String(value)
    value isa Complex && return Dict("real" => real(value), "imag" => imag(value))
    value isa NamedTuple && return Dict(String(name) => _json_safe(item) for (name, item) in pairs(value))
    value isa AbstractDict && return Dict(String(key) => _json_safe(item) for (key, item) in pairs(value))
    value isa Tuple && return [_json_safe(item) for item in value]
    value isa AbstractVector && return [_json_safe(item) for item in value]
    return value
end

function _exact_properties(value, fields, label)
    Tuple(propertynames(value)) == fields || _fail(
        "full_qrp_receipt.malformed",
        "$(label) fields do not match the existing extractor contract.",
    )
    return value
end

function _validate_foundation(foundation, candidate, lc_qualification)
    hasproperty(foundation, :contract_id) &&
        foundation.contract_id in (
            "d3-stage2-candidate-metrics.v4",
            "d3-stage2-candidate-foundation.v5",
        ) || _fail(
        "full_qrp_receipt.foundation_mismatch",
        "Full-QRP qualification requires current Stage-2 metrics/foundation.",
    )
    hasproperty(foundation, :stage_id) && foundation.stage_id == :stage2_equivalent &&
        hasproperty(foundation, :model_family) &&
        foundation.model_family == :equivalent_exact_n || _fail(
        "full_qrp_receipt.foundation_mismatch",
        "Full-QRP qualification requires the Stage-2 Equivalent Exact-N model.",
    )
    hasproperty(foundation, :objective_ready) && foundation.objective_ready === true ||
        _fail("full_qrp_receipt.foundation_mismatch", "Foundation is not objective-ready.")
    foundation.stage.candidate == candidate || _fail(
        "full_qrp_receipt.candidate_mismatch",
        "Foundation belongs to a different candidate.",
    )
    hasproperty(foundation.stage, :lc_qualification) &&
        foundation.stage.lc_qualification isa D3AuthorizedStage2LC || _fail(
        "full_qrp_receipt.lc_mismatch",
        "Foundation omits current LC authorization.",
    )
    validate_d3_stage2_lc_authorization_match(
        foundation.stage.lc_qualification,
        lc_qualification,
    )
    hasproperty(foundation, :metrics) && hasproperty(foundation, :extractions) ||
        _fail("full_qrp_receipt.foundation_mismatch", "Foundation omits cared outputs.")
    return _model_identity(
        foundation.cqed_handoff.source_model_identity,
        "foundation model identity",
    )
end

function _metrics(metrics, model_identity)
    numbers = NamedTuple{_METRIC_FIELDS}(Tuple(
        begin
            hasproperty(metrics, name) || _fail(
                "full_qrp_receipt.missing_operand",
                "Full-QRP metrics omit $(name).",
            )
            _real(getproperty(metrics, name), "metrics.$(name)"; nonnegative=true)
        end for name in _METRIC_FIELDS
    ))
    all(value -> 0 <= value <= 1, (numbers.eta_r_qrp_on, numbers.eta_p_qrp_on)) &&
        abs(numbers.eta_r_qrp_on + numbers.eta_p_qrp_on - 1.0) <= 1.0e-9 || _fail(
        "full_qrp_receipt.failed_gate",
        "Full-QRP linewidth participation is invalid.",
    )
    authority = NamedTuple{_AUTHORITY_FIELDS}(Tuple(
        begin
            hasproperty(metrics, name) || _fail(
                "full_qrp_receipt.missing_operand",
                "Full-QRP metrics omit $(name).",
            )
            Symbol(getproperty(metrics, name))
        end for name in _AUTHORITY_FIELDS
    ))
    authority == (
        effective_diagonal_frequency_extraction=
            :q_feedline_downfolded_rp_complex_operator,
        effective_exchange_extraction=
            :q_feedline_downfolded_rp_complex_midpoint_residue,
        notch_authority=:rp_on,
        linewidth_pole_scope=:qrp_three,
        primary_linewidth_extraction=:L_C,
    ) || _fail(
        "full_qrp_receipt.authority_mismatch",
        "Full-QRP operand authority changed.",
    )
    metric_identity = _model_identity(metrics, "metrics model identity")
    metric_identity == model_identity || _fail(
        "full_qrp_receipt.model_mismatch",
        "Full-QRP metrics and foundation model identities differ.",
    )
    return numbers, authority
end

function _effective_evidence(effective, model_identity)
    effective.contract_id == "d3-q-feedline-downfolded-rp-effective-operator.v1" &&
        effective.coupling_state == :qrp_on &&
        effective.external_port_state == :matched_open &&
        Symbol.(collect(effective.retained_coordinates)) == [:r, :p] &&
        Symbol.(collect(effective.eliminated_coordinates)) == [:q, :f1, :fc, :f2] || _fail(
        "full_qrp_receipt.extraction_mismatch",
        "Effective RP extraction changed its coupling/open/partition contract.",
    )
    source_identity = _model_identity(effective.source_model_identity, "effective RP model identity")
    source_identity == model_identity || _fail(
        "full_qrp_receipt.model_mismatch",
        "Effective RP extraction belongs to another model.",
    )
    _exact_properties(effective.gate_policy, _GATE_POLICY_FIELDS, "effective RP gate policy")
    gate_policy = NamedTuple{_GATE_POLICY_FIELDS}(Tuple(
        _real(getproperty(effective.gate_policy, name), "gate_policy.$(name)"; nonnegative=true)
        for name in _GATE_POLICY_FIELDS
    ))
    return Dict(
        "contract_id" => String(effective.contract_id),
        "coupling_state" => "qrp_on",
        "external_port_state" => "matched_open",
        "retained_coordinates" => ["r", "p"],
        "eliminated_coordinates" => ["q", "f1", "fc", "f2"],
        "source_model_identity" => _json_safe(source_identity),
        "gate_policy" => _json_safe(gate_policy),
        "gate_policy_sha256" => semantic_value_sha256(_json_safe(gate_policy)),
        "context_validation" => _json_safe(effective.context_validation),
        "readout_frequency_hz" => _real(effective.readout.frequency_hz, "effective readout"; positive=true),
        "filter_frequency_hz" => _real(effective.filter.frequency_hz, "effective filter"; positive=true),
        "coherent_exchange_hz" => _real(effective.coherent_exchange_hz, "effective exchange"; nonnegative=true),
        "determinant_closure" => _json_safe(effective.determinant_closure),
        "provenance" => _json_safe(effective.provenance),
    )
end

function _notch_evidence(notch)
    notch.quantity == :f_n_rp_on &&
        notch.provenance.contract_id == "d3-intrinsic-pair-rp-on-z21-zero.v1" &&
        notch.provenance.coupling_state == :rp_on &&
        all(values(notch.residual_gates)) || _fail(
        "full_qrp_receipt.failed_gate",
        "Intrinsic RP-on notch extraction is not qualified.",
    )
    return Dict(
        "contract_id" => String(notch.provenance.contract_id),
        "coupling_state" => "rp_on",
        "frequency_hz" => _real(notch.frequency_hz, "notch frequency"; positive=true),
        "frequency_bracket_hz" => _json_safe(notch.frequency_bracket_hz),
        "frequency_tolerance_hz" => _real(notch.frequency_tolerance_hz, "notch tolerance"; nonnegative=true),
        "residual_tolerances_ohm" => _json_safe(notch.residual_tolerances_ohm),
        "residual_gates" => _json_safe(notch.residual_gates),
        "circuit_plan_sha256" => _sha(notch.provenance.circuit_plan_sha256, "notch circuit plan"),
        "provenance" => _json_safe(notch.provenance),
    )
end

function _identity_evidence(identity, linewidth, model_identity)
    identity.contract_id == "d3-exact-open-qrp-identity-continuation.v1" &&
        Tuple(identity.identities) == (:q, :r, :p) &&
        identity.provenance.identity_rule == :global_normalized_stored_energy_overlap &&
        identity.provenance.frequency_rank_assignment == :forbidden || _fail(
        "full_qrp_receipt.extraction_mismatch",
        "Exact-open q/r/p identity contract changed.",
    )
    _model_identity(identity.provenance.source_model_identity, "identity continuation model") ==
        model_identity || _fail(
        "full_qrp_receipt.model_mismatch",
        "Identity continuation belongs to another model.",
    )
    assignment = identity.assignment
    assignment.minimum_selected_overlap >= assignment.minimum_overlap &&
        assignment.assignment_margin >= assignment.minimum_assignment_margin || _fail(
        "full_qrp_receipt.failed_gate",
        "Exact-open identity overlap or assignment margin failed.",
    )
    linewidth.provenance.contract_id ==
        "d3-linewidth-lc-identity-continued-qrp-sum.v1" &&
        linewidth.provenance.pole_scope == :qrp_three &&
        linewidth.provenance.frequency_rank_assignment == :forbidden || _fail(
        "full_qrp_receipt.extraction_mismatch",
        "L_C linewidth authority changed.",
    )
    return Dict(
        "identity_contract_id" => String(identity.contract_id),
        "exact_open_generator_sha256" =>
            _sha(identity.provenance.exact_open_generator_sha256, "exact-open generator"),
        "assignment" => _json_safe(assignment),
        "energy_metric" => _json_safe(identity.energy_metric),
        "references" => _json_safe(identity.references),
        "linewidth_contract_id" => String(linewidth.provenance.contract_id),
        "per_identity_linewidth_hz" => _json_safe(linewidth.per_identity_linewidth_hz),
        "linewidth_sum_hz" => _real(linewidth.linewidth_hz, "linewidth sum"; positive=true),
        "eta_r" => _real(linewidth.eta_r, "eta_r"; nonnegative=true),
        "eta_p" => _real(linewidth.eta_p, "eta_p"; nonnegative=true),
    )
end

function _core_evidence(foundation, candidate, lc_qualification, q2d_artifact_sha256)
    values = _candidate(candidate)
    q2d = _sha(q2d_artifact_sha256, "Q2D artifact")
    model_identity = _validate_foundation(foundation, values, lc_qualification)
    metrics, authority = _metrics(foundation.metrics, model_identity)
    effective = _effective_evidence(foundation.extractions.effective_rp, model_identity)
    notch = _notch_evidence(foundation.extractions.notch)
    identity = _identity_evidence(
        foundation.extractions.identity_continuation,
        foundation.extractions.linewidth_lc,
        model_identity,
    )
    metrics.fr_eff_q_feedline_downfolded_qrp_on_ext_on_hz == effective["readout_frequency_hz"] &&
        metrics.fp_eff_q_feedline_downfolded_qrp_on_ext_on_hz == effective["filter_frequency_hz"] &&
        metrics.J_rp_eff_q_feedline_downfolded_coherent_hz == effective["coherent_exchange_hz"] &&
        metrics.notch_rp_on_hz == notch["frequency_hz"] &&
        metrics.kappa_sum_qrp_on_ext_on_hz == identity["linewidth_sum_hz"] &&
        metrics.eta_r_qrp_on == identity["eta_r"] &&
        metrics.eta_p_qrp_on == identity["eta_p"] || _fail(
        "full_qrp_receipt.operand_mismatch",
        "Objective metrics do not equal their cared-output extractors.",
    )
    lc_identity = d3_lc_qualification_receipt_identity(lc_qualification)
    core = Dict{String,Any}(
        "schema_version" => D3_FULL_QRP_QUALIFICATION_SCHEMA,
        "contract_id" => D3_FULL_QRP_QUALIFICATION_CONTRACT,
        "policy_id" => D3_FULL_QRP_QUALIFICATION_POLICY_ID,
        "policy_sha256" => D3_FULL_QRP_QUALIFICATION_POLICY_SHA256,
        "lifecycle_state" => "ACCEPTED",
        "data_class" => "project-internal",
        "authority_status" => "diagnostic_only",
        "promotion_eligible" => false,
        "final_status" => "PASS",
        "first_blocker" => nothing,
        "candidate" => _candidate_dict(values),
        "candidate_sha256" => semantic_value_sha256(_candidate_dict(values)),
        "q2d_artifact_sha256" => q2d,
        "lc_qualification_receipt" => _json_safe(lc_identity),
        "model_identity" => _json_safe(model_identity),
        "effective_rp" => effective,
        "notch_rp_on" => notch,
        "identity_continued_linewidth" => identity,
        "objective_metrics" => _json_safe(metrics),
        "operand_authority" => _json_safe(authority),
        "objective_target_gates_evaluated" => false,
        "nonclaims" => [
            "not an envelope or neighboring-point authority",
            "not an objective result, optimizer result, winner, closure, promotion, or publication claim",
        ],
    )
    return core
end

function produce_d3_full_qrp_qualification_evidence(
    foundation,
    candidate,
    lc_qualification::D3AuthorizedStage2LC;
    q2d_artifact_sha256,
)
    core = _core_evidence(
        foundation,
        candidate,
        lc_qualification,
        q2d_artifact_sha256,
    )
    core["semantic_receipt_sha256"] = semantic_value_sha256(core)
    return core
end

d3_full_qrp_qualification_policy() = merge(
    deepcopy(_POLICY_PAYLOAD),
    Dict("policy_sha256" => D3_FULL_QRP_QUALIFICATION_POLICY_SHA256),
)

function validate_d3_full_qrp_qualification_policy(value)
    value == d3_full_qrp_qualification_policy() || _fail(
        "full_qrp_receipt.stale",
        "Full-QRP qualification policy is not current.",
    )
    return d3_full_qrp_qualification_policy()
end

function validate_d3_full_qrp_qualification_receipt_identity(value)
    isnothing(value) && _fail(
        "full_qrp_receipt.missing",
        "Full-QRP qualification receipt identity is missing.",
    )
    return _sha(value, "Full-QRP receipt identity")
end

function _mapping(value, label)
    value isa AbstractDict ||
        _fail("full_qrp_receipt.malformed", "$(label) must be a mapping.")
    return Dict{String,Any}(String(key) => item for (key, item) in pairs(value))
end

function _normalize(payload)
    raw = _mapping(payload, "Full-QRP receipt")
    required = (
        "schema_version", "contract_id", "policy_id", "policy_sha256",
        "lifecycle_state", "data_class", "authority_status", "promotion_eligible",
        "final_status", "first_blocker", "candidate", "candidate_sha256",
        "q2d_artifact_sha256", "lc_qualification_receipt", "model_identity",
        "effective_rp", "notch_rp_on", "identity_continued_linewidth",
        "objective_metrics", "operand_authority", "objective_target_gates_evaluated",
        "nonclaims", "semantic_receipt_sha256",
    )
    Set(keys(raw)) == Set(required) || _fail(
        "full_qrp_receipt.malformed",
        "Full-QRP receipt fields do not match the accepted schema.",
    )
    raw["schema_version"] == D3_FULL_QRP_QUALIFICATION_SCHEMA &&
        raw["contract_id"] == D3_FULL_QRP_QUALIFICATION_CONTRACT &&
        raw["policy_id"] == D3_FULL_QRP_QUALIFICATION_POLICY_ID &&
        raw["policy_sha256"] == D3_FULL_QRP_QUALIFICATION_POLICY_SHA256 || _fail(
        "full_qrp_receipt.stale",
        "Full-QRP receipt policy or contract is stale.",
    )
    raw["lifecycle_state"] == "ACCEPTED" &&
        raw["data_class"] == "project-internal" &&
        raw["authority_status"] == "diagnostic_only" &&
        raw["promotion_eligible"] === false && raw["final_status"] == "PASS" &&
        isnothing(raw["first_blocker"]) &&
        raw["objective_target_gates_evaluated"] === false || _fail(
        "full_qrp_receipt.authority",
        "Full-QRP receipt authority/status boundary is invalid.",
    )
    declared = _sha(raw["semantic_receipt_sha256"], "Full-QRP semantic receipt")
    core = copy(raw)
    delete!(core, "semantic_receipt_sha256")
    semantic_value_sha256(core) == declared || _fail(
        "full_qrp_receipt.stale",
        "Full-QRP semantic receipt hash changed.",
    )
    candidate_raw = _mapping(raw["candidate"], "Full-QRP candidate")
    candidate = NamedTuple{_CANDIDATE_FIELDS}(Tuple(
        _real(candidate_raw[String(name)], "candidate.$(name)"; positive=true)
        for name in _CANDIDATE_FIELDS
    ))
    semantic_value_sha256(_candidate_dict(candidate)) == raw["candidate_sha256"] ||
        _fail("full_qrp_receipt.candidate_mismatch", "Candidate identity changed.")
    metrics_raw = _mapping(raw["objective_metrics"], "objective metrics")
    metrics = NamedTuple{_METRIC_FIELDS}(Tuple(
        _real(metrics_raw[String(name)], "metrics.$(name)"; nonnegative=true)
        for name in _METRIC_FIELDS
    ))
    all(value -> 0 <= value <= 1, (metrics.eta_r_qrp_on, metrics.eta_p_qrp_on)) &&
        abs(metrics.eta_r_qrp_on + metrics.eta_p_qrp_on - 1) <= 1.0e-9 ||
        _fail("full_qrp_receipt.failed_gate", "Receipt participation is invalid.")
    return (
        candidate=candidate,
        candidate_sha256=raw["candidate_sha256"],
        q2d_artifact_sha256=_sha(raw["q2d_artifact_sha256"], "Q2D artifact"),
        lc_identity=_mapping(raw["lc_qualification_receipt"], "LC identity"),
        model_identity=_mapping(raw["model_identity"], "model identity"),
        objective_metrics=metrics,
        semantic_receipt_sha256=declared,
    )
end

function _read_payload(path)
    bytes = read(path)
    payload = try
        JSON3.read(String(copy(bytes)), Dict{String,Any})
    catch exception
        _fail(
            "full_qrp_receipt.malformed",
            "Full-QRP receipt is not valid JSON.",
            (exception=sprint(showerror, exception),),
        )
    end
    return bytes, payload
end

function load_d3_full_qrp_qualification_receipt(path)
    input_path = abspath(String(path))
    isfile(input_path) || _fail(
        "full_qrp_receipt.missing",
        "Full-QRP receipt does not exist.",
        (path=input_path,),
    )
    bytes, payload = _read_payload(input_path)
    return D3FullQRPQualificationReceipt(
        input_path,
        bytes2hex(SHA.sha256(bytes)),
        _normalize(payload),
    )
end

function write_d3_full_qrp_qualification_receipt(path, evidence)
    destination = abspath(String(path))
    ispath(destination) && _fail(
        "full_qrp_receipt.exists",
        "Full-QRP receipt destination already exists.",
    )
    _normalize(evidence)
    mkpath(dirname(destination))
    temporary, io = mktemp(dirname(destination); cleanup=false)
    try
        JSON3.pretty(io, evidence)
        println(io)
        close(io)
        mv(temporary, destination; force=false)
    catch
        isopen(io) && close(io)
        isfile(temporary) && rm(temporary; force=true)
        rethrow()
    end
    return load_d3_full_qrp_qualification_receipt(destination)
end

function d3_full_qrp_qualification_receipt_identity(receipt::D3FullQRPQualificationReceipt)
    return (
        schema_version=D3_FULL_QRP_QUALIFICATION_SCHEMA,
        contract_id=D3_FULL_QRP_QUALIFICATION_CONTRACT,
        policy_sha256=D3_FULL_QRP_QUALIFICATION_POLICY_SHA256,
        receipt_sha256=receipt.sha256,
        semantic_receipt_sha256=receipt.normalized.semantic_receipt_sha256,
        candidate_sha256=receipt.normalized.candidate_sha256,
        q2d_artifact_sha256=receipt.normalized.q2d_artifact_sha256,
        lc_receipt_sha256=receipt.normalized.lc_identity["receipt_sha256"],
        model_identity=receipt.normalized.model_identity,
    )
end

d3_full_qrp_qualification_receipt_identity(
    authorization::D3AuthorizedStage2FullQRP,
) = d3_full_qrp_qualification_receipt_identity(authorization.receipt)

function _reparse(receipt)
    isfile(receipt.path) || _fail(
        "full_qrp_receipt.missing",
        "Full-QRP receipt disappeared after validation.",
    )
    bytes, payload = _read_payload(receipt.path)
    bytes2hex(SHA.sha256(bytes)) == receipt.sha256 || _fail(
        "full_qrp_receipt.stale",
        "Full-QRP receipt bytes changed after validation.",
    )
    normalized = _normalize(payload)
    normalized == receipt.normalized || _fail(
        "full_qrp_receipt.stale",
        "Full-QRP receipt normalization changed.",
    )
    return normalized
end

function authorize_d3_stage2_full_qrp_receipt(
    receipt::D3FullQRPQualificationReceipt,
    foundation,
    candidate,
    lc_qualification::D3AuthorizedStage2LC;
    q2d_artifact_sha256,
    expected_receipt_sha256=nothing,
)
    normalized = _reparse(receipt)
    !isnothing(expected_receipt_sha256) && receipt.sha256 !=
        validate_d3_full_qrp_qualification_receipt_identity(expected_receipt_sha256) &&
        _fail(
            "full_qrp_receipt.run_spec_mismatch",
            "Full-QRP receipt differs from the expected exact identity.",
        )
    current = produce_d3_full_qrp_qualification_evidence(
        foundation,
        candidate,
        lc_qualification;
        q2d_artifact_sha256=q2d_artifact_sha256,
    )
    current["semantic_receipt_sha256"] == normalized.semantic_receipt_sha256 || _fail(
        "full_qrp_receipt.foundation_mismatch",
        "Full-QRP receipt does not bind the current foundation and LC receipt.",
    )
    values = _candidate(candidate)
    values == normalized.candidate || _fail(
        "full_qrp_receipt.candidate_mismatch",
        "Full-QRP receipt belongs to another candidate.",
    )
    model_identity = _model_identity(
        foundation.cqed_handoff.source_model_identity,
        "foundation model identity",
    )
    return D3AuthorizedStage2FullQRP(
        receipt,
        values,
        lc_qualification,
        model_identity,
    )
end

function authorize_d3_stage2_full_qrp_receipt(
    ::Nothing,
    foundation,
    candidate,
    lc_qualification::D3AuthorizedStage2LC;
    q2d_artifact_sha256,
    expected_receipt_sha256=nothing,
)
    _fail(
        "full_qrp_receipt.missing",
        "Candidate has no Full-QRP cared-output qualification receipt.",
    )
end

function authorize_d3_stage2_full_qrp_receipt(
    authorization::D3AuthorizedStage2FullQRP,
    foundation,
    candidate,
    lc_qualification::D3AuthorizedStage2LC;
    q2d_artifact_sha256,
    expected_receipt_sha256=nothing,
)
    return revalidate_d3_stage2_full_qrp_receipt(
        authorization,
        foundation,
        candidate,
        lc_qualification;
        q2d_artifact_sha256=q2d_artifact_sha256,
        expected_receipt_sha256=expected_receipt_sha256,
    )
end

function revalidate_d3_stage2_full_qrp_receipt(
    authorization::D3AuthorizedStage2FullQRP,
    foundation,
    candidate,
    lc_qualification::D3AuthorizedStage2LC;
    q2d_artifact_sha256,
    expected_receipt_sha256=nothing,
)
    renewed = authorize_d3_stage2_full_qrp_receipt(
        authorization.receipt,
        foundation,
        candidate,
        lc_qualification;
        q2d_artifact_sha256=q2d_artifact_sha256,
        expected_receipt_sha256=expected_receipt_sha256,
    )
    renewed.candidate == authorization.candidate &&
        renewed.model_identity == authorization.model_identity || _fail(
        "full_qrp_receipt.stale",
        "Authorized Full-QRP binding changed during revalidation.",
    )
    return renewed
end

function validate_d3_stage2_full_qrp_authorization_match(
    left::D3AuthorizedStage2FullQRP,
    right::D3AuthorizedStage2FullQRP,
)
    d3_full_qrp_qualification_receipt_identity(left) ==
        d3_full_qrp_qualification_receipt_identity(right) &&
        left.candidate == right.candidate &&
        left.model_identity == right.model_identity || _fail(
            "full_qrp_receipt.foundation_mismatch",
            "Full-QRP authorizations do not bind the same exact evidence.",
        )
    return left
end

function evaluate_d3_stage2_objective_with_evidence(
    authorization::D3AuthorizedStage2FullQRP,
    foundation,
    candidate,
    lc_qualification::D3AuthorizedStage2LC;
    q2d_artifact_sha256,
    objective_evaluator,
)
    renewed = revalidate_d3_stage2_full_qrp_receipt(
        authorization,
        foundation,
        candidate,
        lc_qualification;
        q2d_artifact_sha256=q2d_artifact_sha256,
    )
    return objective_evaluator(foundation, renewed)
end

end
