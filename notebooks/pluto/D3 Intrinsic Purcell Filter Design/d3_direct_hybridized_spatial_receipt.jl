# Exact-candidate spatial qualification authority for the Rev10 direct-Hybridized
# Stage-2 Objective. This module schedules and validates Circuit-owned raw cared
# outputs; it does not define circuit equations, Objective semantics, or search
# controls.

isdefined(@__MODULE__, :D3SemanticHash) ||
    include(joinpath(@__DIR__, "d3_semantic_hash.jl"))

module D3DirectHybridizedSpatialReceipt

using SHA
using SuperconductingCircuitsCore
using ..D3SemanticHash: SEMANTIC_HASH_FRAMING, semantic_value_sha256

const JSON3 = SuperconductingCircuitsCore.JSON3
const D3_DIRECT_HYBRIDIZED_CARED_OUTPUT_CONTRACT =
    "d3-rev10-direct-hybridized-cared-output.v1"
const D3_DIRECT_HYBRIDIZED_SPATIAL_SCHEMA =
    "d3-rev10-direct-hybridized-spatial-qualification.v1"
const D3_DIRECT_HYBRIDIZED_SPATIAL_CONTRACT =
    "d3-rev10-direct-hybridized-spatial-objective-receipt.v1"
const D3_DIRECT_HYBRIDIZED_SPATIAL_POLICY_ID =
    "d3-rev10-direct-hybridized-spatial-policy.v1"
const D3_DIRECT_HYBRIDIZED_OBJECTIVE_CONTRACT =
    "d3-stage2-direct-hybridized-objective.v3"
const D3_DIRECT_HYBRIDIZED_TARGET_CONTRACT_SHA256 =
    "c5ad1b1d3a770334fe29d15b863001a4746d60bb4a5cac9410694c1ac2d6b209"
const _CANDIDATE_FIELDS = (
    :lr_open_m,
    :lr_short_m,
    :lc_m,
    :lp_open_m,
    :lp_short_m,
    :u_IDC,
)
const _COUNT_FIELDS = (
    :readout_resonator,
    :filter_resonator,
    :mtl,
    :feedline_left,
    :feedline_right,
)
const _BOUNDARY_FIELDS = (
    :readout_resonator_boundaries_m,
    :filter_resonator_boundaries_m,
    :feedline_left_boundaries_m,
    :feedline_right_boundaries_m,
)
const _SOURCE_FIELDS = (
    :model_identity,
    :q2d_artifact_id,
    :q2d_artifact_sha256,
    :q2d_topology_id,
    :q2d_geometry_um,
    :fixed_line_input_sha256,
    :fixed_line_input_identity,
    :fixed_input_identity,
    :idc_mapping_id,
    :idc_mapping_sha256,
    :feedline_contract,
)
const _EXTRACTION_FIELDS = (
    :readout_effective_root_band_hz,
    :filter_effective_root_band_hz,
    :effective_operator_gate_policy,
    :notch_frequency_bracket_hz,
    :minimum_q_reference_overlap,
    :minimum_each_rp_subspace_overlap,
    :minimum_unordered_set_assignment_margin,
    :complement,
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
const _PASSIVITY_FIELDS = (
    :capacitance_reciprocity_error,
    :stiffness_reciprocity_error,
    :conductance_reciprocity_error,
    :stiffness_relative_passivity_violation,
    :conductance_relative_passivity_violation,
)
const _CARED_OUTPUT_FIELDS = (
    :contract_id,
    :stage_id,
    :model_family,
    :slot_hz,
    :candidate,
    :f_r_eff_hz,
    :f_p_eff_hz,
    :f_n_hz,
    :abs_real_J_eff_hz,
    :unordered_rp_kappa_sum_hz,
    :unordered_rp_linewidth_fraction_min,
    :unordered_rp_linewidth_fraction_max,
    :source_profile_identity,
    :grid_identity,
    :extraction_profile,
    :validity,
)
const _POLICY_PAYLOAD = Dict{String,Any}(
    "policy_id" => D3_DIRECT_HYBRIDIZED_SPATIAL_POLICY_ID,
    "semantic_hash_framing" => SEMANTIC_HASH_FRAMING,
    "level_indices" => [0, 1, 2, 3],
    "level_zero_max_cell_m" => Dict(
        "cpw_and_feedline" => 50.0e-6,
        "mtl" => 10.0e-6,
    ),
    "section_count_multiplier_per_level" => 2,
    "adjacent_relative_change_maximum" => 1.0e-3,
    "required_consecutive_qualifying_transitions" => 2,
    "relative_change_denominator" => "absolute_coarse_value_with_floatmin_floor",
    "frequency_pair_semantics" => "unordered_ascending_pair",
    "objective_contract_id" => D3_DIRECT_HYBRIDIZED_OBJECTIVE_CONTRACT,
    "target_contract_sha256" => D3_DIRECT_HYBRIDIZED_TARGET_CONTRACT_SHA256,
    "cared_output_fields" => [
        "unordered_f_r_eff_hz_f_p_eff_hz",
        "f_n_hz",
        "abs_real_J_eff_hz",
        "unordered_rp_kappa_sum_hz",
        "unordered_rp_linewidth_fraction_min",
    ],
)
const D3_DIRECT_HYBRIDIZED_SPATIAL_POLICY_SHA256 =
    semantic_value_sha256(_POLICY_PAYLOAD)

export D3AuthorizedDirectHybridizedSpatial,
    D3DirectHybridizedSpatialLevelRequest,
    D3DirectHybridizedSpatialNotEvaluable,
    D3DirectHybridizedSpatialReceipt,
    D3_DIRECT_HYBRIDIZED_CARED_OUTPUT_CONTRACT,
    D3_DIRECT_HYBRIDIZED_OBJECTIVE_CONTRACT,
    D3_DIRECT_HYBRIDIZED_SPATIAL_CONTRACT,
    D3_DIRECT_HYBRIDIZED_SPATIAL_POLICY_ID,
    D3_DIRECT_HYBRIDIZED_SPATIAL_POLICY_SHA256,
    D3_DIRECT_HYBRIDIZED_SPATIAL_SCHEMA,
    D3_DIRECT_HYBRIDIZED_TARGET_CONTRACT_SHA256,
    authorize_d3_direct_hybridized_spatial_receipt,
    d3_direct_hybridized_spatial_level_request,
    d3_direct_hybridized_spatial_cache_key,
    d3_direct_hybridized_objective_authority,
    d3_direct_hybridized_spatial_policy,
    d3_direct_hybridized_spatial_receipt_identity,
    evaluate_d3_direct_hybridized_objective_with_spatial_evidence,
    evaluate_d3_direct_hybridized_cared_output_request,
    load_d3_direct_hybridized_spatial_receipt,
    produce_d3_direct_hybridized_spatial_evidence,
    revalidate_d3_direct_hybridized_spatial_receipt,
    validate_d3_direct_hybridized_cared_output,
    validate_d3_direct_hybridized_objective_authority,
    validate_d3_direct_hybridized_spatial_evidence,
    validate_d3_direct_hybridized_spatial_policy,
    validate_d3_direct_hybridized_spatial_receipt_identity,
    validate_d3_direct_hybridized_spatial_authorization_match,
    write_d3_direct_hybridized_spatial_receipt

struct D3DirectHybridizedSpatialNotEvaluable <: Exception
    code::String
    reason::String
    details
end

Base.showerror(io::IO, exception::D3DirectHybridizedSpatialNotEvaluable) = print(
    io,
    "D3 direct-Hybridized spatial evidence NOT_EVALUABLE [",
    exception.code,
    "]: ",
    exception.reason,
)

struct D3DirectHybridizedSpatialLevelRequest{C,F,G,E,I}
    level::Int
    candidate::C
    fixed_input_identity::F
    grid_identity::G
    extraction_profile::E
    evaluation_input::I
end

struct D3DirectHybridizedSpatialReceipt{T}
    path::String
    sha256::String
    normalized::T
end

struct D3AuthorizedDirectHybridizedSpatial{R,C,O,A}
    receipt::R
    candidate::C
    slot_hz::Float64
    cared_output::O
    objective_authority::A
end

_fail(code, reason, details=nothing) = throw(
    D3DirectHybridizedSpatialNotEvaluable(String(code), String(reason), details),
)

function _is_circuit_type(value, name)
    parent = parentmodule(@__MODULE__)
    return isdefined(parent, name) && value isa getfield(parent, name)
end

function _mapping(value, label)
    if value isa NamedTuple
        return Dict{String,Any}(String(name) => getproperty(value, name) for name in propertynames(value))
    elseif value isa AbstractDict
        return Dict{String,Any}(String(key) => item for (key, item) in pairs(value))
    elseif _is_circuit_type(value, :D3DirectHybridizedCaredOutput)
        propertynames(value) == _CARED_OUTPUT_FIELDS || _fail(
            "direct_spatial.malformed",
            "Circuit cared-output type fields differ from the published contract.",
        )
        return Dict{String,Any}(
            String(name) => getproperty(value, name) for name in _CARED_OUTPUT_FIELDS
        )
    end
    _fail("direct_spatial.malformed", "$(label) must be a mapping.")
end

function _exact_mapping(value, fields, label)
    raw = _mapping(value, label)
    Set(keys(raw)) == Set(String.(fields)) || _fail(
        "direct_spatial.malformed",
        "$(label) fields do not match the accepted contract.",
        (expected=String.(fields), actual=sort!(collect(keys(raw)))),
    )
    return raw
end

function _real(value, label; positive=false, nonnegative=false)
    value isa Real && !(value isa Bool) || _fail(
        "direct_spatial.malformed",
        "$(label) must be numeric.",
    )
    parsed = Float64(value)
    isfinite(parsed) || _fail(
        "direct_spatial.nonfinite",
        "$(label) must be finite; scientific evidence cannot contain NaN or Inf.",
    )
    positive && parsed <= 0 && _fail(
        "direct_spatial.malformed",
        "$(label) must be positive.",
    )
    nonnegative && parsed < 0 && _fail(
        "direct_spatial.malformed",
        "$(label) must be nonnegative.",
    )
    return parsed
end

function _integer(value, label; positive=false)
    value isa Integer && !(value isa Bool) || _fail(
        "direct_spatial.malformed",
        "$(label) must be an integer.",
    )
    parsed = Int(value)
    positive && parsed <= 0 && _fail(
        "direct_spatial.malformed",
        "$(label) must be positive.",
    )
    return parsed
end

function _text(value, label)
    value isa Union{AbstractString,Symbol} || _fail(
        "direct_spatial.malformed",
        "$(label) must be text or a symbol.",
    )
    result = String(value)
    isempty(strip(result)) && _fail(
        "direct_spatial.malformed",
        "$(label) must not be empty.",
    )
    return result
end

function _sha(value, label)
    result = _text(value, label)
    result == lowercase(result) && occursin(r"^[0-9a-f]{64}$", result) || _fail(
        "direct_spatial.malformed",
        "$(label) must be lowercase SHA-256.",
    )
    return result
end

function _json_safe(value, label="value")
    if isnothing(value) || value isa Bool || value isa Integer || value isa AbstractString
        return value
    elseif value isa Symbol
        return String(value)
    elseif value isa Real
        return _real(value, label)
    elseif value isa NamedTuple || value isa AbstractDict
        raw = _mapping(value, label)
        return Dict{String,Any}(
            key => _json_safe(item, "$(label).$(key)") for (key, item) in raw
        )
    elseif value isa Tuple || value isa AbstractVector
        return Any[_json_safe(item, "$(label)[]") for item in value]
    end
    _fail(
        "direct_spatial.malformed",
        "$(label) contains unsupported value type $(typeof(value)).",
    )
end

function _candidate(candidate)
    raw = _exact_mapping(candidate, _CANDIDATE_FIELDS, "direct-Hybridized candidate")
    return NamedTuple{_CANDIDATE_FIELDS}(Tuple(
        _real(raw[String(name)], "candidate.$(name)"; positive=true)
        for name in _CANDIDATE_FIELDS
    ))
end

_candidate_dict(candidate) = Dict(String(name) => getproperty(candidate, name) for name in _CANDIDATE_FIELDS)

function _band(value, label)
    value isa Union{Tuple,AbstractVector} && length(value) == 2 || _fail(
        "direct_spatial.malformed",
        "$(label) must contain exactly two frequencies.",
    )
    result = (_real(value[1], "$(label)[1]"; positive=true), _real(value[2], "$(label)[2]"; positive=true))
    result[1] < result[2] || _fail(
        "direct_spatial.malformed",
        "$(label) must be strictly increasing.",
    )
    return result
end

function _gate_policy(value)
    raw = _exact_mapping(value, _GATE_POLICY_FIELDS, "effective-operator gate policy")
    values = NamedTuple{_GATE_POLICY_FIELDS}(Tuple(
        _real(raw[String(name)], "effective_operator_gate_policy.$(name)")
        for name in _GATE_POLICY_FIELDS
    ))
    values.maximum_elimination_condition_number >= 1 || _fail(
        "direct_spatial.failed_gate",
        "Effective-operator condition-number gate is invalid.",
    )
    for name in (
        :maximum_relative_elimination_solve_residual,
        :maximum_relative_reciprocity_error,
        :maximum_relative_passivity_violation,
        :maximum_relative_root_residual,
        :maximum_root_growth_rate_hz,
        :maximum_relative_coupling_spread,
        :maximum_relative_determinant_closure_error,
    )
        getproperty(values, name) >= 0 || _fail(
            "direct_spatial.failed_gate",
            "Effective-operator gate $(name) must be nonnegative.",
        )
    end
    values.minimum_normalized_residue_slope > 0 || _fail(
        "direct_spatial.failed_gate",
        "Effective-operator residue-slope gate must be positive.",
    )
    return values
end

function _extraction_profile(value)
    raw = _exact_mapping(value, _EXTRACTION_FIELDS, "direct extraction profile")
    minimum_q = _real(raw["minimum_q_reference_overlap"], "minimum_q_reference_overlap"; nonnegative=true)
    minimum_each = _real(raw["minimum_each_rp_subspace_overlap"], "minimum_each_rp_subspace_overlap"; nonnegative=true)
    margin = _real(raw["minimum_unordered_set_assignment_margin"], "minimum_unordered_set_assignment_margin"; nonnegative=true)
    all(value -> value <= 1, (minimum_q, minimum_each, margin)) || _fail(
        "direct_spatial.malformed",
        "Overlap and assignment-margin fractions must not exceed one.",
    )
    _text(raw["complement"], "extraction complement") == "complete_hybridized_complement" || _fail(
        "direct_spatial.stale",
        "Only the complete Hybridized complement is current.",
    )
    gate_policy = _gate_policy(raw["effective_operator_gate_policy"])
    return Dict{String,Any}(
        "readout_effective_root_band_hz" => collect(_band(raw["readout_effective_root_band_hz"], "readout root band")),
        "filter_effective_root_band_hz" => collect(_band(raw["filter_effective_root_band_hz"], "filter root band")),
        "effective_operator_gate_policy" => Dict(String(name) => getproperty(gate_policy, name) for name in _GATE_POLICY_FIELDS),
        "notch_frequency_bracket_hz" => collect(_band(raw["notch_frequency_bracket_hz"], "notch bracket")),
        "minimum_q_reference_overlap" => minimum_q,
        "minimum_each_rp_subspace_overlap" => minimum_each,
        "minimum_unordered_set_assignment_margin" => margin,
        "complement" => "complete_hybridized_complement",
    )
end

function _fixed_input_identity(value)
    fixed = _exact_mapping(
        value,
        (:contract_id, :q2d, :q3d, :idc, :feedline, :canonical_sha256),
        "fixed input identity",
    )
    declared_fixed_sha = _sha(fixed["canonical_sha256"], "fixed input canonical identity")
    fixed_core = copy(fixed)
    delete!(fixed_core, "canonical_sha256")
    fixed_core_safe = _json_safe(fixed_core, "fixed input identity")
    return merge(fixed_core_safe, Dict("canonical_sha256" => declared_fixed_sha))
end

function _source_profile(value)
    raw = _exact_mapping(value, _SOURCE_FIELDS, "source profile identity")
    model = _exact_mapping(
        raw["model_identity"],
        (:circuit_plan_sha256, :capacitance_sha256, :inverse_inductance_sha256, :selector_sha256),
        "source model identity",
    )
    for name in keys(model)
        model[name] = _sha(model[name], "model_identity.$(name)")
    end
    return Dict{String,Any}(
        "model_identity" => model,
        "q2d_artifact_id" => _text(raw["q2d_artifact_id"], "Q2D artifact id"),
        "q2d_artifact_sha256" => _sha(raw["q2d_artifact_sha256"], "Q2D artifact SHA-256"),
        "q2d_topology_id" => _text(raw["q2d_topology_id"], "Q2D topology id"),
        "q2d_geometry_um" => _json_safe(raw["q2d_geometry_um"], "Q2D geometry"),
        "fixed_line_input_sha256" => _sha(raw["fixed_line_input_sha256"], "fixed-line input SHA-256"),
        "fixed_line_input_identity" => _json_safe(raw["fixed_line_input_identity"], "fixed-line input identity"),
        "fixed_input_identity" => _fixed_input_identity(raw["fixed_input_identity"]),
        "idc_mapping_id" => _text(raw["idc_mapping_id"], "IDC mapping id"),
        "idc_mapping_sha256" => _sha(raw["idc_mapping_sha256"], "IDC mapping SHA-256"),
        "feedline_contract" => _json_safe(raw["feedline_contract"], "feedline contract"),
    )
end

function validate_d3_direct_hybridized_objective_authority(value)
    fields = (
        :objective_contract_id,
        :approval_status,
        :target_id,
        :target_revision,
        :target_contract_sha256,
        :notch_authority,
        :effective_diagonal_frequency_extraction,
        :effective_exchange_extraction,
        :linewidth_pole_scope,
        :primary_linewidth_extraction,
    )
    raw = _exact_mapping(value, fields, "direct-Hybridized Objective authority")
    normalized = Dict{String,Any}(
        "objective_contract_id" => _text(raw["objective_contract_id"], "Objective contract id"),
        "approval_status" => _text(raw["approval_status"], "Objective approval status"),
        "target_id" => _text(raw["target_id"], "Objective target id"),
        "target_revision" => _integer(raw["target_revision"], "Objective target revision"; positive=true),
        "target_contract_sha256" => _sha(raw["target_contract_sha256"], "Objective target contract SHA-256"),
        "notch_authority" => _text(raw["notch_authority"], "Objective notch authority"),
        "effective_diagonal_frequency_extraction" => _text(raw["effective_diagonal_frequency_extraction"], "Objective diagonal extraction"),
        "effective_exchange_extraction" => _text(raw["effective_exchange_extraction"], "Objective exchange extraction"),
        "linewidth_pole_scope" => _text(raw["linewidth_pole_scope"], "Objective linewidth scope"),
        "primary_linewidth_extraction" => _text(raw["primary_linewidth_extraction"], "Objective linewidth extraction"),
    )
    normalized == Dict{String,Any}(
        "objective_contract_id" => D3_DIRECT_HYBRIDIZED_OBJECTIVE_CONTRACT,
        "approval_status" => "human_approved",
        "target_id" => "d3-same-face-resonators-opposite-face-qubit-j5-k20-gap8",
        "target_revision" => 10,
        "target_contract_sha256" => D3_DIRECT_HYBRIDIZED_TARGET_CONTRACT_SHA256,
        "notch_authority" => "distributed_rp_on",
        "effective_diagonal_frequency_extraction" => "complete_complement_rp_complex_operator",
        "effective_exchange_extraction" => "complete_complement_rp_complex_midpoint_residue",
        "linewidth_pole_scope" => "unordered_rp_two_pole_subspace",
        "primary_linewidth_extraction" => "exact_open_unordered_rp_poles",
    ) || _fail(
        "direct_spatial.objective_authority_mismatch",
        "Spatial evidence is not bound to the current Human-accepted direct-Hybridized Objective authority.",
    )
    return normalized
end

function d3_direct_hybridized_objective_authority(circuit_authority)
    raw = _mapping(circuit_authority, "Circuit Objective authority")
    haskey(raw, "objective_contract_id") && _fail(
        "direct_spatial.objective_authority_mismatch",
        "Circuit Objective authority must not override its current contract id.",
    )
    raw["objective_contract_id"] = D3_DIRECT_HYBRIDIZED_OBJECTIVE_CONTRACT
    return validate_d3_direct_hybridized_objective_authority(raw)
end

function _boundaries(value, label)
    value isa AbstractVector || value isa Tuple || _fail(
        "direct_spatial.malformed",
        "$(label) must be an array.",
    )
    result = Float64[_real(item, "$(label)[]"; nonnegative=true) for item in value]
    length(result) >= 2 && first(result) == 0.0 && all(diff(result) .> 0) || _fail(
        "direct_spatial.malformed",
        "$(label) must start at zero and increase strictly.",
    )
    return result
end

function _grid_identity(value)
    raw = _exact_mapping(
        value,
        (:counts, :boundaries_m, :canonical_sha256, :refinement_level, :requested_plan_sha256),
        "grid identity",
    )
    count_raw = _exact_mapping(raw["counts"], _COUNT_FIELDS, "grid section counts")
    counts = NamedTuple{_COUNT_FIELDS}(Tuple(
        _integer(count_raw[String(name)], "grid count $(name)"; positive=true)
        for name in _COUNT_FIELDS
    ))
    boundary_raw = _exact_mapping(raw["boundaries_m"], _BOUNDARY_FIELDS, "grid boundaries")
    boundaries = NamedTuple{_BOUNDARY_FIELDS}(Tuple(
        _boundaries(boundary_raw[String(name)], "grid boundaries $(name)")
        for name in _BOUNDARY_FIELDS
    ))
    for (boundary_name, count_name) in zip(
        _BOUNDARY_FIELDS,
        (:readout_resonator, :filter_resonator, :feedline_left, :feedline_right),
    )
        length(getproperty(boundaries, boundary_name)) - 1 == getproperty(counts, count_name) || _fail(
            "direct_spatial.grid_mismatch",
            "Grid boundary count disagrees with $(count_name).",
        )
    end
    declared = _sha(raw["canonical_sha256"], "grid canonical SHA-256")
    actual = bytes2hex(SHA.sha256(codeunits(JSON3.write((
        counts=counts,
        boundaries_m=boundaries,
    )))))
    actual == declared || _fail(
        "direct_spatial.grid_mismatch",
        "Grid canonical SHA-256 does not bind its counts and arrays.",
    )
    return Dict{String,Any}(
        "counts" => Dict(String(name) => getproperty(counts, name) for name in _COUNT_FIELDS),
        "boundaries_m" => Dict(String(name) => collect(getproperty(boundaries, name)) for name in _BOUNDARY_FIELDS),
        "canonical_sha256" => declared,
        "refinement_level" => _integer(raw["refinement_level"], "grid refinement level"),
        "requested_plan_sha256" => _sha(raw["requested_plan_sha256"], "requested grid-plan SHA-256"),
    )
end

function _passivity(value, gate_policy)
    raw = _exact_mapping(value, _PASSIVITY_FIELDS, "passivity validity")
    parsed = Dict{String,Any}(
        String(name) => _real(raw[String(name)], "passivity.$(name)"; nonnegative=true)
        for name in _PASSIVITY_FIELDS
    )
    maximum(parsed[String(name)] for name in _PASSIVITY_FIELDS[1:3]) <=
        gate_policy.maximum_relative_reciprocity_error || _fail(
            "direct_spatial.failed_gate",
            "Serialized reciprocity evidence exceeds its bound gate policy.",
        )
    maximum(parsed[String(name)] for name in _PASSIVITY_FIELDS[4:5]) <=
        gate_policy.maximum_relative_passivity_violation || _fail(
            "direct_spatial.failed_gate",
            "Serialized passivity evidence exceeds its bound gate policy.",
        )
    return parsed
end

function _validity(value, extraction_profile)
    fields = (
        :status,
        :source_identity,
        :passivity,
        :rp_root_and_operator,
        :distributed_rp_on_notch,
        :exact_open_poles,
        :unordered_rp_assignment,
    )
    raw = _exact_mapping(value, fields, "cared-output validity")
    for name in fields
        name === :passivity && continue
        _text(raw[String(name)], "validity.$(name)") == "pass" || _fail(
            "direct_spatial.failed_gate",
            "Cared-output validity gate $(name) did not pass.",
        )
    end
    gate_policy_raw = _mapping(
        extraction_profile["effective_operator_gate_policy"],
        "effective-operator gate policy",
    )
    gate_policy = NamedTuple{_GATE_POLICY_FIELDS}(Tuple(
        gate_policy_raw[String(name)] for name in _GATE_POLICY_FIELDS
    ))
    return Dict{String,Any}(
        "status" => "pass",
        "source_identity" => "pass",
        "passivity" => _passivity(raw["passivity"], gate_policy),
        "rp_root_and_operator" => "pass",
        "distributed_rp_on_notch" => "pass",
        "exact_open_poles" => "pass",
        "unordered_rp_assignment" => "pass",
    )
end

function validate_d3_direct_hybridized_cared_output(value)
    fields = (
        :contract_id,
        :stage_id,
        :model_family,
        :slot_hz,
        :candidate,
        :f_r_eff_hz,
        :f_p_eff_hz,
        :f_n_hz,
        :abs_real_J_eff_hz,
        :unordered_rp_kappa_sum_hz,
        :unordered_rp_linewidth_fraction_min,
        :unordered_rp_linewidth_fraction_max,
        :source_profile_identity,
        :grid_identity,
        :extraction_profile,
        :validity,
    )
    raw = _exact_mapping(value, fields, "direct-Hybridized cared output")
    _text(raw["contract_id"], "cared-output contract") ==
        D3_DIRECT_HYBRIDIZED_CARED_OUTPUT_CONTRACT || _fail(
            "direct_spatial.stale",
            "Direct-Hybridized cared-output contract is stale.",
        )
    _text(raw["stage_id"], "cared-output stage") == "stage2_direct_hybridized" &&
        _text(raw["model_family"], "cared-output model family") ==
            "hybridized_distributed_lumped" || _fail(
                "direct_spatial.authority",
                "Cared output is not from the direct-Hybridized Stage-2 authority.",
            )
    candidate = _candidate(raw["candidate"])
    fraction_min = _real(
        raw["unordered_rp_linewidth_fraction_min"],
        "unordered linewidth-fraction minimum";
        nonnegative=true,
    )
    fraction_max = _real(
        raw["unordered_rp_linewidth_fraction_max"],
        "unordered linewidth-fraction maximum";
        nonnegative=true,
    )
    0 <= fraction_min <= fraction_max <= 1 || _fail(
        "direct_spatial.failed_gate",
        "Unordered linewidth fractions must form an ordered pair inside [0, 1].",
    )
    extraction = _extraction_profile(raw["extraction_profile"])
    return Dict{String,Any}(
        "contract_id" => D3_DIRECT_HYBRIDIZED_CARED_OUTPUT_CONTRACT,
        "stage_id" => "stage2_direct_hybridized",
        "model_family" => "hybridized_distributed_lumped",
        "slot_hz" => _real(raw["slot_hz"], "cared-output slot"; positive=true),
        "candidate" => _candidate_dict(candidate),
        "f_r_eff_hz" => _real(raw["f_r_eff_hz"], "f_r_eff_hz"; positive=true),
        "f_p_eff_hz" => _real(raw["f_p_eff_hz"], "f_p_eff_hz"; positive=true),
        "f_n_hz" => _real(raw["f_n_hz"], "f_n_hz"; positive=true),
        "abs_real_J_eff_hz" => _real(raw["abs_real_J_eff_hz"], "abs_real_J_eff_hz"; nonnegative=true),
        "unordered_rp_kappa_sum_hz" => _real(raw["unordered_rp_kappa_sum_hz"], "unordered_rp_kappa_sum_hz"; nonnegative=true),
        "unordered_rp_linewidth_fraction_min" => fraction_min,
        "unordered_rp_linewidth_fraction_max" => fraction_max,
        "source_profile_identity" => _source_profile(raw["source_profile_identity"]),
        "grid_identity" => _grid_identity(raw["grid_identity"]),
        "extraction_profile" => extraction,
        "validity" => _validity(raw["validity"], extraction),
    )
end

d3_direct_hybridized_spatial_policy() = merge(
    deepcopy(_POLICY_PAYLOAD),
    Dict("policy_sha256" => D3_DIRECT_HYBRIDIZED_SPATIAL_POLICY_SHA256),
)

function validate_d3_direct_hybridized_spatial_policy(value)
    _json_safe(value, "spatial policy") == d3_direct_hybridized_spatial_policy() || _fail(
        "direct_spatial.stale",
        "Direct-Hybridized spatial policy is not current.",
    )
    return d3_direct_hybridized_spatial_policy()
end

function _request(request, candidate, slot, level)
    request isa D3DirectHybridizedSpatialLevelRequest || _fail(
        "direct_spatial.request_mismatch",
        "Level request must be D3DirectHybridizedSpatialLevelRequest.",
    )
    request.level == level || _fail(
        "direct_spatial.request_mismatch",
        "Level request index differs from the controller level.",
    )
    _candidate(request.candidate) == candidate || _fail(
        "direct_spatial.candidate_mismatch",
        "Level request belongs to another exact candidate.",
    )
    fixed = _fixed_input_identity(request.fixed_input_identity)
    grid = _grid_identity(request.grid_identity)
    extraction = _extraction_profile(request.extraction_profile)
    _validate_grid_level(grid, candidate, level)
    return (
        level=level,
        fixed_input_identity=fixed,
        grid_identity=grid,
        extraction_profile=extraction,
        evaluation_input=request.evaluation_input,
        candidate=candidate,
        slot_hz=slot,
    )
end

function d3_direct_hybridized_spatial_level_request(inputs, grid_plan, extraction_profile)
    _is_circuit_type(inputs, :D3DirectHybridizedInputs) || _fail(
        "direct_spatial.request_mismatch",
        "Spatial level request requires canonical D3DirectHybridizedInputs.",
    )
    _is_circuit_type(grid_plan, :D3DirectHybridizedGridPlan) || _fail(
        "direct_spatial.request_mismatch",
        "Spatial level request requires canonical D3DirectHybridizedGridPlan.",
    )
    inputs.source_identity.canonical_sha256 ==
        grid_plan.fixed_input_canonical_sha256 || _fail(
            "direct_spatial.request_mismatch",
            "Grid plan belongs to another sealed direct-Hybridized fixed input.",
        )
    counts = grid_plan.counts
    boundaries = grid_plan.boundaries_m
    actual_grid_sha256 = bytes2hex(SHA.sha256(codeunits(JSON3.write((
        counts=counts,
        boundaries_m=boundaries,
    )))))
    grid_identity = (
        counts=counts,
        boundaries_m=boundaries,
        canonical_sha256=actual_grid_sha256,
        refinement_level=grid_plan.refinement_level,
        requested_plan_sha256=grid_plan.canonical_sha256,
    )
    return D3DirectHybridizedSpatialLevelRequest(
        grid_plan.refinement_level,
        grid_plan.candidate,
        inputs.source_identity,
        grid_identity,
        extraction_profile,
        (
            inputs=inputs,
            grid_plan=grid_plan,
            extraction_profile=extraction_profile,
        ),
    )
end

function evaluate_d3_direct_hybridized_cared_output_request(candidate, slot_hz, input)
    input isa NamedTuple && propertynames(input) ==
        (:inputs, :grid_plan, :extraction_profile) || _fail(
            "direct_spatial.request_mismatch",
            "Direct cared-output evaluation input does not match the canonical adapter.",
        )
    _is_circuit_type(input.inputs, :D3DirectHybridizedInputs) &&
        _is_circuit_type(input.grid_plan, :D3DirectHybridizedGridPlan) || _fail(
            "direct_spatial.request_mismatch",
            "Direct cared-output evaluation input contains noncanonical Circuit types.",
        )
    profile = input.extraction_profile
    profile isa NamedTuple && propertynames(profile) == _EXTRACTION_FIELDS || _fail(
        "direct_spatial.request_mismatch",
        "Direct cared-output extraction profile must use the canonical named fields.",
    )
    _extraction_profile(profile)
    parent = parentmodule(@__MODULE__)
    isdefined(parent, :d3_stage2_direct_cared_outputs) || _fail(
        "direct_spatial.request_mismatch",
        "Canonical direct-Hybridized cared-output producer is unavailable.",
    )
    producer = getfield(parent, :d3_stage2_direct_cared_outputs)
    return producer(
        candidate,
        input.inputs;
        grid_plan=input.grid_plan,
        slot_hz=slot_hz,
        readout_effective_root_band_hz=profile.readout_effective_root_band_hz,
        filter_effective_root_band_hz=profile.filter_effective_root_band_hz,
        effective_operator_gate_policy=profile.effective_operator_gate_policy,
        notch_frequency_bracket_hz=profile.notch_frequency_bracket_hz,
        minimum_q_reference_overlap=profile.minimum_q_reference_overlap,
        minimum_each_rp_subspace_overlap=
            profile.minimum_each_rp_subspace_overlap,
        minimum_unordered_set_assignment_margin=
            profile.minimum_unordered_set_assignment_margin,
    )
end

function _counts(grid)
    raw = _mapping(grid["counts"], "grid counts")
    return NamedTuple{_COUNT_FIELDS}(Tuple(Int(raw[String(name)]) for name in _COUNT_FIELDS))
end

function _grid_arrays(grid)
    raw = _mapping(grid["boundaries_m"], "grid boundaries")
    return NamedTuple{_BOUNDARY_FIELDS}(Tuple(
        Float64.(raw[String(name)]) for name in _BOUNDARY_FIELDS
    ))
end

function _validate_grid_level(grid, candidate, level)
    level in 0:3 || _fail(
        "direct_spatial.request_mismatch",
        "Spatial level must be in the accepted 0:3 range.",
    )
    grid["refinement_level"] == level || _fail(
        "direct_spatial.grid_mismatch",
        "Grid identity refinement level differs from the controller level.",
    )
    arrays = _grid_arrays(grid)
    cpw_max = 50.0e-6 / (1 << level)
    for name in _BOUNDARY_FIELDS
        maximum(diff(getproperty(arrays, name))) <= cpw_max * (1 + 1.0e-9) || _fail(
            "direct_spatial.grid_mismatch",
            "Level $(level) $(name) exceeds the accepted CPW/feedline maximum cell.",
        )
    end
    counts = _counts(grid)
    candidate.lc_m / counts.mtl <= (10.0e-6 / (1 << level)) * (1 + 1.0e-9) || _fail(
        "direct_spatial.grid_mismatch",
        "Level $(level) MTL grid exceeds the accepted maximum cell.",
    )
    return grid
end

function _validate_count_refinement(coarse, fine)
    coarse_counts = _counts(coarse)
    fine_counts = _counts(fine)
    all(
        getproperty(fine_counts, name) == 2 * getproperty(coarse_counts, name)
        for name in _COUNT_FIELDS
    ) || _fail(
        "direct_spatial.grid_mismatch",
        "Every distributed section count must double at each adjacent level.",
        (coarse=coarse_counts, fine=fine_counts),
    )
    return nothing
end

function d3_direct_hybridized_spatial_cache_key(candidate, slot_hz, request)
    values = _candidate(candidate)
    slot = _real(slot_hz, "cache slot"; positive=true)
    request isa D3DirectHybridizedSpatialLevelRequest || _fail(
        "direct_spatial.request_mismatch",
        "Cache request must be D3DirectHybridizedSpatialLevelRequest.",
    )
    level = request.level
    normalized = _request(request, values, slot, level)
    return semantic_value_sha256(Dict(
        "contract_id" => D3_DIRECT_HYBRIDIZED_SPATIAL_CONTRACT,
        "policy_sha256" => D3_DIRECT_HYBRIDIZED_SPATIAL_POLICY_SHA256,
        "candidate" => _candidate_dict(values),
        "slot_hz" => slot,
        "level" => level,
        "fixed_input_identity" => normalized.fixed_input_identity,
        "grid_identity" => normalized.grid_identity,
        "extraction_profile" => normalized.extraction_profile,
    ))
end

function _cared_for_request(value, request)
    cared = validate_d3_direct_hybridized_cared_output(value)
    cared["candidate"] == _candidate_dict(request.candidate) || _fail(
        "direct_spatial.candidate_mismatch",
        "Cared output belongs to another exact candidate.",
    )
    cared["slot_hz"] == request.slot_hz || _fail(
        "direct_spatial.slot_mismatch",
        "Cared output belongs to another slot.",
    )
    cared["source_profile_identity"]["fixed_input_identity"] == request.fixed_input_identity &&
        cared["grid_identity"] == request.grid_identity &&
        cared["extraction_profile"] == request.extraction_profile || _fail(
            "direct_spatial.request_mismatch",
            "Cared output source, grid, or extraction profile differs from its exact request.",
        )
    return cared
end

function _cached_cared(value, request)
    raw = _exact_mapping(
        value,
        (:cared_output, :cared_output_sha256),
        "direct-Hybridized spatial cache entry",
    )
    declared = _sha(raw["cared_output_sha256"], "cached cared-output SHA-256")
    safe = _json_safe(raw["cared_output"], "cached cared output")
    semantic_value_sha256(safe) == declared || _fail(
        "direct_spatial.cache_mismatch",
        "Cached cared-output bytes changed after insertion.",
    )
    return _cared_for_request(safe, request)
end

_relative_change(coarse, fine) = abs(fine - coarse) / max(abs(coarse), floatmin(Float64))

function _comparison(coarse, fine)
    coarse_pair = sort([coarse["f_r_eff_hz"], coarse["f_p_eff_hz"]])
    fine_pair = sort([fine["f_r_eff_hz"], fine["f_p_eff_hz"]])
    pair_changes = [_relative_change(coarse_pair[index], fine_pair[index]) for index in 1:2]
    scalar_names = (
        :f_n_hz,
        :abs_real_J_eff_hz,
        :unordered_rp_kappa_sum_hz,
        :unordered_rp_linewidth_fraction_min,
    )
    scalar_changes = Dict(
        String(name) => _relative_change(coarse[String(name)], fine[String(name)])
        for name in scalar_names
    )
    threshold = 1.0e-3
    passed = all(value -> value <= threshold, pair_changes) &&
        all(value -> value <= threshold, values(scalar_changes))
    return Dict{String,Any}(
        "coarse_level" => nothing,
        "fine_level" => nothing,
        "unordered_frequency_pair_hz" => Dict(
            "coarse" => coarse_pair,
            "fine" => fine_pair,
            "relative_changes" => pair_changes,
        ),
        "scalar_relative_changes" => scalar_changes,
        "threshold" => threshold,
        "passed" => passed,
    )
end

function _not_evaluable_details(candidate, slot, level, records, comparisons; exception=nothing)
    details = Dict{String,Any}(
        "candidate" => _candidate_dict(candidate),
        "slot_hz" => slot,
        "level" => level,
        "cost" => nothing,
        "records" => records,
        "comparisons" => comparisons,
    )
    isnothing(exception) || (details["exception"] = sprint(showerror, exception))
    return details
end

function _success_payload(candidate, slot, objective_authority, records, comparisons)
    qualified_level = records[end]["level"]
    finest = records[end]["cared_output"]
    core = Dict{String,Any}(
        "schema_version" => D3_DIRECT_HYBRIDIZED_SPATIAL_SCHEMA,
        "contract_id" => D3_DIRECT_HYBRIDIZED_SPATIAL_CONTRACT,
        "policy_id" => D3_DIRECT_HYBRIDIZED_SPATIAL_POLICY_ID,
        "policy_sha256" => D3_DIRECT_HYBRIDIZED_SPATIAL_POLICY_SHA256,
        "lifecycle_state" => "ACCEPTED",
        "data_class" => "project-internal",
        "authority_status" => "diagnostic_only",
        "promotion_eligible" => false,
        "final_status" => "PASS",
        "first_blocker" => nothing,
        "candidate" => _candidate_dict(candidate),
        "candidate_sha256" => semantic_value_sha256(_candidate_dict(candidate)),
        "slot_hz" => slot,
        "objective_authority" => objective_authority,
        "controller" => Dict(
            "level_indices" => [record["level"] for record in records],
            "stopped_immediately" => true,
        ),
        "levels" => records,
        "adjacent_comparisons" => comparisons,
        "qualified_level" => qualified_level,
        "finest_qualified_endpoint" => Dict(
            "level" => qualified_level,
            "cared_output_sha256" => semantic_value_sha256(finest),
            "source_profile_identity" => finest["source_profile_identity"],
            "grid_identity" => finest["grid_identity"],
            "extraction_profile" => finest["extraction_profile"],
        ),
        "nonclaims" => [
            "not a neighboring-point, family, or envelope authority",
            "not an LC, Equivalent, HB, fit, winner, closure, promotion, or publication claim",
            "does not contain an Objective value or CMA search control",
        ],
    )
    core["semantic_receipt_sha256"] = semantic_value_sha256(core)
    return core
end

function produce_d3_direct_hybridized_spatial_evidence(
    candidate;
    slot_hz,
    objective_authority,
    level_request,
    cared_output_evaluator=evaluate_d3_direct_hybridized_cared_output_request,
    cache=Dict{String,Any}(),
)
    values = _candidate(candidate)
    slot = _real(slot_hz, "direct-Hybridized slot"; positive=true)
    current_objective_authority =
        validate_d3_direct_hybridized_objective_authority(objective_authority)
    records = Any[]
    comparisons = Any[]
    qualifying_streak = 0
    previous = nothing
    for level in 0:3
        raw_request = try
            level_request(values, slot, level)
        catch exception
            exception isa InterruptException && rethrow()
            exception isa D3DirectHybridizedSpatialNotEvaluable && rethrow()
            _fail(
                "direct_spatial.request_not_evaluable",
                "Direct-Hybridized level request could not be constructed.",
                _not_evaluable_details(values, slot, level, records, comparisons; exception=exception),
            )
        end
        request = _request(raw_request, values, slot, level)
        !isnothing(previous) && _validate_count_refinement(
            previous["cared_output"]["grid_identity"],
            request.grid_identity,
        )
        key = d3_direct_hybridized_spatial_cache_key(values, slot, raw_request)
        cared = if haskey(cache, key)
            try
                _cached_cared(cache[key], request)
            catch exception
                exception isa InterruptException && rethrow()
                _fail(
                    "direct_spatial.cache_mismatch",
                    "Cached cared output is malformed or stale.",
                    _not_evaluable_details(values, slot, level, records, comparisons; exception=exception),
                )
            end
        else
            raw = try
                cared_output_evaluator(values, slot, request.evaluation_input)
            catch exception
                exception isa InterruptException && rethrow()
                exception isa D3DirectHybridizedSpatialNotEvaluable && rethrow()
                _fail(
                    "direct_spatial.cared_output_not_evaluable",
                    "Circuit-owned direct-Hybridized cared output was unavailable.",
                    _not_evaluable_details(values, slot, level, records, comparisons; exception=exception),
                )
            end
            normalized = _cared_for_request(raw, request)
            cache[key] = Dict(
                "cared_output" => deepcopy(normalized),
                "cared_output_sha256" => semantic_value_sha256(normalized),
            )
            normalized
        end
        record = Dict{String,Any}(
            "level" => level,
            "cache_key" => key,
            "cared_output" => cared,
        )
        push!(records, record)
        if !isnothing(previous)
            comparison = _comparison(previous["cared_output"], cared)
            comparison["coarse_level"] = level - 1
            comparison["fine_level"] = level
            push!(comparisons, comparison)
            qualifying_streak = comparison["passed"] ? qualifying_streak + 1 : 0
            qualifying_streak == 2 && return _success_payload(
                values,
                slot,
                current_objective_authority,
                records,
                comparisons,
            )
        end
        previous = record
    end
    _fail(
        "spatial_grid_not_eligible",
        "Direct-Hybridized cared outputs did not qualify through spatial level 3.",
        _not_evaluable_details(values, slot, 3, records, comparisons),
    )
end

function _normalize_evidence(value)
    raw = _exact_mapping(value, (
        :schema_version,
        :contract_id,
        :policy_id,
        :policy_sha256,
        :lifecycle_state,
        :data_class,
        :authority_status,
        :promotion_eligible,
        :final_status,
        :first_blocker,
        :candidate,
        :candidate_sha256,
        :slot_hz,
        :objective_authority,
        :controller,
        :levels,
        :adjacent_comparisons,
        :qualified_level,
        :finest_qualified_endpoint,
        :nonclaims,
        :semantic_receipt_sha256,
    ), "direct-Hybridized spatial evidence")
    raw["schema_version"] == D3_DIRECT_HYBRIDIZED_SPATIAL_SCHEMA &&
        raw["contract_id"] == D3_DIRECT_HYBRIDIZED_SPATIAL_CONTRACT &&
        raw["policy_id"] == D3_DIRECT_HYBRIDIZED_SPATIAL_POLICY_ID &&
        raw["policy_sha256"] == D3_DIRECT_HYBRIDIZED_SPATIAL_POLICY_SHA256 || _fail(
            "direct_spatial.stale",
            "Spatial evidence schema, contract, or policy is stale.",
        )
    raw["lifecycle_state"] == "ACCEPTED" && raw["data_class"] == "project-internal" &&
        raw["authority_status"] == "diagnostic_only" && raw["promotion_eligible"] === false &&
        raw["final_status"] == "PASS" && isnothing(raw["first_blocker"]) || _fail(
            "direct_spatial.authority",
            "Spatial evidence authority/status boundary is invalid.",
        )
    declared = _sha(raw["semantic_receipt_sha256"], "spatial semantic receipt")
    core = _json_safe(copy(raw), "spatial evidence")
    delete!(core, "semantic_receipt_sha256")
    semantic_value_sha256(core) == declared || _fail(
        "direct_spatial.stale",
        "Spatial semantic receipt hash changed.",
    )
    candidate = _candidate(raw["candidate"])
    semantic_value_sha256(_candidate_dict(candidate)) == raw["candidate_sha256"] || _fail(
        "direct_spatial.candidate_mismatch",
        "Spatial candidate identity changed.",
    )
    slot = _real(raw["slot_hz"], "spatial slot"; positive=true)
    objective_authority =
        validate_d3_direct_hybridized_objective_authority(raw["objective_authority"])
    levels_raw = raw["levels"]
    levels_raw isa AbstractVector && length(levels_raw) in (3, 4) || _fail(
        "direct_spatial.malformed",
        "PASS evidence must contain three or four spatial levels.",
    )
    records = Any[]
    previous = nothing
    for (index, raw_record) in enumerate(levels_raw)
        record = _exact_mapping(raw_record, (:level, :cache_key, :cared_output), "spatial level record")
        level = _integer(record["level"], "spatial level")
        level == index - 1 || _fail(
            "direct_spatial.malformed",
            "Spatial levels must be contiguous from zero.",
        )
        cared = validate_d3_direct_hybridized_cared_output(record["cared_output"])
        cared["candidate"] == _candidate_dict(candidate) && cared["slot_hz"] == slot || _fail(
            "direct_spatial.candidate_mismatch",
            "Spatial level cared output belongs to another candidate or slot.",
        )
        _validate_grid_level(cared["grid_identity"], candidate, level)
        !isnothing(previous) && _validate_count_refinement(
            previous["cared_output"]["grid_identity"],
            cared["grid_identity"],
        )
        cache_key = _sha(record["cache_key"], "spatial cache key")
        expected_key = semantic_value_sha256(Dict(
            "contract_id" => D3_DIRECT_HYBRIDIZED_SPATIAL_CONTRACT,
            "policy_sha256" => D3_DIRECT_HYBRIDIZED_SPATIAL_POLICY_SHA256,
            "candidate" => _candidate_dict(candidate),
            "slot_hz" => slot,
            "level" => level,
            "fixed_input_identity" =>
                cared["source_profile_identity"]["fixed_input_identity"],
            "grid_identity" => cared["grid_identity"],
            "extraction_profile" => cared["extraction_profile"],
        ))
        cache_key == expected_key || _fail(
            "direct_spatial.cache_mismatch",
            "Spatial level cache identity changed.",
        )
        normalized = Dict{String,Any}(
            "level" => level,
            "cache_key" => cache_key,
            "cared_output" => cared,
        )
        push!(records, normalized)
        previous = normalized
    end
    comparisons = Any[]
    comparisons_raw = raw["adjacent_comparisons"]
    comparisons_raw isa AbstractVector && length(comparisons_raw) == length(records) - 1 || _fail(
        "direct_spatial.malformed",
        "Adjacent comparison count is inconsistent with spatial levels.",
    )
    for index in eachindex(comparisons_raw)
        expected = _comparison(
            records[index]["cared_output"],
            records[index + 1]["cared_output"],
        )
        expected["coarse_level"] = index - 1
        expected["fine_level"] = index
        _json_safe(comparisons_raw[index], "adjacent comparison") == expected || _fail(
            "direct_spatial.stale",
            "Stored adjacent spatial change differs from recomputation.",
        )
        push!(comparisons, expected)
    end
    length(comparisons) >= 2 && comparisons[end - 1]["passed"] && comparisons[end]["passed"] || _fail(
        "direct_spatial.failed_gate",
        "PASS evidence lacks two consecutive qualifying transitions.",
    )
    for index in 2:(length(comparisons) - 1)
        comparisons[index - 1]["passed"] && comparisons[index]["passed"] && _fail(
            "direct_spatial.stale",
            "Controller continued after the first qualifying joint result.",
        )
    end
    qualified_level = _integer(raw["qualified_level"], "qualified level")
    qualified_level == records[end]["level"] || _fail(
        "direct_spatial.stale",
        "Qualified level is not the finest evaluated endpoint.",
    )
    finest_raw = _exact_mapping(raw["finest_qualified_endpoint"], (
        :level,
        :cared_output_sha256,
        :source_profile_identity,
        :grid_identity,
        :extraction_profile,
    ), "finest qualified endpoint")
    finest = records[end]["cared_output"]
    _integer(finest_raw["level"], "finest qualified level") == qualified_level &&
        _sha(finest_raw["cared_output_sha256"], "finest cared-output SHA-256") == semantic_value_sha256(finest) &&
        _source_profile(finest_raw["source_profile_identity"]) == finest["source_profile_identity"] &&
        _grid_identity(finest_raw["grid_identity"]) == finest["grid_identity"] &&
        _extraction_profile(finest_raw["extraction_profile"]) == finest["extraction_profile"] || _fail(
            "direct_spatial.stale",
            "Finest qualified endpoint binding changed.",
        )
    controller = _exact_mapping(raw["controller"], (
        :level_indices,
        :stopped_immediately,
    ), "spatial controller evidence")
    controller["level_indices"] == collect(0:qualified_level) &&
        controller["stopped_immediately"] === true || _fail(
            "direct_spatial.stale",
            "Spatial controller accounting or early-stop evidence is invalid.",
        )
    return (
        candidate=candidate,
        candidate_sha256=raw["candidate_sha256"],
        slot_hz=slot,
        objective_authority=objective_authority,
        records=records,
        comparisons=comparisons,
        qualified_level=qualified_level,
        cared_output=finest,
        semantic_receipt_sha256=declared,
    )
end

validate_d3_direct_hybridized_spatial_evidence(value) = _normalize_evidence(value)

function _read_payload(path)
    bytes = read(path)
    payload = try
        JSON3.read(String(copy(bytes)), Dict{String,Any})
    catch exception
        _fail(
            "direct_spatial.malformed",
            "Direct-Hybridized spatial receipt is not valid JSON.",
            (exception=sprint(showerror, exception),),
        )
    end
    return bytes, payload
end

function load_d3_direct_hybridized_spatial_receipt(path)
    input_path = abspath(String(path))
    isfile(input_path) || _fail(
        "direct_spatial.missing",
        "Direct-Hybridized spatial receipt does not exist.",
        (path=input_path,),
    )
    bytes, payload = _read_payload(input_path)
    return D3DirectHybridizedSpatialReceipt(
        input_path,
        bytes2hex(SHA.sha256(bytes)),
        _normalize_evidence(payload),
    )
end

function write_d3_direct_hybridized_spatial_receipt(path, evidence)
    destination = abspath(String(path))
    ispath(destination) && _fail(
        "direct_spatial.exists",
        "Direct-Hybridized spatial receipt destination already exists.",
        (path=destination,),
    )
    _normalize_evidence(evidence)
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
    return load_d3_direct_hybridized_spatial_receipt(destination)
end

function _reparse(receipt::D3DirectHybridizedSpatialReceipt)
    isfile(receipt.path) || _fail(
        "direct_spatial.missing",
        "Direct-Hybridized spatial receipt disappeared after validation.",
    )
    bytes, payload = _read_payload(receipt.path)
    bytes2hex(SHA.sha256(bytes)) == receipt.sha256 || _fail(
        "direct_spatial.stale",
        "Direct-Hybridized spatial receipt bytes changed after validation.",
    )
    normalized = _normalize_evidence(payload)
    normalized == receipt.normalized || _fail(
        "direct_spatial.stale",
        "In-memory spatial authority disagrees with its current bytes.",
    )
    return normalized
end

function validate_d3_direct_hybridized_spatial_receipt_identity(value)
    isnothing(value) && _fail(
        "direct_spatial.missing",
        "Direct-Hybridized spatial receipt identity is missing.",
    )
    return _sha(value, "Direct-Hybridized spatial receipt identity")
end

function d3_direct_hybridized_spatial_receipt_identity(receipt::D3DirectHybridizedSpatialReceipt)
    return (
        schema_version=D3_DIRECT_HYBRIDIZED_SPATIAL_SCHEMA,
        contract_id=D3_DIRECT_HYBRIDIZED_SPATIAL_CONTRACT,
        policy_sha256=D3_DIRECT_HYBRIDIZED_SPATIAL_POLICY_SHA256,
        receipt_sha256=receipt.sha256,
        semantic_receipt_sha256=receipt.normalized.semantic_receipt_sha256,
        candidate_sha256=receipt.normalized.candidate_sha256,
        slot_hz=receipt.normalized.slot_hz,
        objective_authority=receipt.normalized.objective_authority,
        qualified_level=receipt.normalized.qualified_level,
        cared_output_sha256=semantic_value_sha256(receipt.normalized.cared_output),
        source_profile_identity=receipt.normalized.cared_output["source_profile_identity"],
        grid_identity=receipt.normalized.cared_output["grid_identity"],
        extraction_profile=receipt.normalized.cared_output["extraction_profile"],
    )
end

d3_direct_hybridized_spatial_receipt_identity(
    authorization::D3AuthorizedDirectHybridizedSpatial,
) = d3_direct_hybridized_spatial_receipt_identity(authorization.receipt)

function authorize_d3_direct_hybridized_spatial_receipt(
    receipt::D3DirectHybridizedSpatialReceipt,
    candidate;
    slot_hz,
    objective_authority,
    expected_receipt_sha256=nothing,
)
    normalized = _reparse(receipt)
    !isnothing(expected_receipt_sha256) && receipt.sha256 !=
        validate_d3_direct_hybridized_spatial_receipt_identity(expected_receipt_sha256) && _fail(
            "direct_spatial.run_spec_mismatch",
            "Spatial receipt differs from the expected exact identity.",
        )
    values = _candidate(candidate)
    slot = _real(slot_hz, "authorized slot"; positive=true)
    current_objective_authority =
        validate_d3_direct_hybridized_objective_authority(objective_authority)
    values == normalized.candidate || _fail(
        "direct_spatial.candidate_mismatch",
        "Spatial receipt belongs to another exact candidate.",
    )
    slot == normalized.slot_hz || _fail(
        "direct_spatial.slot_mismatch",
        "Spatial receipt belongs to another slot.",
    )
    current_objective_authority == normalized.objective_authority || _fail(
        "direct_spatial.objective_authority_mismatch",
        "Spatial receipt belongs to another Objective authority.",
    )
    return D3AuthorizedDirectHybridizedSpatial(
        receipt,
        values,
        slot,
        normalized.cared_output,
        normalized.objective_authority,
    )
end

function authorize_d3_direct_hybridized_spatial_receipt(
    ::Nothing,
    candidate;
    slot_hz,
    objective_authority,
    expected_receipt_sha256=nothing,
)
    _fail(
        "direct_spatial.missing",
        "Candidate has no direct-Hybridized spatial qualification receipt.",
    )
end

function revalidate_d3_direct_hybridized_spatial_receipt(
    authorization::D3AuthorizedDirectHybridizedSpatial,
    candidate;
    slot_hz,
    objective_authority,
    expected_receipt_sha256=nothing,
)
    renewed = authorize_d3_direct_hybridized_spatial_receipt(
        authorization.receipt,
        candidate;
        slot_hz=slot_hz,
        objective_authority=objective_authority,
        expected_receipt_sha256=expected_receipt_sha256,
    )
    renewed.candidate == authorization.candidate &&
        renewed.slot_hz == authorization.slot_hz &&
        renewed.cared_output == authorization.cared_output &&
        renewed.objective_authority == authorization.objective_authority || _fail(
            "direct_spatial.stale",
            "Authorized direct-Hybridized spatial binding changed during revalidation.",
        )
    return renewed
end

function validate_d3_direct_hybridized_spatial_authorization_match(
    authorization::D3AuthorizedDirectHybridizedSpatial,
    current_cared_output,
)
    current = validate_d3_direct_hybridized_cared_output(current_cared_output)
    current == authorization.cared_output || _fail(
        "direct_spatial.foundation_mismatch",
        "Current direct-Hybridized foundation differs from the authorized finest endpoint.",
    )
    return authorization
end

function evaluate_d3_direct_hybridized_objective_with_spatial_evidence(
    authorization::D3AuthorizedDirectHybridizedSpatial,
    candidate,
    current_cared_output;
    slot_hz,
    objective_authority,
    objective_evaluator,
)
    renewed = revalidate_d3_direct_hybridized_spatial_receipt(
        authorization,
        candidate;
        slot_hz=slot_hz,
        objective_authority=objective_authority,
    )
    validate_d3_direct_hybridized_spatial_authorization_match(
        renewed,
        current_cared_output,
    )
    return objective_evaluator(renewed)
end

end
