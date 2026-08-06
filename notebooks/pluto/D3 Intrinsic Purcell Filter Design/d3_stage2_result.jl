# Canonical D3 Stage-2 winner handoff and artifact publication.  This module
# owns neither optimization nor circuit physics: it re-evaluates one optimizer
# winner through caller-supplied canonical evaluators, verifies that every
# result belongs to the same compiled model, and atomically publishes the
# Human-review inputs from that single in-memory foundation.

isdefined(@__MODULE__, :D3LCQualificationReceipt) ||
    include(joinpath(@__DIR__, "d3_lc_qualification_receipt.jl"))
isdefined(@__MODULE__, :D3FullQRPQualificationReceipt) ||
    include(joinpath(@__DIR__, "d3_full_qrp_qualification_receipt.jl"))

module D3Stage2Result

using Printf
using SHA
using SuperconductingCircuitsCore

using ..D3CoupledOptimizer: OptimizationResult, RejectedEvaluation, ValidEvaluation
using ..D3LCQualificationReceipt: D3AuthorizedStage2LC,
    D3_LC_QUALIFICATION_POLICY_SHA256,
    authorize_d3_stage2_lc_receipt,
    d3_lc_qualification_receipt_identity,
    revalidate_d3_stage2_lc_receipt,
    validate_d3_stage2_lc_authorization_match
using ..D3FullQRPQualificationReceipt: D3AuthorizedStage2FullQRP,
    D3_FULL_QRP_QUALIFICATION_POLICY_SHA256,
    authorize_d3_stage2_full_qrp_receipt,
    d3_full_qrp_qualification_receipt_identity,
    evaluate_d3_stage2_objective_with_evidence,
    revalidate_d3_stage2_full_qrp_receipt

include(joinpath(@__DIR__, "d3_resonator_input.jl"))
using .D3ResonatorInput: validate_d3_rev10_q2d_identity

export Stage2RunSpec,
    Stage2EvaluatedResult,
    evaluate_stage2_winner,
    write_stage2_result

const JSON3 = SuperconductingCircuitsCore.JSON3
const SUMMARY_SCHEMA = "d3-stage2-physical-candidate-summary.v4"
const QUBIT_RECEIPT_SCHEMA = "d3-stage2-qubit-admittance-receipt.v1"
const OBJECTIVE_CONTRACT = "d3-stage2-direct-hybridized-objective.v3"
const FOUNDATION_CONTRACT = "d3-stage2-candidate-foundation.v5"
const MAX_PHYSICAL_LINE_SECTION_LENGTH_M = 50e-6
const OBJECTIVE_AUTHORITY = (
    approval_status=:human_approved,
    target_id="d3-same-face-resonators-opposite-face-qubit-j5-k20-gap8",
    target_revision=10,
    target_contract_sha256=
        "c5ad1b1d3a770334fe29d15b863001a4746d60bb4a5cac9410694c1ac2d6b209",
    notch_authority=:distributed_rp_on,
    effective_diagonal_frequency_extraction=
        :complete_complement_rp_complex_operator,
    effective_exchange_extraction=
        :complete_complement_rp_complex_midpoint_residue,
    linewidth_pole_scope=:unordered_rp_two_pole_subspace,
    primary_linewidth_extraction=:exact_open_unordered_rp_poles,
)
const CANDIDATE_NAMES =
    (:lr_open_m, :lr_short_m, :lc_m, :lp_open_m, :lp_short_m, :u_IDC)
const FILES = (
    "summary.json",
    "history.json",
    "s21.csv",
    "linear-quantities.json",
    "qubit-admittance.csv",
    "qubit-admittance-receipt.json",
)

"""Inputs owned by one reproducible Stage-2 winner evaluation."""
struct Stage2RunSpec
    run_id::String
    slot_hz::Float64
    response_frequency_hz::Vector{Float64}
    qubit_frequency_hz::Vector{Float64}
    q2d_spec::Dict{String,Any}
    lc_qualification_policy_sha256::String
    full_qrp_qualification_policy_sha256::String
    bounds::Dict{String,Any}
    optimizer_configuration::Dict{String,Any}

    function Stage2RunSpec(
        run_id::AbstractString,
        slot_hz::Real,
        response_frequency_hz,
        qubit_frequency_hz,
        q2d_spec,
        lc_qualification_policy_sha256,
        full_qrp_qualification_policy_sha256,
        bounds,
        optimizer_configuration,
    )
        id = strip(String(run_id))
        occursin(r"^[a-z0-9][a-z0-9._-]*$", id) || error(
            "D3 Stage-2 run_id must be lowercase filesystem-safe text.",
        )
        slot = Float64(slot_hz)
        isfinite(slot) && slot > 0 || error(
            "D3 Stage-2 Slot must be finite and positive.",
        )
        response = _frequency_grid(response_frequency_hz, "response")
        qubit = _frequency_grid(qubit_frequency_hz, "qubit-admittance")
        lc_policy_sha256 = _sha256_text(
            lc_qualification_policy_sha256,
            "D3 LC qualification policy SHA-256",
        )
        lc_policy_sha256 == D3_LC_QUALIFICATION_POLICY_SHA256 || error(
            "D3 Stage-2 RunSpec uses a stale LC qualification producer policy.",
        )
        full_qrp_policy_sha256 = _sha256_text(
            full_qrp_qualification_policy_sha256,
            "D3 Full-QRP qualification policy SHA-256",
        )
        full_qrp_policy_sha256 == D3_FULL_QRP_QUALIFICATION_POLICY_SHA256 || error(
            "D3 Stage-2 RunSpec uses a stale Full-QRP qualification policy.",
        )
        q2d = _validated_q2d_spec(q2d_spec)
        bound_values = _validated_bounds(bounds)
        optimizer = _validated_optimizer_configuration(
            optimizer_configuration,
            bound_values,
        )
        return new(
            id,
            slot,
            response,
            qubit,
            q2d,
            lc_policy_sha256,
            full_qrp_policy_sha256,
            bound_values,
            optimizer,
        )
    end
end

function Stage2RunSpec(;
    run_id,
    slot_hz,
    response_frequency_hz,
    qubit_frequency_hz,
    q2d_spec,
    lc_qualification_policy_sha256,
    full_qrp_qualification_policy_sha256,
    bounds,
    optimizer_configuration,
)
    return Stage2RunSpec(
        run_id,
        slot_hz,
        response_frequency_hz,
        qubit_frequency_hz,
        q2d_spec,
        lc_qualification_policy_sha256,
        full_qrp_qualification_policy_sha256,
        bounds,
        optimizer_configuration,
    )
end

"""One optimizer winner re-evaluated through the canonical Stage-2 path."""
struct Stage2EvaluatedResult{O,R,L,U,F,J,H,Q}
    specification::Stage2RunSpec
    optimization::O
    winner_record::R
    lc_qualification::L
    full_qrp_qualification::U
    foundation::F
    objective::J
    hb_trace::H
    qubit_admittance::Q
end

function _frequency_grid(values, label)
    frequencies = Float64.(collect(values))
    !isempty(frequencies) && all(isfinite, frequencies) &&
        all(>(0), frequencies) && all(diff(frequencies) .> 0) || error(
        "D3 Stage-2 $(label) frequencies must be finite, positive, and strictly increasing.",
    )
    return frequencies
end

function _string_key_dict(value, label)
    value isa AbstractDict || error("$(label) must be a dictionary.")
    isempty(value) && error("$(label) must not be empty.")
    return Dict{String,Any}(String(key) => item for (key, item) in pairs(value))
end

function _require_dict_keys(value, required, label)
    missing = setdiff(Set(String.(required)), Set(keys(value)))
    isempty(missing) || error("$(label) is missing $(sort!(collect(missing))).")
    return value
end

function _nonempty_text(value, label)
    value isa AbstractString || error("$(label) must be text.")
    text = strip(String(value))
    isempty(text) && error("$(label) must not be empty.")
    return text
end

function _positive_real(value, label)
    value isa Real && !(value isa Bool) || error("$(label) must be numeric.")
    number = Float64(value)
    isfinite(number) && number > 0 || error("$(label) must be finite and positive.")
    return number
end

function _nonnegative_real(value, label)
    value isa Real && !(value isa Bool) || error("$(label) must be numeric.")
    number = Float64(value)
    isfinite(number) && number >= 0 || error(
        "$(label) must be finite and nonnegative.",
    )
    return number
end

function _finite_vector(value, length_expected, label)
    value isa AbstractArray || value isa Tuple || error("$(label) must be an array.")
    raw = collect(value)
    length(raw) == length_expected || error(
        "$(label) must contain exactly $(length_expected) values.",
    )
    all(item -> item isa Real && !(item isa Bool), raw) || error(
        "$(label) must contain only numeric values.",
    )
    numbers = Float64.(raw)
    all(isfinite, numbers) || error("$(label) must contain only finite values.")
    return numbers
end

function _json_generic_copy(value)
    if value isa AbstractDict
        return Dict{String,Any}(
            String(key) => _json_generic_copy(item)
            for (key, item) in pairs(value)
        )
    elseif value isa NamedTuple
        return Dict{String,Any}(
            String(key) => _json_generic_copy(item)
            for (key, item) in pairs(value)
        )
    elseif value isa AbstractArray || value isa Tuple
        return Any[_json_generic_copy(item) for item in value]
    end
    return value
end

function _validated_q2d_spec(value)
    q2d = _string_key_dict(value, "D3 Stage-2 Q2D report specification")
    required = (
        "artifact_id",
        "artifact_sha256",
        "topology_id",
        "single_case_id",
        "pair_case_id",
        "geometry_um",
        "solver",
        "loss_model",
        "authority",
        "single_l_per_m_h",
        "single_c_per_m_f",
        "l_matrix_per_m_h",
        "c_matrix_per_m_f",
        "coupling_orientation",
        "section_length_m",
        "mtl_section_length_m",
    )
    Set(keys(q2d)) == Set(required) || error(
        "D3 Stage-2 Q2D report specification fields must be exactly $(collect(required)).",
    )
    geometry = _string_key_dict(q2d["geometry_um"], "D3 Stage-2 Q2D geometry")
    geometry_fields = (
        "w",
        "s",
        "d",
        "h",
        "upper_ground_clearance",
        "metal_thickness",
    )
    Set(keys(geometry)) == Set(geometry_fields) || error(
        "D3 Stage-2 Q2D geometry fields must be exactly $(collect(geometry_fields)).",
    )
    solver = _string_key_dict(q2d["solver"], "D3 Stage-2 Q2D solver")
    solver_fields = (
        "adaptive_frequency_hz",
        "aedt_version",
        "pyaedt_version",
    )
    Set(keys(solver)) == Set(solver_fields) || error(
        "D3 Stage-2 Q2D solver fields must be exactly $(collect(solver_fields)).",
    )
    artifact_id = _nonempty_text(q2d["artifact_id"], "Q2D artifact_id")
    artifact_sha256 = _sha256_text(q2d["artifact_sha256"], "Q2D artifact_sha256")
    single_case_id = _nonempty_text(q2d["single_case_id"], "Q2D single_case_id")
    pair_case_id = _nonempty_text(q2d["pair_case_id"], "Q2D pair_case_id")
    topology_id = _nonempty_text(q2d["topology_id"], "Q2D topology_id")
    loss_model = _nonempty_text(q2d["loss_model"], "Q2D loss_model")
    coupling_orientation = _nonempty_text(
        q2d["coupling_orientation"],
        "Q2D coupling_orientation",
    )
    normalized_geometry = (
        w=_positive_real(geometry["w"], "Q2D geometry w"),
        s=_positive_real(geometry["s"], "Q2D geometry s"),
        d=_positive_real(geometry["d"], "Q2D geometry d"),
        h=_positive_real(geometry["h"], "Q2D geometry h"),
        upper_ground_clearance=_nonnegative_real(
            geometry["upper_ground_clearance"],
            "Q2D geometry upper_ground_clearance",
        ),
        metal_thickness=_positive_real(
            geometry["metal_thickness"],
            "Q2D geometry metal_thickness",
        ),
    )
    normalized_solver = (
        adaptive_frequency_hz=_positive_real(
            solver["adaptive_frequency_hz"],
            "Q2D adaptive frequency",
        ),
        aedt_version=_nonempty_text(solver["aedt_version"], "Q2D AEDT version"),
        pyaedt_version=_nonempty_text(
            solver["pyaedt_version"],
            "Q2D PyAEDT version",
        ),
    )
    authority = _string_key_dict(q2d["authority"], "D3 Stage-2 Q2D authority")
    authority_fields = (
        "payload_sha256",
        "single_result_id",
        "pair_result_id",
        "source_database_sha256",
        "material_profile_id",
        "material_profile_sha256",
        "material_authority_sha256",
        "single_evidence_sha256",
        "pair_evidence_sha256",
        "single_raw_sources_sha256",
        "pair_raw_sources_sha256",
        "basis",
        "orientation",
        "row_column_order",
        "l_matrix_unit",
        "c_matrix_unit",
        "data_class",
        "allowed_consumers",
        "publication_state",
        "promotion_eligible",
    )
    Set(keys(authority)) == Set(authority_fields) || error(
        "D3 Stage-2 Q2D authority fields must be exactly $(collect(authority_fields)).",
    )
    normalized_authority = (
        payload_sha256=_sha256_text(
            authority["payload_sha256"],
            "Q2D payload SHA-256",
        ),
        single_result_id=_sha256_text(
            authority["single_result_id"],
            "Q2D single result id",
        ),
        pair_result_id=_sha256_text(
            authority["pair_result_id"],
            "Q2D pair result id",
        ),
        source_database_sha256=_sha256_text(
            authority["source_database_sha256"],
            "Q2D database SHA-256",
        ),
        material_profile_id=_nonempty_text(
            authority["material_profile_id"],
            "Q2D material profile id",
        ),
        material_profile_sha256=_sha256_text(
            authority["material_profile_sha256"],
            "Q2D material profile SHA-256",
        ),
        material_authority_sha256=_sha256_text(
            authority["material_authority_sha256"],
            "Q2D material authority SHA-256",
        ),
        single_evidence_sha256=_sha256_text(
            authority["single_evidence_sha256"],
            "Q2D single evidence SHA-256",
        ),
        pair_evidence_sha256=_sha256_text(
            authority["pair_evidence_sha256"],
            "Q2D pair evidence SHA-256",
        ),
        single_raw_sources_sha256=_sha256_text(
            authority["single_raw_sources_sha256"],
            "Q2D single source manifest SHA-256",
        ),
        pair_raw_sources_sha256=_sha256_text(
            authority["pair_raw_sources_sha256"],
            "Q2D pair source manifest SHA-256",
        ),
        basis=_nonempty_text(authority["basis"], "Q2D basis"),
        orientation=_nonempty_text(authority["orientation"], "Q2D orientation"),
        row_column_order=_nonempty_text(authority["row_column_order"], "Q2D matrix order"),
        l_matrix_unit=_nonempty_text(authority["l_matrix_unit"], "Q2D L unit"),
        c_matrix_unit=_nonempty_text(authority["c_matrix_unit"], "Q2D C unit"),
        data_class=_nonempty_text(authority["data_class"], "Q2D data class"),
        allowed_consumers=Tuple(String.(authority["allowed_consumers"])),
        publication_state=_nonempty_text(
            authority["publication_state"],
            "Q2D publication state",
        ),
        promotion_eligible=authority["promotion_eligible"],
    )
    l_values = _finite_vector(q2d["l_matrix_per_m_h"], 4, "Q2D L matrix")
    c_values = _finite_vector(q2d["c_matrix_per_m_f"], 4, "Q2D C matrix")
    current = validate_d3_rev10_q2d_identity((
        section_length_m=_positive_real(
            q2d["section_length_m"],
            "Q2D section length",
        ),
        mtl_section_length_m=_positive_real(
            q2d["mtl_section_length_m"],
            "Q2D MTL section length",
        ),
        readout_l_per_m_h=_positive_real(
            q2d["single_l_per_m_h"],
            "Q2D single-line L per metre",
        ),
        readout_c_per_m_f=_positive_real(
            q2d["single_c_per_m_f"],
            "Q2D single-line C per metre",
        ),
        filter_l_per_m_h=_positive_real(
            q2d["single_l_per_m_h"],
            "Q2D single-line L per metre",
        ),
        filter_c_per_m_f=_positive_real(
            q2d["single_c_per_m_f"],
            "Q2D single-line C per metre",
        ),
        l_matrix_per_m_h=[l_values[1] l_values[2]; l_values[3] l_values[4]],
        c_matrix_per_m_f=[c_values[1] c_values[2]; c_values[3] c_values[4]],
        coupling_orientation=Symbol(coupling_orientation),
        q2d_artifact_id=artifact_id,
        q2d_artifact_sha256=artifact_sha256,
        q2d_topology_id=Symbol(topology_id),
        q2d_geometry_um=normalized_geometry,
        q2d_single_case_id=single_case_id,
        q2d_pair_case_id=pair_case_id,
        q2d_solver=normalized_solver,
        q2d_loss_model=loss_model,
        q2d_authority=normalized_authority,
    ))
    return Dict{String,Any}(
        "artifact_id" => current.q2d_artifact_id,
        "artifact_sha256" => current.q2d_artifact_sha256,
        "topology_id" => String(current.q2d_topology_id),
        "single_case_id" => current.q2d_single_case_id,
        "pair_case_id" => current.q2d_pair_case_id,
        "geometry_um" => _json_generic_copy(current.q2d_geometry_um),
        "solver" => _json_generic_copy(current.q2d_solver),
        "loss_model" => current.q2d_loss_model,
        "authority" => _json_generic_copy(current.q2d_authority),
        "single_l_per_m_h" => current.readout_l_per_m_h,
        "single_c_per_m_f" => current.readout_c_per_m_f,
        "l_matrix_per_m_h" => vec(permutedims(current.l_matrix_per_m_h)),
        "c_matrix_per_m_f" => vec(permutedims(current.c_matrix_per_m_f)),
        "coupling_orientation" => String(current.coupling_orientation),
        "section_length_m" => current.section_length_m,
        "mtl_section_length_m" => current.mtl_section_length_m,
    )
end

function _validated_bounds(value)
    bounds = _string_key_dict(value, "D3 Stage-2 optimizer bounds")
    required = string.(CANDIDATE_NAMES)
    _require_dict_keys(
        bounds,
        required,
        "D3 Stage-2 optimizer bounds",
    )
    Set(keys(bounds)) == Set(required) || error(
        "D3 Stage-2 optimizer bounds must contain exactly $(required).",
    )
    return Dict(name => begin
        interval = _finite_vector(bounds[name], 2, "D3 optimizer bound $(name)")
        0 <= interval[1] < interval[2] || error(
            "D3 optimizer bound $(name) must have 0 <= lower < upper.",
        )
        interval
    end for name in required)
end

function _validated_optimizer_configuration(value, bounds)
    configuration = _string_key_dict(
        value,
        "D3 Stage-2 optimizer configuration",
    )
    required = (
        "algorithm",
        "initial_mean",
        "seed",
        "sigma",
        "popsize",
        "maxiter",
        "maxfevals",
        "ftol",
        "xtol",
    )
    Set(keys(configuration)) == Set(required) || error(
        "D3 Stage-2 optimizer configuration fields must be exactly $(collect(required)).",
    )
    configuration["algorithm"] == "bounded_cma_es_only" || error(
        "D3 Stage-2 optimizer algorithm must be bounded_cma_es_only.",
    )
    initial = _string_key_dict(
        configuration["initial_mean"],
        "D3 Stage-2 CMA initial mean",
    )
    Set(keys(initial)) == Set(string.(CANDIDATE_NAMES)) || error(
        "D3 Stage-2 CMA initial mean must contain exactly the physical candidate coordinates.",
    )
    normalized_initial = Dict{String,Any}()
    for name in string.(CANDIDATE_NAMES)
        number = _positive_real(initial[name], "D3 Stage-2 CMA initial mean $(name)")
        lower, upper = bounds[name]
        lower <= number <= upper || error(
            "D3 Stage-2 CMA initial mean $(name) is outside its declared bounds.",
        )
        normalized_initial[name] = number
    end
    integer_value(name; minimum=0) = begin
        raw = configuration[name]
        raw isa Integer && !(raw isa Bool) || error(
            "D3 Stage-2 CMA $(name) must be an integer.",
        )
        parsed = Int(raw)
        parsed >= minimum || error(
            "D3 Stage-2 CMA $(name) must be at least $(minimum).",
        )
        parsed
    end
    seed = integer_value("seed")
    popsize = integer_value("popsize"; minimum=2)
    maxiter = integer_value("maxiter"; minimum=1)
    maxfevals = integer_value("maxfevals"; minimum=popsize)
    return Dict(
        "algorithm" => "bounded_cma_es_only",
        "initial_mean" => normalized_initial,
        "seed" => seed,
        "sigma" => _positive_real(configuration["sigma"], "D3 Stage-2 CMA sigma"),
        "popsize" => popsize,
        "maxiter" => maxiter,
        "maxfevals" => maxfevals,
        "ftol" => _positive_real(configuration["ftol"], "D3 Stage-2 CMA ftol"),
        "xtol" => _positive_real(configuration["xtol"], "D3 Stage-2 CMA xtol"),
    )
end

function _sha256_text(value, label)
    text = lowercase(strip(String(value)))
    occursin(r"^[0-9a-f]{64}$", text) || error(
        "$(label) must contain 64 lowercase hexadecimal characters.",
    )
    return text
end

_is_json_number(value) =
    (value isa Integer && !(value isa Bool)) || value isa AbstractFloat

function _json_values_equal(left, right)
    if left isa Bool || right isa Bool
        return left isa Bool && right isa Bool && left === right
    elseif _is_json_number(left) || _is_json_number(right)
        return _is_json_number(left) && _is_json_number(right) && left == right
    elseif left isa AbstractDict || right isa AbstractDict
        left isa AbstractDict && right isa AbstractDict || return false
        all(key -> key isa AbstractString, keys(left)) &&
            all(key -> key isa AbstractString, keys(right)) || return false
        Set(keys(left)) == Set(keys(right)) || return false
        return all(key -> _json_values_equal(left[key], right[key]), keys(left))
    elseif left isa AbstractVector || right isa AbstractVector
        left isa AbstractVector && right isa AbstractVector || return false
        length(left) == length(right) || return false
        return all(
            _json_values_equal(left[index], right[index])
            for index in eachindex(left, right)
        )
    elseif left isa AbstractString || right isa AbstractString
        return left isa AbstractString && right isa AbstractString && left == right
    elseif left === nothing || right === nothing
        return left === nothing && right === nothing
    end
    return false
end

_file_sha256(path) = bytes2hex(SHA.sha256(read(path)))

function _model_identity(source, label)
    names = (
        :circuit_plan_sha256,
        :capacitance_sha256,
        :inverse_inductance_sha256,
        :selector_sha256,
    )
    has_field(name) = hasproperty(source, name) ||
        (source isa AbstractDict && (haskey(source, name) || haskey(source, String(name))))
    get_field(name) = hasproperty(source, name) ? getproperty(source, name) :
        haskey(source, name) ? source[name] : source[String(name)]
    all(has_field, names) || error(
        "$(label) must bind all four D3 model-identity hashes.",
    )
    return NamedTuple{names}(Tuple(
        _sha256_text(get_field(name), "$(label).$(name)")
        for name in names
    ))
end

function _winner_record(optimization::OptimizationResult)
    record_id = optimization.promotion.candidate_record_id
    isnothing(record_id) && error(
        "D3 Stage-2 optimization has no incumbent candidate to publish.",
    )
    matches = [record for record in optimization.history if record.record_id == record_id]
    length(matches) == 1 || error(
        "D3 Stage-2 promotion candidate must identify exactly one history record.",
    )
    record = only(matches)
    record.evaluation isa ValidEvaluation || error(
        "D3 Stage-2 winner must be a valid evaluator result.",
    )
    isnothing(record.cost) && error("D3 Stage-2 winner must retain its optimizer cost.")
    return record
end

function _require_same_grid(actual, expected, label)
    values = Float64.(collect(actual))
    values == expected || error("$(label) frequency grid disagrees with the Run specification.")
    return values
end

function _require_complex_trace(values, expected_length, label)
    trace = ComplexF64.(collect(values))
    length(trace) == expected_length || error("$(label) length disagrees with its frequency grid.")
    all(isfinite, trace) || error("$(label) must contain only finite values.")
    return trace
end

function _flatten_fixed_matrix(value, label)
    rows = collect(value)
    length(rows) == 2 && all(row -> length(row) == 2, rows) || error(
        "$(label) must be an ordered 2x2 matrix.",
    )
    return Float64[
        rows[1][1],
        rows[1][2],
        rows[2][1],
        rows[2][2],
    ]
end

function _q2d_snapshot_from_fixed_line_identity(value)
    identity = _string_key_dict(
        _json_value(value, "D3 fixed-line identity"),
        "D3 fixed-line identity",
    )
    fields = (
        "contract_id",
        "q2d_artifact_id",
        "q2d_artifact_sha256",
        "q2d_topology_id",
        "q2d_geometry_um",
        "q2d_single_case_id",
        "q2d_pair_case_id",
        "q2d_solver",
        "q2d_loss_model",
        "q2d_authority",
        "section_length_m",
        "mtl_section_length_m",
        "readout_l_per_m_h",
        "readout_c_per_m_f",
        "filter_l_per_m_h",
        "filter_c_per_m_f",
        "l_matrix_per_m_h",
        "c_matrix_per_m_f",
        "coupling_orientation",
    )
    Set(keys(identity)) == Set(fields) || error(
        "D3 fixed-line identity fields must be exactly $(collect(fields)).",
    )
    identity["contract_id"] == "d3-selected-continuous-ground-fixed-line.v2" ||
        error("D3 fixed-line identity uses the wrong contract.")
    readout_l = _positive_real(
        identity["readout_l_per_m_h"],
        "D3 fixed-line readout L per metre",
    )
    readout_c = _positive_real(
        identity["readout_c_per_m_f"],
        "D3 fixed-line readout C per metre",
    )
    readout_l == _positive_real(
        identity["filter_l_per_m_h"],
        "D3 fixed-line filter L per metre",
    ) && readout_c == _positive_real(
        identity["filter_c_per_m_f"],
        "D3 fixed-line filter C per metre",
    ) || error(
        "D3 fixed-line identity must retain one artifact-owned single-line L/C pair.",
    )
    return _validated_q2d_spec(Dict(
        "artifact_id" => identity["q2d_artifact_id"],
        "artifact_sha256" => identity["q2d_artifact_sha256"],
        "topology_id" => identity["q2d_topology_id"],
        "single_case_id" => identity["q2d_single_case_id"],
        "pair_case_id" => identity["q2d_pair_case_id"],
        "geometry_um" => identity["q2d_geometry_um"],
        "solver" => identity["q2d_solver"],
        "loss_model" => identity["q2d_loss_model"],
        "authority" => identity["q2d_authority"],
        "single_l_per_m_h" => readout_l,
        "single_c_per_m_f" => readout_c,
        "l_matrix_per_m_h" => _flatten_fixed_matrix(
            identity["l_matrix_per_m_h"],
            "D3 fixed-line L matrix",
        ),
        "c_matrix_per_m_f" => _flatten_fixed_matrix(
            identity["c_matrix_per_m_f"],
            "D3 fixed-line C matrix",
        ),
        "coupling_orientation" => identity["coupling_orientation"],
        "section_length_m" => identity["section_length_m"],
        "mtl_section_length_m" => identity["mtl_section_length_m"],
    ))
end

function _foundation_q2d_snapshot(foundation)
    response_match = foundation.stage.response_match
    required = (
        :q2d_artifact_id,
        :q2d_artifact_sha256,
        :topology_id,
        :fixed_line_input_sha256,
        :fixed_line_input_identity,
        :fixed_line_input_identity_canonical_json,
        :match_evidence,
    )
    all(name -> hasproperty(response_match, name), required) || error(
        "D3 Stage-2 response match is missing fixed-line publication provenance.",
    )
    canonical = response_match.fixed_line_input_identity_canonical_json
    canonical isa AbstractString && !isempty(canonical) || error(
        "D3 Stage-2 fixed-line canonical identity must be non-empty text.",
    )
    canonical = String(canonical)
    canonical == JSON3.write(response_match.fixed_line_input_identity) || error(
        "D3 Stage-2 fixed-line canonical JSON disagrees with its normalized identity.",
    )
    identity_sha256 = bytes2hex(SHA.sha256(codeunits(canonical)))
    identity_sha256 == _sha256_text(
        response_match.fixed_line_input_sha256,
        "D3 response-match fixed-line identity SHA-256",
    ) || error(
        "D3 Stage-2 fixed-line identity SHA-256 disagrees with its canonical JSON.",
    )
    snapshot = _q2d_snapshot_from_fixed_line_identity(
        response_match.fixed_line_input_identity,
    )
    String(response_match.q2d_artifact_id) == snapshot["artifact_id"] || error(
        "D3 response-match artifact id disagrees with its fixed-line identity.",
    )
    _sha256_text(
        response_match.q2d_artifact_sha256,
        "D3 response-match Q2D artifact SHA-256",
    ) == snapshot["artifact_sha256"] || error(
        "D3 response-match artifact SHA-256 disagrees with its fixed-line identity.",
    )
    String(response_match.topology_id) == snapshot["topology_id"] || error(
        "D3 response-match topology disagrees with its fixed-line identity.",
    )
    reference = response_match.match_evidence.reference_model
    Float64(reference.section_length_m) == snapshot["section_length_m"] &&
        Float64(reference.mtl_section_length_m) == snapshot["mtl_section_length_m"] || error(
        "D3 response-match reference grids disagree with its fixed-line identity.",
    )
    return snapshot
end

function _validate_q2d_publication_binding(foundation, specification)
    snapshot = _foundation_q2d_snapshot(foundation)
    _json_values_equal(snapshot, specification.q2d_spec) || error(
        "D3 Stage-2 caller Q2D snapshot disagrees with the artifact-derived fixed-line identity.",
    )
    return snapshot
end

function _revalidate_lc_qualification(
    qualification::D3AuthorizedStage2LC,
    candidate,
    specification,
)
    specification.lc_qualification_policy_sha256 ==
        D3_LC_QUALIFICATION_POLICY_SHA256 || error(
        "D3 Stage-2 RunSpec LC qualification policy changed after construction.",
    )
    return revalidate_d3_stage2_lc_receipt(
        qualification,
        candidate;
        q2d_artifact_sha256=specification.q2d_spec["artifact_sha256"],
    )
end

function _revalidate_full_qrp_qualification(
    qualification::D3AuthorizedStage2FullQRP,
    foundation,
    candidate,
    lc_qualification,
    specification,
)
    specification.full_qrp_qualification_policy_sha256 ==
        D3_FULL_QRP_QUALIFICATION_POLICY_SHA256 || error(
        "D3 Stage-2 RunSpec Full-QRP qualification policy changed after construction.",
    )
    return revalidate_d3_stage2_full_qrp_receipt(
        qualification,
        foundation,
        candidate,
        lc_qualification;
        q2d_artifact_sha256=specification.q2d_spec["artifact_sha256"],
    )
end

function _validate_foundation(
    foundation,
    candidate,
    specification,
    qualification::D3AuthorizedStage2LC,
)
    renewed = _revalidate_lc_qualification(
        qualification,
        candidate,
        specification,
    )
    hasproperty(foundation, :contract_id) &&
        foundation.contract_id == FOUNDATION_CONTRACT || error(
        "D3 Stage-2 result requires the current candidate foundation.",
    )
    hasproperty(foundation, :stage_id) && foundation.stage_id == :stage2_equivalent ||
        error("D3 Stage-2 result received a non-Stage-2 foundation.")
    hasproperty(foundation, :model_family) &&
        foundation.model_family == :equivalent_exact_n || error(
        "D3 Stage-2 result requires the Equivalent Exact-N model family.",
    )
    hasproperty(foundation, :objective_ready) && foundation.objective_ready === true ||
        error("D3 Stage-2 foundation is not objective-ready.")
    foundation.stage.candidate == candidate || error(
        "Re-evaluated Stage-2 foundation does not retain the optimizer winner candidate.",
    )
    hasproperty(foundation.stage, :lc_qualification) || error(
        "D3 Stage-2 foundation does not retain its LC qualification authority.",
    )
    stage_qualification = foundation.stage.lc_qualification
    stage_qualification isa D3AuthorizedStage2LC || error(
        "D3 Stage-2 foundation retains an unsupported LC qualification authority.",
    )
    stage_renewed = _revalidate_lc_qualification(
        stage_qualification,
        candidate,
        specification,
    )
    validate_d3_stage2_lc_authorization_match(stage_renewed, renewed)
    _validate_q2d_publication_binding(foundation, specification)
    return _model_identity(
        foundation.cqed_handoff.source_model_identity,
        "D3 Stage-2 foundation model identity",
    )
end

function _validate_objective(objective, model_identity, winner_cost)
    hasproperty(objective, :contract_id) &&
        objective.contract_id == OBJECTIVE_CONTRACT || error(
        "D3 Stage-2 result requires the revision-10 objective receipt.",
    )
    hasproperty(objective, :stage_id) && objective.stage_id == :stage2_equivalent ||
        error("D3 Stage-2 result received a non-Stage-2 objective.")
    hasproperty(objective, :model_family) &&
        objective.model_family == :equivalent_exact_n || error(
        "D3 Stage-2 objective uses the wrong model family.",
    )
    _model_identity(objective.model_identity, "D3 Stage-2 objective model identity") ==
        model_identity || error("D3 Stage-2 foundation and objective model identities disagree.")
    hasproperty(objective, :authority) && objective.authority == OBJECTIVE_AUTHORITY ||
        error(
            "D3 Stage-2 objective authority does not equal the Human-approved revision-10 contract.",
        )
    cost = Float64(objective.cost)
    isfinite(cost) && cost >= 0 || error("D3 Stage-2 objective cost must be finite and non-negative.")
    isapprox(cost, Float64(winner_cost); rtol=1.0e-12, atol=1.0e-12) || error(
        "Re-evaluated revision-10 objective cost disagrees with the optimizer winner cost.",
    )
    return cost
end

function _validate_optimization_provenance(optimization, specification)
    configuration = specification.optimizer_configuration
    optimization.cma.declared_iteration_budget == configuration["maxiter"] || error(
        "D3 Stage-2 CMA maxiter disagrees with the Run specification.",
    )
    optimization.cma.declared_evaluation_budget == configuration["maxfevals"] || error(
        "D3 Stage-2 CMA maxfevals disagrees with the Run specification.",
    )
    initial_records = [
        record for record in optimization.history
        if record.record_id == optimization.initial_seed_record_id
    ]
    length(initial_records) == 1 || error(
        "D3 Stage-2 Run must retain exactly one declared initial-seed record.",
    )
    initial_candidate = only(initial_records).candidate
    initial_mean = configuration["initial_mean"]
    for name in CANDIDATE_NAMES
        hasproperty(initial_candidate, name) || error(
            "D3 Stage-2 initial-seed record is missing $(name).",
        )
        Float64(getproperty(initial_candidate, name)) == initial_mean[String(name)] ||
            error("D3 Stage-2 initial-seed record disagrees with initial_mean.$(name).")
    end
    return nothing
end

function _validate_candidate_bounds(candidate, bounds, label)
    for name in CANDIDATE_NAMES
        hasproperty(candidate, name) || error("$(label) is missing $(name).")
        value = Float64(getproperty(candidate, name))
        lower, upper = bounds[String(name)]
        lower <= value <= upper || error(
            "$(label) $(name)=$(value) is outside its declared bounds.",
        )
    end
    return nothing
end

function _validate_qubit_result(qubit, foundation, frequencies)
    _require_same_grid(qubit.frequency_hz, frequencies, "D3 qubit admittance")
    hasproperty(qubit, :contract_id) &&
        qubit.contract_id == "d3-stage2-hb-qubit-differential-admittance.candidate-v1" ||
        error("D3 Stage-2 result requires the HB/direct qubit-admittance receipt.")
    provenance = qubit.direct.diagnostics.source_model_provenance
    foundation_identity = _model_identity(
        foundation.cqed_handoff.source_model_identity,
        "D3 Stage-2 foundation model identity",
    )
    _model_identity(qubit.model_identity, "D3 qubit HB model identity") ==
        foundation_identity || error(
        "D3 qubit HB result and Stage-2 foundation model identities disagree.",
    )
    _model_identity(provenance, "D3 qubit direct model identity") == foundation_identity ||
        error("D3 qubit admittance and Stage-2 foundation model identities disagree.")
    count = length(frequencies)
    for (name, values) in (
        (:hb_differential_admittance_s, qubit.hb_differential_admittance_s),
        (:direct_differential_admittance_s, qubit.direct.differential_admittance_s),
    )
        _require_complex_trace(values, count, "D3 qubit $(name)")
    end
    return nothing
end

"""
    evaluate_stage2_winner(optimization, specification; ...)

Select the optimizer's incumbent, evaluate one canonical physical foundation,
and derive the objective, HB trace, and weighted-qubit admittance from that same
foundation. Callbacks receive `(foundation, specification)` except the
foundation callback, which receives
`(candidate, specification, lc_qualification)`. The objective callback receives
`(foundation, specification, full_qrp_qualification)` and is reached only after
both exact candidate receipts have been revalidated.
"""
function evaluate_stage2_winner(
    optimization::OptimizationResult,
    specification::Stage2RunSpec;
    lc_qualification_receipt=nothing,
    full_qrp_qualification_receipt=nothing,
    foundation_evaluator,
    objective_evaluator,
    hb_evaluator,
    qubit_evaluator,
)
    error(
        "The LC/Equivalent-before-Objective Stage-2 winner path is superseded by the revision-10 direct-Hybridized search authority. Winner-only closure must use a separately bound post-winner entry point.",
    )
    _validate_optimization_provenance(optimization, specification)
    winner = _winner_record(optimization)
    _validate_candidate_bounds(
        winner.candidate,
        specification.bounds,
        "D3 Stage-2 optimizer winner",
    )
    lc_qualification = authorize_d3_stage2_lc_receipt(
        lc_qualification_receipt,
        winner.candidate;
        q2d_artifact_sha256=specification.q2d_spec["artifact_sha256"],
    )
    foundation = foundation_evaluator(
        winner.candidate,
        specification,
        lc_qualification,
    )
    model_identity = _validate_foundation(
        foundation,
        winner.candidate,
        specification,
        lc_qualification,
    )
    _require_same_grid(
        foundation.response_closure.frequency_hz,
        specification.response_frequency_hz,
        "D3 Stage-2 Exact/direct closure",
    )
    full_qrp_qualification = authorize_d3_stage2_full_qrp_receipt(
        full_qrp_qualification_receipt,
        foundation,
        winner.candidate,
        lc_qualification;
        q2d_artifact_sha256=specification.q2d_spec["artifact_sha256"],
    )
    objective = evaluate_d3_stage2_objective_with_evidence(
        full_qrp_qualification,
        foundation,
        winner.candidate,
        lc_qualification;
        q2d_artifact_sha256=specification.q2d_spec["artifact_sha256"],
        objective_evaluator=(current_foundation, current_qualification) ->
            objective_evaluator(
                current_foundation,
                specification,
                current_qualification,
            ),
    )
    _validate_objective(objective, model_identity, winner.cost)

    hb = hb_evaluator(foundation, specification)
    _require_same_grid(hb.frequency_hz, specification.response_frequency_hz, "D3 Stage-2 HB")
    _model_identity(hb.model_identity, "D3 Stage-2 HB model identity") ==
        model_identity || error(
        "D3 Stage-2 HB trace and canonical foundation model identities disagree.",
    )
    _require_complex_trace(
        hb.s21,
        length(specification.response_frequency_hz),
        "D3 Stage-2 HB S21",
    )
    qubit = qubit_evaluator(foundation, specification)
    _validate_qubit_result(qubit, foundation, specification.qubit_frequency_hz)
    return Stage2EvaluatedResult(
        specification,
        optimization,
        winner,
        lc_qualification,
        full_qrp_qualification,
        foundation,
        objective,
        hb,
        qubit,
    )
end

function _revalidate_evaluated_result(evaluated::Stage2EvaluatedResult)
    specification = evaluated.specification
    optimization = evaluated.optimization
    _validate_optimization_provenance(optimization, specification)
    winner = _winner_record(optimization)
    winner.record_id == evaluated.winner_record.record_id &&
        winner.candidate_id == evaluated.winner_record.candidate_id &&
        winner.candidate == evaluated.winner_record.candidate &&
        winner.cost == evaluated.winner_record.cost || error(
        "D3 Stage-2 retained winner no longer equals the optimizer incumbent.",
    )
    _validate_candidate_bounds(
        winner.candidate,
        specification.bounds,
        "D3 Stage-2 retained optimizer winner",
    )
    model_identity = _validate_foundation(
        evaluated.foundation,
        winner.candidate,
        specification,
        evaluated.lc_qualification,
    )
    full_qrp_qualification = _revalidate_full_qrp_qualification(
        evaluated.full_qrp_qualification,
        evaluated.foundation,
        winner.candidate,
        evaluated.lc_qualification,
        specification,
    )
    _validate_objective(evaluated.objective, model_identity, winner.cost)
    lc_qualification = _revalidate_lc_qualification(
        evaluated.lc_qualification,
        winner.candidate,
        specification,
    )
    return (
        lc_qualification=lc_qualification,
        full_qrp_qualification=full_qrp_qualification,
    )
end

function _json_value(value, label="value")
    if value === nothing || value isa Bool || value isa AbstractString
        return value
    elseif value isa Symbol
        return String(value)
    elseif value isa Real
        number = Float64(value)
        isfinite(number) || error("$(label) contains a non-finite number.")
        return value isa Integer ? Int(value) : number
    elseif value isa Complex
        isfinite(value) || error("$(label) contains a non-finite complex number.")
        return Dict("real" => Float64(real(value)), "imag" => Float64(imag(value)))
    elseif value isa NamedTuple
        return Dict(
            String(name) => _json_value(item, "$(label).$(name)")
            for (name, item) in pairs(value)
        )
    elseif value isa AbstractDict
        return Dict(
            String(key) => _json_value(item, "$(label).$(key)")
            for (key, item) in pairs(value)
        )
    elseif value isa AbstractArray || value isa Tuple
        return [_json_value(item, "$(label)[]") for item in value]
    end
    error("$(label) contains unsupported $(typeof(value)); refusing lossy serialization.")
end

function _history_record(record, evaluation_index)
    record.evaluation isa Union{ValidEvaluation,RejectedEvaluation} || error(
        "D3 optimization history contains an unsupported evaluation type.",
    )
    result = Dict(
        "evaluation" => Int(evaluation_index),
        "cost" => record.cost,
        "candidate" => _json_value(record.candidate, "history candidate"),
        "record_id" => record.record_id,
        "candidate_id" => record.candidate_id,
        "stage" => String(record.stage),
        "cache_hit" => record.cache_hit,
    )
    if record.evaluation isa RejectedEvaluation
        result["rejection"] = string(
            record.evaluation.code,
            ": ",
            record.evaluation.reason,
        )
    end
    return result
end

function _write_json(path, value)
    open(path, "w") do io
        JSON3.pretty(io, value)
        println(io)
    end
    return path
end

function _write_s21(path, evaluated)
    closure = evaluated.foundation.response_closure
    frequencies = evaluated.specification.response_frequency_hz
    direct = _require_complex_trace(closure.direct.s21, length(frequencies), "Direct S21")
    exact = _require_complex_trace(
        closure.analytical.exact.s21,
        length(frequencies),
        "Exact-12 S21",
    )
    hb = _require_complex_trace(evaluated.hb_trace.s21, length(frequencies), "HB S21")
    open(path, "w") do io
        println(
            io,
            "frequency_hz,direct_real,direct_imag,exact_real,exact_imag,hb_real,hb_imag",
        )
        for index in eachindex(frequencies)
            @printf(
                io,
                "%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g\n",
                frequencies[index],
                real(direct[index]),
                imag(direct[index]),
                real(exact[index]),
                imag(exact[index]),
                real(hb[index]),
                imag(hb[index]),
            )
        end
    end
    return path
end

function _write_qubit(path, evaluated)
    result = evaluated.qubit_admittance
    frequencies = evaluated.specification.qubit_frequency_hz
    open(path, "w") do io
        println(
            io,
            "frequency_hz,hb_y_eff_real_s,hb_y_eff_imag_s,direct_y_eff_real_s," *
            "direct_y_eff_imag_s,hb_t1_s,direct_t1_s,c_q_eff_f,alpha,beta," *
            "kron_condition_number,hb_direct_abs_y_residual_s",
        )
        for index in eachindex(frequencies)
            @printf(
                io,
                "%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g\n",
                frequencies[index],
                real(result.hb_differential_admittance_s[index]),
                imag(result.hb_differential_admittance_s[index]),
                real(result.direct.differential_admittance_s[index]),
                imag(result.direct.differential_admittance_s[index]),
                result.hb_purcell_t1_s[index],
                result.direct.purcell_t1_s[index],
                result.effective_differential_capacitance_f,
                result.alpha,
                result.beta,
                result.kron_condition_number[index],
                result.hb_direct_abs_y_residual_s[index],
            )
        end
    end
    return path
end

function _validate_linear_quantity_payload(
    payload,
    source_summary_sha256,
    model_identity,
)
    record = _string_key_dict(payload, "D3 linear-quantity payload")
    required = (
        "schema_version",
        "source_summary_sha256",
        "objective_contract_id",
        "objective_authority",
        "coordinate_foundation",
        "anchored_oscillator_representation",
        "matched_open_q_feedline_schur_downfolded_rp_effective_representation",
        "fully_hybridized_closed_normal_mode_spectrum",
        "matched_open_port_poles",
        "model_identity",
    )
    Set(keys(record)) == Set(required) || error(
        "D3 linear-quantity payload must contain exactly the V4 review projections.",
    )
    record["schema_version"] == "d3-stage2-linear-quantity-review.v4" || error(
        "D3 linear-quantity payload uses the wrong schema.",
    )
    record["source_summary_sha256"] == source_summary_sha256 || error(
        "D3 linear-quantity payload did not bind the canonical summary.",
    )
    record["objective_contract_id"] == OBJECTIVE_CONTRACT || error(
        "D3 linear-quantity payload uses the wrong objective contract.",
    )
    authority = _string_key_dict(
        record["objective_authority"],
        "D3 linear-quantity objective authority",
    )
    authority == _json_value(OBJECTIVE_AUTHORITY, "revision-10 authority") || error(
        "D3 linear-quantity payload does not carry the complete revision-10 authority.",
    )
    _model_identity(record["model_identity"], "D3 linear-quantity model identity") ==
        model_identity || error(
        "D3 linear-quantity payload and canonical foundation model identities disagree.",
    )
    anchored = _string_key_dict(
        record["anchored_oscillator_representation"],
        "D3 anchored oscillator payload",
    )
    anchored["coupling_state"] == "qrp_on" &&
        anchored["boundary"] == "closed_conservative_block" &&
        anchored["coordinate_basis"] ==
        "reduced_physically_anchored_flux_charge_coordinates" &&
        anchored["representation"] == "anchored_bare_coordinate_oscillator" &&
        anchored["coordinate_rotation"] == "none" &&
        anchored["normalization"] ==
            "Z_i_equals_sqrt_C_inverse_ii_over_K_ii" || error(
        "D3 anchored oscillator payload does not retain its accepted basis/normalization semantics.",
    )
    effective = _string_key_dict(
        record["matched_open_q_feedline_schur_downfolded_rp_effective_representation"],
        "D3 q+feedline-downfolded RP effective payload",
    )
    effective_fields = (
        "contract_id",
        "coupling_state",
        "external_port_state",
        "retained_coordinates",
        "eliminated_coordinates",
        "coordinate_basis",
        "representation",
        "diagonal_root_extraction",
        "diagonal_roots",
        "residue_normalized_exchange",
        "determinant_closure",
        "gate_policy",
        "context_validation",
        "operator_diagnostics",
        "source_model_identity",
        "provenance",
    )
    Set(keys(effective)) == Set(effective_fields) || error(
        "D3 q+feedline-downfolded RP payload must contain exactly the V4 effective fields.",
    )
    effective["contract_id"] ==
        "d3-q-feedline-downfolded-rp-effective-operator.v1" &&
        effective["coupling_state"] == "qrp_on" &&
        effective["external_port_state"] == "matched_open" &&
        effective["retained_coordinates"] == ["r", "p"] &&
        effective["eliminated_coordinates"] == ["q", "f1", "fc", "f2"] &&
        effective["coordinate_basis"] ==
            "physically_anchored_rp_coordinates_no_retained_pair_rotation" &&
        effective["representation"] ==
            "frequency_dependent_dynamic_effective_operator" &&
        effective["diagonal_root_extraction"] ==
            "principal_subsystem_matched_open_poles_in_declared_band" || error(
        "D3 q+feedline-downfolded RP payload does not retain its effective-operator semantics.",
    )
    exchange = _string_key_dict(
        effective["residue_normalized_exchange"],
        "D3 q+feedline-downfolded RP exchange payload",
    )
    exchange["square_root_branch"] == "principal_complex_square_root" || error(
        "D3 q+feedline-downfolded RP payload does not declare the extraction branch.",
    )
    operator_diagnostics = _string_key_dict(
        effective["operator_diagnostics"],
        "D3 q+feedline-downfolded RP operator diagnostics",
    )
    Set(keys(operator_diagnostics)) == Set(("readout", "midpoint", "filter")) || error(
        "D3 q+feedline-downfolded RP operator diagnostics must contain exactly three samples.",
    )
    diagnostic_fields = Set((
        "elimination_condition_number",
        "relative_elimination_solve_residual",
        "relative_derivative_solve_residual",
        "effective_reciprocity_error",
    ))
    all(
        sample -> Set(keys(_string_key_dict(
            operator_diagnostics[sample],
            "D3 q+feedline-downfolded RP $(sample) diagnostics",
        ))) == diagnostic_fields,
        ("readout", "midpoint", "filter"),
    ) || error(
        "D3 q+feedline-downfolded RP operator diagnostic fields are incomplete.",
    )
    effective_identity = _model_identity(
        effective["source_model_identity"],
        "D3 q+feedline-downfolded RP source model identity",
    )
    effective_identity == model_identity || error(
        "D3 q+feedline-downfolded RP payload and canonical foundation identities disagree.",
    )
    closed = _string_key_dict(
        record["fully_hybridized_closed_normal_mode_spectrum"],
        "D3 closed normal-mode payload",
    )
    closed["spectrum"] == "fully_hybridized_closed_normal_modes" &&
        closed["coupling_state"] == "qrp_on" &&
        closed["boundary"] == "closed" &&
        closed["construction"] ==
            "generalized_eigenproblem_K_u_equals_omega2_C_u" &&
        closed["identity_assignment"] == "none" &&
        closed["display_order"] == "ascending_frequency_only" || error(
        "D3 closed normal-mode payload does not retain its spectrum semantics.",
    )
    matched_open = _string_key_dict(
        record["matched_open_port_poles"],
        "D3 matched-open pole payload",
    )
    matched_open["response_class"] == "matched_open_port_response" &&
        matched_open["coupling_state"] == "qrp_on" &&
        matched_open["external_port_state"] == "matched_open" &&
        matched_open["basis_claim"] == "none" &&
        matched_open["identity_assignment"] ==
            "global_normalized_stored_energy_overlap" || error(
        "D3 matched-open pole payload does not retain its response/identity semantics.",
    )
    return record
end

function _effective_rp_linear_review_payload(foundation)
    hasproperty(foundation, :extractions) &&
        hasproperty(foundation.extractions, :effective_rp) || error(
        "D3 Stage-2 foundation is missing the q+feedline-downfolded RP extraction.",
    )
    effective = foundation.extractions.effective_rp
    effective.contract_id ==
        "d3-q-feedline-downfolded-rp-effective-operator.v1" || error(
        "D3 Stage-2 foundation uses the wrong q+feedline-downfolded RP extraction.",
    )
    root_record(root) = Dict(
        "coordinate" => String(root.coordinate),
        "complex_frequency_hz" => _json_value(root.root_hz, "effective diagonal root"),
        "frequency_hz" => root.frequency_hz,
        "external_linewidth_hz" => root.external_linewidth_hz,
        "frequency_band_hz" => root.frequency_band_hz,
        "principal_subsystem_coordinates" => string.(root.principal_subsystem_coordinates),
        "principal_subsystem_pole_index" => root.principal_subsystem_pole_index,
        "relative_root_residual" => root.relative_root_residual,
    )
    return Dict(
        "contract_id" => String(effective.contract_id),
        "coupling_state" => String(effective.coupling_state),
        "external_port_state" => String(effective.external_port_state),
        "retained_coordinates" => string.(effective.retained_coordinates),
        "eliminated_coordinates" => string.(effective.eliminated_coordinates),
        "coordinate_basis" =>
            "physically_anchored_rp_coordinates_no_retained_pair_rotation",
        "representation" => "frequency_dependent_dynamic_effective_operator",
        "diagonal_root_extraction" =>
            "principal_subsystem_matched_open_poles_in_declared_band",
        "diagonal_roots" => Dict(
            "r" => root_record(effective.readout),
            "p" => root_record(effective.filter),
        ),
        "residue_normalized_exchange" => Dict(
            "midpoint_angular_frequency_rad_s" => _json_value(
                effective.midpoint_angular_frequency_rad_s,
                "effective RP midpoint",
            ),
            "residue_slopes" => _json_value(
                effective.residue_slopes,
                "effective RP residue slopes",
            ),
            "residue_normalization" => _json_value(
                effective.residue_normalization,
                "effective RP residue normalization",
            ),
            "square_root_branch" => String(effective.square_root_branch),
            "coupling_samples_rad_s" => _json_value(
                effective.coupling_samples_rad_s,
                "effective RP coupling samples",
            ),
            "effective_exchange_rad_s" => _json_value(
                effective.effective_exchange_rad_s,
                "effective RP exchange",
            ),
            "coherent_exchange_hz" => effective.coherent_exchange_hz,
            "total_exchange_hz" => effective.total_exchange_hz,
            "dissipative_cross_coupling_hz" =>
                effective.dissipative_cross_coupling_hz,
            "maximum_pairwise_coupling_spread_rad_s" =>
                effective.maximum_pairwise_coupling_spread_rad_s,
            "relative_coupling_spread" => effective.relative_coupling_spread,
        ),
        "determinant_closure" => _json_value(
            effective.determinant_closure,
            "effective RP determinant closure",
        ),
        "gate_policy" => _json_value(
            effective.gate_policy,
            "effective RP gate policy",
        ),
        "context_validation" => _json_value(
            effective.context_validation,
            "effective RP context validation",
        ),
        "operator_diagnostics" => Dict(
            String(name) => _json_value(
                operator.diagnostics,
                "effective RP $(name) operator diagnostics",
            )
            for (name, operator) in pairs((
                readout=effective.operator_samples.readout,
                midpoint=effective.operator_samples.midpoint,
                filter=effective.operator_samples.filter,
            ))
        ),
        "source_model_identity" => _json_value(
            effective.source_model_identity,
            "effective RP source model identity",
        ),
        "provenance" => _json_value(
            effective.provenance,
            "effective RP provenance",
        ),
    )
end

function _summary(evaluated, artifact_hashes)
    qualifications = _revalidate_evaluated_result(evaluated)
    lc_qualification = qualifications.lc_qualification
    full_qrp_qualification = qualifications.full_qrp_qualification
    optimization = evaluated.optimization
    foundation = evaluated.foundation
    stage = foundation.stage
    objective = evaluated.objective
    model_identity = _model_identity(
        foundation.cqed_handoff.source_model_identity,
        "D3 Stage-2 foundation model identity",
    )
    q2d_snapshot = _validate_q2d_publication_binding(
        foundation,
        evaluated.specification,
    )
    metrics = foundation.metrics
    required_metrics = (
        :fr_eff_q_feedline_downfolded_qrp_on_ext_on_hz,
        :fp_eff_q_feedline_downfolded_qrp_on_ext_on_hz,
        :J_rp_eff_q_feedline_downfolded_coherent_hz,
        :notch_rp_on_hz,
        :kappa_sum_qrp_on_ext_on_hz,
        :eta_r_qrp_on,
        :eta_p_qrp_on,
        :effective_diagonal_frequency_extraction,
        :effective_exchange_extraction,
        :notch_authority,
        :linewidth_pole_scope,
        :primary_linewidth_extraction,
    )
    all(name -> hasproperty(metrics, name), required_metrics) || error(
        "D3 Stage-2 foundation is missing one or more revision-10 summary metrics.",
    )
    history = optimization.history
    valid_evaluations = count(record -> !isnothing(record.cost), history)
    return Dict(
        "schema_version" => SUMMARY_SCHEMA,
        "run_id" => evaluated.specification.run_id,
        "status" => "converging_candidate_complete",
        "objective_contract_id" => String(objective.contract_id),
        "objective_authority" =>
            _json_value(objective.authority, "objective authority"),
        "model_identity" => _json_value(model_identity, "model identity"),
        "slot_hz" => evaluated.specification.slot_hz,
        "q2d_spec" => _json_value(q2d_snapshot, "artifact-derived Q2D specification"),
        "lc_qualification_receipt" => _json_value(
            d3_lc_qualification_receipt_identity(lc_qualification),
            "LC qualification receipt identity",
        ),
        "lc_qualification_policy_sha256" => D3_LC_QUALIFICATION_POLICY_SHA256,
        "full_qrp_qualification_receipt" => _json_value(
            d3_full_qrp_qualification_receipt_identity(full_qrp_qualification),
            "Full-QRP qualification receipt identity",
        ),
        "full_qrp_qualification_policy_sha256" =>
            D3_FULL_QRP_QUALIFICATION_POLICY_SHA256,
        "bounds" => _json_value(evaluated.specification.bounds, "optimizer bounds"),
        "cma" => Dict(
            "evaluations" => length(history),
            "valid_evaluations" => valid_evaluations,
            "rejected_evaluations" => length(history) - valid_evaluations,
            "configuration" => _json_value(
                evaluated.specification.optimizer_configuration,
                "CMA configuration",
            ),
            "state" => String(optimization.cma.state),
            "termination_reason" => optimization.cma.termination_reason,
            "observed_iterations" => optimization.cma.observed_iterations,
            "declared_iteration_budget" => optimization.cma.declared_iteration_budget,
            "declared_evaluation_budget" => optimization.cma.declared_evaluation_budget,
            "initial_seed_record_id" => optimization.initial_seed_record_id,
        ),
        "best_candidate" =>
            _json_value(evaluated.winner_record.candidate, "winner candidate"),
        "best_resolved_lc" => _json_value(
            stage.resolved_equivalent_candidate,
            "resolved Equivalent candidate",
        ),
        "best_metrics" => Dict(
            String(name) => _json_value(getproperty(metrics, name), "Stage-2 metric $(name)")
            for name in required_metrics
        ),
        "best_objective" => Dict(
            "cost" => objective.cost,
            "target_gates" =>
                _json_value(objective.target_gates, "objective target gates"),
            "target_gates_pass" => objective.target_gates_pass,
            "normalized_residuals" =>
                _json_value(objective.normalized_residuals, "objective residuals"),
        ),
        "condition_manifest" => Dict(
            "id" => optimization.condition_manifest_id,
            "sha256" => optimization.condition_manifest_sha256,
            "approval_status" => optimization.condition_manifest_approval_status,
        ),
        "winner_selection" => Dict(
            "record_id" => evaluated.winner_record.record_id,
            "candidate_id" => evaluated.winner_record.candidate_id,
            "state" => String(optimization.promotion.state),
            "reason" => optimization.promotion.reason,
        ),
        "response_match" => Dict(
            "mapping_id" => stage.response_match.mapping_id,
            "mapping_sha256" => stage.response_match.mapping_sha256,
            "match_contract_id" => stage.response_match.match_contract_id,
            "q2d_artifact_id" => stage.response_match.q2d_artifact_id,
            "q2d_artifact_sha256" => stage.response_match.q2d_artifact_sha256,
            "fixed_line_input_sha256" => stage.response_match.fixed_line_input_sha256,
            "fixed_line_input_identity" => _json_value(
                stage.response_match.fixed_line_input_identity,
                "normalized fixed-line identity",
            ),
            "fixed_line_input_identity_canonical_json" =>
                stage.response_match.fixed_line_input_identity_canonical_json,
            "topology_id" => stage.response_match.topology_id,
            "match_evidence" => _json_value(
                stage.response_match.match_evidence,
                "length-to-equivalent-LC response-match evidence",
            ),
        ),
        "idc" => _json_value(stage.idc, "IDC result"),
        "response_frequency_hz" => evaluated.specification.response_frequency_hz,
        "qubit_frequency_hz" => evaluated.specification.qubit_frequency_hz,
        "artifacts" => artifact_hashes,
        "artifact_contract" => collect(FILES),
    )
end

"""
    write_stage2_result(evaluated, output_directory; linear_quantity_payload_builder)

Write the six canonical Stage-2 artifacts into an unpublished sibling
directory, cross-bind their hashes, and rename that directory into place only
after every artifact is complete. `output_directory` must not already exist.
"""
function write_stage2_result(
    evaluated::Stage2EvaluatedResult,
    output_directory;
    linear_quantity_payload_builder,
)
    error(
        "The historical dual-authority Stage-2 result publisher is superseded and cannot publish revision-10 direct-Hybridized search results.",
    )
    _revalidate_evaluated_result(evaluated)
    destination = abspath(String(output_directory))
    ispath(destination) && error("D3 Stage-2 output directory already exists: $(destination)")
    parent = dirname(destination)
    mkpath(parent)
    temporary = mktempdir(parent; prefix=".$(basename(destination)).building-", cleanup=false)
    try
        history_path = joinpath(temporary, "history.json")
        s21_path = joinpath(temporary, "s21.csv")
        qubit_path = joinpath(temporary, "qubit-admittance.csv")
        _write_json(history_path, [
            _history_record(record, index)
            for (index, record) in enumerate(evaluated.optimization.history)
        ])
        _write_s21(s21_path, evaluated)
        _write_qubit(qubit_path, evaluated)

        first_hashes = Dict(
            "history.json" => _file_sha256(history_path),
            "s21.csv" => _file_sha256(s21_path),
            "qubit-admittance.csv" => _file_sha256(qubit_path),
        )
        summary_path = joinpath(temporary, "summary.json")
        _write_json(summary_path, _summary(evaluated, first_hashes))
        summary_sha256 = _file_sha256(summary_path)

        linear_payload_candidate = _string_key_dict(
            linear_quantity_payload_builder(
                evaluated.foundation,
                evaluated.objective,
                summary_sha256,
            ),
            "D3 linear-quantity payload builder result",
        )
        haskey(
            linear_payload_candidate,
            "matched_open_q_feedline_schur_downfolded_rp_effective_representation",
        ) && error(
            "D3 linear-quantity builder must not override the canonical effective extraction receipt.",
        )
        linear_payload_candidate["schema_version"] =
            "d3-stage2-linear-quantity-review.v4"
        linear_payload_candidate[
            "matched_open_q_feedline_schur_downfolded_rp_effective_representation"
        ] = _effective_rp_linear_review_payload(evaluated.foundation)
        linear_payload = _validate_linear_quantity_payload(
            linear_payload_candidate,
            summary_sha256,
            _model_identity(
                evaluated.foundation.cqed_handoff.source_model_identity,
                "D3 Stage-2 foundation model identity",
            ),
        )
        linear_path = joinpath(temporary, "linear-quantities.json")
        _write_json(linear_path, linear_payload)
        model_identity = _model_identity(
            evaluated.foundation.cqed_handoff.source_model_identity,
            "D3 Stage-2 foundation model identity",
        )
        qubit_receipt = Dict(
            "schema_version" => QUBIT_RECEIPT_SCHEMA,
            "source_summary_sha256" => summary_sha256,
            "qubit_admittance_csv_sha256" => first_hashes["qubit-admittance.csv"],
            "objective_contract_id" => String(evaluated.objective.contract_id),
            "objective_authority" => _json_value(
                evaluated.objective.authority,
                "qubit receipt objective authority",
            ),
            "model_identity" => _json_value(model_identity, "qubit receipt model identity"),
        )
        _write_json(
            joinpath(temporary, "qubit-admittance-receipt.json"),
            qubit_receipt,
        )
        sort(readdir(temporary)) == sort(collect(FILES)) || error(
            "D3 Stage-2 transactional directory contains an unexpected artifact set.",
        )
        ispath(destination) && error(
            "D3 Stage-2 output directory appeared during publication: $(destination)",
        )
        _revalidate_evaluated_result(evaluated)
        mv(temporary, destination)
        return destination
    catch
        rm(temporary; recursive=true, force=true)
        rethrow()
    end
end

end
