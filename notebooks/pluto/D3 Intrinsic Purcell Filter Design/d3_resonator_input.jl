# D3 material-aware Q2D input. The loader validates reusable v4 artifact
# authority. Rev10 applies its exact W7/S6 selection in a separate binder.

module D3ResonatorInput

using LinearAlgebra
using SHA
using SuperconductingCircuitsCore

const JSON3 = SuperconductingCircuitsCore.JSON3
const D3_MAX_LINE_SECTION_LENGTH_M = 50e-6
const D3_Q2D_V4_SCHEMA = "orpen-q2d-intrinsic-purcell-maxwell-lc-cases.v4"

const D3_REV10_Q2D_ARTIFACT_ID =
    "orpen-q2d-maxwell-lc-7922f869c6566309fb0511d3b9e2b4e596d70f520c06cd65eb664ba8a858b181"
const D3_REV10_Q2D_PAYLOAD_SHA256 =
    "7922f869c6566309fb0511d3b9e2b4e596d70f520c06cd65eb664ba8a858b181"
const D3_REV10_Q2D_FILE_SHA256 =
    "301d3501a30614b994cf3f28d46eb75b545620a164bbb346fa557120d643fe6c"
const D3_REV10_Q2D_SINGLE_CASE_ID =
    "single__w7000_s6000_h8000__e3aadd091c"
const D3_REV10_Q2D_PAIR_CASE_ID =
    "pair__w7000_s6000_d3000_h8000__1b4ad74450"
const D3_REV10_Q2D_SINGLE_RESULT_ID =
    "698550388234887bb768cf7d23659ef184ca4031fb16f5a852895a055571e570"
const D3_REV10_Q2D_PAIR_RESULT_ID =
    "5f431ca3418500e9dbfa32b4ee6bef6e28d3eb13423bf7d3e336086a23de10fb"
const D3_REV10_Q2D_DATABASE_SHA256 =
    "21874a582c1ffac4fac457866c5c6d94e67c9693857cdc40db96d5d45c400a90"
const D3_REV10_Q2D_MATERIAL_PROFILE_ID =
    "d3-q2d-silicon-er11p9-scalar-v1"
const D3_REV10_Q2D_MATERIAL_PROFILE_SHA256 =
    "ab92f6e20284f0c803a07f4f9368e1d2dc85ed051372c8db22f65d83efedef60"
const D3_REV10_Q2D_MATERIAL_AUTHORITY_SHA256 =
    "b96d249391a5420af07cc614b117fa0fb398e8078acd8bd7bc3e4e11d4c267af"
const D3_REV10_Q2D_SINGLE_EVIDENCE_SHA256 =
    "1d17de1bab2b21fdd6ee74e180f4cef017c5eaede79494a07536204b6ac5c231"
const D3_REV10_Q2D_PAIR_EVIDENCE_SHA256 =
    "6fb461b964592ae85f767bda6ec76ffbd9a357bab8c7151f821ace8a6026441a"
const D3_REV10_Q2D_SINGLE_SOURCES_SHA256 =
    "d502a4204c804117c5750b32563b66ff7c6b1101654d7bb19683f357ec909091"
const D3_REV10_Q2D_PAIR_SOURCES_SHA256 =
    "a5c5f7277c18308067606f03364bae422f654a753c4784aa9ec6789fac4d7c35"

const D3_REV10_Q2D_GEOMETRY_UM = (
    w=7.0,
    s=6.0,
    d=3.0,
    h=8.0,
    upper_ground_clearance=0.0,
    metal_thickness=0.2,
)
const D3_REV10_Q2D_SINGLE_L_PER_M_H = 3.788309072034884e-7
const D3_REV10_Q2D_SINGLE_C_PER_M_F = 1.5851727751577202e-10
const D3_REV10_Q2D_L_MATRIX_PER_M_H = [
    3.799417410057405e-7 1.495299415758173e-8
    1.495299415758173e-8 3.799405738536101e-7
]
const D3_REV10_Q2D_C_MATRIX_PER_M_F = [
    1.577696520905595e-10 -1.390725020136303e-11
    -1.390725020136303e-11 1.577591545674956e-10
]
const D3_REV10_Q2D_ALLOWED_CONSUMERS = (
    "d3_q2d",
    "rev10_five_slot_search",
    "stage_2_stage_3_closure",
)
const D3_REV10_Q2D_AUTHORITY = (
    payload_sha256=D3_REV10_Q2D_PAYLOAD_SHA256,
    single_result_id=D3_REV10_Q2D_SINGLE_RESULT_ID,
    pair_result_id=D3_REV10_Q2D_PAIR_RESULT_ID,
    source_database_sha256=D3_REV10_Q2D_DATABASE_SHA256,
    material_profile_id=D3_REV10_Q2D_MATERIAL_PROFILE_ID,
    material_profile_sha256=D3_REV10_Q2D_MATERIAL_PROFILE_SHA256,
    material_authority_sha256=D3_REV10_Q2D_MATERIAL_AUTHORITY_SHA256,
    single_evidence_sha256=D3_REV10_Q2D_SINGLE_EVIDENCE_SHA256,
    pair_evidence_sha256=D3_REV10_Q2D_PAIR_EVIDENCE_SHA256,
    single_raw_sources_sha256=D3_REV10_Q2D_SINGLE_SOURCES_SHA256,
    pair_raw_sources_sha256=D3_REV10_Q2D_PAIR_SOURCES_SHA256,
    basis="distributed_maxwell_per_unit_length",
    orientation="xy_cross_section_positive_z_propagation",
    row_column_order="conductor_order",
    l_matrix_unit="H/m",
    c_matrix_unit="F/m",
    data_class="project-internal",
    allowed_consumers=D3_REV10_Q2D_ALLOWED_CONSUMERS,
    publication_state="diagnostic",
    promotion_eligible=false,
)
const D3_Q2D_AUTHORITY_FIELDS = (
    :payload_sha256,
    :single_result_id,
    :pair_result_id,
    :source_database_sha256,
    :material_profile_id,
    :material_profile_sha256,
    :material_authority_sha256,
    :single_evidence_sha256,
    :pair_evidence_sha256,
    :single_raw_sources_sha256,
    :pair_raw_sources_sha256,
    :basis,
    :orientation,
    :row_column_order,
    :l_matrix_unit,
    :c_matrix_unit,
    :data_class,
    :allowed_consumers,
    :publication_state,
    :promotion_eligible,
)

struct D3Q2DAuthorityReceipt{T}
    normalized::T
end

struct D3Rev10Q2DInput{T}
    normalized::T
end

const D3Q2DNominalInput = Union{D3Q2DAuthorityReceipt,D3Rev10Q2DInput}
Base.propertynames(value::D3Q2DNominalInput) =
    propertynames(getfield(value, :normalized))
Base.hasproperty(value::D3Q2DNominalInput, name::Symbol) =
    hasproperty(getfield(value, :normalized), name)
function Base.getproperty(value::D3Q2DNominalInput, name::Symbol)
    name === :normalized && return getfield(value, :normalized)
    return getproperty(getfield(value, :normalized), name)
end

export load_d3_continuous_ground_q2d_input,
    bind_d3_rev10_q2d_input,
    validate_d3_q2d_authority_input,
    validate_d3_rev10_q2d_identity

function _d3_q2d_real(value, label)
    value isa Real && !(value isa Bool) || error("$(label) must be numeric.")
    number = Float64(value)
    isfinite(number) || error("$(label) must be finite.")
    return number
end

function _d3_q2d_positive(value, label)
    number = _d3_q2d_real(value, label)
    number > 0 || error("$(label) must be positive.")
    return number
end

function _d3_q2d_nonnegative(value, label)
    number = _d3_q2d_real(value, label)
    number >= 0 || error("$(label) must be nonnegative.")
    return number
end

function _d3_q2d_text(value, label)
    value isa AbstractString || error("$(label) must be text.")
    text = String(value)
    isempty(strip(text)) && error("$(label) must not be empty.")
    return text
end

function _d3_q2d_hash(value, label)
    hash = _d3_q2d_text(value, label)
    occursin(r"^[0-9a-f]{64}$", hash) ||
        error("$(label) must contain 64 lowercase hexadecimal characters.")
    return hash
end

function _d3_q2d_exact_fields(value, expected, label)
    actual = Set(Symbol.(keys(value)))
    actual == Set(expected) || error(
        "$(label) fields must be exactly $(collect(expected)); received $(sort!(collect(actual))).",
    )
    return value
end

function _d3_q2d_exact_properties(value, expected, label)
    actual = Set(propertynames(value))
    actual == Set(expected) || error(
        "$(label) fields must be exactly $(collect(expected)); received $(sort!(collect(actual))).",
    )
    return value
end

function _d3_q2d_matrix(value, shape, label)
    matrix = if value isa AbstractMatrix
        size(value) == shape ||
            error("$(label) must be a $(shape[1])x$(shape[2]) matrix.")
        Float64[
            _d3_q2d_real(value[row, column], "$(label)[$(row),$(column)]")
            for row in 1:shape[1], column in 1:shape[2]
        ]
    else
        rows = collect(value)
        length(rows) == shape[1] && all(row -> length(row) == shape[2], rows) ||
            error("$(label) must be a $(shape[1])x$(shape[2]) matrix.")
        Float64[
            _d3_q2d_real(rows[row][column], "$(label)[$(row),$(column)]")
            for row in 1:shape[1], column in 1:shape[2]
        ]
    end
    isapprox(matrix, transpose(matrix); rtol=1e-12, atol=0.0) ||
        error("$(label) must be symmetric.")
    isposdef(Symmetric(matrix)) || error("$(label) must have positive energy.")
    return matrix
end

function _d3_q2d_exact_value(actual, expected)
    if expected isa Bool
        return actual isa Bool && actual === expected
    elseif expected isa Real
        return actual isa Real && !(actual isa Bool) && actual == expected
    elseif expected isa Tuple
        return actual isa Tuple && length(actual) == length(expected) && all(
            _d3_q2d_exact_value(actual[index], expected[index])
            for index in eachindex(expected)
        )
    end
    return actual == expected
end

function _d3_q2d_exact_namedtuple(actual, expected, label)
    _d3_q2d_exact_properties(actual, propertynames(expected), label)
    for name in propertynames(expected)
        _d3_q2d_exact_value(
            getproperty(actual, name),
            getproperty(expected, name),
        ) || error("$(label) $(name) disagrees with the Rev10 W7 authority.")
    end
    return expected
end

function _d3_q2d_python_float(value)
    isfinite(value) || error("D3 Q2D canonical JSON rejects non-finite numbers.")
    text = string(value)
    occursin('e', text) || return text
    mantissa, exponent_text = split(text, 'e')
    exponent = parse(Int, exponent_text)
    if -4 <= exponent < 16
        sign = startswith(mantissa, "-") ? "-" : ""
        unsigned = isempty(sign) ? mantissa : mantissa[2:end]
        whole, fraction = split(unsigned, '.'; limit=2)
        digits = whole * fraction
        decimal_position = length(whole) + exponent
        if decimal_position <= 0
            return sign * "0." * repeat("0", -decimal_position) * digits
        elseif decimal_position >= length(digits)
            return sign * digits * repeat("0", decimal_position - length(digits)) * ".0"
        end
        return sign * digits[1:decimal_position] * "." * digits[(decimal_position + 1):end]
    end
    endswith(mantissa, ".0") && (mantissa = mantissa[1:(end - 2)])
    exponent_sign = exponent < 0 ? "-" : "+"
    return mantissa * "e" * exponent_sign * lpad(string(abs(exponent)), 2, '0')
end

function _d3_q2d_python_string!(io, value)
    write(io, '"')
    for character in String(value)
        code = Int(character)
        if character == '"'
            write(io, "\\\"")
        elseif character == '\\'
            write(io, "\\\\")
        elseif character == '\b'
            write(io, "\\b")
        elseif character == '\f'
            write(io, "\\f")
        elseif character == '\n'
            write(io, "\\n")
        elseif character == '\r'
            write(io, "\\r")
        elseif character == '\t'
            write(io, "\\t")
        elseif code < 0x20
            write(io, "\\u", string(code; base=16, pad=4))
        elseif code <= 0x7f
            write(io, character)
        elseif code <= 0xffff
            write(io, "\\u", string(code; base=16, pad=4))
        else
            adjusted = code - 0x10000
            high = 0xd800 + (adjusted >> 10)
            low = 0xdc00 + (adjusted & 0x3ff)
            write(io, "\\u", string(high; base=16, pad=4))
            write(io, "\\u", string(low; base=16, pad=4))
        end
    end
    write(io, '"')
    return io
end

function _d3_q2d_python_json!(io, value)
    if isnothing(value)
        write(io, "null")
    elseif value isa Bool
        write(io, value ? "true" : "false")
    elseif value isa Integer
        write(io, string(value))
    elseif value isa AbstractFloat
        write(io, _d3_q2d_python_float(value))
    elseif value isa AbstractString
        sentinel = "\0d3-q2d-number:"
        if startswith(value, sentinel)
            raw = value[(length(sentinel) + 1):end]
            if occursin(r"[.eE]", raw)
                write(io, _d3_q2d_python_float(parse(Float64, raw)))
            else
                write(io, string(parse(BigInt, raw)))
            end
        else
            _d3_q2d_python_string!(io, value)
        end
    elseif value isa AbstractVector || value isa Tuple
        write(io, '[')
        for (index, item) in enumerate(value)
            index == 1 || write(io, ',')
            _d3_q2d_python_json!(io, item)
        end
        write(io, ']')
    elseif value isa AbstractDict
        names = String[]
        for key in keys(value)
            key isa AbstractString || error("D3 Q2D canonical JSON keys must be text.")
            push!(names, String(key))
        end
        length(unique(names)) == length(names) ||
            error("D3 Q2D canonical JSON keys must be unique.")
        sort!(names)
        write(io, '{')
        for (index, name) in enumerate(names)
            index == 1 || write(io, ',')
            _d3_q2d_python_string!(io, name)
            write(io, ':')
            _d3_q2d_python_json!(io, value[name])
        end
        write(io, '}')
    else
        error("D3 Q2D canonical JSON does not support $(typeof(value)).")
    end
    return io
end

function _d3_q2d_preserve_json_numbers(text)
    sentinel = "\0d3-q2d-number:"
    occursin("\\u0000d3-q2d-number:", lowercase(text)) &&
        error("D3 Q2D JSON contains the reserved canonical-number sentinel.")
    io = IOBuffer()
    index = firstindex(text)
    terminal = lastindex(text)
    in_string = false
    escaped = false
    while index <= terminal
        character = text[index]
        if in_string
            write(io, character)
            if escaped
                escaped = false
            elseif character == '\\'
                escaped = true
            elseif character == '"'
                in_string = false
            end
            index = nextind(text, index)
        elseif character == '"'
            in_string = true
            write(io, character)
            index = nextind(text, index)
        elseif character == '-' || isdigit(character)
            start = index
            character == '-' && (index = nextind(text, index))
            while index <= terminal && isdigit(text[index])
                index = nextind(text, index)
            end
            if index <= terminal && text[index] == '.'
                index = nextind(text, index)
                while index <= terminal && isdigit(text[index])
                    index = nextind(text, index)
                end
            end
            if index <= terminal && (text[index] == 'e' || text[index] == 'E')
                index = nextind(text, index)
                if index <= terminal && (text[index] == '+' || text[index] == '-')
                    index = nextind(text, index)
                end
                while index <= terminal && isdigit(text[index])
                    index = nextind(text, index)
                end
            end
            raw = text[start:prevind(text, index)]
            _d3_q2d_python_string!(io, sentinel * raw)
        else
            write(io, character)
            index = nextind(text, index)
        end
    end
    in_string && error("D3 Q2D JSON contains an unterminated string.")
    return String(take!(io))
end

function _d3_q2d_payload_sha256(artifact_text)
    payload = JSON3.read(
        _d3_q2d_preserve_json_numbers(artifact_text),
        Dict{String,Any},
    )
    canonical_payload = copy(payload)
    pop!(canonical_payload, "artifact_identity")
    io = IOBuffer()
    _d3_q2d_python_json!(io, canonical_payload)
    return bytes2hex(SHA.sha256(take!(io)))
end

function _d3_q2d_common_authority(value, label)
    fields = (
        :air_height_nm,
        :basis,
        :die_thickness_nm,
        :ground_width_nm,
        :h_nm,
        :metal_thickness_nm,
        :orientation,
        :s_nm,
        :schema_version,
        :topology,
        :w_nm,
    )
    _d3_q2d_exact_fields(value, fields, label)
    value["schema_version"] == "d3-q2d-common-request-authority.v1" ||
        error("$(label) schema is unsupported.")
    value["basis"] == "distributed_maxwell_per_unit_length" ||
        error("$(label) basis is unsupported.")
    value["orientation"] == "xy_cross_section_positive_z_propagation" ||
        error("$(label) orientation is unsupported.")
    value["topology"] == "same_face_continuous_upper_ground" ||
        error("$(label) topology is unsupported.")
    return (
        air_height_nm=_d3_q2d_positive(value["air_height_nm"], "$(label) air height"),
        basis=String(value["basis"]),
        die_thickness_nm=_d3_q2d_positive(
            value["die_thickness_nm"],
            "$(label) die thickness",
        ),
        ground_width_nm=_d3_q2d_positive(
            value["ground_width_nm"],
            "$(label) ground width",
        ),
        h_nm=_d3_q2d_positive(value["h_nm"], "$(label) H"),
        metal_thickness_nm=_d3_q2d_positive(
            value["metal_thickness_nm"],
            "$(label) metal thickness",
        ),
        orientation=String(value["orientation"]),
        s_nm=_d3_q2d_positive(value["s_nm"], "$(label) S"),
        schema_version=String(value["schema_version"]),
        topology=String(value["topology"]),
        w_nm=_d3_q2d_positive(value["w_nm"], "$(label) W"),
    )
end

function _d3_q2d_material_authority(value, label; role_evidence)
    common_fields = (
        "material_profile_id",
        "material_profile_hash",
        "material_authority_hash",
        "data_class",
        "allowed_consumers",
        "publication_state",
        "promotion_eligible",
    )
    expected_fields = role_evidence ?
        (common_fields..., "material_evidence_snapshot_hash", "provenance_layers",
            "substrate_assignments") : common_fields
    _d3_q2d_exact_fields(value, Symbol.(expected_fields), label)
    allowed_consumers = Tuple(
        _d3_q2d_text(item, "$(label) allowed consumer")
        for item in value["allowed_consumers"]
    )
    !isempty(allowed_consumers) && length(unique(allowed_consumers)) == length(allowed_consumers) ||
        error("$(label) allowed consumers must be non-empty and unique.")
    value["data_class"] == "project-internal" ||
        error("$(label) must remain project-internal.")
    value["publication_state"] == "diagnostic" ||
        error("$(label) must remain diagnostic.")
    value["promotion_eligible"] === false ||
        error("$(label) must not be promotion eligible.")
    evidence_sha256 = role_evidence ?
        _d3_q2d_hash(
            value["material_evidence_snapshot_hash"],
            "$(label) evidence SHA-256",
        ) : nothing
    if role_evidence
        layers = value["provenance_layers"]
        requested_context = layers["requested"]["material_context"]
        requested_context["material_profile_hash"] == value["material_profile_hash"] ||
            error("$(label) requested profile hash is inconsistent.")
        requested_context["material_profile"]["material_profile_id"] ==
            value["material_profile_id"] ||
            error("$(label) requested profile id is inconsistent.")
        layers["resolved"]["material_profile_hash"] == value["material_profile_hash"] ||
            error("$(label) resolved profile hash is inconsistent.")
        assignments = collect(value["substrate_assignments"])
        !isempty(assignments) || error("$(label) substrate assignments are empty.")
        for assignment in assignments
            _d3_q2d_text(assignment["object_name"], "$(label) substrate object")
            _d3_q2d_text(
                assignment["stored_material_name"],
                "$(label) substrate material",
            )
        end
    end
    return (
        material_profile_id=_d3_q2d_text(
            value["material_profile_id"],
            "$(label) profile id",
        ),
        material_profile_sha256=_d3_q2d_hash(
            value["material_profile_hash"],
            "$(label) profile SHA-256",
        ),
        material_authority_sha256=_d3_q2d_hash(
            value["material_authority_hash"],
            "$(label) authority SHA-256",
        ),
        evidence_sha256=evidence_sha256,
        data_class="project-internal",
        allowed_consumers=allowed_consumers,
        publication_state="diagnostic",
        promotion_eligible=false,
    )
end

function _d3_q2d_source_manifest_sha256(records, label)
    normalized = NamedTuple[]
    paths = String[]
    for record in records
        _d3_q2d_exact_fields(record, (:path, :size_bytes, :sha256), label)
        path = _d3_q2d_text(record["path"], "$(label) path")
        push!(paths, path)
        push!(normalized, (
            path=path,
            sha256=_d3_q2d_hash(record["sha256"], "$(label) SHA-256"),
            size_bytes=Int(_d3_q2d_positive(record["size_bytes"], "$(label) size")),
        ))
    end
    !isempty(normalized) && length(unique(paths)) == length(paths) ||
        error("$(label) records must be non-empty with unique paths.")
    return bytes2hex(SHA.sha256(codeunits(JSON3.write(normalized))))
end

function _d3_q2d_validate_raw_sources(value, single_case_id, pair_case_id)
    _d3_q2d_exact_fields(
        value,
        (:algorithm, :all_sources_hashed, :solver_export_sizes_verified,
            :material_result_database, :cases),
        "D3 Q2D source integrity",
    )
    value["algorithm"] == "sha256" || error("D3 Q2D sources must use SHA-256.")
    value["all_sources_hashed"] === true || error("D3 Q2D sources are incomplete.")
    value["solver_export_sizes_verified"] === true ||
        error("D3 Q2D source sizes were not verified.")
    database = value["material_result_database"]
    _d3_q2d_exact_fields(database, (:path, :size_bytes, :sha256), "D3 Q2D database")
    database_sha256 = _d3_q2d_hash(database["sha256"], "D3 Q2D database SHA-256")
    _d3_q2d_positive(database["size_bytes"], "D3 Q2D database size")
    _d3_q2d_text(database["path"], "D3 Q2D database path")
    sources = value["cases"]
    Set(keys(sources)) == Set((single_case_id, pair_case_id)) ||
        error("D3 Q2D raw-source case bindings are incomplete.")
    return (
        source_database_sha256=database_sha256,
        single_raw_sources_sha256=_d3_q2d_source_manifest_sha256(
            collect(sources[single_case_id]),
            "D3 Q2D single raw source",
        ),
        pair_raw_sources_sha256=_d3_q2d_source_manifest_sha256(
            collect(sources[pair_case_id]),
            "D3 Q2D pair raw source",
        ),
    )
end

function _d3_q2d_validate_convergence(value, label)
    Set(keys(value)) == Set(("CG", "RL")) ||
        error("$(label) must include CG and RL convergence.")
    for name in ("CG", "RL")
        record = value[name]
        _d3_q2d_exact_fields(
            record,
            (:problem_type, :completed_passes, :maximum_passes,
                :target_percent, :current_percent),
            "$(label) $(name)",
        )
        record["problem_type"] == name || error("$(label) $(name) type is wrong.")
        completed = _d3_q2d_positive(record["completed_passes"], "$(label) passes")
        maximum = _d3_q2d_positive(record["maximum_passes"], "$(label) max passes")
        completed <= maximum || error("$(label) completed passes exceed the maximum.")
        target = _d3_q2d_positive(record["target_percent"], "$(label) target")
        current = [
            _d3_q2d_nonnegative(item, "$(label) current percent")
            for item in record["current_percent"]
        ]
        !isempty(current) && all(<=(target), current) ||
            error("$(label) did not meet its declared convergence target.")
    end
    return nothing
end

function _d3_q2d_validate_case(case, role, common, bundle_material, directions)
    single = role == "single_reference"
    expected_fields = single ?
        (:schema_version, :id, :case_role, :parameters, :topology, :metadata,
            :l_matrix_h_per_m, :c_matrix_f_per_m, :convergence, :selected_result,
            :material_authority, :common_request_authority, :derived) :
        (:schema_version, :id, :case_role, :parameters, :topology, :metadata,
            :l_matrix_h_per_m, :c_matrix_f_per_m, :convergence, :selected_result,
            :material_authority, :common_request_authority)
    _d3_q2d_exact_fields(case, expected_fields, "D3 Q2D $(role) case")
    case["case_role"] == role || error("D3 Q2D case role order is wrong.")
    case["schema_version"] == (single ?
        "orpen-q2d-single-reference-maxwell-lc.v1" :
        "orpen-q2d-coupled-pair-maxwell-lc.v1") ||
        error("D3 Q2D $(role) schema is unsupported.")
    case_id = _d3_q2d_text(case["id"], "D3 Q2D $(role) case id")

    parameters = case["parameters"]
    _d3_q2d_exact_fields(
        parameters,
        (:case_role, :trace_width_um, :trace_gap_um,
            :inter_trace_ground_width_um, :flip_chip_gap_height_um,
            :upper_ground_clearance_width_um),
        "D3 Q2D $(role) parameters",
    )
    parameters["case_role"] == role || error("D3 Q2D parameter role is wrong.")
    w = _d3_q2d_positive(parameters["trace_width_um"], "D3 Q2D W")
    s = _d3_q2d_positive(parameters["trace_gap_um"], "D3 Q2D S")
    h = _d3_q2d_positive(parameters["flip_chip_gap_height_um"], "D3 Q2D H")
    clearance = _d3_q2d_nonnegative(
        parameters["upper_ground_clearance_width_um"],
        "D3 Q2D upper-ground clearance",
    )
    clearance == 0.0 || error("D3 continuous upper ground requires zero clearance.")
    d = if single
        parameters["inter_trace_ground_width_um"] == "" ||
            error("D3 Q2D single reference must not declare D.")
        nothing
    else
        _d3_q2d_positive(parameters["inter_trace_ground_width_um"], "D3 Q2D D")
    end
    w == common.w_nm / 1000 && s == common.s_nm / 1000 && h == common.h_nm / 1000 ||
        error("D3 Q2D $(role) geometry disagrees with common authority.")

    topology = case["topology"]
    topology_fields = (
        :schema_version, :resonator_die, :resonator_face, :trace_names,
        :upper_die, :upper_die_substrate_present, :upper_ground_face,
        :upper_ground_clearance_width_um, :upper_ground_metal_policy,
        :reference_group,
    )
    _d3_q2d_exact_fields(
        topology,
        single ? (topology_fields..., :upper_ground_clearance_alignment) :
        topology_fields,
        "D3 Q2D $(role) topology",
    )
    topology["schema_version"] == (single ?
        "q2d-single-reference-continuous-upper-ground.v1" :
        "q2d-same-face-continuous-upper-ground.v1") ||
        error("D3 Q2D $(role) topology schema is unsupported.")
    topology["resonator_die"] == "D0" && topology["resonator_face"] == "top" ||
        error("D3 Q2D resonator face is unsupported.")
    topology["upper_die"] == "D1" && topology["upper_die_substrate_present"] === true ||
        error("D3 Q2D upper substrate is unsupported.")
    topology["upper_ground_face"] == "bottom" ||
        error("D3 Q2D upper-ground face is unsupported.")
    if single
        topology["upper_ground_clearance_alignment"] == "not_applicable" ||
            error("D3 continuous upper ground cannot declare a clearance alignment.")
    end
    topology["upper_ground_metal_policy"] ==
        "continuous_over_full_modeled_lateral_extent" ||
        error("D3 Q2D upper-ground policy is unsupported.")
    topology["reference_group"] == "Ground" || error("D3 Q2D reference is wrong.")
    topology["upper_ground_clearance_width_um"] == clearance ||
        error("D3 Q2D topology clearance disagrees with its parameters.")
    metadata = case["metadata"]
    expected_order = single ? ["T1"] : ["T1", "T2"]
    _d3_q2d_exact_fields(
        metadata,
        (:conductor_order, :reference_group, :directions, :matrix_representation),
        "D3 Q2D $(role) metadata",
    )
    metadata["conductor_order"] == expected_order || error("D3 Q2D conductor order is wrong.")
    topology["trace_names"] == expected_order || error("D3 Q2D trace order is wrong.")
    metadata["reference_group"] == "Ground" || error("D3 Q2D reference group is wrong.")
    metadata["directions"] == directions || error("D3 Q2D directions are inconsistent.")
    representation = metadata["matrix_representation"]
    _d3_q2d_exact_fields(
        representation,
        (:kind, :row_column_order, :shape, :C, :L),
        "D3 Q2D $(role) matrix representation",
    )
    representation["kind"] == "distributed_maxwell_per_unit_length" ||
        error("D3 Q2D matrix basis is wrong.")
    representation["row_column_order"] == "conductor_order" ||
        error("D3 Q2D matrix ordering is wrong.")
    representation["shape"] == (single ? [1, 1] : [2, 2]) ||
        error("D3 Q2D matrix shape is wrong.")
    startswith(String(representation["L"]), "H/m;") || error("D3 Q2D L' unit is wrong.")
    startswith(String(representation["C"]), "F/m;") || error("D3 Q2D C' unit is wrong.")

    selected = case["selected_result"]
    _d3_q2d_exact_fields(
        selected,
        (:result_id, :request_cache_key, :source_case_id, :source_run_root,
            :solver_completed_at, :material_evidence_snapshot_hash,
            :common_request_authority),
        "D3 Q2D $(role) selected result",
    )
    result_id = _d3_q2d_hash(selected["result_id"], "D3 Q2D $(role) result id")
    _d3_q2d_hash(selected["request_cache_key"], "D3 Q2D request cache key")
    selected["source_case_id"] == case_id || error("D3 Q2D source case id is wrong.")
    _d3_q2d_text(selected["source_run_root"], "D3 Q2D source run root")
    _d3_q2d_text(selected["solver_completed_at"], "D3 Q2D solver completion time")
    evidence_sha256 = _d3_q2d_hash(
        selected["material_evidence_snapshot_hash"],
        "D3 Q2D $(role) evidence SHA-256",
    )
    selected_common = _d3_q2d_common_authority(
        selected["common_request_authority"],
        "D3 Q2D selected-result common authority",
    )
    case_common = _d3_q2d_common_authority(
        case["common_request_authority"],
        "D3 Q2D case common authority",
    )
    selected_common == common == case_common ||
        error("D3 Q2D common authority bindings are inconsistent.")
    material = _d3_q2d_material_authority(
        case["material_authority"],
        "D3 Q2D case material";
        role_evidence=true,
    )
    material.evidence_sha256 == evidence_sha256 ||
        error("D3 Q2D material evidence binding is inconsistent.")
    for name in (
        :material_profile_id,
        :material_profile_sha256,
        :material_authority_sha256,
        :data_class,
        :allowed_consumers,
        :publication_state,
        :promotion_eligible,
    )
        getproperty(material, name) == getproperty(bundle_material, name) ||
            error("D3 Q2D material authority is inconsistent across roles.")
    end
    _d3_q2d_validate_convergence(case["convergence"], "D3 Q2D $(role)")
    l_matrix = _d3_q2d_matrix(
        case["l_matrix_h_per_m"],
        single ? (1, 1) : (2, 2),
        "D3 Q2D L'",
    )
    c_matrix = _d3_q2d_matrix(
        case["c_matrix_f_per_m"],
        single ? (1, 1) : (2, 2),
        "D3 Q2D C'",
    )
    z0_ohm = if single
        Set(keys(case["derived"])) == Set(["z0_ohm"]) ||
            error("D3 single reference may derive only z0.")
        z0 = _d3_q2d_positive(case["derived"]["z0_ohm"], "D3 single-reference z0")
        isapprox(z0, sqrt(l_matrix[1, 1] / c_matrix[1, 1]); rtol=1e-12, atol=0.0) ||
            error("D3 single-reference z0 disagrees with its L'/C'.")
        z0
    else
        haskey(case, "derived") && error(
            "D3 coupled pair must not expose derived or heuristic impedance authority.",
        )
        nothing
    end
    return (
        case_id=case_id,
        result_id=result_id,
        evidence_sha256=evidence_sha256,
        w=w,
        s=s,
        d=d,
        h=h,
        clearance=clearance,
        l_matrix=l_matrix,
        c_matrix=c_matrix,
        z0_ohm=z0_ohm,
    )
end

function _d3_q2d_generic_authority(value)
    _d3_q2d_exact_properties(value, D3_Q2D_AUTHORITY_FIELDS, "D3 Q2D authority")
    allowed_consumers = Tuple(
        _d3_q2d_text(item, "D3 Q2D allowed consumer")
        for item in value.allowed_consumers
    )
    !isempty(allowed_consumers) && length(unique(allowed_consumers)) == length(allowed_consumers) ||
        error("D3 Q2D allowed consumers must be non-empty and unique.")
    value.basis == "distributed_maxwell_per_unit_length" ||
        error("D3 Q2D basis is unsupported.")
    value.orientation == "xy_cross_section_positive_z_propagation" ||
        error("D3 Q2D orientation is unsupported.")
    value.row_column_order == "conductor_order" ||
        error("D3 Q2D matrix ordering is unsupported.")
    value.l_matrix_unit == "H/m" && value.c_matrix_unit == "F/m" ||
        error("D3 Q2D matrix units are unsupported.")
    value.data_class == "project-internal" || error("D3 Q2D input must be project-internal.")
    value.publication_state == "diagnostic" || error("D3 Q2D input must be diagnostic.")
    value.promotion_eligible === false || error("D3 Q2D input must not be promotable.")
    return (
        payload_sha256=_d3_q2d_hash(value.payload_sha256, "D3 Q2D payload SHA-256"),
        single_result_id=_d3_q2d_hash(value.single_result_id, "D3 Q2D single result id"),
        pair_result_id=_d3_q2d_hash(value.pair_result_id, "D3 Q2D pair result id"),
        source_database_sha256=_d3_q2d_hash(
            value.source_database_sha256,
            "D3 Q2D database SHA-256",
        ),
        material_profile_id=_d3_q2d_text(
            value.material_profile_id,
            "D3 Q2D material profile id",
        ),
        material_profile_sha256=_d3_q2d_hash(
            value.material_profile_sha256,
            "D3 Q2D material profile SHA-256",
        ),
        material_authority_sha256=_d3_q2d_hash(
            value.material_authority_sha256,
            "D3 Q2D material authority SHA-256",
        ),
        single_evidence_sha256=_d3_q2d_hash(
            value.single_evidence_sha256,
            "D3 Q2D single evidence SHA-256",
        ),
        pair_evidence_sha256=_d3_q2d_hash(
            value.pair_evidence_sha256,
            "D3 Q2D pair evidence SHA-256",
        ),
        single_raw_sources_sha256=_d3_q2d_hash(
            value.single_raw_sources_sha256,
            "D3 Q2D single raw-source SHA-256",
        ),
        pair_raw_sources_sha256=_d3_q2d_hash(
            value.pair_raw_sources_sha256,
            "D3 Q2D pair raw-source SHA-256",
        ),
        basis=String(value.basis),
        orientation=String(value.orientation),
        row_column_order=String(value.row_column_order),
        l_matrix_unit=String(value.l_matrix_unit),
        c_matrix_unit=String(value.c_matrix_unit),
        data_class="project-internal",
        allowed_consumers=allowed_consumers,
        publication_state="diagnostic",
        promotion_eligible=false,
    )
end

function _d3_q2d_normalize_authority_input(fixed)
    required = (
        :single_l_per_m_h,
        :single_c_per_m_f,
        :l_matrix_per_m_h,
        :c_matrix_per_m_f,
        :coupling_orientation,
        :q2d_artifact_id,
        :q2d_artifact_sha256,
        :q2d_topology_id,
        :q2d_geometry_um,
        :q2d_single_case_id,
        :q2d_pair_case_id,
        :q2d_solver,
        :q2d_loss_model,
        :q2d_authority,
    )
    all(name -> hasproperty(fixed, name), required) ||
        error("D3 input is missing material-aware Q2D authority fields.")
    artifact_sha256 = _d3_q2d_hash(fixed.q2d_artifact_sha256, "D3 Q2D artifact SHA-256")
    authority = _d3_q2d_generic_authority(fixed.q2d_authority)
    artifact_id = _d3_q2d_text(fixed.q2d_artifact_id, "D3 Q2D artifact id")
    artifact_id == "orpen-q2d-maxwell-lc-$(authority.payload_sha256)" ||
        error("D3 Q2D artifact id disagrees with its canonical payload identity.")
    Symbol(fixed.q2d_topology_id) == :continuous_upper_ground ||
        error("D3 Q2D input must use continuous upper ground.")
    Symbol(fixed.coupling_orientation) == :same_direction ||
        error("D3 Q2D input must use same-direction coupling.")
    fixed.q2d_loss_model == "lossless_R_equals_G_equals_zero" ||
        error("D3 Q2D input must use its declared downstream LC-only assumption.")
    geometry = fixed.q2d_geometry_um
    _d3_q2d_exact_properties(
        geometry,
        (:w, :s, :d, :h, :upper_ground_clearance, :metal_thickness),
        "D3 Q2D geometry",
    )
    normalized_geometry = (
        w=_d3_q2d_positive(geometry.w, "D3 Q2D W"),
        s=_d3_q2d_positive(geometry.s, "D3 Q2D S"),
        d=_d3_q2d_positive(geometry.d, "D3 Q2D D"),
        h=_d3_q2d_positive(geometry.h, "D3 Q2D H"),
        upper_ground_clearance=_d3_q2d_nonnegative(
            geometry.upper_ground_clearance,
            "D3 Q2D upper-ground clearance",
        ),
        metal_thickness=_d3_q2d_positive(
            geometry.metal_thickness,
            "D3 Q2D metal thickness",
        ),
    )
    normalized_geometry.upper_ground_clearance == 0.0 ||
        error("D3 continuous upper ground requires zero clearance.")
    solver = fixed.q2d_solver
    _d3_q2d_exact_properties(
        solver,
        (:adaptive_frequency_hz, :aedt_version, :pyaedt_version),
        "D3 Q2D solver",
    )
    normalized_solver = (
        adaptive_frequency_hz=_d3_q2d_positive(
            solver.adaptive_frequency_hz,
            "D3 Q2D adaptive frequency",
        ),
        aedt_version=_d3_q2d_text(solver.aedt_version, "D3 Q2D AEDT version"),
        pyaedt_version=_d3_q2d_text(solver.pyaedt_version, "D3 Q2D PyAEDT version"),
    )
    single_l = _d3_q2d_positive(fixed.single_l_per_m_h, "D3 single-reference L'")
    single_c = _d3_q2d_positive(fixed.single_c_per_m_f, "D3 single-reference C'")
    l_matrix = _d3_q2d_matrix(fixed.l_matrix_per_m_h, (2, 2), "D3 Q2D L'")
    c_matrix = _d3_q2d_matrix(fixed.c_matrix_per_m_f, (2, 2), "D3 Q2D C'")
    return (
        single_l_per_m_h=single_l,
        single_c_per_m_f=single_c,
        l_matrix_per_m_h=l_matrix,
        c_matrix_per_m_f=c_matrix,
        coupling_orientation=:same_direction,
        q2d_artifact_id=artifact_id,
        q2d_artifact_sha256=artifact_sha256,
        q2d_topology_id=:continuous_upper_ground,
        q2d_geometry_um=normalized_geometry,
        q2d_single_case_id=_d3_q2d_text(
            fixed.q2d_single_case_id,
            "D3 Q2D single case id",
        ),
        q2d_pair_case_id=_d3_q2d_text(fixed.q2d_pair_case_id, "D3 Q2D pair case id"),
        q2d_solver=normalized_solver,
        q2d_loss_model="lossless_R_equals_G_equals_zero",
        q2d_authority=authority,
    )
end

"""Revalidate a sealed material-aware v4 Q2D authority without selecting a target."""
function validate_d3_q2d_authority_input(fixed::D3Q2DAuthorityReceipt)
    return _d3_q2d_normalize_authority_input(fixed)
end

"""Bind generic v4 authority to the exact Human-accepted Rev10 W7 selection."""
function _d3_q2d_bind_rev10(fixed)
    authority_input = fixed
    authority_input.q2d_artifact_id == D3_REV10_Q2D_ARTIFACT_ID ||
        error("D3 Rev10 uses the wrong Q2D artifact id.")
    authority_input.q2d_artifact_sha256 == D3_REV10_Q2D_FILE_SHA256 ||
        error("D3 Rev10 uses the wrong Q2D artifact hash.")
    authority_input.q2d_single_case_id == D3_REV10_Q2D_SINGLE_CASE_ID ||
        error("D3 Rev10 uses the wrong single-reference case.")
    authority_input.q2d_pair_case_id == D3_REV10_Q2D_PAIR_CASE_ID ||
        error("D3 Rev10 uses the wrong coupled-pair case.")
    _d3_q2d_exact_namedtuple(
        authority_input.q2d_geometry_um,
        D3_REV10_Q2D_GEOMETRY_UM,
        "D3 Rev10 Q2D geometry",
    )
    _d3_q2d_exact_namedtuple(
        authority_input.q2d_solver,
        (adaptive_frequency_hz=6.0e9, aedt_version="2024.2", pyaedt_version="0.26.2"),
        "D3 Rev10 Q2D solver",
    )
    _d3_q2d_exact_namedtuple(
        authority_input.q2d_authority,
        D3_REV10_Q2D_AUTHORITY,
        "D3 Rev10 Q2D authority",
    )
    "rev10_five_slot_search" in authority_input.q2d_authority.allowed_consumers ||
        error("D3 Rev10 is not an allowed consumer of the selected Q2D artifact.")
    authority_input.single_l_per_m_h == D3_REV10_Q2D_SINGLE_L_PER_M_H &&
        authority_input.single_c_per_m_f == D3_REV10_Q2D_SINGLE_C_PER_M_F ||
        error("D3 Rev10 single-reference L'/C' is wrong.")
    authority_input.l_matrix_per_m_h == D3_REV10_Q2D_L_MATRIX_PER_M_H ||
        error("D3 Rev10 coupled-pair L' is wrong.")
    authority_input.c_matrix_per_m_f == D3_REV10_Q2D_C_MATRIX_PER_M_F ||
        error("D3 Rev10 coupled-pair C' is wrong.")
    return authority_input
end

"""Bind one sealed v4 authority to Rev10 and its physical line discretization."""
function bind_d3_rev10_q2d_input(
    fixed::D3Q2DAuthorityReceipt;
    section_length_m,
    mtl_section_length_m=section_length_m,
)
    authority_input = _d3_q2d_bind_rev10(validate_d3_q2d_authority_input(fixed))
    section = _d3_q2d_positive(section_length_m, "D3 line section length")
    section <= D3_MAX_LINE_SECTION_LENGTH_M ||
        error("D3 physical line section length must not exceed 50 um.")
    mtl_section = _d3_q2d_positive(
        mtl_section_length_m,
        "D3 MTL section length",
    )
    mtl_section <= D3_MAX_LINE_SECTION_LENGTH_M ||
        error("D3 physical MTL section length must not exceed 50 um.")
    return D3Rev10Q2DInput(merge(
        (
            section_length_m=section,
            mtl_section_length_m=mtl_section,
            readout_l_per_m_h=authority_input.single_l_per_m_h,
            readout_c_per_m_f=authority_input.single_c_per_m_f,
            filter_l_per_m_h=authority_input.single_l_per_m_h,
            filter_c_per_m_f=authority_input.single_c_per_m_f,
        ),
        authority_input,
    ))
end

function validate_d3_rev10_q2d_input(fixed::D3Rev10Q2DInput)
    authority_input = _d3_q2d_bind_rev10(_d3_q2d_normalize_authority_input(fixed))
    section = _d3_q2d_positive(fixed.section_length_m, "D3 line section length")
    mtl_section = _d3_q2d_positive(fixed.mtl_section_length_m, "D3 MTL section length")
    section <= D3_MAX_LINE_SECTION_LENGTH_M &&
        mtl_section <= D3_MAX_LINE_SECTION_LENGTH_M ||
        error("D3 Rev10 physical line section length must not exceed 50 um.")
    fixed.readout_l_per_m_h == authority_input.single_l_per_m_h &&
        fixed.readout_c_per_m_f == authority_input.single_c_per_m_f &&
        fixed.filter_l_per_m_h == authority_input.single_l_per_m_h &&
        fixed.filter_c_per_m_f == authority_input.single_c_per_m_f ||
        error("D3 Rev10 line parameters must come from the sealed single reference.")
    return merge(
        (
            section_length_m=section,
            mtl_section_length_m=mtl_section,
            readout_l_per_m_h=authority_input.single_l_per_m_h,
            readout_c_per_m_f=authority_input.single_c_per_m_f,
            filter_l_per_m_h=authority_input.single_l_per_m_h,
            filter_c_per_m_f=authority_input.single_c_per_m_f,
        ),
        authority_input,
    )
end

"""Revalidate a serialized Fixed-line V2 identity without making it executable."""
function validate_d3_rev10_q2d_identity(fixed)
    fixed.readout_l_per_m_h == fixed.filter_l_per_m_h &&
        fixed.readout_c_per_m_f == fixed.filter_c_per_m_f ||
        error("D3 Fixed-line V2 must retain one sealed single-reference L'/C' pair.")
    authority_input = _d3_q2d_bind_rev10(_d3_q2d_normalize_authority_input((
        single_l_per_m_h=fixed.readout_l_per_m_h,
        single_c_per_m_f=fixed.readout_c_per_m_f,
        l_matrix_per_m_h=fixed.l_matrix_per_m_h,
        c_matrix_per_m_f=fixed.c_matrix_per_m_f,
        coupling_orientation=fixed.coupling_orientation,
        q2d_artifact_id=fixed.q2d_artifact_id,
        q2d_artifact_sha256=fixed.q2d_artifact_sha256,
        q2d_topology_id=fixed.q2d_topology_id,
        q2d_geometry_um=fixed.q2d_geometry_um,
        q2d_single_case_id=fixed.q2d_single_case_id,
        q2d_pair_case_id=fixed.q2d_pair_case_id,
        q2d_solver=fixed.q2d_solver,
        q2d_loss_model=fixed.q2d_loss_model,
        q2d_authority=fixed.q2d_authority,
    )))
    section = _d3_q2d_positive(fixed.section_length_m, "D3 line section length")
    mtl_section = _d3_q2d_positive(fixed.mtl_section_length_m, "D3 MTL section length")
    section <= D3_MAX_LINE_SECTION_LENGTH_M &&
        mtl_section <= D3_MAX_LINE_SECTION_LENGTH_M ||
        error("D3 Rev10 physical line section length must not exceed 50 um.")
    return merge(
        (
            section_length_m=section,
            mtl_section_length_m=mtl_section,
            readout_l_per_m_h=authority_input.single_l_per_m_h,
            readout_c_per_m_f=authority_input.single_c_per_m_f,
            filter_l_per_m_h=authority_input.single_l_per_m_h,
            filter_c_per_m_f=authority_input.single_c_per_m_f,
        ),
        authority_input,
    )
end

"""Load and normalize one supported material-aware continuous-ground v4 artifact."""
function load_d3_continuous_ground_q2d_input(path)
    input_path = abspath(String(path))
    isfile(input_path) || error("D3 Q2D input does not exist: $(input_path)")
    artifact_bytes = read(input_path)
    artifact_sha256 = bytes2hex(SHA.sha256(artifact_bytes))
    artifact_text = String(copy(artifact_bytes))
    payload = JSON3.read(artifact_text, Dict{String,Any})
    _d3_q2d_exact_fields(
        payload,
        (:schema_version, :artifact_status, :metadata, :cases, :artifact_identity),
        "D3 Q2D bundle",
    )
    payload["schema_version"] == D3_Q2D_V4_SCHEMA ||
        error("D3 Q2D bundle schema is unsupported.")
    payload["artifact_status"] == "complete" || error("D3 Q2D bundle is incomplete.")
    identity = payload["artifact_identity"]
    _d3_q2d_exact_fields(
        identity,
        (:algorithm, :payload_sha256, :artifact_id),
        "D3 Q2D artifact identity",
    )
    identity["algorithm"] == "sha256" || error("D3 Q2D identity algorithm is wrong.")
    payload_sha256 = _d3_q2d_hash(
        identity["payload_sha256"],
        "D3 Q2D payload SHA-256",
    )
    payload_sha256 == _d3_q2d_payload_sha256(artifact_text) ||
        error("D3 Q2D canonical payload identity is wrong.")
    artifact_id = _d3_q2d_text(identity["artifact_id"], "D3 Q2D artifact id")
    artifact_id == "orpen-q2d-maxwell-lc-$(payload_sha256)" ||
        error("D3 Q2D artifact id disagrees with its canonical payload identity.")

    metadata = payload["metadata"]
    _d3_q2d_exact_fields(
        metadata,
        (:reference_group, :directions, :extraction_frequency_hz,
            :adaptive_frequency_expression, :loss_terms, :solver_provenance,
            :material_authority, :common_request_authority, :run_provenance,
            :source_integrity),
        "D3 Q2D metadata",
    )
    metadata["reference_group"] == "Ground" || error("D3 Q2D reference is wrong.")
    directions = metadata["directions"]
    _d3_q2d_exact_fields(
        directions,
        (:voltage, :current, :positive_z),
        "D3 Q2D directions",
    )
    directions["voltage"] == "V[i] = potential(Ti) - potential(Ground)" ||
        error("D3 Q2D voltage direction is wrong.")
    directions["current"] == "positive I[i] flows in +z" ||
        error("D3 Q2D current direction is wrong.")
    directions["positive_z"] ==
        "normal to the XY cross-section and along line propagation" ||
        error("D3 Q2D propagation orientation is wrong.")
    extraction_frequency_hz = _d3_q2d_positive(
        metadata["extraction_frequency_hz"],
        "D3 Q2D extraction frequency",
    )
    _d3_q2d_text(
        metadata["adaptive_frequency_expression"],
        "D3 Q2D adaptive frequency expression",
    )
    solver = metadata["solver_provenance"]
    _d3_q2d_exact_fields(
        solver,
        (:solver, :aedt_version, :pyaedt_version),
        "D3 Q2D solver provenance",
    )
    solver["solver"] == "Ansys Electronics Desktop 2D Extractor" ||
        error("D3 Q2D solver is unsupported.")
    aedt_version = _d3_q2d_text(solver["aedt_version"], "D3 Q2D AEDT version")
    pyaedt_version = _d3_q2d_text(solver["pyaedt_version"], "D3 Q2D PyAEDT version")
    losses = metadata["loss_terms"]
    _d3_q2d_exact_fields(losses, (:R, :G), "D3 Q2D loss terms")
    for (name, unit) in (("R", "ohm/m"), ("G", "S/m"))
        _d3_q2d_exact_fields(
            losses[name],
            (:status, :assumed_zero_for_v1, :unit),
            "D3 Q2D $(name) loss term",
        )
        losses[name]["status"] == "unavailable" || error("D3 Q2D $(name) status is wrong.")
        losses[name]["assumed_zero_for_v1"] === true ||
            error("D3 Q2D $(name) must use the declared downstream LC-only assumption.")
        losses[name]["unit"] == unit || error("D3 Q2D $(name) unit is wrong.")
    end
    bundle_material = _d3_q2d_material_authority(
        metadata["material_authority"],
        "D3 Q2D bundle material";
        role_evidence=false,
    )
    isnothing(bundle_material.evidence_sha256) ||
        error("D3 Q2D bundle-level material authority must not select one role's evidence.")
    common = _d3_q2d_common_authority(
        metadata["common_request_authority"],
        "D3 Q2D bundle common authority",
    )
    cases = collect(payload["cases"])
    length(cases) == 2 || error("D3 Q2D bundle must contain exactly two roles.")
    single = _d3_q2d_validate_case(
        cases[1],
        "single_reference",
        common,
        bundle_material,
        directions,
    )
    pair = _d3_q2d_validate_case(
        cases[2],
        "coupled_pair",
        common,
        bundle_material,
        directions,
    )
    single.w == pair.w && single.s == pair.s && single.h == pair.h &&
        single.clearance == pair.clearance ||
        error("D3 Q2D single and pair geometries are inconsistent.")
    run = metadata["run_provenance"]
    _d3_q2d_exact_fields(
        run,
        (:run_id, :project_name, :manifest_schema_version, :recipe_id,
            :case_ids, :selected_case_status),
        "D3 Q2D run provenance",
    )
    _d3_q2d_text(run["run_id"], "D3 Q2D run id")
    _d3_q2d_text(run["project_name"], "D3 Q2D project name")
    run["manifest_schema_version"] isa Integer ||
        error("D3 Q2D manifest schema version must be an integer.")
    _d3_q2d_text(run["recipe_id"], "D3 Q2D recipe id")
    run["case_ids"] == [single.case_id, pair.case_id] ||
        error("D3 Q2D run provenance case ordering is wrong.")
    run["selected_case_status"] == "solve_complete" ||
        error("D3 Q2D selected cases are incomplete.")
    raw_sources = _d3_q2d_validate_raw_sources(
        metadata["source_integrity"],
        single.case_id,
        pair.case_id,
    )
    authority = (
        payload_sha256=payload_sha256,
        single_result_id=single.result_id,
        pair_result_id=pair.result_id,
        source_database_sha256=raw_sources.source_database_sha256,
        material_profile_id=bundle_material.material_profile_id,
        material_profile_sha256=bundle_material.material_profile_sha256,
        material_authority_sha256=bundle_material.material_authority_sha256,
        single_evidence_sha256=single.evidence_sha256,
        pair_evidence_sha256=pair.evidence_sha256,
        single_raw_sources_sha256=raw_sources.single_raw_sources_sha256,
        pair_raw_sources_sha256=raw_sources.pair_raw_sources_sha256,
        basis=common.basis,
        orientation=common.orientation,
        row_column_order="conductor_order",
        l_matrix_unit="H/m",
        c_matrix_unit="F/m",
        data_class=bundle_material.data_class,
        allowed_consumers=bundle_material.allowed_consumers,
        publication_state=bundle_material.publication_state,
        promotion_eligible=bundle_material.promotion_eligible,
    )
    normalized = _d3_q2d_normalize_authority_input((
        single_l_per_m_h=single.l_matrix[1, 1],
        single_c_per_m_f=single.c_matrix[1, 1],
        l_matrix_per_m_h=pair.l_matrix,
        c_matrix_per_m_f=pair.c_matrix,
        coupling_orientation=:same_direction,
        q2d_artifact_id=artifact_id,
        q2d_artifact_sha256=artifact_sha256,
        q2d_topology_id=:continuous_upper_ground,
        q2d_geometry_um=(
            w=pair.w,
            s=pair.s,
            d=pair.d,
            h=pair.h,
            upper_ground_clearance=pair.clearance,
            metal_thickness=common.metal_thickness_nm / 1000,
        ),
        q2d_single_case_id=single.case_id,
        q2d_pair_case_id=pair.case_id,
        q2d_solver=(
            adaptive_frequency_hz=extraction_frequency_hz,
            aedt_version=aedt_version,
            pyaedt_version=pyaedt_version,
        ),
        q2d_loss_model="lossless_R_equals_G_equals_zero",
        q2d_authority=authority,
    ))
    return D3Q2DAuthorityReceipt(normalized)
end

end
