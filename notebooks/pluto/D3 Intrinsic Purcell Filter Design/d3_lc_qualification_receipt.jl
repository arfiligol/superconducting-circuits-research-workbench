# Strict consumption contract for D3 frequency-priority LC qualification
# receipts.  This module does not produce receipts or define an envelope.

isdefined(@__MODULE__, :D3SemanticHash) ||
    include(joinpath(@__DIR__, "d3_semantic_hash.jl"))

module D3LCQualificationReceipt

using SHA
using SuperconductingCircuitsCore
using ..D3SemanticHash: SEMANTIC_HASH_FRAMING, semantic_value_sha256

const JSON3 = SuperconductingCircuitsCore.JSON3

const D3_LC_QUALIFICATION_SCHEMA = "d3-root-derivative-lc-readback.v1"
const D3_LC_QUALIFICATION_CONTRACT =
    "d3-rev10-frequency-priority-lc-receipt-enforcement.v1"
const D3_ACCEPTED_LC_RECEIPT_SHA256 =
    "f7e5b2381695676acf520543bc79f95a90f8d2394010d15041e22880686a0db5"
const D3_ACCEPTED_LC_EVIDENCE_ID =
    "d3-w7s6-singleton-frequency-priority-lc-readback-v1"
const D3_ACCEPTED_LC_RUNNER_SHA256 =
    "ad55133cd21b9af72806a7ba673bd1260768450b8a24b597177fe156da146627"
const D3_ACCEPTED_SPATIAL_RECEIPT_SHA256 =
    "8917bd26e96c57711e56f8388bdc6e54cb2fc5a150a559e546717e53770d2566"
const D3_ACCEPTED_CONVERGENCE_RUNNER_SHA256 =
    "320b6d2a2919ad6bd8913f5d10b134c8020a65a2f979859f253de102f496f6f4"
const D3_ACCEPTED_EXTRACTOR_SHA256 =
    "e86c0baf1b8af9e7b870ebe69f6cbdb0606148552c017110c57d2dbdad991994"
const D3_ACCEPTED_Q2D_ARTIFACT_SHA256 =
    "301d3501a30614b994cf3f28d46eb75b545620a164bbb346fa557120d643fe6c"

const D3_LC_THRESHOLDS = (
    root_absolute_tolerance_hz=1.25,
    normalized_root_residual=2.0e-3,
    readout_frequency_relative=1.0e-3,
    filter_frequency_relative=1.0e-3,
    notch_frequency_relative=1.0e-2,
    diagonal_derivative_step_relative=1.0e-3,
    notch_derivative_step_relative=5.0e-2,
    diagonal_extraction_relative=1.0e-3,
    notch_extraction_relative=5.0e-2,
)
const _DERIVATIVE_STEP_FRACTION = 1.0e-6
const _REACTIVE_PURITY_RELATIVE = 1.0e-7

const _POLICY_PAYLOAD = Dict(
    "contract_id" => D3_LC_QUALIFICATION_CONTRACT,
    "schema_version" => D3_LC_QUALIFICATION_SCHEMA,
    "semantic_hash_framing" => SEMANTIC_HASH_FRAMING,
    "authority_mode" => "exact_receipt_only",
    "accepted_receipt_sha256" => D3_ACCEPTED_LC_RECEIPT_SHA256,
    "accepted_receipt_candidate_scope" => "exact_historical_lengths_only",
    "accepted_receipt_numeric_u_idc_authority" => false,
    "accepted_envelope" => nothing,
    "thresholds" => Dict(String(name) => value for (name, value) in pairs(D3_LC_THRESHOLDS)),
)
const D3_LC_QUALIFICATION_POLICY_SHA256 =
    semantic_value_sha256(_POLICY_PAYLOAD)

export D3LCQualificationReceipt,
    D3LCReceiptNotEvaluable,
    D3AuthorizedStage2LC,
    D3_ACCEPTED_LC_RECEIPT_SHA256,
    D3_LC_QUALIFICATION_CONTRACT,
    D3_LC_QUALIFICATION_POLICY_SHA256,
    D3_LC_QUALIFICATION_SCHEMA,
    authorize_d3_stage2_lc_receipt,
    d3_lc_qualification_policy,
    d3_lc_qualification_receipt_identity,
    load_d3_lc_qualification_receipt,
    revalidate_d3_stage2_lc_receipt,
    validate_d3_lc_qualification_receipt_identity,
    validate_d3_lc_qualification_policy,
    validate_d3_stage2_lc_authorization_match

struct D3LCReceiptNotEvaluable <: Exception
    code::String
    reason::String
    details
end

function Base.showerror(io::IO, error::D3LCReceiptNotEvaluable)
    print(io, "D3 LC receipt NOT_EVALUABLE [", error.code, "]: ", error.reason)
end

struct D3LCQualificationReceipt{T}
    path::String
    sha256::String
    normalized::T
end

struct D3AuthorizedStage2LC{R,C,L}
    receipt::R
    candidate::C
    lc_readback::L
end

function _not_evaluable(code, reason, details=nothing)
    throw(D3LCReceiptNotEvaluable(String(code), String(reason), details))
end

function _mapping(value, label; exact=nothing)
    value isa AbstractDict || _not_evaluable(
        "lc_receipt.malformed",
        "$(label) must be a mapping.",
    )
    result = Dict{String,Any}(String(key) => item for (key, item) in pairs(value))
    if !isnothing(exact) && Set(keys(result)) != Set(String.(exact))
        _not_evaluable(
            "lc_receipt.malformed",
            "$(label) fields do not match the accepted schema.",
            (expected=sort!(String.(collect(exact))), actual=sort!(collect(keys(result)))),
        )
    end
    return result
end

function _text(value, label)
    value isa AbstractString || _not_evaluable(
        "lc_receipt.malformed",
        "$(label) must be text.",
    )
    result = strip(String(value))
    isempty(result) && _not_evaluable("lc_receipt.malformed", "$(label) must not be empty.")
    return result
end

function _sha256(value, label)
    result = _text(value, label)
    result == lowercase(result) && occursin(r"^[0-9a-f]{64}$", result) || _not_evaluable(
        "lc_receipt.malformed",
        "$(label) must be lowercase SHA-256.",
    )
    return result
end

function _git_revision(value, label)
    result = _text(value, label)
    result == lowercase(result) && occursin(r"^[0-9a-f]{40}$", result) || _not_evaluable(
        "lc_receipt.malformed",
        "$(label) must be a full lowercase Git revision.",
    )
    return result
end

function _real(value, label; positive=false, nonnegative=false)
    value isa Real && !(value isa Bool) || _not_evaluable(
        "lc_receipt.malformed",
        "$(label) must be numeric.",
    )
    result = Float64(value)
    isfinite(result) || _not_evaluable("lc_receipt.malformed", "$(label) must be finite.")
    positive && result <= 0 && _not_evaluable(
        "lc_receipt.malformed",
        "$(label) must be positive.",
    )
    nonnegative && result < 0 && _not_evaluable(
        "lc_receipt.malformed",
        "$(label) must be nonnegative.",
    )
    return result
end

function _all_true(value, label, fields)
    checks = _mapping(value, label; exact=fields)
    for name in fields
        checks[String(name)] === true || _not_evaluable(
            "lc_receipt.failed_gate",
            "$(label).$(name) is not PASS.",
        )
    end
    return true
end

function _relative_delta(reference, operational)
    isfinite(operational) && !iszero(operational) || return Inf
    return abs(reference - operational) / abs(operational)
end

const _ANCHOR_CHECKS = (
    "same_bracket",
    "midpoint_distance_hz",
    "stencil_inside_bracket",
    "finite_samples",
    "derivative_step_convergence",
    "reactive_purity",
    "normalized_root_residual",
)
const _STATE_CHECKS = (
    "identity",
    "anchor_and_derivative",
    "diagonal_poles",
    "physical_pole",
    "physical_formulations",
    "y_r_at_notch_purity",
    "y_p_at_notch_purity",
    "c_n_star_purity",
    "z21_real_residual",
    "z21_imag_residual",
    "z21_abs_residual",
    "positive_finite_lc",
)
const _LC_NAMES = ("Cr_f", "Lr_h", "Cp_f", "Lp_h", "Cn_f", "Ln_h")

function _lc_tuple(value, label)
    raw = _mapping(value, label; exact=_LC_NAMES)
    values = Tuple(_real(raw[name], "$(label).$(name)"; positive=true) for name in _LC_NAMES)
    return NamedTuple{Tuple(Symbol.(collect(_LC_NAMES)))}(values)
end

function _anchor(value, observable, step_tolerance)
    raw = _mapping(
        value,
        "$(observable) anchor";
        exact=(
            "observable",
            "authoritative_midpoint_receipt",
            "construction_anchor_frequency_hz",
            "bracket_hz",
            "h_rad_s",
            "samples",
            "root_value",
            "derivative_h",
            "derivative_h2",
            "derivative_step_relative_change",
            "derivative_step_tolerance",
            "reactive_purity_relative",
            "normalized_root_residual",
            "checks",
            "passed",
            "root_rad_s",
            "derivative",
        ),
    )
    _text(raw["observable"], "$(observable) anchor observable") == observable ||
        _not_evaluable("lc_receipt.mismatched", "$(observable) anchor identity is wrong.")
    raw["passed"] === true || _not_evaluable(
        "lc_receipt.failed_gate",
        "$(observable) anchor is not PASS.",
    )
    _all_true(raw["checks"], "$(observable) anchor checks", _ANCHOR_CHECKS)
    root = _real(
        raw["construction_anchor_frequency_hz"],
        "$(observable) construction root";
        positive=true,
    )
    root_rad_s = _real(raw["root_rad_s"], "$(observable) angular root"; positive=true)
    isapprox(root_rad_s, 2π * root; rtol=8eps(Float64), atol=0.0) || _not_evaluable(
        "lc_receipt.mismatched",
        "$(observable) frequency and angular root disagree.",
    )
    bracket = raw["bracket_hz"] isa AbstractArray || raw["bracket_hz"] isa Tuple ?
        collect(raw["bracket_hz"]) : Any[]
    length(bracket) == 2 || _not_evaluable(
        "lc_receipt.malformed",
        "$(observable) root bracket must contain two frequencies.",
    )
    lower = _real(bracket[1], "$(observable) lower bracket"; positive=true)
    upper = _real(bracket[2], "$(observable) upper bracket"; positive=true)
    lower <= root <= upper || _not_evaluable(
        "lc_receipt.failed_gate",
        "$(observable) construction root lies outside its accepted bracket.",
    )
    h_rad_s = _real(raw["h_rad_s"], "$(observable) derivative step"; positive=true)
    isapprox(
        h_rad_s / root_rad_s,
        _DERIVATIVE_STEP_FRACTION;
        rtol=8eps(Float64),
        atol=0.0,
    ) || _not_evaluable(
        "lc_receipt.mismatched",
        "$(observable) derivative step fraction is not the accepted value.",
    )
    step = _real(
        raw["derivative_step_relative_change"],
        "$(observable) derivative step change";
        nonnegative=true,
    )
    declared_step = _real(
        raw["derivative_step_tolerance"],
        "$(observable) derivative step tolerance";
        nonnegative=true,
    )
    declared_step == step_tolerance && step <= step_tolerance || _not_evaluable(
        "lc_receipt.failed_gate",
        "$(observable) derivative step gate is not the accepted threshold or does not pass.",
    )
    _real(
        raw["reactive_purity_relative"],
        "$(observable) reactive purity";
        nonnegative=true,
    ) <= _REACTIVE_PURITY_RELATIVE || _not_evaluable(
        "lc_receipt.failed_gate",
        "$(observable) reactive purity exceeds the accepted threshold.",
    )
    residual = _real(
        raw["normalized_root_residual"],
        "$(observable) normalized root residual";
        nonnegative=true,
    )
    residual <= D3_LC_THRESHOLDS.normalized_root_residual || _not_evaluable(
        "lc_receipt.failed_gate",
        "$(observable) normalized root residual exceeds the accepted threshold.",
    )
    return (frequency_hz=root, derivative_step_relative_change=step, normalized_root_residual=residual)
end

function _state(value, label)
    raw = _mapping(
        value,
        label;
        exact=(
            "status",
            "state",
            "actual_grid",
            "identity_checks",
            "midpoint_receipts",
            "anchors",
            "pole_certificates",
            "physical_formulation",
            "bridge_inputs",
            "lc_readback",
            "checks",
        ),
    )
    _text(raw["status"], "$(label) status") == "PASS" || _not_evaluable(
        "lc_receipt.failed_status",
        "$(label) is not PASS.",
    )
    _all_true(raw["checks"], "$(label) checks", _STATE_CHECKS)
    anchors = _mapping(raw["anchors"], "$(label) anchors"; exact=("f_r", "f_p", "f_n"))
    normalized_anchors = (
        f_r=_anchor(
            anchors["f_r"],
            "f_r",
            D3_LC_THRESHOLDS.diagonal_derivative_step_relative,
        ),
        f_p=_anchor(
            anchors["f_p"],
            "f_p",
            D3_LC_THRESHOLDS.diagonal_derivative_step_relative,
        ),
        f_n=_anchor(
            anchors["f_n"],
            "f_n",
            D3_LC_THRESHOLDS.notch_derivative_step_relative,
        ),
    )
    return (anchors=normalized_anchors, lc_readback=_lc_tuple(raw["lc_readback"], "$(label) LC readback"))
end

function _comparison(value, operational, reference)
    raw = _mapping(
        value,
        "LC comparison";
        exact=(
            "derivative_and_c_n_star_deltas_fraction",
            "derivative_and_c_n_star_deltas_percent",
            "derivative_and_c_n_star_checks",
            "lc_deltas_fraction",
            "lc_deltas_percent",
            "diagonal_lc_checks",
            "notch_lc_checks",
            "passed",
        ),
    )
    raw["passed"] === true || _not_evaluable(
        "lc_receipt.failed_gate",
        "Operational/reference LC comparison is not PASS.",
    )
    derivative_checks = (
        "dY_r_domega",
        "dY_p_domega",
        "dZ21_domega",
        "Cn_star",
    )
    _all_true(
        raw["derivative_and_c_n_star_checks"],
        "derivative comparison checks",
        derivative_checks,
    )
    _all_true(
        raw["diagonal_lc_checks"],
        "diagonal LC comparison checks",
        ("Cr_f", "Lr_h", "Cp_f", "Lp_h"),
    )
    _all_true(
        raw["notch_lc_checks"],
        "notch LC comparison checks",
        ("Cn_f", "Ln_h"),
    )
    derivative = _mapping(
        raw["derivative_and_c_n_star_deltas_fraction"],
        "derivative comparison deltas";
        exact=derivative_checks,
    )
    for name in ("dY_r_domega", "dY_p_domega")
        _real(derivative[name], name; nonnegative=true) <=
            D3_LC_THRESHOLDS.diagonal_extraction_relative || _not_evaluable(
            "lc_receipt.failed_gate",
            "$(name) exceeds the accepted 0.1% extraction gate.",
        )
    end
    for name in ("dZ21_domega", "Cn_star")
        _real(derivative[name], name; nonnegative=true) <=
            D3_LC_THRESHOLDS.notch_extraction_relative || _not_evaluable(
            "lc_receipt.failed_gate",
            "$(name) exceeds the accepted 5% extraction gate.",
        )
    end
    lc_deltas = _mapping(raw["lc_deltas_fraction"], "LC comparison deltas"; exact=_LC_NAMES)
    for name in ("Cr_f", "Lr_h", "Cp_f", "Lp_h")
        _real(lc_deltas[name], name; nonnegative=true) <=
            D3_LC_THRESHOLDS.diagonal_extraction_relative || _not_evaluable(
            "lc_receipt.failed_gate",
            "$(name) exceeds the accepted 0.1% extraction gate.",
        )
    end
    for name in ("Cn_f", "Ln_h")
        _real(lc_deltas[name], name; nonnegative=true) <=
            D3_LC_THRESHOLDS.notch_extraction_relative || _not_evaluable(
            "lc_receipt.failed_gate",
            "$(name) exceeds the accepted 5% extraction gate.",
        )
    end
    frequency_deltas = (
        f_r=_relative_delta(reference.anchors.f_r.frequency_hz, operational.anchors.f_r.frequency_hz),
        f_p=_relative_delta(reference.anchors.f_p.frequency_hz, operational.anchors.f_p.frequency_hz),
        f_n=_relative_delta(reference.anchors.f_n.frequency_hz, operational.anchors.f_n.frequency_hz),
    )
    frequency_deltas.f_r <= D3_LC_THRESHOLDS.readout_frequency_relative &&
        frequency_deltas.f_p <= D3_LC_THRESHOLDS.filter_frequency_relative &&
        frequency_deltas.f_n <= D3_LC_THRESHOLDS.notch_frequency_relative ||
        _not_evaluable(
            "lc_receipt.failed_gate",
            "Operational/reference frequency stability exceeds the accepted gates.",
            frequency_deltas,
        )
    return frequency_deltas
end

function _candidate(value)
    raw = _mapping(value, "LC receipt candidate"; exact=("id", "lengths", "u_idc"))
    lengths_raw = _mapping(
        raw["lengths"],
        "LC receipt candidate lengths";
        exact=("lr_open_m", "lr_short_m", "lc_m", "lp_open_m", "lp_short_m"),
    )
    lengths = (
        lr_open_m=_real(lengths_raw["lr_open_m"], "lr_open_m"; positive=true),
        lr_short_m=_real(lengths_raw["lr_short_m"], "lr_short_m"; positive=true),
        lc_m=_real(lengths_raw["lc_m"], "lc_m"; positive=true),
        lp_open_m=_real(lengths_raw["lp_open_m"], "lp_open_m"; positive=true),
        lp_short_m=_real(lengths_raw["lp_short_m"], "lp_short_m"; positive=true),
    )
    u_idc = raw["u_idc"] isa Real && !(raw["u_idc"] isa Bool) ?
        _real(raw["u_idc"], "LC receipt u_IDC"; positive=true) :
        _text(raw["u_idc"], "LC receipt u_IDC")
    return (id=_text(raw["id"], "LC receipt candidate id"), lengths=lengths, u_IDC=u_idc)
end

function _normalize_receipt(payload, receipt_sha256)
    raw = _mapping(
        payload,
        "D3 LC receipt";
        exact=(
            "schema_version",
            "evidence_id",
            "generated_at_utc",
            "lifecycle_state",
            "data_class",
            "authority_status",
            "promotion_eligible",
            "final_status",
            "first_blocker",
            "source",
            "contract",
            "candidate",
            "operational",
            "retained_reference",
            "comparison",
            "operational_lc_tuple",
            "nonclaims",
        ),
    )
    receipt_sha256 == D3_ACCEPTED_LC_RECEIPT_SHA256 || _not_evaluable(
        "lc_receipt.unaccepted_authority",
        "No exact D3 LC receipt authority accepts these bytes.",
        (receipt_sha256=receipt_sha256, accepted_receipt_sha256=D3_ACCEPTED_LC_RECEIPT_SHA256),
    )
    _text(raw["schema_version"], "LC receipt schema") == D3_LC_QUALIFICATION_SCHEMA ||
        _not_evaluable("lc_receipt.mismatched", "LC receipt schema is unsupported.")
    _text(raw["evidence_id"], "LC evidence id") == D3_ACCEPTED_LC_EVIDENCE_ID ||
        _not_evaluable("lc_receipt.mismatched", "LC evidence identity is unsupported.")
    _text(raw["generated_at_utc"], "LC generation timestamp")
    _text(raw["lifecycle_state"], "LC lifecycle state") == "ACCEPTED" ||
        _not_evaluable("lc_receipt.stale", "LC receipt does not carry the accepted lifecycle state.")
    _text(raw["data_class"], "LC data class") == "project-internal" ||
        _not_evaluable("lc_receipt.mismatched", "LC receipt data class is unsupported.")
    _text(raw["authority_status"], "LC authority status") == "diagnostic_only" ||
        _not_evaluable("lc_receipt.mismatched", "LC receipt authority status is unsupported.")
    raw["promotion_eligible"] === false || _not_evaluable(
        "lc_receipt.mismatched",
        "The accepted singleton receipt is not promotion eligible.",
    )
    _text(raw["final_status"], "LC final status") == "PASS" ||
        _not_evaluable("lc_receipt.failed_status", "LC receipt is not PASS.")
    isnothing(raw["first_blocker"]) || _not_evaluable(
        "lc_receipt.failed_status",
        "LC receipt retains a blocker.",
    )

    source = _mapping(
        raw["source"],
        "LC receipt source";
        exact=(
            "root_revision",
            "workbench_revision",
            "runner_sha256",
            "spatial_receipt_sha256",
            "convergence_runner_sha256",
            "extractor_sha256",
            "q2d_artifact_sha256",
            "q2d_payload_sha256",
            "orpen_producer_revision",
        ),
    )
    for (name, expected) in (
        ("runner_sha256", D3_ACCEPTED_LC_RUNNER_SHA256),
        ("spatial_receipt_sha256", D3_ACCEPTED_SPATIAL_RECEIPT_SHA256),
        ("convergence_runner_sha256", D3_ACCEPTED_CONVERGENCE_RUNNER_SHA256),
        ("extractor_sha256", D3_ACCEPTED_EXTRACTOR_SHA256),
        ("q2d_artifact_sha256", D3_ACCEPTED_Q2D_ARTIFACT_SHA256),
    )
        _sha256(source[name], "LC source $(name)") == expected || _not_evaluable(
            "lc_receipt.stale",
            "LC receipt source $(name) is stale or mismatched.",
        )
    end
    for name in ("root_revision", "workbench_revision", "orpen_producer_revision")
        _git_revision(source[name], "LC source $(name)")
    end
    _sha256(source["q2d_payload_sha256"], "LC source q2d_payload_sha256")

    contract = _mapping(
        raw["contract"],
        "LC receipt contract";
        exact=(
            "authoritative_frequency_observable",
            "construction_anchor",
            "derivative_step_fraction",
            "diagonal_derivative_step_tolerance",
            "notch_derivative_step_tolerance",
            "reactive_purity_tolerance",
            "root_residual_tolerance",
            "diagonal_extraction_stability_tolerance",
            "notch_extraction_stability_tolerance",
            "c_n_l_n_extraction_stability_tolerance",
            "terminal_order",
            "time_convention",
            "loss_model",
        ),
    )
    _text(contract["construction_anchor"], "LC construction anchor") ==
        "same-bracket 1.25-Hz bisection root" || _not_evaluable(
        "lc_receipt.mismatched",
        "LC construction root contract is not the accepted 1.25-Hz contract.",
    )
    _text(
        contract["authoritative_frequency_observable"],
        "LC authoritative frequency observable",
    ) == "accepted 0.25-MHz signed-bracket midpoint" || _not_evaluable(
        "lc_receipt.mismatched",
        "LC authoritative frequency observable is not the accepted midpoint contract.",
    )
    _real(
        contract["derivative_step_fraction"],
        "LC derivative step fraction";
        positive=true,
    ) == _DERIVATIVE_STEP_FRACTION || _not_evaluable(
        "lc_receipt.mismatched",
        "LC derivative step fraction is not the accepted value.",
    )
    _real(
        contract["reactive_purity_tolerance"],
        "LC reactive purity tolerance";
        nonnegative=true,
    ) == _REACTIVE_PURITY_RELATIVE || _not_evaluable(
        "lc_receipt.mismatched",
        "LC reactive purity tolerance is not the accepted threshold.",
    )
    for (name, expected) in (
        ("diagonal_derivative_step_tolerance", D3_LC_THRESHOLDS.diagonal_derivative_step_relative),
        ("notch_derivative_step_tolerance", D3_LC_THRESHOLDS.notch_derivative_step_relative),
        ("root_residual_tolerance", D3_LC_THRESHOLDS.normalized_root_residual),
        ("diagonal_extraction_stability_tolerance", D3_LC_THRESHOLDS.diagonal_extraction_relative),
        ("notch_extraction_stability_tolerance", D3_LC_THRESHOLDS.notch_extraction_relative),
        ("c_n_l_n_extraction_stability_tolerance", D3_LC_THRESHOLDS.notch_extraction_relative),
    )
        _real(contract[name], "LC contract $(name)"; nonnegative=true) == expected ||
            _not_evaluable(
                "lc_receipt.mismatched",
                "LC contract $(name) is not the accepted threshold.",
            )
    end
    terminal_order = contract["terminal_order"] isa AbstractArray ||
        contract["terminal_order"] isa Tuple ? collect(contract["terminal_order"]) : Any[]
    String.(terminal_order) == ["P_r", "P_p"] || _not_evaluable(
        "lc_receipt.mismatched",
        "LC terminal order is not the accepted (P_r, P_p) order.",
    )
    _text(contract["time_convention"], "LC time convention") == "exp(-i*omega*t)" ||
        _not_evaluable("lc_receipt.mismatched", "LC time convention is unsupported.")
    _text(contract["loss_model"], "LC loss model") ==
        "R'=G'=0 downstream lossless-circuit assumption" || _not_evaluable(
        "lc_receipt.mismatched",
        "LC loss model is unsupported.",
    )

    operational = _state(raw["operational"], "operational LC qualification")
    reference = _state(raw["retained_reference"], "retained-reference LC qualification")
    frequency_deltas = _comparison(raw["comparison"], operational, reference)
    lc = _lc_tuple(raw["operational_lc_tuple"], "operational LC tuple")
    lc == operational.lc_readback || _not_evaluable(
        "lc_receipt.mismatched",
        "Published operational LC tuple disagrees with its qualified state.",
    )
    nonclaims = raw["nonclaims"] isa AbstractArray || raw["nonclaims"] isa Tuple ?
        String.(collect(raw["nonclaims"])) : String[]
    nonclaims == [
        "not a replacement for the accepted midpoint frequency observables",
        "not Equivalent-arm or Experiment-A comparison evidence",
        "not optimizer or Full-QRP grid eligibility",
        "not Stage-2/Stage-3 closure",
        "not a Rev10 slot result",
        "not promotion or publication evidence",
    ] || _not_evaluable(
        "lc_receipt.mismatched",
        "LC receipt nonclaims do not equal the accepted singleton boundary.",
    )
    candidate = _candidate(raw["candidate"])
    return (
        schema_version=D3_LC_QUALIFICATION_SCHEMA,
        evidence_id=D3_ACCEPTED_LC_EVIDENCE_ID,
        candidate=candidate,
        source=(
            runner_sha256=D3_ACCEPTED_LC_RUNNER_SHA256,
            spatial_receipt_sha256=D3_ACCEPTED_SPATIAL_RECEIPT_SHA256,
            convergence_runner_sha256=D3_ACCEPTED_CONVERGENCE_RUNNER_SHA256,
            extractor_sha256=D3_ACCEPTED_EXTRACTOR_SHA256,
            q2d_artifact_sha256=D3_ACCEPTED_Q2D_ARTIFACT_SHA256,
        ),
        frequency_deltas=frequency_deltas,
        lc_readback=lc,
    )
end

function _policy_copy(value)
    value isa AbstractDict && return Dict(
        String(key) => _policy_copy(item) for (key, item) in pairs(value)
    )
    value isa AbstractArray && return [_policy_copy(item) for item in value]
    return value
end

function d3_lc_qualification_policy()
    return merge(_policy_copy(_POLICY_PAYLOAD), Dict(
        "policy_sha256" => D3_LC_QUALIFICATION_POLICY_SHA256,
    ))
end

function validate_d3_lc_qualification_policy(value)
    policy = _mapping(value, "D3 LC qualification policy")
    policy == d3_lc_qualification_policy() || _not_evaluable(
        "lc_receipt.stale",
        "D3 LC qualification policy does not equal the accepted exact-receipt policy.",
    )
    return d3_lc_qualification_policy()
end

function validate_d3_lc_qualification_receipt_identity(value)
    isnothing(value) && _not_evaluable(
        "lc_receipt.missing",
        "Stage-2 RunSpec has no LC qualification receipt identity.",
    )
    identity = _sha256(value, "D3 LC qualification receipt identity")
    identity == D3_ACCEPTED_LC_RECEIPT_SHA256 || _not_evaluable(
        "lc_receipt.unaccepted_authority",
        "Stage-2 RunSpec names an unaccepted LC receipt authority.",
        (receipt_sha256=identity, accepted_receipt_sha256=D3_ACCEPTED_LC_RECEIPT_SHA256),
    )
    return identity
end

function d3_lc_qualification_receipt_identity(receipt::D3LCQualificationReceipt)
    return (
        schema_version=receipt.normalized.schema_version,
        evidence_id=receipt.normalized.evidence_id,
        receipt_sha256=receipt.sha256,
        contract_id=D3_LC_QUALIFICATION_CONTRACT,
        policy_sha256=D3_LC_QUALIFICATION_POLICY_SHA256,
        candidate_id=receipt.normalized.candidate.id,
        candidate=receipt.normalized.candidate,
        source=receipt.normalized.source,
        frequency_deltas=receipt.normalized.frequency_deltas,
    )
end

d3_lc_qualification_receipt_identity(authorization::D3AuthorizedStage2LC) =
    d3_lc_qualification_receipt_identity(authorization.receipt)

function load_d3_lc_qualification_receipt(path)
    input_path = abspath(String(path))
    isfile(input_path) || _not_evaluable(
        "lc_receipt.missing",
        "D3 LC qualification receipt does not exist.",
        (path=input_path,),
    )
    bytes = read(input_path)
    receipt_sha256 = bytes2hex(SHA.sha256(bytes))
    receipt_sha256 == D3_ACCEPTED_LC_RECEIPT_SHA256 || _not_evaluable(
        "lc_receipt.unaccepted_authority",
        "D3 LC qualification receipt bytes are not the accepted exact authority.",
        (receipt_sha256=receipt_sha256, accepted_receipt_sha256=D3_ACCEPTED_LC_RECEIPT_SHA256),
    )
    payload = try
        JSON3.read(String(copy(bytes)), Dict{String,Any})
    catch exception
        _not_evaluable(
            "lc_receipt.malformed",
            "D3 LC qualification receipt is not valid JSON.",
            (exception=string(exception),),
        )
    end
    return D3LCQualificationReceipt(
        input_path,
        receipt_sha256,
        _normalize_receipt(payload, receipt_sha256),
    )
end

function _validate_receipt_authority(receipt::D3LCQualificationReceipt)
    validate_d3_lc_qualification_receipt_identity(receipt.sha256)
    isfile(receipt.path) || _not_evaluable(
        "lc_receipt.missing",
        "D3 LC qualification receipt disappeared before authorization.",
    )
    bytes = read(receipt.path)
    bytes2hex(SHA.sha256(bytes)) == receipt.sha256 || _not_evaluable(
        "lc_receipt.stale",
        "D3 LC qualification receipt bytes changed after validation.",
    )
    payload = try
        JSON3.read(String(copy(bytes)), Dict{String,Any})
    catch exception
        _not_evaluable(
            "lc_receipt.malformed",
            "D3 LC qualification receipt is not valid JSON.",
            (exception=string(exception),),
        )
    end
    _normalize_receipt(payload, receipt.sha256) == receipt.normalized || _not_evaluable(
        "lc_receipt.stale",
        "In-memory LC receipt normalization disagrees with the authorized bytes.",
    )
    return receipt
end

function _candidate_values(candidate)
    names = (:lr_open_m, :lr_short_m, :lc_m, :lp_open_m, :lp_short_m, :u_IDC)
    Set(propertynames(candidate)) == Set(names) || _not_evaluable(
        "lc_receipt.candidate_mismatch",
        "Stage-2 candidate fields do not match the physical Rev10 coordinates.",
    )
    return NamedTuple{names}(Tuple(
        _real(getproperty(candidate, name), "Stage-2 candidate $(name)"; positive=true)
        for name in names
    ))
end

function authorize_d3_stage2_lc_receipt(
    receipt::D3LCQualificationReceipt,
    candidate;
    q2d_artifact_sha256,
    expected_receipt_sha256=nothing,
)
    _validate_receipt_authority(receipt)
    if !isnothing(expected_receipt_sha256)
        expected_identity = validate_d3_lc_qualification_receipt_identity(
            expected_receipt_sha256,
        )
        receipt.sha256 == expected_identity || _not_evaluable(
            "lc_receipt.run_spec_mismatch",
            "LC receipt disagrees with the Stage-2 RunSpec receipt identity.",
        )
    end
    _sha256(q2d_artifact_sha256, "Stage-2 Q2D artifact SHA-256") ==
        receipt.normalized.source.q2d_artifact_sha256 || _not_evaluable(
        "lc_receipt.q2d_mismatch",
        "LC receipt belongs to a different Q2D artifact.",
    )
    values = _candidate_values(candidate)
    expected = receipt.normalized.candidate
    expected.lengths == NamedTuple{propertynames(expected.lengths)}(Tuple(
        getproperty(values, name) for name in propertynames(expected.lengths)
    )) || _not_evaluable(
        "lc_receipt.candidate_mismatch",
        "LC receipt belongs to different physical lengths.",
    )
    expected.u_IDC isa Real || _not_evaluable(
        "lc_receipt.u_idc_unbound",
        "The accepted singleton receipt does not bind numeric u_IDC and cannot authorize a Rev10 candidate.",
        (receipt_u_IDC=expected.u_IDC, candidate_u_IDC=values.u_IDC),
    )
    Float64(expected.u_IDC) == values.u_IDC || _not_evaluable(
        "lc_receipt.candidate_mismatch",
        "LC receipt belongs to a different u_IDC coordinate.",
    )
    return D3AuthorizedStage2LC(receipt, values, receipt.normalized.lc_readback)
end

function authorize_d3_stage2_lc_receipt(
    ::Nothing,
    candidate;
    q2d_artifact_sha256,
    expected_receipt_sha256=nothing,
)
    _not_evaluable(
        "lc_receipt.missing",
        "Stage-2 candidate has no LC qualification receipt.",
    )
end

function authorize_d3_stage2_lc_receipt(
    authorization::D3AuthorizedStage2LC,
    candidate;
    q2d_artifact_sha256,
    expected_receipt_sha256=nothing,
)
    return revalidate_d3_stage2_lc_receipt(
        authorization,
        candidate;
        q2d_artifact_sha256=q2d_artifact_sha256,
        expected_receipt_sha256=expected_receipt_sha256,
    )
end

function revalidate_d3_stage2_lc_receipt(
    authorization::D3AuthorizedStage2LC,
    candidate;
    q2d_artifact_sha256,
    expected_receipt_sha256=nothing,
)
    renewed = authorize_d3_stage2_lc_receipt(
        authorization.receipt,
        candidate;
        q2d_artifact_sha256=q2d_artifact_sha256,
        expected_receipt_sha256=expected_receipt_sha256,
    )
    renewed.lc_readback == authorization.lc_readback || _not_evaluable(
        "lc_receipt.stale",
        "Authorized LC tuple changed after validation.",
    )
    return renewed
end

function validate_d3_stage2_lc_authorization_match(
    left::D3AuthorizedStage2LC,
    right::D3AuthorizedStage2LC,
)
    d3_lc_qualification_receipt_identity(left) ==
        d3_lc_qualification_receipt_identity(right) &&
        left.candidate == right.candidate &&
        left.lc_readback == right.lc_readback || _not_evaluable(
        "lc_receipt.foundation_mismatch",
        "Stage-2 foundation LC binding disagrees with the winner authority.",
    )
    return left
end

end
