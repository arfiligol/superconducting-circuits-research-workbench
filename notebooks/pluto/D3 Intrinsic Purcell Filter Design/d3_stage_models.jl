# D3 revision-10 direct-Hybridized candidate construction. The sole search
# authority consumes all six physical coordinates in the distributed/lumped
# Circuit Plan. Equivalent construction remains a winner-only closure tool.
# Cost semantics and optimizer orchestration remain outside this file.

using LinearAlgebra
using SHA
using SuperconductingCircuitsCore

isdefined(@__MODULE__, :D3IDCInput) ||
    include(joinpath(@__DIR__, "d3_idc_input.jl"))
using .D3IDCInput: D3IDCMapping, d3_idc_mapping_semantic_sha256

isdefined(@__MODULE__, :D3LCQualificationReceipt) ||
    include(joinpath(@__DIR__, "d3_lc_qualification_receipt.jl"))
using .D3LCQualificationReceipt: D3AuthorizedStage2LC,
    D3_LC_QUALIFICATION_CONTRACT,
    D3_LC_QUALIFICATION_POLICY_SHA256

isdefined(@__MODULE__, :D3ResonatorInput) ||
    include(joinpath(@__DIR__, "d3_resonator_input.jl"))
using .D3ResonatorInput: D3Rev10Q2DInput, validate_d3_rev10_q2d_input

isdefined(@__MODULE__, :D3FloatingQubitInput) ||
    include(joinpath(@__DIR__, "d3_floating_qubit_input.jl"))
using .D3FloatingQubitInput: load_floating_qubit_nominal_input

const D3_PHYSICAL_VARIABLE_ORDER = (
    :lr_open_m,
    :lr_short_m,
    :lc_m,
    :lp_open_m,
    :lp_short_m,
    :u_IDC,
)

const D3_STAGE2_VARIABLE_ORDER = D3_PHYSICAL_VARIABLE_ORDER
const D3_TARGETED_SCHUR_CONTEXT_CONTRACT =
    "d3-rev10-fixed-node-targeted-schur-objective-context.v1"
const D3_TARGETED_SCHUR_CARED_OUTPUT_CONTRACT =
    "d3-rev10-targeted-schur-cared-output.v1"

struct D3DirectHybridizedInputs{Q,I,U,F,S}
    q2d_input::Q
    idc_mapping::I
    qubit::U
    feedline::F
    source_identity::S
end

struct D3DirectHybridizedGridPlan{C,B}
    contract_id::String
    refinement_level::Int
    candidate::NamedTuple
    fixed_input_canonical_sha256::String
    counts::C
    boundaries_m::B
    canonical_sha256::String
end

struct D3TargetedSchurNotEvaluable{D} <: Exception
    code::String
    reason::String
    details::D
end

Base.showerror(io::IO, failure::D3TargetedSchurNotEvaluable) =
    print(io, failure.code, ": ", failure.reason)

function _d3_targeted_fail(code, reason, details=nothing)
    throw(D3TargetedSchurNotEvaluable(String(code), String(reason), details))
end

struct D3TargetedSchurObjectiveContext{R,I,G,F,N,X,S,P}
    contract_id::String
    id::String
    reference_candidate::R
    fixed_inputs::I
    grid_plan::G
    full_kernel::F
    notch_kernel::N
    fixed_schur_context::X
    source_profile_identity::S
    provenance::P
end

struct D3TargetedSchurCaredOutput{C,S,G,E,V}
    contract_id::String
    stage_id::Symbol
    model_family::Symbol
    slot_hz::Float64
    candidate::C
    f_r_eff_hz::Float64
    f_p_eff_hz::Float64
    f_n_hz::Float64
    abs_real_J_eff_hz::Float64
    local_hybrid_kappa_sum_hz::Float64
    local_hybrid_linewidth_fraction_min::Float64
    local_hybrid_linewidth_fraction_max::Float64
    source_profile_identity::S
    grid_identity::G
    extraction_profile::E
    validity::V
end

const D3_RESPONSE_EQUIVALENT_VARIABLE_ORDER = (
    :Cr_f,
    :Lr_h,
    :Cp_f,
    :Lp_h,
    :Cn_f,
    :Ln_h,
    :u_IDC,
)

const D3_SELECTED_IDC_MAPPING_ID =
    "d3-same-die-filter-feedline-idc-q3d-gap8-linear-length-v1"
const D3_SELECTED_IDC_MAPPING_SHA256 =
    "db549a78564ab1dd25aba4cd0004304651ea3da7a1e66ce92bbb31bceb79e66c"
const D3_SELECTED_IDC_SOURCE_SHA256 =
    "6a54fec0669c01dacf433f3cc639192e5e5202ae232aa5b1e786ac7147b172e3"
const D3_SELECTED_IDC_SEMANTIC_SHA256 =
    "bd187b234e402b2a1dcd03009dcc07354f53721bf81b251e63a50f0aeb4435eb"
struct D3Stage2ResonatorMapping{L,S,C}
    fixed_line_input::L
    settings::S
    contract::C
    mapping_sha256::String
end

function (mapping::D3Stage2ResonatorMapping)(lengths)
    return _d3_stage2_evaluate_response_match(mapping, lengths)
end

function _d3_stage_positive(candidate, name, label)
    hasproperty(candidate, name) || error("$(label) is missing $(name).")
    raw = getproperty(candidate, name)
    raw isa Real || error("$(label) $(name) must be real.")
    value = Float64(raw)
    isfinite(value) && value > 0 || error(
        "$(label) $(name) must be finite and positive.",
    )
    return value
end

function _d3_stage_require_exact_fields(candidate, expected, label)
    actual = Tuple(propertynames(candidate))
    Set(actual) == Set(expected) || error(
        "$(label) fields must be exactly $(collect(expected)); received $(collect(actual)).",
    )
    return nothing
end

function _d3_stage_idc_triplet(idc_mapping, u_idc)
    u_idc isa Real || error("D3 IDC u_IDC coordinate must be real.")
    u_idc_value = Float64(u_idc)
    isfinite(u_idc_value) && u_idc_value > 0 || error(
        "D3 IDC u_IDC coordinate must be finite and positive.",
    )
    applicable(idc_mapping, u_idc_value) || error(
        "D3 IDC mapping must be callable with the scalar u_IDC coordinate.",
    )
    raw = idc_mapping(u_idc_value)
    required = (
        :idc_filter_ground_capacitance_f,
        :idc_feedline_ground_capacitance_f,
        :idc_mutual_capacitance_f,
        :mapping_id,
        :mapping_sha256,
        :mapping_semantic_sha256,
        :source_mapping_id,
        :source_length_range_um,
        :runtime_length_domain,
        :evaluation_source,
    )
    all(name -> hasproperty(raw, name), required) || error(
        "D3 IDC mapping must return all capacitances, identities, source support, and runtime classification.",
    )
    values = (
        idc_filter_ground_capacitance_f=_d3_stage_positive(
            raw,
            :idc_filter_ground_capacitance_f,
            "D3 IDC mapping result",
        ),
        idc_feedline_ground_capacitance_f=_d3_stage_positive(
            raw,
            :idc_feedline_ground_capacitance_f,
            "D3 IDC mapping result",
        ),
        idc_mutual_capacitance_f=_d3_stage_positive(
            raw,
            :idc_mutual_capacitance_f,
            "D3 IDC mapping result",
        ),
    )
    mapping_id = strip(String(raw.mapping_id))
    mapping_sha256 = lowercase(strip(String(raw.mapping_sha256)))
    mapping_semantic_sha256 = lowercase(strip(String(raw.mapping_semantic_sha256)))
    source_mapping_id = strip(String(raw.source_mapping_id))
    isempty(mapping_id) && error("D3 IDC mapping id must not be empty.")
    isempty(source_mapping_id) && error("D3 IDC source mapping id must not be empty.")
    occursin(r"^[0-9a-f]{64}$", mapping_sha256) || error(
        "D3 IDC mapping SHA-256 must contain 64 lowercase hexadecimal characters.",
    )
    occursin(r"^[0-9a-f]{64}$", mapping_semantic_sha256) || error(
        "D3 IDC mapping semantic SHA-256 must contain 64 lowercase hexadecimal characters.",
    )
    source_length_range_um = Tuple(Float64.(collect(raw.source_length_range_um)))
    length(source_length_range_um) == 2 &&
        all(isfinite, source_length_range_um) &&
        0 < source_length_range_um[1] < source_length_range_um[2] || error(
        "D3 IDC source length support must contain two increasing positive bounds.",
    )
    runtime_length_domain = strip(String(raw.runtime_length_domain))
    runtime_length_domain == "closed_source_support_um" || error(
        "D3 IDC runtime length domain must be the closed source-support interval in um.",
    )
    source_length_range_um[1] <= u_idc_value <= source_length_range_um[2] ||
        error(
            "D3 IDC u_IDC coordinate must be within the declared closed source support.",
        )
    evaluation_source = strip(String(raw.evaluation_source))
    evaluation_source == "linear_length_least_squares_interpolation" || error(
        "D3 IDC evaluation source must be linear-length least-squares interpolation.",
    )
    return merge(
        values,
        (
            u_IDC=u_idc_value,
            mapping_id=mapping_id,
            mapping_sha256=mapping_sha256,
            mapping_semantic_sha256=mapping_semantic_sha256,
            source_mapping_id=source_mapping_id,
            source_length_range_um=source_length_range_um,
            runtime_length_domain=runtime_length_domain,
            evaluation_source=evaluation_source,
        ),
    )
end

function _d3_stage_require_physical_idc_mapping(idc_mapping::D3IDCMapping)
    idc_mapping.gap_um == 8.0 || error(
        "D3 physical stages require the Q3D IDC mapping evaluated at the accepted 8 um gap.",
    )
    idc_mapping.mapping_id == D3_SELECTED_IDC_MAPPING_ID || error(
        "D3 physical stages require the selected three-branch IDC mapping id.",
    )
    lowercase(strip(idc_mapping.mapping_sha256)) ==
        D3_SELECTED_IDC_MAPPING_SHA256 || error(
        "D3 physical IDC mapping SHA-256 does not match the selected artifact.",
    )
    get(idc_mapping.source_artifact, "sha256", nothing) ==
        D3_SELECTED_IDC_SOURCE_SHA256 || error(
        "D3 physical IDC mapping source SHA-256 does not match the selected Q3D workbook.",
    )
    idc_mapping.valid_gap_range_um == (5.0, 10.0) &&
        idc_mapping.source_length_range_um == (35.0, 75.0) &&
        idc_mapping.runtime_length_domain == "closed_source_support_um" || error(
        "D3 physical IDC mapping source support or runtime domain is not the selected contract.",
    )
    d3_idc_mapping_semantic_sha256(idc_mapping) ==
        D3_SELECTED_IDC_SEMANTIC_SHA256 || error(
        "D3 physical IDC mapping contents do not match the selected v1 artifact.",
    )
    return idc_mapping
end

function _d3_stage_require_physical_idc_mapping(idc_mapping)
    error(
        "D3 Stage-2/3 physical candidates require D3IDCInput.D3IDCMapping " *
        "loaded from the validated three-branch Q3D artifact; raw callables are diagnostic-only.",
    )
end

function _d3_stage_fixed_qubit_keywords(fixed)
    required = (
        :c0r_f,
        :c01_f,
        :c02_f,
        :c12_qubit_f,
        :cr1_f,
        :cr2_f,
        :l_j_per_junction_h,
    )
    return NamedTuple{
        required,
    }(Tuple(_d3_stage_positive(fixed, name, "D3 fixed qubit input") for name in required))
end

function _d3_stage_sha256(value, label)
    text = lowercase(strip(String(value)))
    occursin(r"^[0-9a-f]{64}$", text) || error(
        "$(label) must contain 64 lowercase hexadecimal characters.",
    )
    return text
end

function _d3_q3d_model_identity(model)
    branch_fields = (
        :C0r_fF,
        :C01_fF,
        :C02_fF,
        :C12_fF,
        :Cr1_fF,
        :Cr2_fF,
        :L_J_per_junction_nH,
    )
    all(name -> hasproperty(model, name), branch_fields) || error(
        "D3 Q3D floating-qubit model is missing one or more normalized branch values.",
    )
    values = NamedTuple{branch_fields}(Tuple(
        begin
            value = Float64(getproperty(model, name))
            isfinite(value) && value > 0 || error(
                "D3 Q3D floating-qubit $(name) must be finite and positive.",
            )
            value
        end
        for name in branch_fields
    ))
    hasproperty(model, :model_id) && hasproperty(model, :capacitance_source_id) || error(
        "D3 Q3D floating-qubit model must declare model_id and capacitance_source_id.",
    )
    model_id = strip(String(model.model_id))
    capacitance_source_id = strip(String(model.capacitance_source_id))
    !isempty(model_id) && !isempty(capacitance_source_id) || error(
        "D3 Q3D floating-qubit model/source identities must be nonempty.",
    )
    hasproperty(model, :electrostatic_reduction) || error(
        "D3 Q3D floating-qubit model must carry its validated electrostatic reduction.",
    )
    reduction = model.electrostatic_reduction
    hasproperty(reduction, :input_schema) || error(
        "D3 Q3D electrostatic reduction must declare input_schema.",
    )
    input_schema = strip(String(reduction.input_schema))
    !isempty(input_schema) || error(
        "D3 Q3D electrostatic reduction input_schema must be nonempty.",
    )
    reduction_json = SuperconductingCircuitsCore.JSON3.write(reduction)
    return (
        model_id=model_id,
        capacitance_source_id=capacitance_source_id,
        input_schema=input_schema,
        branch_values_fF_and_nH=values,
        electrostatic_reduction_sha256=
            bytes2hex(SHA.sha256(codeunits(reduction_json))),
    )
end

function _d3_require_same_q3d_model(supplied_model, reloaded_model)
    supplied = _d3_q3d_model_identity(supplied_model)
    reloaded = _d3_q3d_model_identity(reloaded_model)
    supplied == reloaded || error(
        "D3 Q3D floating-qubit values or reduction evidence disagree with the exact source bytes.",
    )
    return reloaded
end

function _d3_bind_q3d_authority(raw_authority)
    required = (:model, :input_path, :input_sha256)
    all(name -> hasproperty(raw_authority, name), required) || error(
        "D3 Q3D authority must be the validated nominal-loader result with model, input_path, and input_sha256.",
    )
    input_path = abspath(String(raw_authority.input_path))
    isfile(input_path) || error(
        "D3 Q3D authority source file does not exist: $(input_path)",
    )
    declared_sha256 = _d3_stage_sha256(
        raw_authority.input_sha256,
        "D3 Q3D floating-qubit input SHA-256",
    )
    supplied_reduction = hasproperty(raw_authority.model, :electrostatic_reduction) ?
        raw_authority.model.electrostatic_reduction : error(
            "D3 Q3D authority model is missing electrostatic_reduction.",
        )
    gap_um = hasproperty(supplied_reduction, :evaluation_gap_um) ?
        supplied_reduction.evaluation_gap_um : nothing
    reloaded = load_floating_qubit_nominal_input(
        input_path,
        (; kwargs...) -> (; kwargs...);
        gap_um=gap_um,
    )
    reloaded_sha256 = _d3_stage_sha256(
        reloaded.input_sha256,
        "D3 reloaded Q3D floating-qubit input SHA-256",
    )
    reloaded_sha256 == declared_sha256 || error(
        "D3 Q3D authority source bytes disagree with the declared SHA-256.",
    )
    identity = _d3_require_same_q3d_model(
        raw_authority.model,
        reloaded.model,
    )
    return (
        model=reloaded.model,
        identity=merge(identity, (input_sha256=reloaded_sha256,)),
    )
end

"""Bind the complete fixed input authority for direct-Hybridized Stage 2.

The sealed Rev10 Q2D input, reduced Q3D floating-qubit model, fixed feedline
discretization, and validated IDC mapping enter one typed bundle. The Task does
not construct an internal merged tuple.
"""
function bind_d3_stage2_direct_hybridized_inputs(
    q2d_input::D3Rev10Q2DInput,
    q3d_authority,
    idc_mapping::D3IDCMapping;
    feedline_length_m,
    feedline_n_sections,
    feedline_l_per_m_h,
    feedline_c_per_m_f,
    port_resistance_ohm,
)
    q2d = validate_d3_rev10_q2d_input(q2d_input)
    _d3_stage_require_physical_idc_mapping(idc_mapping)
    q3d = _d3_bind_q3d_authority(q3d_authority)
    q3d_qubit_model = q3d.model
    qubit_fields_fF = (
        c0r_f=:C0r_fF,
        c01_f=:C01_fF,
        c02_f=:C02_fF,
        c12_qubit_f=:C12_fF,
        cr1_f=:Cr1_fF,
        cr2_f=:Cr2_fF,
    )
    all(name -> hasproperty(q3d_qubit_model, name), values(qubit_fields_fF)) || error(
        "D3 Q3D floating-qubit model is missing one or more reduced Maxwell branches.",
    )
    hasproperty(q3d_qubit_model, :L_J_per_junction_nH) || error(
        "D3 Q3D floating-qubit model is missing L_J_per_junction_nH.",
    )
    qubit_values = NamedTuple{keys(qubit_fields_fF)}(Tuple(
        begin
            value = Float64(getproperty(q3d_qubit_model, source_name)) * 1.0e-15
            isfinite(value) && value > 0 || error(
                "D3 Q3D floating-qubit $(source_name) must be finite and positive.",
            )
            value
        end
        for source_name in values(qubit_fields_fF)
    ))
    l_j = Float64(q3d_qubit_model.L_J_per_junction_nH) * 1.0e-9
    isfinite(l_j) && l_j > 0 || error(
        "D3 Q3D floating-qubit per-junction inductance must be finite and positive.",
    )
    qubit = merge(qubit_values, (l_j_per_junction_h=l_j,))

    feedline_count = Int(feedline_n_sections)
    feedline_n_sections isa Integer && feedline_count >= 2 && iseven(feedline_count) || error(
        "D3 direct-Hybridized feedline_n_sections must be an even integer of at least two.",
    )
    feedline = (
        feedline_length_m=Float64(feedline_length_m),
        feedline_n_sections=feedline_count,
        feedline_l_per_m_h=Float64(feedline_l_per_m_h),
        feedline_c_per_m_f=Float64(feedline_c_per_m_f),
        port_resistance_ohm=Float64(port_resistance_ohm),
    )
    all(value -> isfinite(value) && value > 0, (
        feedline.feedline_length_m,
        feedline.feedline_l_per_m_h,
        feedline.feedline_c_per_m_f,
        feedline.port_resistance_ohm,
    )) || error(
        "D3 direct-Hybridized fixed feedline values must be finite and positive.",
    )
    feedline.port_resistance_ohm == 50.0 || error(
        "D3 direct-Hybridized matched ports are fixed at exactly 50 ohm.",
    )
    q2d_identity = (
        artifact_id=q2d.q2d_artifact_id,
        artifact_sha256=q2d.q2d_artifact_sha256,
        topology_id=q2d.q2d_topology_id,
        geometry_um=q2d.q2d_geometry_um,
        section_length_m=q2d.section_length_m,
        mtl_section_length_m=q2d.mtl_section_length_m,
    )
    source_identity = (
        contract_id="d3-rev10-direct-hybridized-fixed-input.v1",
        q2d=q2d_identity,
        q3d=q3d.identity,
        idc=(
            mapping_id=idc_mapping.mapping_id,
            mapping_sha256=idc_mapping.mapping_sha256,
            mapping_semantic_sha256=
                d3_idc_mapping_semantic_sha256(idc_mapping),
            source_mapping_id=idc_mapping.source_mapping_id,
            source_length_range_um=idc_mapping.source_length_range_um,
            runtime_length_domain=idc_mapping.runtime_length_domain,
            source_artifact=idc_mapping.source_artifact,
        ),
        feedline=feedline,
    )
    return D3DirectHybridizedInputs(
        q2d_input,
        idc_mapping,
        qubit,
        feedline,
        merge(source_identity, (
            canonical_sha256=bytes2hex(SHA.sha256(codeunits(
                SuperconductingCircuitsCore.JSON3.write(source_identity),
            ))),
        )),
    )
end

function _d3_stage_physical_lengths(candidate, label)
    return (
        lr_open_m=_d3_stage_positive(candidate, :lr_open_m, label),
        lr_short_m=_d3_stage_positive(candidate, :lr_short_m, label),
        lc_m=_d3_stage_positive(candidate, :lc_m, label),
        lp_open_m=_d3_stage_positive(candidate, :lp_open_m, label),
        lp_short_m=_d3_stage_positive(candidate, :lp_short_m, label),
    )
end

function _d3_stage2_direct_candidate(candidate)
    _d3_stage_require_exact_fields(
        candidate,
        D3_STAGE2_VARIABLE_ORDER,
        "D3 direct-Hybridized Stage-2 candidate",
    )
    return NamedTuple{D3_STAGE2_VARIABLE_ORDER}(Tuple(
        _d3_stage_positive(
            candidate,
            name,
            "D3 direct-Hybridized Stage-2 candidate",
        )
        for name in D3_STAGE2_VARIABLE_ORDER
    ))
end

"""Construct the exact Circuit-owned grid plan for one candidate and level.

Level zero derives the existing CPW/MTL/feedline discretization from the sealed
fixed input. Each subsequent level bisects every existing section, so all five
actual section counts are exactly doubled without reconstructing a grid from
halved maximum-cell lengths.
"""
function d3_stage2_direct_hybridized_grid_plan(
    candidate,
    inputs::D3DirectHybridizedInputs;
    refinement_level,
)
    refinement_level isa Integer && refinement_level >= 0 || error(
        "D3 direct-Hybridized refinement_level must be a nonnegative integer.",
    )
    normalized_candidate = _d3_stage2_direct_candidate(candidate)
    lengths = _d3_stage_physical_lengths(
        normalized_candidate,
        "D3 direct-Hybridized Stage-2 candidate",
    )
    selected_lines = _d3_selected_q2d_line_input(inputs.q2d_input)
    lines = _d3_hybridized_fixed_line_keywords(selected_lines)
    feedline = _d3_distributed_feedline_keywords(inputs.feedline)
    factor = 1 << Int(refinement_level)
    factor > 0 || error("D3 direct-Hybridized refinement factor overflowed.")
    readout = _d3_refined_hybridized_line_breakpoints(
        lengths.lr_short_m,
        lengths.lc_m,
        lengths.lr_open_m,
        lines.section_length_m,
        lines.mtl_section_length_m,
        Int(refinement_level),
    )
    filter = _d3_refined_hybridized_line_breakpoints(
        lengths.lp_short_m,
        lengths.lc_m,
        lengths.lp_open_m,
        lines.section_length_m,
        lines.mtl_section_length_m,
        Int(refinement_level),
    )
    readout.mtl_count == filter.mtl_count || error(
        "D3 direct-Hybridized readout/filter MTL section counts disagree.",
    )
    base_feedline_half_count = feedline.feedline_n_sections ÷ 2
    feedline_half_count = base_feedline_half_count * factor
    feedline_half_length_m = feedline.feedline_length_m / 2
    feedline_left = _d3_exact_interval_breakpoints(
        0.0,
        feedline_half_length_m,
        feedline_half_count,
    )
    feedline_right = _d3_exact_interval_breakpoints(
        0.0,
        feedline_half_length_m,
        feedline_half_count,
    )
    counts = (
        readout_resonator=readout.count,
        filter_resonator=filter.count,
        mtl=readout.mtl_count,
        feedline_left=feedline_half_count,
        feedline_right=feedline_half_count,
    )
    boundaries_m = (
        readout_resonator_boundaries_m=readout.boundaries_m,
        filter_resonator_boundaries_m=filter.boundaries_m,
        feedline_left_boundaries_m=feedline_left,
        feedline_right_boundaries_m=feedline_right,
    )
    payload = (
        contract_id="d3-rev10-direct-hybridized-grid-plan.v1",
        refinement_level=Int(refinement_level),
        candidate=normalized_candidate,
        fixed_input_canonical_sha256=inputs.source_identity.canonical_sha256,
        counts=counts,
        boundaries_m=boundaries_m,
    )
    canonical_sha256 = bytes2hex(SHA.sha256(codeunits(
        SuperconductingCircuitsCore.JSON3.write(payload),
    )))
    return D3DirectHybridizedGridPlan(
        payload.contract_id,
        payload.refinement_level,
        payload.candidate,
        payload.fixed_input_canonical_sha256,
        counts,
        boundaries_m,
        canonical_sha256,
    )
end

function _d3_validate_stage2_direct_grid_plan(
    candidate,
    inputs::D3DirectHybridizedInputs,
    grid_plan::D3DirectHybridizedGridPlan,
)
    expected = d3_stage2_direct_hybridized_grid_plan(
        candidate,
        inputs;
        refinement_level=grid_plan.refinement_level,
    )
    for name in propertynames(expected)
        getproperty(grid_plan, name) == getproperty(expected, name) || error(
            "D3 direct-Hybridized grid plan $(name) disagrees with its candidate or fixed input.",
        )
    end
    return grid_plan
end

function _d3_validate_targeted_schur_grid_plan(
    candidate,
    inputs::D3DirectHybridizedInputs,
    grid_plan::D3DirectHybridizedGridPlan,
)
    grid_plan.contract_id == "d3-rev10-direct-hybridized-grid-plan.v1" || error(
        "D3 targeted-Schur grid plan contract is unsupported.",
    )
    grid_plan.refinement_level >= 0 || error(
        "D3 targeted-Schur grid refinement level must be nonnegative.",
    )
    refinement_factor = 1 << grid_plan.refinement_level
    refinement_factor > 0 || error("D3 targeted-Schur refinement factor overflowed.")
    grid_plan.candidate == candidate || error(
        "D3 targeted-Schur grid plan belongs to a different reference candidate.",
    )
    grid_plan.fixed_input_canonical_sha256 == inputs.source_identity.canonical_sha256 ||
        error("D3 targeted-Schur grid plan belongs to different fixed inputs.")
    count_names = (
        :readout_resonator,
        :filter_resonator,
        :mtl,
        :feedline_left,
        :feedline_right,
    )
    Tuple(propertynames(grid_plan.counts)) == count_names || error(
        "D3 targeted-Schur grid counts have the wrong fields.",
    )
    all(name -> getproperty(grid_plan.counts, name) isa Integer &&
        getproperty(grid_plan.counts, name) > 0, count_names) || error(
        "D3 targeted-Schur grid counts must be positive integers.",
    )
    grid_plan.counts.feedline_left == grid_plan.counts.feedline_right &&
        grid_plan.counts.feedline_left + grid_plan.counts.feedline_right ==
            inputs.feedline.feedline_n_sections * refinement_factor || error(
        "D3 targeted-Schur split-feedline counts disagree with the fixed input.",
    )
    boundary_names = (
        :readout_resonator_boundaries_m,
        :filter_resonator_boundaries_m,
        :feedline_left_boundaries_m,
        :feedline_right_boundaries_m,
    )
    Tuple(propertynames(grid_plan.boundaries_m)) == boundary_names || error(
        "D3 targeted-Schur grid boundaries have the wrong fields.",
    )
    count_by_boundary = (
        readout_resonator_boundaries_m=:readout_resonator,
        filter_resonator_boundaries_m=:filter_resonator,
        feedline_left_boundaries_m=:feedline_left,
        feedline_right_boundaries_m=:feedline_right,
    )
    for name in boundary_names
        values = getproperty(grid_plan.boundaries_m, name)
        length(values) == getproperty(
            grid_plan.counts,
            getproperty(count_by_boundary, name),
        ) + 1 || error("D3 targeted-Schur $(name) count disagrees with its array.")
        all(isfinite, values) && first(values) == 0.0 && all(diff(values) .> 0) ||
            error("D3 targeted-Schur $(name) must be finite and strictly increasing from zero.")
    end
    readout = grid_plan.boundaries_m.readout_resonator_boundaries_m
    filter = grid_plan.boundaries_m.filter_resonator_boundaries_m
    last(readout) == candidate.lr_short_m + candidate.lc_m + candidate.lr_open_m &&
        count(==(candidate.lr_short_m), readout) == 1 &&
        count(==(candidate.lr_short_m + candidate.lc_m), readout) == 1 || error(
        "D3 targeted-Schur readout boundaries do not contain the exact candidate endpoints.",
    )
    last(filter) == candidate.lp_short_m + candidate.lc_m + candidate.lp_open_m &&
        count(==(candidate.lp_short_m), filter) == 1 &&
        count(==(candidate.lp_short_m + candidate.lc_m), filter) == 1 || error(
        "D3 targeted-Schur filter boundaries do not contain the exact candidate endpoints.",
    )
    feedline_endpoint = inputs.feedline.feedline_length_m / 2
    last(grid_plan.boundaries_m.feedline_left_boundaries_m) == feedline_endpoint &&
        last(grid_plan.boundaries_m.feedline_right_boundaries_m) == feedline_endpoint || error(
        "D3 targeted-Schur feedline boundaries do not end at the fixed half length.",
    )
    payload = (
        contract_id=grid_plan.contract_id,
        refinement_level=grid_plan.refinement_level,
        candidate=grid_plan.candidate,
        fixed_input_canonical_sha256=grid_plan.fixed_input_canonical_sha256,
        counts=grid_plan.counts,
        boundaries_m=grid_plan.boundaries_m,
    )
    expected_sha256 = bytes2hex(SHA.sha256(codeunits(
        SuperconductingCircuitsCore.JSON3.write(payload),
    )))
    grid_plan.canonical_sha256 == expected_sha256 || error(
        "D3 targeted-Schur grid plan canonical SHA-256 is inconsistent.",
    )
    grid_plan.counts.mtl <= min(
        grid_plan.counts.readout_resonator,
        grid_plan.counts.filter_resonator,
    ) || error("D3 targeted-Schur MTL count exceeds a resonator section count.")
    return grid_plan
end

const _D3_TARGETED_SCHUR_LENGTH_COORDINATES = D3_STAGE2_VARIABLE_ORDER[1:5]

function _d3_targeted_segment(start_m, length_m, count)
    return collect(range(start_m; stop=start_m + length_m, length=count + 1))
end

function _d3_targeted_line_boundaries(short_m, coupling_m, open_m, counts)
    short = _d3_targeted_segment(0.0, short_m, counts.short)
    coupling = _d3_targeted_segment(short_m, coupling_m, counts.mtl)
    open = _d3_targeted_segment(short_m + coupling_m, open_m, counts.open)
    boundaries = vcat(short, coupling[2:end], open[2:end])
    all(diff(boundaries) .> 0) || error(
        "D3 targeted-Schur fixed-node boundaries must increase strictly.",
    )
    return boundaries
end

function _d3_targeted_line_counts(boundaries, short_m, coupling_m, label)
    endpoint(value) = begin
        matches = findall(candidate -> isapprox(
            candidate,
            value;
            atol=1.0e-12,
            rtol=1.0e-9,
        ), boundaries)
        length(matches) == 1 || error("$(label) endpoint is not unique in the fixed grid.")
        only(matches)
    end
    short_stop = endpoint(short_m)
    coupling_stop = endpoint(short_m + coupling_m)
    return (
        short=short_stop - 1,
        mtl=coupling_stop - short_stop,
        open=length(boundaries) - coupling_stop,
    )
end

function _d3_targeted_topology(reference_candidate, grid_plan)
    readout = _d3_targeted_line_counts(
        grid_plan.boundaries_m.readout_resonator_boundaries_m,
        reference_candidate.lr_short_m,
        reference_candidate.lc_m,
        "D3 targeted-Schur readout",
    )
    filter = _d3_targeted_line_counts(
        grid_plan.boundaries_m.filter_resonator_boundaries_m,
        reference_candidate.lp_short_m,
        reference_candidate.lc_m,
        "D3 targeted-Schur filter",
    )
    readout.mtl == filter.mtl == grid_plan.counts.mtl || error(
        "D3 targeted-Schur fixed MTL counts disagree.",
    )
    return (
        readout=readout,
        filter=filter,
        feedline_left=grid_plan.counts.feedline_left,
        feedline_right=grid_plan.counts.feedline_right,
    )
end

function _d3_targeted_candidate_boundaries(candidate, topology, grid_plan)
    return (
        readout_resonator_boundaries_m=_d3_targeted_line_boundaries(
            candidate.lr_short_m,
            candidate.lc_m,
            candidate.lr_open_m,
            topology.readout,
        ),
        filter_resonator_boundaries_m=_d3_targeted_line_boundaries(
            candidate.lp_short_m,
            candidate.lc_m,
            candidate.lp_open_m,
            topology.filter,
        ),
        feedline_left_boundaries_m=copy(
            grid_plan.boundaries_m.feedline_left_boundaries_m,
        ),
        feedline_right_boundaries_m=copy(
            grid_plan.boundaries_m.feedline_right_boundaries_m,
        ),
    )
end

function _d3_targeted_real_models(candidate, inputs, topology, grid_plan; id)
    normalized = _d3_stage2_direct_candidate(candidate)
    boundaries = _d3_targeted_candidate_boundaries(normalized, topology, grid_plan)
    idc = _d3_stage_idc_triplet(inputs.idc_mapping, normalized.u_IDC)
    qubit = _d3_stage_fixed_qubit_keywords(inputs.qubit)
    lines = _d3_hybridized_fixed_line_keywords(
        _d3_selected_q2d_line_input(inputs.q2d_input),
    )
    feedline = merge(_d3_distributed_feedline_keywords(inputs.feedline), (
        feedline_n_sections=topology.feedline_left + topology.feedline_right,
    ))
    full = build_d3_intrinsic_purcell_hybridized_circuit_plan(;
        id=String(id),
        idc_filter_ground_capacitance_f=idc.idc_filter_ground_capacitance_f,
        idc_feedline_ground_capacitance_f=idc.idc_feedline_ground_capacitance_f,
        idc_mutual_capacitance_f=idc.idc_mutual_capacitance_f,
        readout_length_m=normalized.lr_short_m + normalized.lc_m + normalized.lr_open_m,
        filter_length_m=normalized.lp_short_m + normalized.lc_m + normalized.lp_open_m,
        window_start_readout_m=normalized.lr_short_m,
        window_start_filter_m=normalized.lp_short_m,
        window_length_m=normalized.lc_m,
        mtl_section_length_m=normalized.lc_m / topology.readout.mtl,
        readout_l_per_m_h=lines.readout_l_per_m_h,
        readout_c_per_m_f=lines.readout_c_per_m_f,
        filter_l_per_m_h=lines.filter_l_per_m_h,
        filter_c_per_m_f=lines.filter_c_per_m_f,
        l_matrix_per_m_h=lines.l_matrix_per_m_h,
        c_matrix_per_m_f=lines.c_matrix_per_m_f,
        coupling_orientation=lines.coupling_orientation,
        qubit...,
        feedline...,
        readout_breakpoints_m=boundaries.readout_resonator_boundaries_m,
        filter_breakpoints_m=boundaries.filter_resonator_boundaries_m,
        feedline_left_breakpoints_m=boundaries.feedline_left_boundaries_m,
        feedline_right_breakpoints_m=boundaries.feedline_right_boundaries_m,
    )
    notch = build_d3_intrinsic_pair_notch_hybridized_circuit_plan(;
        id="$(id)-intrinsic-pair-notch",
        readout_length_m=normalized.lr_short_m + normalized.lc_m + normalized.lr_open_m,
        filter_length_m=normalized.lp_short_m + normalized.lc_m + normalized.lp_open_m,
        section_length_m=lines.section_length_m,
        mtl_section_length_m=normalized.lc_m / topology.readout.mtl,
        readout_l_per_m_h=lines.readout_l_per_m_h,
        readout_c_per_m_f=lines.readout_c_per_m_f,
        filter_l_per_m_h=lines.filter_l_per_m_h,
        filter_c_per_m_f=lines.filter_c_per_m_f,
        window_start_readout_m=normalized.lr_short_m,
        window_start_filter_m=normalized.lp_short_m,
        window_length_m=normalized.lc_m,
        l_matrix_per_m_h=lines.l_matrix_per_m_h,
        c_matrix_per_m_f=lines.c_matrix_per_m_f,
        coupling_orientation=lines.coupling_orientation,
        port_resistance_ohm=feedline.port_resistance_ohm,
        readout_breakpoints_m=boundaries.readout_resonator_boundaries_m,
        filter_breakpoints_m=boundaries.filter_resonator_boundaries_m,
    )
    return (
        full=d3_hybridized_compiled_model(full),
        notch=d3_auxiliary_compiled_port_model(
            notch;
            contract_id="d3-intrinsic-pair-rp-on-z21-zero.v1",
        ),
        boundaries_m=boundaries,
    )
end

function _d3_targeted_training_candidate(candidate, name, inputs)
    value = getproperty(candidate, name)
    trained = if name == :u_IDC
        bounds = inputs.idc_mapping.source_length_range_um
        step = 0.1 * (bounds[2] - bounds[1])
        value + step <= bounds[2] ? value + step : value - step
    else
        1.1 * value
    end
    trained > 0 && trained != value || error(
        "D3 targeted-Schur coefficient training could not perturb $(name).",
    )
    return merge(candidate, NamedTuple{(name,)}((trained,)))
end

function _d3_targeted_train_kernels(reference_candidate, inputs, topology, grid_plan, id)
    reference = _d3_targeted_real_models(
        reference_candidate,
        inputs,
        topology,
        grid_plan;
        id="$(id)-reference",
    )
    full_c_terms = Matrix{Float64}[]
    full_k_terms = Matrix{Float64}[]
    notch_c_terms = Matrix{Float64}[]
    notch_k_terms = Matrix{Float64}[]
    for name in D3_STAGE2_VARIABLE_ORDER
        perturbed_candidate = _d3_targeted_training_candidate(reference_candidate, name, inputs)
        perturbed = _d3_targeted_real_models(
            perturbed_candidate,
            inputs,
            topology,
            grid_plan;
            id="$(id)-training-$(name)",
        )
        size(perturbed.full.capacitance) == size(reference.full.capacitance) ||
            error("D3 targeted-Schur full topology changed during coefficient training.")
        x0 = getproperty(reference_candidate, name)
        x1 = getproperty(perturbed_candidate, name)
        push!(full_c_terms, (perturbed.full.capacitance - reference.full.capacitance) / (x1 - x0))
        if name in _D3_TARGETED_SCHUR_LENGTH_COORDINATES
            push!(full_k_terms, (perturbed.full.inverse_inductance - reference.full.inverse_inductance) / (inv(x1) - inv(x0)))
            push!(notch_c_terms, (perturbed.notch.capacitance - reference.notch.capacitance) / (x1 - x0))
            push!(notch_k_terms, (perturbed.notch.inverse_inductance - reference.notch.inverse_inductance) / (inv(x1) - inv(x0)))
        else
            perturbed.full.inverse_inductance == reference.full.inverse_inductance ||
                error("D3 targeted-Schur IDC coordinate changed inverse inductance.")
        end
    end
    full_c0 = copy(reference.full.capacitance)
    full_k0 = copy(reference.full.inverse_inductance)
    notch_c0 = copy(reference.notch.capacitance)
    notch_k0 = copy(reference.notch.inverse_inductance)
    for (index, name) in enumerate(D3_STAGE2_VARIABLE_ORDER)
        value = getproperty(reference_candidate, name)
        full_c0 .-= value .* full_c_terms[index]
    end
    for (index, name) in enumerate(_D3_TARGETED_SCHUR_LENGTH_COORDINATES)
        value = getproperty(reference_candidate, name)
        full_k0 .-= inv(value) .* full_k_terms[index]
        notch_c0 .-= value .* notch_c_terms[index]
        notch_k0 .-= inv(value) .* notch_k_terms[index]
    end
    full_kernel = (
        c0=full_c0,
        k0=full_k0,
        c_terms=NamedTuple{D3_STAGE2_VARIABLE_ORDER}(Tuple(full_c_terms)),
        k_terms=NamedTuple{_D3_TARGETED_SCHUR_LENGTH_COORDINATES}(Tuple(full_k_terms)),
        reference_model=reference.full,
    )
    notch_kernel = (
        c0=notch_c0,
        k0=notch_k0,
        c_terms=NamedTuple{_D3_TARGETED_SCHUR_LENGTH_COORDINATES}(Tuple(notch_c_terms)),
        k_terms=NamedTuple{_D3_TARGETED_SCHUR_LENGTH_COORDINATES}(Tuple(notch_k_terms)),
        reference_model=reference.notch,
    )
    return full_kernel, notch_kernel
end

function _d3_targeted_kernel_matrices(kernel, candidate, coordinates)
    capacitance = copy(kernel.c0)
    stiffness = copy(kernel.k0)
    for name in coordinates
        value = getproperty(candidate, name)
        capacitance .+= value .* getproperty(kernel.c_terms, name)
    end
    for name in _D3_TARGETED_SCHUR_LENGTH_COORDINATES
        value = getproperty(candidate, name)
        stiffness .+= inv(value) .* getproperty(kernel.k_terms, name)
    end
    return capacitance, stiffness
end

"""Build one immutable, shareable fixed-node targeted-Schur Objective context."""
function build_d3_stage2_targeted_schur_objective_context(
    reference_candidate,
    inputs::D3DirectHybridizedInputs;
    grid_plan::D3DirectHybridizedGridPlan,
    id="d3-stage2-targeted-schur-context",
)::D3TargetedSchurObjectiveContext
    candidate = _d3_stage2_direct_candidate(reference_candidate)
    grid = _d3_validate_targeted_schur_grid_plan(candidate, inputs, grid_plan)
    topology = _d3_targeted_topology(candidate, grid)
    full_kernel, notch_kernel = _d3_targeted_train_kernels(
        candidate,
        inputs,
        topology,
        grid,
        String(id),
    )
    fixed_schur_context = _d3_targeted_schur_fixed_context(
        full_kernel.reference_model,
    )
    full_kernel_identity = (
        c0_sha256=_d3_exact_n_matrix_sha256("d3-targeted-full-c0", full_kernel.c0),
        k0_sha256=_d3_exact_n_matrix_sha256("d3-targeted-full-k0", full_kernel.k0),
        c_term_sha256=NamedTuple{D3_STAGE2_VARIABLE_ORDER}(Tuple(
            _d3_exact_n_matrix_sha256("d3-targeted-full-c-$(name)", getproperty(full_kernel.c_terms, name))
            for name in D3_STAGE2_VARIABLE_ORDER
        )),
        k_term_sha256=NamedTuple{_D3_TARGETED_SCHUR_LENGTH_COORDINATES}(Tuple(
            _d3_exact_n_matrix_sha256("d3-targeted-full-k-$(name)", getproperty(full_kernel.k_terms, name))
            for name in _D3_TARGETED_SCHUR_LENGTH_COORDINATES
        )),
    )
    notch_kernel_identity = (
        c0_sha256=_d3_exact_n_matrix_sha256("d3-targeted-notch-c0", notch_kernel.c0),
        k0_sha256=_d3_exact_n_matrix_sha256("d3-targeted-notch-k0", notch_kernel.k0),
        c_term_sha256=NamedTuple{_D3_TARGETED_SCHUR_LENGTH_COORDINATES}(Tuple(
            _d3_exact_n_matrix_sha256("d3-targeted-notch-c-$(name)", getproperty(notch_kernel.c_terms, name))
            for name in _D3_TARGETED_SCHUR_LENGTH_COORDINATES
        )),
        k_term_sha256=NamedTuple{_D3_TARGETED_SCHUR_LENGTH_COORDINATES}(Tuple(
            _d3_exact_n_matrix_sha256("d3-targeted-notch-k-$(name)", getproperty(notch_kernel.k_terms, name))
            for name in _D3_TARGETED_SCHUR_LENGTH_COORDINATES
        )),
    )
    source_payload = (
        fixed_input_identity=inputs.source_identity,
        reference_grid_plan_sha256=grid.canonical_sha256,
        topology_counts=topology,
        full_kernel_identity=full_kernel_identity,
        notch_kernel_identity=notch_kernel_identity,
        full_selector_sha256=full_kernel.reference_model.provenance.selector_sha256,
        fixed_conductance_sha256=_d3_exact_n_matrix_sha256(
            "d3-targeted-fixed-port-conductance",
            fixed_schur_context.conductance,
        ),
        full_coordinate_order=Tuple(full_kernel.reference_model.coordinate_order),
        anchored_coordinate_indices=full_kernel.reference_model.anchored_coordinate_indices,
        notch_port_indices=Tuple(notch_kernel.reference_model.port_indices),
    )
    source_profile_identity = merge(source_payload, (
        canonical_sha256=bytes2hex(SHA.sha256(codeunits(
            SuperconductingCircuitsCore.JSON3.write(source_payload),
        ))),
    ))
    return D3TargetedSchurObjectiveContext(
        D3_TARGETED_SCHUR_CONTEXT_CONTRACT,
        String(id),
        candidate,
        inputs,
        grid,
        full_kernel,
        notch_kernel,
        fixed_schur_context,
        source_profile_identity,
        (
            topology_counts=topology,
            coefficient_construction=:exact_fixed_node_affine_C_inverse_length_K,
            external_conductance=:fixed_matched_port_selector,
        ),
    )
end

function _d3_stage2_response_matched_resonators(
    resonator_mapping::D3Stage2ResonatorMapping,
    lengths,
)
    applicable(resonator_mapping, lengths) || error(
        "D3 Stage-2 resonator mapping must be callable with the five physical lengths.",
    )
    raw = resonator_mapping(lengths)
    required = (
        :Cr_f,
        :Lr_h,
        :Cp_f,
        :Lp_h,
        :Cn_f,
        :Ln_h,
        :mapping_id,
        :mapping_sha256,
        :q2d_artifact_id,
        :q2d_artifact_sha256,
        :topology_id,
        :match_contract_id,
        :fixed_line_input_sha256,
        :fixed_line_input_identity,
        :fixed_line_input_identity_canonical_json,
        :match_evidence,
    )
    all(name -> hasproperty(raw, name), required) || error(
        "D3 Stage-2 resonator mapping must return six response-matched LC values, " *
        "Q2D/topology provenance, its match contract, and fixed-line identity.",
    )
    contract = resonator_mapping.contract
    for (name, expected) in (
        (:mapping_id, "d3-continuous-ground-response-match"),
        (:q2d_artifact_id, contract.q2d_artifact_id),
        (:q2d_artifact_sha256, contract.q2d_artifact_sha256),
        (:topology_id, contract.topology_id),
        (:match_contract_id, contract.match_contract_id),
        (:fixed_line_input_sha256, contract.fixed_line_input_sha256),
    )
        String(getproperty(raw, name)) == String(expected) || error(
            "D3 Stage-2 response match $(name) disagrees with its attested mapping contract.",
        )
    end
    values = NamedTuple{
        (:Cr_f, :Lr_h, :Cp_f, :Lp_h, :Cn_f, :Ln_h),
    }(Tuple(
        _d3_stage_positive(raw, name, "D3 Stage-2 response match")
        for name in (:Cr_f, :Lr_h, :Cp_f, :Lp_h, :Cn_f, :Ln_h)
    ))
    strings = NamedTuple{
        (:mapping_id, :q2d_artifact_id, :topology_id, :match_contract_id),
    }(Tuple(
        begin
            value = strip(String(getproperty(raw, name)))
            isempty(value) && error("D3 Stage-2 $(name) must not be empty.")
            value
        end
        for name in (
            :mapping_id,
            :q2d_artifact_id,
            :topology_id,
            :match_contract_id,
        )
    ))
    hashes = NamedTuple{
        (
            :mapping_sha256,
            :q2d_artifact_sha256,
            :fixed_line_input_sha256,
        ),
    }(Tuple(
        begin
            value = lowercase(strip(String(getproperty(raw, name))))
            occursin(r"^[0-9a-f]{64}$", value) || error(
                "D3 Stage-2 $(name) must contain 64 lowercase hexadecimal characters.",
            )
            value
        end
        for name in (
            :mapping_sha256,
            :q2d_artifact_sha256,
            :fixed_line_input_sha256,
        )
    ))
    canonical_identity = String(raw.fixed_line_input_identity_canonical_json)
    canonical_identity == SuperconductingCircuitsCore.JSON3.write(
        raw.fixed_line_input_identity,
    ) || error(
        "D3 Stage-2 fixed-line canonical JSON disagrees with its normalized identity.",
    )
    bytes2hex(SHA.sha256(codeunits(canonical_identity))) ==
        hashes.fixed_line_input_sha256 || error(
        "D3 Stage-2 fixed-line identity SHA-256 disagrees with its canonical JSON.",
    )
    return merge(
        values,
        strings,
        hashes,
        (
            physical_lengths=lengths,
            fixed_line_input_identity=raw.fixed_line_input_identity,
            fixed_line_input_identity_canonical_json=canonical_identity,
            match_evidence=raw.match_evidence,
        ),
    )
end

function _d3_stage2_response_matched_resonators(resonator_mapping, lengths)
    error(
        "D3 Stage-2 requires D3Stage2ResonatorMapping from the selected Q2D " *
        "response-match constructor; raw callables cannot enter the physical evaluator.",
    )
end

function _d3_stage2_validate_resonator_mapping(
    resonator_mapping::D3Stage2ResonatorMapping,
    fixed,
)
    selected = _d3_selected_q2d_line_input(fixed)
    mapping_selected = _d3_selected_q2d_line_input(
        resonator_mapping.fixed_line_input,
    )
    selected.fixed_line_input_sha256 ==
        mapping_selected.fixed_line_input_sha256 || error(
        "D3 Stage-2 resonator mapping does not use the supplied selected fixed input.",
    )
    contract = resonator_mapping.contract
    expected = (
        match_contract_id="d3-cpw-mtl-response-match.v1",
        q2d_artifact_id=selected.q2d_artifact_id,
        q2d_artifact_sha256=selected.q2d_artifact_sha256,
        topology_id=String(selected.q2d_topology_id),
        fixed_line_input_sha256=selected.fixed_line_input_sha256,
        settings=resonator_mapping.settings,
    )
    contract == expected || error(
        "D3 Stage-2 resonator mapping contract is not bound to the selected fixed input and settings.",
    )
    expected_sha256 = bytes2hex(SHA.sha256(codeunits(
        SuperconductingCircuitsCore.JSON3.write(expected),
    )))
    resonator_mapping.mapping_sha256 == expected_sha256 || error(
        "D3 Stage-2 resonator mapping SHA-256 disagrees with its declared contract.",
    )
    return resonator_mapping
end

function _d3_stage2_receipt_qualified_resonators(
    authorization::D3AuthorizedStage2LC,
    resonator_mapping::D3Stage2ResonatorMapping,
    lengths,
)
    selected = _d3_selected_q2d_line_input(resonator_mapping.fixed_line_input)
    receipt = authorization.receipt
    lc = authorization.lc_readback
    return merge(
        lc,
        (
            mapping_id="d3-frequency-priority-lc-qualification-receipt",
            mapping_sha256=receipt.sha256,
            q2d_artifact_id=selected.q2d_artifact_id,
            q2d_artifact_sha256=selected.q2d_artifact_sha256,
            topology_id=String(selected.q2d_topology_id),
            fixed_line_input_sha256=selected.fixed_line_input_sha256,
            fixed_line_input_identity=selected.fixed_line_input_identity,
            fixed_line_input_identity_canonical_json=
                selected.fixed_line_input_identity_canonical_json,
            match_contract_id=D3_LC_QUALIFICATION_CONTRACT,
            physical_lengths=lengths,
            match_evidence=(
                reference_model=(
                    role=:receipt_qualified_physical_length_to_equivalent_lc,
                    final_stage2_hb_model=:resolved_lumped_equivalent_circuit,
                    topology=:two_grounded_head_open_tail_quarter_wave_resonators_with_mtl_window,
                    terminal_coordinates=(:readout_open_tail, :filter_open_tail),
                    diagonal_match_state=:mtl_mutual_terms_disabled_diagonal_loading_preserved,
                    bridge_match_state=:full_mtl_mutual_terms_preserved,
                    internal_coordinate_elimination=:frequency_dependent_dynamic_schur_complement,
                    section_length_m=selected.section_length_m,
                    mtl_section_length_m=selected.mtl_section_length_m,
                ),
                qualification_receipt=(
                    schema_version=receipt.normalized.schema_version,
                    evidence_id=receipt.normalized.evidence_id,
                    receipt_sha256=receipt.sha256,
                    policy_sha256=D3_LC_QUALIFICATION_POLICY_SHA256,
                    candidate_id=receipt.normalized.candidate.id,
                    source=receipt.normalized.source,
                    frequency_deltas=receipt.normalized.frequency_deltas,
                ),
            ),
        ),
    )
end

function _d3_stage2_resonator_response_model(lengths, lines; diagonal)
    l_matrix = diagonal ?
        Matrix(Diagonal(LinearAlgebra.diag(lines.l_matrix_per_m_h))) :
        lines.l_matrix_per_m_h
    c_matrix = diagonal ?
        Matrix(Diagonal(LinearAlgebra.diag(lines.c_matrix_per_m_f))) :
        lines.c_matrix_per_m_f
    plan = CircuitPlan(
        diagonal ?
            "d3-stage2-diagonal-response-reference" :
            "d3-stage2-physical-response-reference",
    )
    readout_grounded_head = external_node("d3_stage2_readout_grounded_head")
    readout_open_tail = external_node("d3_stage2_readout_open_tail")
    filter_grounded_head = external_node("d3_stage2_filter_grounded_head")
    filter_open_tail = external_node("d3_stage2_filter_open_tail")
    mtl_model = MTLCoupledRLGCSpec(
        start1_m=lengths.lr_short_m,
        start2_m=lengths.lp_short_m,
        length_m=lengths.lc_m,
        section_length_m=lines.mtl_section_length_m,
        l_matrix_per_m_h=l_matrix,
        c_matrix_per_m_f=c_matrix,
    )
    readout = add_quarter_wave_resonator!(
        plan;
        id=:d3_stage2_readout_resonator,
        grounded_head=readout_grounded_head,
        open_tail=readout_open_tail,
        spec=_d3_line_spec(
            length_m=
                lengths.lr_short_m + lengths.lc_m + lengths.lr_open_m,
            section_length_m=lines.section_length_m,
            l_per_m_h=lines.readout_l_per_m_h,
            c_per_m_f=lines.readout_c_per_m_f,
        ),
        breakpoints_m=_d3_mtl_window_breakpoints(
            lengths.lr_short_m,
            lengths.lc_m,
            lines.mtl_section_length_m,
        ),
        section_overrides=[coupled_line_section_override(mtl_model, 1)],
    )
    filter = add_quarter_wave_resonator!(
        plan;
        id=:d3_stage2_filter_resonator,
        grounded_head=filter_grounded_head,
        open_tail=filter_open_tail,
        spec=_d3_line_spec(
            length_m=
                lengths.lp_short_m + lengths.lc_m + lengths.lp_open_m,
            section_length_m=lines.section_length_m,
            l_per_m_h=lines.filter_l_per_m_h,
            c_per_m_f=lines.filter_c_per_m_f,
        ),
        breakpoints_m=_d3_mtl_window_breakpoints(
            lengths.lp_short_m,
            lengths.lc_m,
            lines.mtl_section_length_m,
        ),
        section_overrides=[coupled_line_section_override(mtl_model, 2)],
    )
    couple_transmission_window!(
        plan;
        id=:d3_stage2_mtl_window,
        line1=readout.line,
        line2=filter.line,
        start1=lengths.lr_short_m,
        start2=lengths.lp_short_m,
        length=lengths.lc_m,
        model=mtl_model,
        coupling_orientation=lines.coupling_orientation,
    )
    compiled = compile_to_josephson(plan)
    model = extract_linear_nodal_model(compiled)
    endpoints = (
        readout_open_tail,
        filter_open_tail,
    )
    terminal_indices = [
        begin
        node_name = compiled.node_map[endpoint]
        matches = findall(==(node_name), model.node_names)
        length(matches) == 1 || error(
            "D3 Stage-2 response-match terminal $(node_name) must resolve exactly once.",
        )
        only(matches)
        end
        for endpoint in endpoints
    ]
    return (
        plan=plan,
        compiled=compiled,
        model=model,
        terminal_indices=terminal_indices,
    )
end

function _d3_stage2_terminal_admittance(
    reference,
    terminal_position,
    angular_frequency,
)
    reduced = schur_dynamic_stiffness(
        reference.model.capacitance,
        reference.model.inverse_inductance,
        angular_frequency,
        reference.terminal_indices,
    )
    return reduced.dynamic_stiffness[terminal_position, terminal_position] /
        (-im * angular_frequency)
end

"""
    d3_stage2_response_matched_resonator_mapping(fixed; ...)

Create the physical-length-to-LC map shared by the Stage-2 optimizer. The map
keeps the declared Q2D diagonal loading when mutual terms are disabled,
matches `Cr/Lr` and `Cp/Lp` from terminal-admittance roots/slopes, and matches
`Cn/Ln` from the physical-pair `Z21` notch and slope.
"""
function d3_stage2_response_matched_resonator_mapping(
    fixed;
    readout_root_bracket_hz,
    filter_root_bracket_hz,
    notch_root_bracket_hz,
    parallel_derivative_step_rad_s,
    bridge_derivative_step_rad_s,
    bisection_absolute_tolerance_rad_s=2π * 10.0,
    bisection_relative_tolerance=1.0e-13,
    bisection_max_iterations=128,
    match_root_relative_tolerance=2.0e-3,
    derivative_relative_tolerance=1.0e-7,
)
    selected_lines = _d3_selected_q2d_line_input(fixed)
    settings = (
        readout_root_bracket_hz=Tuple(Float64.(collect(readout_root_bracket_hz))),
        filter_root_bracket_hz=Tuple(Float64.(collect(filter_root_bracket_hz))),
        notch_root_bracket_hz=Tuple(Float64.(collect(notch_root_bracket_hz))),
        parallel_derivative_step_rad_s=Float64(parallel_derivative_step_rad_s),
        bridge_derivative_step_rad_s=Float64(bridge_derivative_step_rad_s),
        bisection_absolute_tolerance_rad_s=
            Float64(bisection_absolute_tolerance_rad_s),
        bisection_relative_tolerance=Float64(bisection_relative_tolerance),
        bisection_max_iterations=Int(bisection_max_iterations),
        match_root_relative_tolerance=Float64(match_root_relative_tolerance),
        derivative_relative_tolerance=Float64(derivative_relative_tolerance),
    )
    all(bracket -> length(bracket) == 2 && 0 < bracket[1] < bracket[2], (
        settings.readout_root_bracket_hz,
        settings.filter_root_bracket_hz,
        settings.notch_root_bracket_hz,
    )) || error("D3 Stage-2 response-match root brackets must be positive and increasing.")
    mapping_contract = (
        match_contract_id="d3-cpw-mtl-response-match.v1",
        q2d_artifact_id=selected_lines.q2d_artifact_id,
        q2d_artifact_sha256=selected_lines.q2d_artifact_sha256,
        topology_id=String(selected_lines.q2d_topology_id),
        fixed_line_input_sha256=selected_lines.fixed_line_input_sha256,
        settings=settings,
    )
    mapping_sha256 = bytes2hex(SHA.sha256(codeunits(
        SuperconductingCircuitsCore.JSON3.write(mapping_contract),
    )))
    return D3Stage2ResonatorMapping(
        selected_lines,
        settings,
        mapping_contract,
        mapping_sha256,
    )
end

function _d3_stage2_evaluate_response_match(
    mapping::D3Stage2ResonatorMapping,
    lengths,
)
    selected_lines = _d3_selected_q2d_line_input(mapping.fixed_line_input)
    lines = _d3_hybridized_fixed_line_keywords(selected_lines)
    settings = mapping.settings
    diagonal = _d3_stage2_resonator_response_model(
        lengths,
        lines;
        diagonal=true,
    )
    physical = _d3_stage2_resonator_response_model(
        lengths,
        lines;
        diagonal=false,
    )
    yr = angular_frequency -> _d3_stage2_terminal_admittance(
        diagonal,
        1,
        angular_frequency,
    )
    yp = angular_frequency -> _d3_stage2_terminal_admittance(
        diagonal,
        2,
        angular_frequency,
    )
    z21 = angular_frequency -> linear_terminal_response(
        physical.model.capacitance,
        physical.model.inverse_inductance,
        angular_frequency,
        physical.terminal_indices,
    ).impedance[2, 1]
    bisection = (
        absolute_tolerance=settings.bisection_absolute_tolerance_rad_s,
        relative_tolerance=settings.bisection_relative_tolerance,
        max_iterations=settings.bisection_max_iterations,
    )
    root(response, bracket_hz) = bracketed_bisection(
        angular_frequency -> imag(response(angular_frequency)),
        2π .* collect(bracket_hz);
        bisection...,
    )
    readout_root = root(yr, settings.readout_root_bracket_hz)
    filter_root = root(yp, settings.filter_root_bracket_hz)
    notch_root = root(z21, settings.notch_root_bracket_hz)
    readout = match_parallel_lc(
        yr,
        readout_root;
        derivative_step_rad_s=settings.parallel_derivative_step_rad_s,
        root_relative_tolerance=settings.match_root_relative_tolerance,
        imaginary_derivative_relative_tolerance=
            settings.derivative_relative_tolerance,
    )
    filter = match_parallel_lc(
        yp,
        filter_root;
        derivative_step_rad_s=settings.parallel_derivative_step_rad_s,
        root_relative_tolerance=settings.match_root_relative_tolerance,
        imaginary_derivative_relative_tolerance=
            settings.derivative_relative_tolerance,
    )
    bridge = match_bridge_lc(
        z21,
        yr,
        yp,
        notch_root;
        derivative_step_rad_s=settings.bridge_derivative_step_rad_s,
        root_relative_tolerance=settings.match_root_relative_tolerance,
        imaginary_capacitance_relative_tolerance=
            settings.derivative_relative_tolerance,
    )
    return (
        Cr_f=readout.capacitance_f,
        Lr_h=readout.inductance_h,
        Cp_f=filter.capacitance_f,
        Lp_h=filter.inductance_h,
        Cn_f=bridge.capacitance_f,
        Ln_h=bridge.inductance_h,
        mapping_id="d3-continuous-ground-response-match",
        mapping_sha256=mapping.mapping_sha256,
        q2d_artifact_id=selected_lines.q2d_artifact_id,
        q2d_artifact_sha256=selected_lines.q2d_artifact_sha256,
        topology_id=String(selected_lines.q2d_topology_id),
        fixed_line_input_sha256=selected_lines.fixed_line_input_sha256,
        fixed_line_input_identity=selected_lines.fixed_line_input_identity,
        fixed_line_input_identity_canonical_json=
            selected_lines.fixed_line_input_identity_canonical_json,
        match_contract_id=mapping.contract.match_contract_id,
        match_evidence=(
            reference_model=(
                role=:physical_length_to_equivalent_lc_extraction_only,
                final_stage2_hb_model=:resolved_lumped_equivalent_circuit,
                topology=:two_grounded_head_open_tail_quarter_wave_resonators_with_mtl_window,
                terminal_coordinates=(:readout_open_tail, :filter_open_tail),
                diagonal_match_state=:mtl_mutual_terms_disabled_diagonal_loading_preserved,
                bridge_match_state=:full_mtl_mutual_terms_preserved,
                internal_coordinate_elimination=:frequency_dependent_dynamic_schur_complement,
                section_length_m=lines.section_length_m,
                mtl_section_length_m=lines.mtl_section_length_m,
            ),
            readout=readout,
            filter=filter,
            bridge=bridge,
            settings=settings,
        ),
    )
end

function _d3_stage2_fixed_feedline_keywords(fixed)
    obsolete = (
        :separator_inductance_h,
        :separator_model,
        :separator_characteristic_impedance_ohm,
        :separator_phase_velocity_m_per_s,
        :feedline_length_m,
        :feedline_l_per_m_h,
        :feedline_c_per_m_f,
        :feedline_n_sections,
    )
    stale = filter(name -> hasproperty(fixed, name), obsolete)
    isempty(stale) || error(
        "D3 Stage-2 fixed input contains obsolete feedline fields $(collect(stale)); " *
        "the matched two-section port regularizer is fixed by its CircuitPlan.",
    )
    port_resistance_ohm = _d3_stage_positive(
        fixed,
        :port_resistance_ohm,
        "D3 fixed feedline input",
    )
    port_resistance_ohm == 50.0 || error(
        "D3 Stage-2 matched ports are fixed at exactly 50 ohm.",
    )
    return (port_resistance_ohm=port_resistance_ohm,)
end

function d3_stage2_matched_port_regularizer_contract(port_resistance_ohm=50.0)
    resistance = Float64(port_resistance_ohm)
    isfinite(resistance) && resistance == 50.0 || error(
        "D3 Stage-2 matched ports are fixed at exactly 50 ohm.",
    )
    return (
        feedline_model=:matched_port_regularizer_two_pi,
        regularizer_series_inductance_h=
            D3_PORT_REGULARIZER_SERIES_INDUCTANCE_H,
        regularizer_section_capacitance_f=
            D3_PORT_REGULARIZER_SECTION_CAPACITANCE_F,
        regularizer_characteristic_impedance_ohm=
            D3_PORT_REGULARIZER_CHARACTERISTIC_IMPEDANCE_OHM,
        regularizer_phase_velocity_m_per_s=
            D3_PORT_REGULARIZER_PHASE_VELOCITY_M_PER_S,
        regularizer_section_length_m=
            D3_PORT_REGULARIZER_SECTION_LENGTH_M,
        regularizer_section_count=2,
        port_resistance_ohm=resistance,
    )
end

function d3_stage2_validate_matched_port_regularizer_contract(raw)
    expected = d3_stage2_matched_port_regularizer_contract()
    names = propertynames(expected)
    Set(Symbol.(keys(raw))) == Set(names) || error(
        "D3 Stage-2 fixed-feedline fields must be exactly $(collect(names)).",
    )
    Symbol(raw["feedline_model"]) == expected.feedline_model || error(
        "D3 Stage-2 fixed feedline must use the matched two-pi port regularizer.",
    )
    for name in names
        name === :feedline_model && continue
        value = Float64(raw[String(name)])
        value == Float64(getproperty(expected, name)) || error(
            "D3 Stage-2 fixed-feedline $(name) disagrees with its CircuitPlan constant.",
        )
    end
    return expected
end

function _d3_distributed_feedline_keywords(fixed)
    required = (
        :feedline_length_m,
        :feedline_l_per_m_h,
        :feedline_c_per_m_f,
        :port_resistance_ohm,
    )
    values = NamedTuple{
        required,
    }(Tuple(_d3_stage_positive(fixed, name, "D3 distributed feedline input") for name in required))
    values.port_resistance_ohm == 50.0 || error(
        "D3 distributed matched ports are fixed at exactly 50 ohm.",
    )
    hasproperty(fixed, :feedline_n_sections) || error(
        "D3 distributed feedline input is missing feedline_n_sections.",
    )
    raw = fixed.feedline_n_sections
    raw isa Real && isfinite(raw) && raw == round(raw) && raw >= 2 &&
        iseven(Int(round(raw))) || error(
        "D3 distributed feedline_n_sections must be an even integer-valued count of at least two.",
    )
    return merge(values, (feedline_n_sections=Int(round(raw)),))
end

"""
    d3_response_equivalent_model_from_lc(candidate, fixed, idc_mapping; id=...)

Build a finite response-equivalent diagnostic from six explicit LC values.
This is the topology-constrained fitter realization; it is not a fabrication
witness and must not be passed to the Stage-2 optimizer.
"""
function d3_response_equivalent_model_from_lc(
    candidate,
    fixed,
    idc_mapping;
    id="d3-response-equivalent-diagnostic",
)
    _d3_stage_require_exact_fields(
        candidate,
        D3_RESPONSE_EQUIVALENT_VARIABLE_ORDER,
        "D3 response-equivalent diagnostic",
    )
    u_idc = _d3_stage_positive(
        candidate,
        :u_IDC,
        "D3 response-equivalent diagnostic",
    )
    idc = _d3_stage_idc_triplet(idc_mapping, u_idc)
    qubit = _d3_stage_fixed_qubit_keywords(fixed)
    feedline = _d3_stage2_fixed_feedline_keywords(fixed)
    built = build_d3_intrinsic_purcell_equivalent_circuit_plan(;
        id=String(id),
        idc_filter_ground_capacitance_f=
            idc.idc_filter_ground_capacitance_f,
        idc_feedline_ground_capacitance_f=
            idc.idc_feedline_ground_capacitance_f,
        idc_mutual_capacitance_f=idc.idc_mutual_capacitance_f,
        readout_capacitance_f=
            _d3_stage_positive(candidate, :Cr_f, "D3 response-equivalent diagnostic"),
        readout_inductance_h=
            _d3_stage_positive(candidate, :Lr_h, "D3 response-equivalent diagnostic"),
        filter_capacitance_f=
            _d3_stage_positive(candidate, :Cp_f, "D3 response-equivalent diagnostic"),
        filter_inductance_h=
            _d3_stage_positive(candidate, :Lp_h, "D3 response-equivalent diagnostic"),
        bridge_capacitance_f=
            _d3_stage_positive(candidate, :Cn_f, "D3 response-equivalent diagnostic"),
        bridge_inductance_h=
            _d3_stage_positive(candidate, :Ln_h, "D3 response-equivalent diagnostic"),
        qubit...,
        feedline...,
    )
    auxiliary = (
        linewidth_la=build_d3_linewidth_la_equivalent_circuit_plan(;
            id="$(id)-linewidth-la",
            idc_filter_ground_capacitance_f=
                idc.idc_filter_ground_capacitance_f,
            idc_feedline_ground_capacitance_f=
                idc.idc_feedline_ground_capacitance_f,
            idc_mutual_capacitance_f=idc.idc_mutual_capacitance_f,
            filter_capacitance_f=
                _d3_stage_positive(candidate, :Cp_f, "D3 response-equivalent diagnostic"),
            filter_inductance_h=
                _d3_stage_positive(candidate, :Lp_h, "D3 response-equivalent diagnostic"),
            bridge_capacitance_f=
                _d3_stage_positive(candidate, :Cn_f, "D3 response-equivalent diagnostic"),
            bridge_inductance_h=
                _d3_stage_positive(candidate, :Ln_h, "D3 response-equivalent diagnostic"),
            feedline...,
        ),
        notch=build_d3_intrinsic_pair_notch_equivalent_circuit_plan(;
            id="$(id)-intrinsic-pair-notch",
            readout_capacitance_f=
                _d3_stage_positive(candidate, :Cr_f, "D3 response-equivalent diagnostic"),
            readout_inductance_h=
                _d3_stage_positive(candidate, :Lr_h, "D3 response-equivalent diagnostic"),
            filter_capacitance_f=
                _d3_stage_positive(candidate, :Cp_f, "D3 response-equivalent diagnostic"),
            filter_inductance_h=
                _d3_stage_positive(candidate, :Lp_h, "D3 response-equivalent diagnostic"),
            bridge_capacitance_f=
                _d3_stage_positive(candidate, :Cn_f, "D3 response-equivalent diagnostic"),
            bridge_inductance_h=
                _d3_stage_positive(candidate, :Ln_h, "D3 response-equivalent diagnostic"),
            port_resistance_ohm=feedline.port_resistance_ohm,
        ),
    )
    return (
        stage_id=:response_equivalent_diagnostic,
        model_family=:finite_order_response_equivalent,
        variable_order=D3_RESPONSE_EQUIVALENT_VARIABLE_ORDER,
        candidate=candidate,
        idc=idc,
        built=built,
        auxiliary=auxiliary,
    )
end

function _d3_hybridized_fixed_line_keywords(fixed)
    required = (
        :section_length_m,
        :readout_l_per_m_h,
        :readout_c_per_m_f,
        :filter_l_per_m_h,
        :filter_c_per_m_f,
        :l_matrix_per_m_h,
        :c_matrix_per_m_f,
        :coupling_orientation,
    )
    all(name -> hasproperty(fixed, name), required) || error(
        "D3 Hybridized fixed input is missing one or more CPW/MTL fields.",
    )
    section_length_m = _d3_stage_positive(
        fixed,
        :section_length_m,
        "D3 Hybridized fixed input",
    )
    mtl_section_length_m = hasproperty(fixed, :mtl_section_length_m) ?
        _d3_stage_positive(fixed, :mtl_section_length_m, "D3 Hybridized fixed input") :
        section_length_m
    for name in (
        :readout_l_per_m_h,
        :readout_c_per_m_f,
        :filter_l_per_m_h,
        :filter_c_per_m_f,
    )
        _d3_stage_positive(fixed, name, "D3 Hybridized fixed input")
    end
    for (name, matrix) in (
        (:l_matrix_per_m_h, fixed.l_matrix_per_m_h),
        (:c_matrix_per_m_f, fixed.c_matrix_per_m_f),
    )
        matrix isa AbstractMatrix && size(matrix) == (2, 2) ||
            error("D3 Hybridized $(name) must be a 2x2 matrix.")
        all(value -> value isa Real && isfinite(value), matrix) ||
            error("D3 Hybridized $(name) must contain finite real values.")
        isposdef(Symmetric(Matrix{Float64}(matrix))) ||
            error("D3 Hybridized $(name) must be positive definite.")
    end
    fixed.coupling_orientation in (:same_direction, :opposite_direction) ||
        error("D3 Hybridized coupling orientation is unsupported.")
    return (
        section_length_m=section_length_m,
        mtl_section_length_m=mtl_section_length_m,
        readout_l_per_m_h=Float64(fixed.readout_l_per_m_h),
        readout_c_per_m_f=Float64(fixed.readout_c_per_m_f),
        filter_l_per_m_h=Float64(fixed.filter_l_per_m_h),
        filter_c_per_m_f=Float64(fixed.filter_c_per_m_f),
        l_matrix_per_m_h=Matrix{Float64}(fixed.l_matrix_per_m_h),
        c_matrix_per_m_f=Matrix{Float64}(fixed.c_matrix_per_m_f),
        coupling_orientation=Symbol(fixed.coupling_orientation),
    )
end

function _d3_selected_q2d_line_input(fixed)
    current = validate_d3_rev10_q2d_input(fixed)
    lines = _d3_hybridized_fixed_line_keywords(current)
    identity = (
        contract_id="d3-selected-continuous-ground-fixed-line.v2",
        q2d_artifact_id=current.q2d_artifact_id,
        q2d_artifact_sha256=current.q2d_artifact_sha256,
        q2d_topology_id=String(current.q2d_topology_id),
        q2d_geometry_um=current.q2d_geometry_um,
        q2d_single_case_id=current.q2d_single_case_id,
        q2d_pair_case_id=current.q2d_pair_case_id,
        q2d_solver=current.q2d_solver,
        q2d_loss_model=current.q2d_loss_model,
        q2d_authority=current.q2d_authority,
        section_length_m=lines.section_length_m,
        mtl_section_length_m=lines.mtl_section_length_m,
        readout_l_per_m_h=lines.readout_l_per_m_h,
        readout_c_per_m_f=lines.readout_c_per_m_f,
        filter_l_per_m_h=lines.filter_l_per_m_h,
        filter_c_per_m_f=lines.filter_c_per_m_f,
        l_matrix_per_m_h=(
            Tuple(lines.l_matrix_per_m_h[1, :]),
            Tuple(lines.l_matrix_per_m_h[2, :]),
        ),
        c_matrix_per_m_f=(
            Tuple(lines.c_matrix_per_m_f[1, :]),
            Tuple(lines.c_matrix_per_m_f[2, :]),
        ),
        coupling_orientation=String(lines.coupling_orientation),
    )
    fixed_line_input_identity_canonical_json =
        SuperconductingCircuitsCore.JSON3.write(identity)
    fixed_line_input_sha256 = bytes2hex(SHA.sha256(codeunits(
        fixed_line_input_identity_canonical_json,
    )))
    return merge(
        lines,
        (
            q2d_artifact_id=current.q2d_artifact_id,
            q2d_artifact_sha256=current.q2d_artifact_sha256,
            q2d_topology_id=current.q2d_topology_id,
            q2d_geometry_um=current.q2d_geometry_um,
            q2d_single_case_id=current.q2d_single_case_id,
            q2d_pair_case_id=current.q2d_pair_case_id,
            q2d_solver=identity.q2d_solver,
            q2d_loss_model=current.q2d_loss_model,
            q2d_authority=current.q2d_authority,
            fixed_line_input_sha256=fixed_line_input_sha256,
            fixed_line_input_identity=identity,
            fixed_line_input_identity_canonical_json=
                fixed_line_input_identity_canonical_json,
        ),
    )
end

"""
    d3_stage2_direct_hybridized_model(candidate, inputs; grid_plan, id=...)

Build one revision-10 direct-Hybridized Stage-2 candidate. The six physical
coordinates are consumed together; no LC/Equivalent candidate is constructed.
"""
function d3_stage2_direct_hybridized_model(
    candidate,
    inputs::D3DirectHybridizedInputs;
    grid_plan::D3DirectHybridizedGridPlan,
    id="d3-stage2-direct-hybridized-candidate",
)
    _d3_stage_require_exact_fields(
        candidate,
        D3_STAGE2_VARIABLE_ORDER,
        "D3 direct-Hybridized Stage-2 candidate",
    )
    _d3_stage_require_physical_idc_mapping(inputs.idc_mapping)
    grid = _d3_validate_stage2_direct_grid_plan(candidate, inputs, grid_plan)
    lengths = (
        lr_open_m=_d3_stage_positive(
            candidate,
            :lr_open_m,
            "D3 direct-Hybridized Stage-2 candidate",
        ),
        lr_short_m=_d3_stage_positive(
            candidate,
            :lr_short_m,
            "D3 direct-Hybridized Stage-2 candidate",
        ),
        lc_m=_d3_stage_positive(
            candidate,
            :lc_m,
            "D3 direct-Hybridized Stage-2 candidate",
        ),
        lp_open_m=_d3_stage_positive(
            candidate,
            :lp_open_m,
            "D3 direct-Hybridized Stage-2 candidate",
        ),
        lp_short_m=_d3_stage_positive(
            candidate,
            :lp_short_m,
            "D3 direct-Hybridized Stage-2 candidate",
        ),
    )
    u_idc = _d3_stage_positive(
        candidate,
        :u_IDC,
        "D3 direct-Hybridized Stage-2 candidate",
    )
    idc = _d3_stage_idc_triplet(inputs.idc_mapping, u_idc)
    qubit = _d3_stage_fixed_qubit_keywords(inputs.qubit)
    base_feedline = _d3_distributed_feedline_keywords(inputs.feedline)
    feedline = merge(base_feedline, (
        feedline_n_sections=
            grid.counts.feedline_left + grid.counts.feedline_right,
    ))
    selected_lines = _d3_selected_q2d_line_input(inputs.q2d_input)
    base_lines = _d3_hybridized_fixed_line_keywords(selected_lines)
    lines = merge(base_lines, (
        mtl_section_length_m=lengths.lc_m / grid.counts.mtl,
    ))
    built = build_d3_intrinsic_purcell_hybridized_circuit_plan(;
        id=String(id),
        idc_filter_ground_capacitance_f=
            idc.idc_filter_ground_capacitance_f,
        idc_feedline_ground_capacitance_f=
            idc.idc_feedline_ground_capacitance_f,
        idc_mutual_capacitance_f=idc.idc_mutual_capacitance_f,
        readout_length_m=
            lengths.lr_short_m + lengths.lc_m + lengths.lr_open_m,
        filter_length_m=
            lengths.lp_short_m + lengths.lc_m + lengths.lp_open_m,
        window_start_readout_m=lengths.lr_short_m,
        window_start_filter_m=lengths.lp_short_m,
        window_length_m=lengths.lc_m,
        lines...,
        qubit...,
        feedline...,
        readout_breakpoints_m=
            grid.boundaries_m.readout_resonator_boundaries_m,
        filter_breakpoints_m=
            grid.boundaries_m.filter_resonator_boundaries_m,
        feedline_left_breakpoints_m=
            grid.boundaries_m.feedline_left_boundaries_m,
        feedline_right_breakpoints_m=
            grid.boundaries_m.feedline_right_boundaries_m,
    )
    auxiliary = (
        notch=build_d3_intrinsic_pair_notch_hybridized_circuit_plan(;
            id="$(id)-intrinsic-pair-notch",
            readout_length_m=
                lengths.lr_short_m + lengths.lc_m + lengths.lr_open_m,
            filter_length_m=
                lengths.lp_short_m + lengths.lc_m + lengths.lp_open_m,
            section_length_m=lines.section_length_m,
            mtl_section_length_m=lines.mtl_section_length_m,
            readout_l_per_m_h=lines.readout_l_per_m_h,
            readout_c_per_m_f=lines.readout_c_per_m_f,
            filter_l_per_m_h=lines.filter_l_per_m_h,
            filter_c_per_m_f=lines.filter_c_per_m_f,
            window_start_readout_m=lengths.lr_short_m,
            window_start_filter_m=lengths.lp_short_m,
            window_length_m=lengths.lc_m,
            l_matrix_per_m_h=lines.l_matrix_per_m_h,
            c_matrix_per_m_f=lines.c_matrix_per_m_f,
            coupling_orientation=lines.coupling_orientation,
            port_resistance_ohm=feedline.port_resistance_ohm,
            readout_breakpoints_m=
                grid.boundaries_m.readout_resonator_boundaries_m,
            filter_breakpoints_m=
                grid.boundaries_m.filter_resonator_boundaries_m,
        ),
    )
    return (
        stage_id=:stage2_direct_hybridized,
        model_family=:hybridized_distributed_lumped,
        variable_order=D3_STAGE2_VARIABLE_ORDER,
        candidate=candidate,
        lengths=lengths,
        idc=idc,
        feedline_contract=(
            model=:split_distributed_cpw,
            length_m=feedline.feedline_length_m,
            n_sections=feedline.feedline_n_sections,
            l_per_m_h=feedline.feedline_l_per_m_h,
            c_per_m_f=feedline.feedline_c_per_m_f,
            port_resistance_ohm=feedline.port_resistance_ohm,
        ),
        resonator_input_contract=(
            q2d_artifact_id=selected_lines.q2d_artifact_id,
            q2d_artifact_sha256=selected_lines.q2d_artifact_sha256,
            q2d_topology_id=selected_lines.q2d_topology_id,
            q2d_geometry_um=selected_lines.q2d_geometry_um,
            fixed_line_input_sha256=selected_lines.fixed_line_input_sha256,
            fixed_line_input_identity=selected_lines.fixed_line_input_identity,
        ),
        fixed_input_identity=inputs.source_identity,
        grid_plan=grid,
        built=built,
        auxiliary=auxiliary,
    )
end

function d3_stage2_direct_hybridized_model(candidate, args...; kwargs...)
    error(
        "D3 direct-Hybridized Stage-2 evaluation requires D3DirectHybridizedInputs " *
        "from bind_d3_stage2_direct_hybridized_inputs.",
    )
end

function d3_stage3_hybridized_model(args...; kwargs...)
    error(
        "The independent Stage-3 Hybridized optimizer authority is superseded; " *
        "revision-10 search uses d3_stage2_direct_hybridized_model, and Stage 3 is Layout/EM only.",
    )
end

function _d3_stage_response_closure(model, cqed_handoff, frequency_hz)
    analytical = d3_cqed_port_trace(cqed_handoff, frequency_hz)
    direct = d3_compiled_port_trace(model, analytical.frequency_hz)
    exact_scattering_residual = [
        analytical.exact.scattering[index] - direct.scattering[index]
        for index in eachindex(direct.scattering)
    ]
    return (
        frequency_hz=analytical.frequency_hz,
        direct=direct,
        analytical=analytical,
        residuals=(
            exact_scattering=exact_scattering_residual,
            exact_s21=analytical.exact.s21 - direct.s21,
            max_abs_exact_scattering=maximum(
                maximum(abs, residual)
                for residual in exact_scattering_residual
            ),
            max_abs_exact_s21=maximum(
                abs,
                analytical.exact.s21 - direct.s21,
            ),
        ),
        exact_closure_status=:candidate_gate__tolerance_not_human_frozen,
    )
end

function _d3_targeted_grid_identity(candidate, context)
    boundaries = _d3_targeted_candidate_boundaries(
        candidate,
        context.provenance.topology_counts,
        context.grid_plan,
    )
    counts = context.grid_plan.counts
    payload = (candidate=candidate, counts=counts, boundaries_m=boundaries)
    return merge(payload, (
        canonical_sha256=bytes2hex(SHA.sha256(codeunits(
            SuperconductingCircuitsCore.JSON3.write(payload),
        ))),
        refinement_level=context.grid_plan.refinement_level,
        reference_grid_plan_sha256=context.grid_plan.canonical_sha256,
    ))
end

function _d3_targeted_metric_record(cared::D3TargetedSchurCaredOutput)
    return (
        contract_id="d3-stage2-targeted-schur-candidate-metrics.v1",
        stage_id=cared.stage_id,
        model_family=cared.model_family,
        slot_hz=cared.slot_hz,
        source_profile_identity=cared.source_profile_identity,
        grid_identity=cared.grid_identity,
        fr_eff_complete_complement_rp_hz=cared.f_r_eff_hz,
        fp_eff_complete_complement_rp_hz=cared.f_p_eff_hz,
        J_eff_complete_complement_rp_coherent_hz=cared.abs_real_J_eff_hz,
        notch_distributed_rp_on_hz=cared.f_n_hz,
        kappa_sum_local_hybrid_rp_hz=cared.local_hybrid_kappa_sum_hz,
        linewidth_fraction_min_local_hybrid_rp=
            cared.local_hybrid_linewidth_fraction_min,
        linewidth_fraction_max_local_hybrid_rp=
            cared.local_hybrid_linewidth_fraction_max,
        effective_diagonal_frequency_extraction=
            :complete_complement_rp_complex_operator,
        effective_exchange_extraction=
            :complete_complement_rp_complex_midpoint_residue,
        notch_authority=:distributed_rp_on,
        linewidth_pole_scope=:complete_complement_rp_local_hybrid_two_pole,
        primary_linewidth_extraction=:targeted_schur_determinant_poles,
    )
end

"""Evaluate one candidate from local scratch against a fixed targeted-Schur context."""
function d3_stage2_direct_cared_outputs(
    candidate,
    context::D3TargetedSchurObjectiveContext;
    slot_hz,
    readout_root_anchor_hz,
    filter_root_anchor_hz,
    notch_zero_anchor_hz,
)::D3TargetedSchurCaredOutput
    normalized = try
        _d3_stage2_direct_candidate(candidate)
    catch exception
        exception isa ErrorException || rethrow()
        _d3_targeted_fail(
            "d3_targeted_schur_invalid_candidate",
            sprint(showerror, exception),
            (candidate=candidate,),
        )
    end
    slot = Float64(slot_hz)
    isfinite(slot) && slot > 0 || _d3_targeted_fail(
        "d3_targeted_schur_invalid_slot",
        "D3 targeted-Schur slot frequency must be finite and positive.",
    )
    full_c, full_k = _d3_targeted_kernel_matrices(
        context.full_kernel,
        normalized,
        D3_STAGE2_VARIABLE_ORDER,
    )
    notch_c, notch_k = _d3_targeted_kernel_matrices(
        context.notch_kernel,
        normalized,
        _D3_TARGETED_SCHUR_LENGTH_COORDINATES,
    )
    schur_context = try
        _d3_targeted_schur_candidate_context(
            context.fixed_schur_context,
            full_c,
            full_k,
        )
    catch exception
        exception isa ErrorException || rethrow()
        _d3_targeted_fail(
            "d3_targeted_schur_invalid_candidate_matrices",
            sprint(showerror, exception),
        )
    end
    targeted = try
        _d3_targeted_schur_outputs(
            schur_context;
            readout_root_anchor_hz=readout_root_anchor_hz,
            filter_root_anchor_hz=filter_root_anchor_hz,
        )
    catch exception
        exception isa ErrorException || rethrow()
        _d3_targeted_fail(
            "d3_targeted_schur_root_or_solve_failure",
            sprint(showerror, exception),
        )
    end
    notch_anchor = Float64(notch_zero_anchor_hz)
    isfinite(notch_anchor) && notch_anchor > 0 || _d3_targeted_fail(
        "d3_targeted_schur_invalid_notch_anchor",
        "D3 targeted-Schur notch-zero anchor must be finite and positive.",
    )
    notch_model = merge(context.notch_kernel.reference_model, (
        capacitance=notch_c,
        inverse_inductance=notch_k,
    ))
    notch = try
        _d3_targeted_cofactor_notch_from_model(
            notch_model,
            notch_anchor,
        )
    catch exception
        exception isa ErrorException || rethrow()
        _d3_targeted_fail(
            "d3_targeted_schur_notch_failure",
            sprint(showerror, exception),
        )
    end
    grid_identity = _d3_targeted_grid_identity(normalized, context)
    source_profile_identity = context.source_profile_identity
    return D3TargetedSchurCaredOutput(
            D3_TARGETED_SCHUR_CARED_OUTPUT_CONTRACT,
            :stage2_direct_hybridized,
            :hybridized_distributed_lumped,
            slot,
            normalized,
            Float64(real(targeted.readout.root_rad_s / (2π))),
            Float64(real(targeted.filter.root_rad_s / (2π))),
            Float64(notch.frequency_hz),
            Float64(abs(real(targeted.exchange_rad_s)) / (2π)),
            Float64(targeted.local_hybrid_kappa_sum_hz),
            Float64(targeted.local_hybrid_linewidth_fraction_min),
            Float64(targeted.local_hybrid_linewidth_fraction_max),
            source_profile_identity,
            grid_identity,
            (
                extraction=:targeted_schur_determinant_poles,
                retained_coordinates=(:r, :p),
                complement=:complete_hybridized_complement,
                readout_root_anchor_hz=Float64(readout_root_anchor_hz),
                filter_root_anchor_hz=Float64(filter_root_anchor_hz),
                notch_zero_anchor_hz=notch_anchor,
                linewidth_scope=:complete_complement_rp_local_hybrid_two_pole,
            ),
            (
                status=:pass,
                diagonal_root_iterations=(
                    readout=targeted.readout.iterations,
                    filter=targeted.filter.iterations,
                ),
                local_hybrid_root_iterations=(
                    first=targeted.local_hybrid_poles.first.iterations,
                    second=targeted.local_hybrid_poles.second.iterations,
                ),
                machine_validation=context.fixed_schur_context.validation,
            ),
    )
end
