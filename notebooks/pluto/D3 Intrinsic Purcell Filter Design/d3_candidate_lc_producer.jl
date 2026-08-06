# Reusable D3 Rev10 exact-candidate local spatial/LC qualification controller.
# Circuit construction and extraction stay caller-owned; this module owns the
# accepted deterministic scheduling, exact cache identity, gates, and evidence
# contract consumed by the strict receipt validator.

isdefined(@__MODULE__, :D3SemanticHash) ||
    include(joinpath(@__DIR__, "d3_semantic_hash.jl"))

module D3CandidateLCProducer

using Dates
using ..D3SemanticHash: SEMANTIC_HASH_FRAMING, semantic_value_sha256

const D3_CANDIDATE_LC_SCHEMA = "d3-root-derivative-lc-readback.v2"
const D3_CANDIDATE_LC_CONTRACT =
    "d3-rev10-exact-per-candidate-frequency-priority-lc.v1"
const D3_CANDIDATE_LC_POLICY_ID =
    "d3-rev10-frequency-priority-lc-producer-policy.v1"
const D3_REQUIRED_Q2D_ARTIFACT_SHA256 =
    "301d3501a30614b994cf3f28d46eb75b545620a164bbb346fa557120d643fe6c"
const D3_REQUIRED_ORPEN_REVISION =
    "80576910d596dbf4720335188e66b6a520cc2e36"
const D3_LC_NAMES = (:Cr_f, :Lr_h, :Cp_f, :Lp_h, :Cn_f, :Ln_h)
const D3_LENGTH_NAMES =
    (:lr_open_m, :lr_short_m, :lc_m, :lp_open_m, :lp_short_m)
const D3_STATE_CHECKS = (
    :finite_values,
    :root_existence,
    :unique_signed_branches,
    :pole_exclusion,
    :matrix_passivity_positive_energy,
    :breakpoint_basis_terminal_identity,
    :schur_full_node_formulation,
)
const D3_LC_CHECKS = (
    :identity,
    :anchor_and_derivative,
    :diagonal_poles,
    :physical_pole,
    :physical_formulations,
    :y_r_at_notch_purity,
    :y_p_at_notch_purity,
    :c_n_star_purity,
    :z21_real_residual,
    :z21_imag_residual,
    :z21_abs_residual,
    :positive_finite_lc,
    :no_free_fit,
)

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

const _POLICY_PAYLOAD = Dict(
    "policy_id" => D3_CANDIDATE_LC_POLICY_ID,
    "schema_version" => D3_CANDIDATE_LC_SCHEMA,
    "contract_id" => D3_CANDIDATE_LC_CONTRACT,
    "semantic_hash_framing" => SEMANTIC_HASH_FRAMING,
    "authority_mode" => "exact_candidate_receipt_only",
    "accepted_envelope" => nothing,
    "q2d_artifact_sha256" => D3_REQUIRED_Q2D_ARTIFACT_SHA256,
    "orpen_revision" => D3_REQUIRED_ORPEN_REVISION,
    "frequency_grid_hz" => Dict(
        "minimum" => 3.5e9,
        "maximum" => 7.0e9,
        "step" => 0.25e6,
    ),
    "initial_maximum_section_m" => Dict("cpw" => 50.0e-6, "mtl" => 10.0e-6),
    "controller" => Dict(
        "order" => ["mtl", "cpw", "mtl_recheck", "joint"],
        "maximum_level_index" => 10,
        "required_consecutive_passes" => 2,
        "maximum_rounds" => 3,
        "maximum_state_requests" => 102,
        "binary_search" => false,
    ),
    "thresholds" => Dict(String(name) => value for (name, value) in pairs(D3_LC_THRESHOLDS)),
)
const D3_CANDIDATE_LC_POLICY_SHA256 = semantic_value_sha256(_POLICY_PAYLOAD)

export D3CandidateLCNotEvaluable,
    D3_CANDIDATE_LC_CONTRACT,
    D3_CANDIDATE_LC_POLICY_ID,
    D3_CANDIDATE_LC_POLICY_SHA256,
    D3_CANDIDATE_LC_SCHEMA,
    D3_LC_THRESHOLDS,
    d3_candidate_lc_policy,
    d3_candidate_wrapper_identity,
    d3_local_lc_physics_identity,
    produce_d3_candidate_lc_evidence,
    validate_d3_candidate_lc_evidence

struct D3CandidateLCNotEvaluable <: Exception
    code::String
    reason::String
    details
end

Base.showerror(io::IO, exception::D3CandidateLCNotEvaluable) = print(
    io,
    "D3 candidate LC NOT_EVALUABLE [",
    exception.code,
    "]: ",
    exception.reason,
)

_fail(code, reason, details=nothing) =
    throw(D3CandidateLCNotEvaluable(String(code), String(reason), details))

function _real(value, label; positive=false, nonnegative=false)
    value isa Real && !(value isa Bool) ||
        _fail("lc_producer.malformed", "$(label) must be numeric.")
    parsed = Float64(value)
    isfinite(parsed) || _fail("lc_producer.malformed", "$(label) must be finite.")
    positive && parsed <= 0 &&
        _fail("lc_producer.malformed", "$(label) must be positive.")
    nonnegative && parsed < 0 &&
        _fail("lc_producer.malformed", "$(label) must be nonnegative.")
    return parsed
end

function _sha(value, label; git=false)
    value isa AbstractString ||
        _fail("lc_producer.malformed", "$(label) must be text.")
    parsed = strip(String(value))
    pattern = git ? r"^[0-9a-f]{40}$" : r"^[0-9a-f]{64}$"
    occursin(pattern, parsed) ||
        _fail("lc_producer.malformed", "$(label) has the wrong hash format.")
    return parsed
end

function _candidate(candidate)
    names = (D3_LENGTH_NAMES..., :u_IDC)
    Set(propertynames(candidate)) == Set(names) || _fail(
        "lc_producer.candidate_mismatch",
        "Candidate must contain exactly the five lengths and numeric u_IDC.",
    )
    values = NamedTuple{names}(Tuple(
        _real(getproperty(candidate, name), "candidate.$(name)"; positive=true)
        for name in names
    ))
    return values
end

function _source(source)
    source isa AbstractDict ||
        _fail("lc_producer.malformed", "LC source identity must be a mapping.")
    normalized = Dict{String,Any}(String(key) => value for (key, value) in pairs(source))
    required = (
        "workbench_revision",
        "orpen_revision",
        "q2d_artifact_sha256",
        "q2d_payload_sha256",
        "q2d_result_sha256",
        "material_profile_id",
        "material_profile_sha256",
        "material_authority_sha256",
        "extractor_sha256",
        "discretizer_sha256",
        "state_evaluator_sha256",
    )
    Set(keys(normalized)) == Set(required) || _fail(
        "lc_producer.source_mismatch",
        "LC source identity fields do not match the accepted contract.",
    )
    _sha(normalized["workbench_revision"], "workbench revision"; git=true)
    _sha(normalized["orpen_revision"], "OrPen revision"; git=true) ==
        D3_REQUIRED_ORPEN_REVISION ||
        _fail("lc_producer.source_mismatch", "LC source uses the wrong OrPen revision.")
    _sha(normalized["q2d_artifact_sha256"], "Q2D artifact") ==
        D3_REQUIRED_Q2D_ARTIFACT_SHA256 ||
        _fail("lc_producer.source_mismatch", "LC source uses the wrong W7/S6 artifact.")
    for name in (
        "q2d_payload_sha256",
        "q2d_result_sha256",
        "material_profile_sha256",
        "material_authority_sha256",
        "extractor_sha256",
        "discretizer_sha256",
        "state_evaluator_sha256",
    )
        _sha(normalized[name], name)
    end
    normalized["material_profile_id"] isa AbstractString &&
        !isempty(strip(String(normalized["material_profile_id"]))) ||
        _fail("lc_producer.source_mismatch", "Material profile id is missing.")
    return normalized
end

_semantic(value) = semantic_value_sha256(value)

function _candidate_dict(candidate)
    return Dict(
        "lr_open_m" => candidate.lr_open_m,
        "lr_short_m" => candidate.lr_short_m,
        "lc_m" => candidate.lc_m,
        "lp_open_m" => candidate.lp_open_m,
        "lp_short_m" => candidate.lp_short_m,
        "u_IDC" => candidate.u_IDC,
    )
end

function d3_candidate_wrapper_identity(candidate)
    values = _candidate(candidate)
    payload = Dict(
        "contract_id" => D3_CANDIDATE_LC_CONTRACT,
        "candidate" => _candidate_dict(values),
    )
    return (candidate=values, sha256=_semantic(payload))
end

function d3_local_lc_physics_identity(candidate, source)
    values = _candidate(candidate)
    normalized_source = _source(source)
    payload = Dict(
        "policy_sha256" => D3_CANDIDATE_LC_POLICY_SHA256,
        "lengths" => Dict(String(name) => getproperty(values, name) for name in D3_LENGTH_NAMES),
        "source" => normalized_source,
        "u_idc_electrically_consumed" => false,
    )
    return (candidate=values, source=normalized_source, sha256=_semantic(payload))
end

function d3_candidate_lc_policy()
    value = deepcopy(_POLICY_PAYLOAD)
    value["policy_sha256"] = D3_CANDIDATE_LC_POLICY_SHA256
    return value
end

_ceil_count(length_m, maximum_section_m) = ceil(Int, length_m / maximum_section_m)

function _state(outer_counts, mtl_count, origin)
    outer = (
        r_short=Int(outer_counts.r_short),
        r_open=Int(outer_counts.r_open),
        p_short=Int(outer_counts.p_short),
        p_open=Int(outer_counts.p_open),
    )
    all(>(0), values(outer)) && Int(mtl_count) > 0 ||
        _fail("lc_producer.grid", "Every exact grid count must be positive.")
    payload = Dict(
        "outer_counts" => Dict(String(name) => getproperty(outer, name) for name in propertynames(outer)),
        "mtl_count" => Int(mtl_count),
    )
    return (
        id="grid-" * _semantic(payload),
        outer_counts=outer,
        mtl_count=Int(mtl_count),
        origin=String(origin),
    )
end

_double_outer(outer, level) = NamedTuple{propertynames(outer)}(
    Tuple(getproperty(outer, name) * (1 << level) for name in propertynames(outer)),
)

function _checks(value, required, label)
    names = propertynames(value)
    Set(names) == Set(required) ||
        _fail("lc_producer.malformed", "$(label) checks do not match the accepted registry.")
    all(getproperty(value, name) === true for name in required) ||
        _fail("lc_producer.failed_gate", "$(label) contains a failed validity gate.")
    return value
end

function _state_result(raw, state)
    hasproperty(raw, :status) && String(raw.status) in ("PASS", "COMPLETE") ||
        _fail("lc_producer.state_not_evaluable", "Grid state is not complete PASS.", state)
    hasproperty(raw, :values_hz) ||
        _fail("lc_producer.malformed", "Grid state omits cared frequencies.")
    frequencies = (
        f_r=_real(raw.values_hz.f_r, "state f_r"; positive=true),
        f_p=_real(raw.values_hz.f_p, "state f_p"; positive=true),
        f_n=_real(raw.values_hz.f_n, "state f_n"; positive=true),
    )
    hasproperty(raw, :checks) ||
        _fail("lc_producer.malformed", "Grid state omits validity checks.")
    _checks(raw.checks, D3_STATE_CHECKS, "Grid state")
    evidence = hasproperty(raw, :evidence) ? raw.evidence : nothing
    return (state=state, values_hz=frequencies, checks=raw.checks, evidence=evidence)
end

function _frequency_comparison(operational, reference, phase)
    changes = NamedTuple{(:f_r, :f_p, :f_n)}(Tuple(
        begin
            coarse = getproperty(operational.values_hz, name)
            fine = getproperty(reference.values_hz, name)
            delta = abs(fine - coarse) / abs(coarse)
            threshold = name == :f_r ? D3_LC_THRESHOLDS.readout_frequency_relative :
                name == :f_p ? D3_LC_THRESHOLDS.filter_frequency_relative :
                D3_LC_THRESHOLDS.notch_frequency_relative
            (operational_hz=coarse, reference_hz=fine, delta_fraction=delta,
                threshold_fraction=threshold, passed=delta <= threshold)
        end
        for name in (:f_r, :f_p, :f_n)
    ))
    return (
        phase=String(phase),
        operational_state_id=operational.state.id,
        reference_state_id=reference.state.id,
        changes=changes,
        passed=all(value.passed for value in values(changes)),
    )
end

mutable struct _Controller
    requests::Int
    solves::Int
    cache_hits::Int
    cache::Dict{String,Any}
    state_evaluator
    candidate
    physics_sha256::String
end

function _request!(controller::_Controller, state)
    controller.requests += 1
    controller.requests <= 102 || _fail(
        "lc_producer.request_cap",
        "LC controller exceeded the accepted 102-request ceiling.",
    )
    key = _semantic(Dict(
        "physics_sha256" => controller.physics_sha256,
        "outer_counts" => Dict(String(name) => getproperty(state.outer_counts, name)
            for name in propertynames(state.outer_counts)),
        "mtl_count" => state.mtl_count,
    ))
    if haskey(controller.cache, key)
        controller.cache_hits += 1
        return controller.cache[key]
    end
    raw = try
        controller.state_evaluator(controller.candidate, state)
    catch exception
        exception isa InterruptException && rethrow()
        _fail(
            "lc_producer.state_evaluator",
            "Exact local state evaluation failed.",
            (state=state, exception=sprint(showerror, exception)),
        )
    end
    result = _state_result(raw, state)
    controller.solves += 1
    controller.cache[key] = result
    return result
end

function _discover!(controller, state_at_level, phase)
    records = Any[]
    transitions = Any[]
    streak = 0
    for level in 0:10
        record = _request!(controller, state_at_level(level))
        push!(records, record)
        length(records) == 1 && continue
        comparison = _frequency_comparison(records[end - 1], records[end], phase)
        push!(transitions, comparison)
        streak = comparison.passed ? streak + 1 : 0
        if streak == 2
            return (
                operational=records[end - 1],
                reference=records[end],
                records=records,
                transitions=transitions,
            )
        end
    end
    _fail(
        "lc_producer.level_cap",
        "$(phase) reached level 10 without two consecutive PASS transitions.",
    )
end

function _lc_result(raw, label)
    hasproperty(raw, :status) && String(raw.status) == "PASS" ||
        _fail("lc_producer.lc_not_evaluable", "$(label) LC qualification is not PASS.")
    hasproperty(raw, :checks) || _fail("lc_producer.malformed", "$(label) omits LC checks.")
    _checks(raw.checks, D3_LC_CHECKS, "$(label) LC")
    roots = NamedTuple{(:f_r, :f_p, :f_n)}(Tuple(
        begin
            item = getproperty(raw.roots, name)
            step_limit = name == :f_n ?
                D3_LC_THRESHOLDS.notch_derivative_step_relative :
                D3_LC_THRESHOLDS.diagonal_derivative_step_relative
            root_error = _real(item.absolute_error_hz, "$(label) $(name) root error"; nonnegative=true)
            residual = _real(item.normalized_residual, "$(label) $(name) residual"; nonnegative=true)
            step = _real(item.derivative_step_relative_change, "$(label) $(name) derivative step"; nonnegative=true)
            root_error <= D3_LC_THRESHOLDS.root_absolute_tolerance_hz &&
                residual <= D3_LC_THRESHOLDS.normalized_root_residual && step <= step_limit ||
                _fail("lc_producer.failed_gate", "$(label) $(name) root/derivative gate failed.")
            (frequency_hz=_real(item.frequency_hz, "$(label) $(name) frequency"; positive=true),
                absolute_error_hz=root_error, normalized_residual=residual,
                derivative_step_relative_change=step)
        end for name in (:f_r, :f_p, :f_n)
    ))
    lc = NamedTuple{D3_LC_NAMES}(Tuple(
        _real(getproperty(raw.lc_readback, name), "$(label) $(name)"; positive=true)
        for name in D3_LC_NAMES
    ))
    derivatives = (
        dY_r_domega=ComplexF64(raw.derivatives.dY_r_domega),
        dY_p_domega=ComplexF64(raw.derivatives.dY_p_domega),
        dZ21_domega=ComplexF64(raw.derivatives.dZ21_domega),
        Cn_star=ComplexF64(raw.derivatives.Cn_star),
    )
    all(value -> isfinite(real(value)) && isfinite(imag(value)), values(derivatives)) ||
        _fail("lc_producer.malformed", "$(label) derivatives must be finite.")
    return (roots=roots, derivatives=derivatives, lc_readback=lc,
        checks=raw.checks, evidence=hasproperty(raw, :evidence) ? raw.evidence : nothing)
end

_relative(reference, operational) = abs(reference - operational) / max(abs(operational), floatmin(Float64))

function _lc_comparison(operational, reference)
    derivative_deltas = NamedTuple{propertynames(operational.derivatives)}(Tuple(
        _relative(getproperty(reference.derivatives, name), getproperty(operational.derivatives, name))
        for name in propertynames(operational.derivatives)
    ))
    lc_deltas = NamedTuple{D3_LC_NAMES}(Tuple(
        _relative(getproperty(reference.lc_readback, name), getproperty(operational.lc_readback, name))
        for name in D3_LC_NAMES
    ))
    diagonal_ok = all(getproperty(derivative_deltas, name) <=
        D3_LC_THRESHOLDS.diagonal_extraction_relative for name in (:dY_r_domega, :dY_p_domega)) &&
        all(getproperty(lc_deltas, name) <= D3_LC_THRESHOLDS.diagonal_extraction_relative
            for name in (:Cr_f, :Lr_h, :Cp_f, :Lp_h))
    notch_ok = all(getproperty(derivative_deltas, name) <=
        D3_LC_THRESHOLDS.notch_extraction_relative for name in (:dZ21_domega, :Cn_star)) &&
        all(getproperty(lc_deltas, name) <= D3_LC_THRESHOLDS.notch_extraction_relative
            for name in (:Cn_f, :Ln_h))
    diagonal_ok && notch_ok || _fail(
        "lc_producer.failed_gate",
        "Operational/reference derivative or LC stability gate failed.",
    )
    return (derivative_deltas_fraction=derivative_deltas,
        lc_deltas_fraction=lc_deltas, passed=true)
end

_complex_json(value) = Dict("real" => real(value), "imag" => imag(value))

function _json_safe(value)
    value isa Complex && return _complex_json(value)
    value isa NamedTuple && return Dict(String(name) => _json_safe(item) for (name, item) in pairs(value))
    value isa AbstractDict && return Dict(String(key) => _json_safe(item) for (key, item) in pairs(value))
    value isa Tuple && return [_json_safe(item) for item in value]
    value isa AbstractVector && return [_json_safe(item) for item in value]
    value isa Symbol && return String(value)
    return value
end

function _success_payload(candidate, source, wrapper, physics, rounds, controller, operational,
    joint_reference, joint_comparison, operational_lc, reference_lc, lc_comparison)
    core = Dict{String,Any}(
        "schema_version" => D3_CANDIDATE_LC_SCHEMA,
        "contract_id" => D3_CANDIDATE_LC_CONTRACT,
        "policy_id" => D3_CANDIDATE_LC_POLICY_ID,
        "policy_sha256" => D3_CANDIDATE_LC_POLICY_SHA256,
        "lifecycle_state" => "ACCEPTED",
        "data_class" => "project-internal",
        "authority_status" => "diagnostic_only",
        "promotion_eligible" => false,
        "final_status" => "PASS",
        "first_blocker" => nothing,
        "candidate" => merge(_candidate_dict(candidate), Dict(
            "candidate_sha256" => wrapper.sha256,
            "u_idc_electrically_consumed" => false,
        )),
        "source" => source,
        "physics_sha256" => physics.sha256,
        "controller" => Dict(
            "maximum_level_index" => 10,
            "maximum_rounds" => 3,
            "maximum_state_requests" => 102,
            "state_requests" => controller.requests,
            "state_solves" => controller.solves,
            "cache_hits" => controller.cache_hits,
            "rounds" => _json_safe(rounds),
        ),
        "operational_state" => _json_safe(operational),
        "joint_reference_state" => _json_safe(joint_reference),
        "joint_comparison" => _json_safe(joint_comparison),
        "operational_lc_qualification" => _json_safe(operational_lc),
        "joint_reference_lc_qualification" => _json_safe(reference_lc),
        "lc_comparison" => _json_safe(lc_comparison),
        "operational_lc_tuple" => _json_safe(operational_lc.lc_readback),
        "nonclaims" => [
            "not an envelope or neighboring-point authority",
            "not an objective, optimizer result, winner, closure, promotion, or publication claim",
        ],
    )
    core["semantic_receipt_sha256"] = _semantic(core)
    return core
end

function produce_d3_candidate_lc_evidence(
    candidate,
    source;
    state_evaluator,
    lc_evaluator,
    cache=Dict{String,Any}(),
)
    values = _candidate(candidate)
    normalized_source = _source(source)
    wrapper = d3_candidate_wrapper_identity(values)
    physics = d3_local_lc_physics_identity(values, normalized_source)
    base_outer = (
        r_short=_ceil_count(values.lr_short_m, 50.0e-6),
        r_open=_ceil_count(values.lr_open_m, 50.0e-6),
        p_short=_ceil_count(values.lp_short_m, 50.0e-6),
        p_open=_ceil_count(values.lp_open_m, 50.0e-6),
    )
    base_mtl = _ceil_count(values.lc_m, 10.0e-6)
    controller = _Controller(0, 0, 0, cache, state_evaluator, values, physics.sha256)
    rounds = Any[]
    round_outer = base_outer
    round_mtl = base_mtl
    for round_index in 1:3
        mtl = _discover!(controller,
            level -> _state(round_outer, round_mtl * (1 << level), "round-$(round_index)-mtl-$(level)"),
            "mtl")
        cpw = _discover!(controller,
            level -> _state(_double_outer(round_outer, level), mtl.operational.state.mtl_count,
                "round-$(round_index)-cpw-$(level)"), "cpw")
        recheck = _discover!(controller,
            level -> _state(cpw.operational.state.outer_counts,
                mtl.operational.state.mtl_count * (1 << level),
                "round-$(round_index)-mtl-recheck-$(level)"), "mtl_recheck")
        operational = recheck.operational
        joint_state = _state(
            cpw.reference.state.outer_counts,
            recheck.reference.state.mtl_count,
            "round-$(round_index)-joint-reference",
        )
        joint_reference = _request!(controller, joint_state)
        joint = _frequency_comparison(operational, joint_reference, "joint")
        push!(rounds, (round=round_index, mtl=mtl, cpw=cpw, mtl_recheck=recheck,
            joint=joint))
        if joint.passed
            operational_lc = _lc_result(lc_evaluator(values, operational), "operational")
            reference_lc = _lc_result(lc_evaluator(values, joint_reference), "joint reference")
            lc_comparison = _lc_comparison(operational_lc, reference_lc)
            return _success_payload(values, normalized_source, wrapper, physics, rounds,
                controller, operational, joint_reference, joint, operational_lc,
                reference_lc, lc_comparison)
        end
        round_outer = joint_reference.state.outer_counts
        round_mtl = joint_reference.state.mtl_count
    end
    _fail("lc_producer.round_cap", "Joint qualification failed through the third round.")
end

function _dict(value, label)
    value isa AbstractDict || _fail("lc_producer.malformed", "$(label) must be a mapping.")
    return Dict{String,Any}(String(key) => item for (key, item) in pairs(value))
end

function _json_checks(value, required, label)
    checks = _dict(value, "$(label) checks")
    Set(keys(checks)) == Set(String.(required)) ||
        _fail("lc_producer.malformed", "$(label) checks do not match the accepted registry.")
    all(checks[String(name)] === true for name in required) ||
        _fail("lc_producer.failed_gate", "$(label) contains a failed validity gate.")
    return checks
end

function _json_state(value, label)
    raw = _dict(value, label)
    Set(keys(raw)) == Set(("state", "values_hz", "checks", "evidence")) ||
        _fail("lc_producer.malformed", "$(label) fields are incomplete.")
    state_raw = _dict(raw["state"], "$(label) identity")
    Set(keys(state_raw)) == Set(("id", "outer_counts", "mtl_count", "origin")) ||
        _fail("lc_producer.malformed", "$(label) identity fields are incomplete.")
    outer_raw = _dict(state_raw["outer_counts"], "$(label) outer counts")
    Set(keys(outer_raw)) == Set(("r_short", "r_open", "p_short", "p_open")) ||
        _fail("lc_producer.malformed", "$(label) outer-count fields are incomplete.")
    outer = (
        r_short=Int(outer_raw["r_short"]),
        r_open=Int(outer_raw["r_open"]),
        p_short=Int(outer_raw["p_short"]),
        p_open=Int(outer_raw["p_open"]),
    )
    expected = _state(outer, Int(state_raw["mtl_count"]), state_raw["origin"])
    state_raw["id"] == expected.id ||
        _fail("lc_producer.grid", "$(label) state identity does not match its exact counts.")
    values = _dict(raw["values_hz"], "$(label) cared frequencies")
    frequencies = (
        f_r=_real(values["f_r"], "$(label) f_r"; positive=true),
        f_p=_real(values["f_p"], "$(label) f_p"; positive=true),
        f_n=_real(values["f_n"], "$(label) f_n"; positive=true),
    )
    _json_checks(raw["checks"], D3_STATE_CHECKS, label)
    return (state=expected, values_hz=frequencies)
end

function _json_frequency_comparison(value, operational, reference, label)
    raw = _dict(value, label)
    Set(keys(raw)) == Set((
        "phase", "operational_state_id", "reference_state_id", "changes", "passed",
    )) || _fail("lc_producer.malformed", "$(label) fields are incomplete.")
    raw["operational_state_id"] == operational.state.id &&
        raw["reference_state_id"] == reference.state.id ||
        _fail("lc_producer.grid", "$(label) names different grid states.")
    changes = _dict(raw["changes"], "$(label) changes")
    Set(keys(changes)) == Set(("f_r", "f_p", "f_n")) ||
        _fail("lc_producer.malformed", "$(label) cared-frequency fields are incomplete.")
    recalculated = _frequency_comparison(operational, reference, raw["phase"])
    for name in (:f_r, :f_p, :f_n)
        item = _dict(changes[String(name)], "$(label) $(name)")
        expected = getproperty(recalculated.changes, name)
        item["operational_hz"] == expected.operational_hz &&
            item["reference_hz"] == expected.reference_hz &&
            item["delta_fraction"] == expected.delta_fraction &&
            item["threshold_fraction"] == expected.threshold_fraction &&
            item["passed"] === expected.passed || _fail(
            "lc_producer.failed_gate",
            "$(label) $(name) delta or threshold changed.",
        )
    end
    raw["passed"] === recalculated.passed ||
        _fail("lc_producer.failed_gate", "$(label) PASS status changed.")
    return recalculated
end

function _json_discovery(value, phase, expected_state)
    raw = _dict(value, "$(phase) discovery")
    Set(keys(raw)) == Set(("operational", "reference", "records", "transitions")) ||
        _fail("lc_producer.malformed", "$(phase) discovery fields are incomplete.")
    records_raw = raw["records"] isa AbstractVector ? raw["records"] :
        _fail("lc_producer.controller", "$(phase) records must be an array.")
    3 <= length(records_raw) <= 11 || _fail(
        "lc_producer.controller",
        "$(phase) must stop on two consecutive PASS transitions within level 10.",
    )
    records = [_json_state(item, "$(phase) level $(level)")
        for (level, item) in enumerate(records_raw)]
    for (level, record) in enumerate(records)
        expected = expected_state(level - 1)
        record.state.outer_counts == expected.outer_counts &&
            record.state.mtl_count == expected.mtl_count || _fail(
            "lc_producer.controller",
            "$(phase) grid schedule differs from the accepted deterministic controller.",
        )
    end
    transitions_raw = raw["transitions"] isa AbstractVector ? raw["transitions"] :
        _fail("lc_producer.controller", "$(phase) transitions must be an array.")
    length(transitions_raw) == length(records) - 1 || _fail(
        "lc_producer.controller",
        "$(phase) transition count does not match its grid records.",
    )
    transitions = [_json_frequency_comparison(
        item,
        records[index],
        records[index + 1],
        "$(phase) transition $(index)",
    ) for (index, item) in enumerate(transitions_raw)]
    transitions[end - 1].passed && transitions[end].passed || _fail(
        "lc_producer.controller",
        "$(phase) did not stop on two consecutive PASS transitions.",
    )
    length(transitions) > 2 && any(
        transitions[index - 1].passed && transitions[index].passed
        for index in 2:(length(transitions) - 1)
    ) && _fail(
        "lc_producer.controller",
        "$(phase) continued after its first qualifying transition pair.",
    )
    operational = _json_state(raw["operational"], "$(phase) operational")
    reference = _json_state(raw["reference"], "$(phase) reference")
    operational == records[end - 1] && reference == records[end] || _fail(
        "lc_producer.controller",
        "$(phase) selected states differ from its first qualifying pair.",
    )
    return (operational=operational, reference=reference, records=records,
        transitions=transitions)
end

function _json_joint_comparison(value, operational, expected_state)
    raw = _dict(value, "joint comparison")
    changes = _dict(raw["changes"], "joint comparison changes")
    reference = (
        state=expected_state,
        values_hz=NamedTuple{(:f_r, :f_p, :f_n)}(Tuple(
            _real(
                _dict(changes[String(name)], "joint comparison $(name)")["reference_hz"],
                "joint comparison $(name) reference";
                positive=true,
            ) for name in (:f_r, :f_p, :f_n)
        )),
    )
    comparison = _json_frequency_comparison(
        raw,
        operational,
        reference,
        "joint comparison",
    )
    return reference, comparison
end


_same_grid_output(left, right) =
    left.state.id == right.state.id &&
    left.state.outer_counts == right.state.outer_counts &&
    left.state.mtl_count == right.state.mtl_count &&
    left.values_hz == right.values_hz

function _json_complex(value, label)
    raw = _dict(value, label)
    Set(keys(raw)) == Set(("real", "imag")) ||
        _fail("lc_producer.malformed", "$(label) must contain real and imag.")
    parsed = ComplexF64(
        _real(raw["real"], "$(label).real"),
        _real(raw["imag"], "$(label).imag"),
    )
    return parsed
end

function _json_lc_result(value, label)
    raw = _dict(value, label)
    Set(keys(raw)) == Set(("roots", "derivatives", "lc_readback", "checks", "evidence")) ||
        _fail("lc_producer.malformed", "$(label) fields are incomplete.")
    _json_checks(raw["checks"], D3_LC_CHECKS, label)
    roots_raw = _dict(raw["roots"], "$(label) roots")
    Set(keys(roots_raw)) == Set(("f_r", "f_p", "f_n")) ||
        _fail("lc_producer.malformed", "$(label) root fields are incomplete.")
    roots = NamedTuple{(:f_r, :f_p, :f_n)}(Tuple(
        begin
            item = _dict(roots_raw[String(name)], "$(label) $(name) root")
            Set(keys(item)) == Set((
                "frequency_hz", "absolute_error_hz", "normalized_residual",
                "derivative_step_relative_change",
            )) || _fail("lc_producer.malformed", "$(label) $(name) root fields are incomplete.")
            step_limit = name == :f_n ?
                D3_LC_THRESHOLDS.notch_derivative_step_relative :
                D3_LC_THRESHOLDS.diagonal_derivative_step_relative
            root = (
                frequency_hz=_real(item["frequency_hz"], "$(label) $(name) frequency"; positive=true),
                absolute_error_hz=_real(item["absolute_error_hz"], "$(label) $(name) root error"; nonnegative=true),
                normalized_residual=_real(item["normalized_residual"], "$(label) $(name) residual"; nonnegative=true),
                derivative_step_relative_change=_real(item["derivative_step_relative_change"], "$(label) $(name) step"; nonnegative=true),
            )
            root.absolute_error_hz <= D3_LC_THRESHOLDS.root_absolute_tolerance_hz &&
                root.normalized_residual <= D3_LC_THRESHOLDS.normalized_root_residual &&
                root.derivative_step_relative_change <= step_limit || _fail(
                "lc_producer.failed_gate",
                "$(label) $(name) root/derivative gate failed.",
            )
            root
        end for name in (:f_r, :f_p, :f_n)
    ))
    derivatives_raw = _dict(raw["derivatives"], "$(label) derivatives")
    Set(keys(derivatives_raw)) ==
        Set(("dY_r_domega", "dY_p_domega", "dZ21_domega", "Cn_star")) ||
        _fail("lc_producer.malformed", "$(label) derivative fields are incomplete.")
    derivatives = (
        dY_r_domega=_json_complex(derivatives_raw["dY_r_domega"], "$(label) dY_r_domega"),
        dY_p_domega=_json_complex(derivatives_raw["dY_p_domega"], "$(label) dY_p_domega"),
        dZ21_domega=_json_complex(derivatives_raw["dZ21_domega"], "$(label) dZ21_domega"),
        Cn_star=_json_complex(derivatives_raw["Cn_star"], "$(label) Cn_star"),
    )
    lc_raw = _dict(raw["lc_readback"], "$(label) LC tuple")
    Set(keys(lc_raw)) == Set(String.(D3_LC_NAMES)) ||
        _fail("lc_producer.malformed", "$(label) LC fields are incomplete.")
    lc = NamedTuple{D3_LC_NAMES}(Tuple(
        _real(lc_raw[String(name)], "$(label) $(name)"; positive=true)
        for name in D3_LC_NAMES
    ))
    return (roots=roots, derivatives=derivatives, lc_readback=lc)
end

function _validate_json_lc_comparison(value, operational, reference)
    raw = _dict(value, "LC comparison")
    Set(keys(raw)) ==
        Set(("derivative_deltas_fraction", "lc_deltas_fraction", "passed")) ||
        _fail("lc_producer.malformed", "LC comparison fields are incomplete.")
    recalculated = _lc_comparison(operational, reference)
    derivative_raw = _dict(raw["derivative_deltas_fraction"], "derivative deltas")
    lc_raw = _dict(raw["lc_deltas_fraction"], "LC deltas")
    Set(keys(derivative_raw)) == Set(String.(propertynames(operational.derivatives))) &&
        Set(keys(lc_raw)) == Set(String.(D3_LC_NAMES)) ||
        _fail("lc_producer.malformed", "LC comparison delta fields are incomplete.")
    all(derivative_raw[String(name)] == getproperty(recalculated.derivative_deltas_fraction, name)
        for name in propertynames(recalculated.derivative_deltas_fraction)) &&
        all(lc_raw[String(name)] == getproperty(recalculated.lc_deltas_fraction, name)
            for name in D3_LC_NAMES) && raw["passed"] === true || _fail(
        "lc_producer.failed_gate",
        "LC comparison values or PASS status changed.",
    )
    return recalculated
end

function validate_d3_candidate_lc_evidence(value)
    receipt = _dict(value, "LC evidence")
    required = (
        "schema_version", "contract_id", "policy_id", "policy_sha256",
        "lifecycle_state", "data_class", "authority_status", "promotion_eligible",
        "final_status", "first_blocker", "candidate", "source", "physics_sha256",
        "controller", "operational_state", "joint_reference_state", "joint_comparison",
        "operational_lc_qualification", "joint_reference_lc_qualification",
        "lc_comparison", "operational_lc_tuple", "nonclaims", "semantic_receipt_sha256",
    )
    Set(keys(receipt)) == Set(required) ||
        _fail("lc_producer.malformed", "LC evidence fields do not match schema v2.")
    receipt["schema_version"] == D3_CANDIDATE_LC_SCHEMA &&
        receipt["contract_id"] == D3_CANDIDATE_LC_CONTRACT &&
        receipt["policy_id"] == D3_CANDIDATE_LC_POLICY_ID &&
        receipt["policy_sha256"] == D3_CANDIDATE_LC_POLICY_SHA256 ||
        _fail("lc_producer.stale", "LC evidence policy or contract is stale.")
    receipt["lifecycle_state"] == "ACCEPTED" &&
        receipt["data_class"] == "project-internal" &&
        receipt["authority_status"] == "diagnostic_only" &&
        receipt["promotion_eligible"] === false ||
        _fail("lc_producer.authority", "LC evidence authority boundary is invalid.")
    receipt["final_status"] == "PASS" && isnothing(receipt["first_blocker"]) ||
        _fail("lc_producer.failed_status", "LC evidence is not PASS.")
    declared = _sha(receipt["semantic_receipt_sha256"], "semantic receipt")
    core = copy(receipt)
    delete!(core, "semantic_receipt_sha256")
    _semantic(core) == declared ||
        _fail("lc_producer.stale", "LC evidence semantic hash changed.")
    candidate_raw = _dict(receipt["candidate"], "candidate")
    Set(keys(candidate_raw)) ==
        Set((String.(D3_LENGTH_NAMES)..., "u_IDC", "candidate_sha256",
            "u_idc_electrically_consumed")) ||
        _fail("lc_producer.malformed", "Candidate receipt fields are incomplete.")
    candidate = NamedTuple{(D3_LENGTH_NAMES..., :u_IDC)}(Tuple(
        _real(candidate_raw[String(name)], "candidate.$(name)"; positive=true)
        for name in (D3_LENGTH_NAMES..., :u_IDC)
    ))
    d3_candidate_wrapper_identity(candidate).sha256 == candidate_raw["candidate_sha256"] ||
        _fail("lc_producer.candidate_mismatch", "Candidate semantic identity changed.")
    candidate_raw["u_idc_electrically_consumed"] === false ||
        _fail("lc_producer.authority", "Local LC evidence may not consume u_IDC.")
    physics = d3_local_lc_physics_identity(candidate, _dict(receipt["source"], "source"))
    physics.sha256 == receipt["physics_sha256"] ||
        _fail("lc_producer.stale", "Local physics identity changed.")
    controller = _dict(receipt["controller"], "controller")
    Set(keys(controller)) == Set((
        "maximum_level_index", "maximum_rounds", "maximum_state_requests",
        "state_requests", "state_solves", "cache_hits", "rounds",
    )) || _fail("lc_producer.malformed", "Controller fields are incomplete.")
    controller["maximum_level_index"] == 10 && controller["maximum_rounds"] == 3 &&
        controller["maximum_state_requests"] == 102 &&
        0 < controller["state_requests"] <= 102 &&
        0 <= controller["state_solves"] <= controller["state_requests"] &&
        controller["cache_hits"] == controller["state_requests"] - controller["state_solves"] ||
        _fail("lc_producer.controller", "LC controller telemetry violates its ceilings.")
    rounds = controller["rounds"] isa AbstractVector ? controller["rounds"] :
        _fail("lc_producer.controller", "Controller rounds must be an array.")
    1 <= length(rounds) <= 3 ||
        _fail("lc_producer.controller", "Controller must stop within three rounds.")
    base_outer = (
        r_short=_ceil_count(candidate.lr_short_m, 50.0e-6),
        r_open=_ceil_count(candidate.lr_open_m, 50.0e-6),
        p_short=_ceil_count(candidate.lp_short_m, 50.0e-6),
        p_open=_ceil_count(candidate.lp_open_m, 50.0e-6),
    )
    base_mtl = _ceil_count(candidate.lc_m, 10.0e-6)
    round_outer = base_outer
    round_mtl = base_mtl
    request_count = 0
    last_operational = nothing
    last_reference = nothing
    last_joint = nothing
    for (index, round_value) in enumerate(rounds)
        round = _dict(round_value, "controller round")
        Set(keys(round)) == Set(("round", "mtl", "cpw", "mtl_recheck", "joint")) ||
            _fail("lc_producer.malformed", "Controller round fields are incomplete.")
        round["round"] == index ||
            _fail("lc_producer.controller", "Controller rounds are not ordered.")
        mtl = _json_discovery(
            round["mtl"],
            "mtl",
            level -> _state(round_outer, round_mtl * (1 << level), "validation"),
        )
        cpw = _json_discovery(
            round["cpw"],
            "cpw",
            level -> _state(_double_outer(round_outer, level),
                mtl.operational.state.mtl_count, "validation"),
        )
        recheck = _json_discovery(
            round["mtl_recheck"],
            "mtl_recheck",
            level -> _state(cpw.operational.state.outer_counts,
                mtl.operational.state.mtl_count * (1 << level), "validation"),
        )
        expected_joint = _state(
            cpw.reference.state.outer_counts,
            recheck.reference.state.mtl_count,
            "validation",
        )
        joint_reference, joint = _json_joint_comparison(
            round["joint"], recheck.operational, expected_joint,
        )
        index < length(rounds) && joint.passed && _fail(
            "lc_producer.controller",
            "Controller continued after the first qualifying joint result.",
        )
        index == length(rounds) && !joint.passed && _fail(
            "lc_producer.failed_gate",
            "Final controller round is not joint-qualified.",
        )
        request_count += length(mtl.records) + length(cpw.records) +
            length(recheck.records) + 1
        round_outer = joint_reference.state.outer_counts
        round_mtl = joint_reference.state.mtl_count
        last_operational = recheck.operational
        last_reference = joint_reference
        last_joint = joint
    end
    operational = _json_state(receipt["operational_state"], "operational state")
    reference = _json_state(receipt["joint_reference_state"], "joint reference state")
    joint = _json_frequency_comparison(
        receipt["joint_comparison"],
        operational,
        reference,
        "joint comparison",
    )
    _same_grid_output(operational, last_operational) &&
        _same_grid_output(reference, last_reference) && joint == last_joint ||
        _fail("lc_producer.controller", "Top-level evidence differs from the final controller round.")
    controller["state_requests"] == request_count || _fail(
        "lc_producer.controller",
        "Controller request telemetry does not match its exact serialized schedule.",
    )
    joint.passed || _fail("lc_producer.failed_gate", "Joint comparison is not PASS.")
    operational_lc = _json_lc_result(
        receipt["operational_lc_qualification"],
        "operational LC qualification",
    )
    reference_lc = _json_lc_result(
        receipt["joint_reference_lc_qualification"],
        "joint reference LC qualification",
    )
    operational_lc.roots.f_r.frequency_hz == operational.values_hz.f_r &&
        operational_lc.roots.f_p.frequency_hz == operational.values_hz.f_p &&
        operational_lc.roots.f_n.frequency_hz == operational.values_hz.f_n &&
        reference_lc.roots.f_r.frequency_hz == reference.values_hz.f_r &&
        reference_lc.roots.f_p.frequency_hz == reference.values_hz.f_p &&
        reference_lc.roots.f_n.frequency_hz == reference.values_hz.f_n || _fail(
        "lc_producer.failed_gate",
        "LC roots do not equal the accepted signed-midpoint cared frequencies.",
    )
    _validate_json_lc_comparison(receipt["lc_comparison"], operational_lc, reference_lc)
    lc = _dict(receipt["operational_lc_tuple"], "LC tuple")
    Set(keys(lc)) == Set(String.(D3_LC_NAMES)) ||
        _fail("lc_producer.malformed", "LC tuple fields are incomplete.")
    normalized_lc = NamedTuple{D3_LC_NAMES}(Tuple(
        _real(lc[String(name)], "LC tuple $(name)"; positive=true) for name in D3_LC_NAMES
    ))
    normalized_lc == operational_lc.lc_readback ||
        _fail("lc_producer.operand_mismatch", "Published LC tuple changed after qualification.")
    return (candidate=candidate, source=physics.source, candidate_sha256=candidate_raw["candidate_sha256"],
        physics_sha256=physics.sha256, lc_readback=normalized_lc,
        semantic_receipt_sha256=declared)
end

end
