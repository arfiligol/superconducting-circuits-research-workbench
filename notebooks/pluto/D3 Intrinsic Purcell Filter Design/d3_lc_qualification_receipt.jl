# Strict current-authority validator for D3 Rev10 exact-candidate LC receipts.
# The historical v1 singleton remains immutable evidence in Git/artifacts but
# is deliberately not a reachable Stage-2 authorization fallback.

isdefined(@__MODULE__, :D3CandidateLCProducer) ||
    include(joinpath(@__DIR__, "d3_candidate_lc_producer.jl"))

module D3LCQualificationReceipt

using SHA
using SuperconductingCircuitsCore
using ..D3CandidateLCProducer: D3CandidateLCNotEvaluable,
    D3_CANDIDATE_LC_CONTRACT,
    D3_CANDIDATE_LC_POLICY_SHA256,
    D3_CANDIDATE_LC_SCHEMA,
    d3_candidate_lc_policy,
    d3_candidate_wrapper_identity,
    validate_d3_candidate_lc_evidence

const JSON3 = SuperconductingCircuitsCore.JSON3
const D3_LC_QUALIFICATION_SCHEMA = D3_CANDIDATE_LC_SCHEMA
const D3_LC_QUALIFICATION_CONTRACT = D3_CANDIDATE_LC_CONTRACT
const D3_LC_QUALIFICATION_POLICY_SHA256 = D3_CANDIDATE_LC_POLICY_SHA256

export D3LCQualificationReceipt,
    D3LCReceiptNotEvaluable,
    D3AuthorizedStage2LC,
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
    validate_d3_stage2_lc_authorization_match,
    write_d3_lc_qualification_receipt

struct D3LCReceiptNotEvaluable <: Exception
    code::String
    reason::String
    details
end

Base.showerror(io::IO, exception::D3LCReceiptNotEvaluable) = print(
    io,
    "D3 LC receipt NOT_EVALUABLE [",
    exception.code,
    "]: ",
    exception.reason,
)

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

_fail(code, reason, details=nothing) =
    throw(D3LCReceiptNotEvaluable(String(code), String(reason), details))

function _translate(f)
    try
        return f()
    catch exception
        exception isa InterruptException && rethrow()
        exception isa D3LCReceiptNotEvaluable && rethrow()
        exception isa D3CandidateLCNotEvaluable || rethrow()
        _fail(exception.code, exception.reason, exception.details)
    end
end

function _sha256(value, label)
    value isa AbstractString ||
        _fail("lc_receipt.malformed", "$(label) must be text.")
    result = strip(String(value))
    result == lowercase(result) && occursin(r"^[0-9a-f]{64}$", result) ||
        _fail("lc_receipt.malformed", "$(label) must be lowercase SHA-256.")
    return result
end

function _real(value, label; positive=false)
    value isa Real && !(value isa Bool) ||
        _fail("lc_receipt.malformed", "$(label) must be numeric.")
    parsed = Float64(value)
    isfinite(parsed) || _fail("lc_receipt.malformed", "$(label) must be finite.")
    positive && parsed <= 0 &&
        _fail("lc_receipt.malformed", "$(label) must be positive.")
    return parsed
end

function _candidate_values(candidate)
    names = (:lr_open_m, :lr_short_m, :lc_m, :lp_open_m, :lp_short_m, :u_IDC)
    Set(propertynames(candidate)) == Set(names) || _fail(
        "lc_receipt.candidate_mismatch",
        "Stage-2 candidate fields do not match the physical Rev10 coordinates.",
    )
    return NamedTuple{names}(Tuple(
        _real(getproperty(candidate, name), "Stage-2 candidate $(name)"; positive=true)
        for name in names
    ))
end

function _mapping(value, label)
    value isa AbstractDict ||
        _fail("lc_receipt.malformed", "$(label) must be a mapping.")
    return Dict{String,Any}(String(key) => item for (key, item) in pairs(value))
end

function _normalize(payload)
    validated = _translate(() -> validate_d3_candidate_lc_evidence(payload))
    raw = _mapping(payload, "D3 LC receipt")
    candidate = validated.candidate
    candidate_identity = d3_candidate_wrapper_identity(candidate)
    lengths = (
        lr_open_m=candidate.lr_open_m,
        lr_short_m=candidate.lr_short_m,
        lc_m=candidate.lc_m,
        lp_open_m=candidate.lp_open_m,
        lp_short_m=candidate.lp_short_m,
    )
    joint = _mapping(raw["joint_comparison"], "joint comparison")
    changes = _mapping(joint["changes"], "joint frequency changes")
    frequency_deltas = (
        f_r=_real(_mapping(changes["f_r"], "f_r change")["delta_fraction"], "f_r delta"),
        f_p=_real(_mapping(changes["f_p"], "f_p change")["delta_fraction"], "f_p delta"),
        f_n=_real(_mapping(changes["f_n"], "f_n change")["delta_fraction"], "f_n delta"),
    )
    return (
        schema_version=D3_LC_QUALIFICATION_SCHEMA,
        evidence_id="d3-rev10-candidate-lc-$(candidate_identity.sha256)",
        contract_id=D3_LC_QUALIFICATION_CONTRACT,
        policy_sha256=D3_LC_QUALIFICATION_POLICY_SHA256,
        semantic_receipt_sha256=validated.semantic_receipt_sha256,
        candidate=(
            id=candidate_identity.sha256,
            lengths=lengths,
            u_IDC=candidate.u_IDC,
        ),
        source=validated.source,
        physics_sha256=validated.physics_sha256,
        frequency_deltas=frequency_deltas,
        lc_readback=validated.lc_readback,
    )
end

d3_lc_qualification_policy() = d3_candidate_lc_policy()

function validate_d3_lc_qualification_policy(value)
    value == d3_lc_qualification_policy() || _fail(
        "lc_receipt.stale",
        "D3 LC qualification policy differs from the current accepted producer policy.",
    )
    return d3_lc_qualification_policy()
end

function validate_d3_lc_qualification_receipt_identity(value)
    isnothing(value) && _fail(
        "lc_receipt.missing",
        "LC qualification receipt identity is missing.",
    )
    return _sha256(value, "LC qualification receipt identity")
end

function d3_lc_qualification_receipt_identity(receipt::D3LCQualificationReceipt)
    return (
        schema_version=receipt.normalized.schema_version,
        evidence_id=receipt.normalized.evidence_id,
        receipt_sha256=receipt.sha256,
        semantic_receipt_sha256=receipt.normalized.semantic_receipt_sha256,
        contract_id=D3_LC_QUALIFICATION_CONTRACT,
        policy_sha256=D3_LC_QUALIFICATION_POLICY_SHA256,
        candidate_id=receipt.normalized.candidate.id,
        candidate=receipt.normalized.candidate,
        physics_sha256=receipt.normalized.physics_sha256,
        source=receipt.normalized.source,
        frequency_deltas=receipt.normalized.frequency_deltas,
    )
end

d3_lc_qualification_receipt_identity(authorization::D3AuthorizedStage2LC) =
    d3_lc_qualification_receipt_identity(authorization.receipt)

function _read_payload(path)
    bytes = read(path)
    payload = try
        JSON3.read(String(copy(bytes)), Dict{String,Any})
    catch exception
        _fail(
            "lc_receipt.malformed",
            "D3 LC qualification receipt is not valid JSON.",
            (exception=sprint(showerror, exception),),
        )
    end
    return bytes, payload
end

function load_d3_lc_qualification_receipt(path)
    input_path = abspath(String(path))
    isfile(input_path) || _fail(
        "lc_receipt.missing",
        "D3 LC qualification receipt does not exist.",
        (path=input_path,),
    )
    bytes, payload = _read_payload(input_path)
    raw = _mapping(payload, "D3 LC receipt")
    get(raw, "schema_version", nothing) == D3_LC_QUALIFICATION_SCHEMA || _fail(
        "lc_receipt.superseded_schema",
        "Only current v2 exact-candidate LC receipts are reachable; v1 is historical evidence only.",
    )
    return D3LCQualificationReceipt(
        input_path,
        bytes2hex(SHA.sha256(bytes)),
        _normalize(payload),
    )
end

function write_d3_lc_qualification_receipt(path, evidence)
    destination = abspath(String(path))
    ispath(destination) && _fail(
        "lc_receipt.exists",
        "LC receipt destination already exists.",
        (path=destination,),
    )
    _normalize(evidence)
    parent = dirname(destination)
    mkpath(parent)
    temporary, io = mktemp(parent; cleanup=false)
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
    return load_d3_lc_qualification_receipt(destination)
end

function _validate_receipt_authority(receipt::D3LCQualificationReceipt)
    isfile(receipt.path) || _fail(
        "lc_receipt.missing",
        "D3 LC qualification receipt disappeared after validation.",
    )
    bytes, payload = _read_payload(receipt.path)
    bytes2hex(SHA.sha256(bytes)) == receipt.sha256 || _fail(
        "lc_receipt.stale",
        "D3 LC qualification receipt bytes changed after validation.",
    )
    _normalize(payload) == receipt.normalized || _fail(
        "lc_receipt.stale",
        "In-memory LC qualification disagrees with its current bytes.",
    )
    return receipt
end

function authorize_d3_stage2_lc_receipt(
    receipt::D3LCQualificationReceipt,
    candidate;
    q2d_artifact_sha256,
    expected_receipt_sha256=nothing,
)
    _validate_receipt_authority(receipt)
    if !isnothing(expected_receipt_sha256)
        receipt.sha256 == validate_d3_lc_qualification_receipt_identity(
            expected_receipt_sha256,
        ) || _fail(
            "lc_receipt.run_spec_mismatch",
            "LC receipt differs from the expected exact identity.",
        )
    end
    values = _candidate_values(candidate)
    expected = receipt.normalized.candidate
    expected.lengths == NamedTuple{propertynames(expected.lengths)}(Tuple(
        getproperty(values, name) for name in propertynames(expected.lengths)
    )) && expected.u_IDC == values.u_IDC || _fail(
        "lc_receipt.candidate_mismatch",
        "LC receipt belongs to a different exact candidate.",
    )
    _sha256(q2d_artifact_sha256, "Stage-2 Q2D artifact SHA-256") ==
        receipt.normalized.source["q2d_artifact_sha256"] || _fail(
        "lc_receipt.q2d_mismatch",
        "LC receipt belongs to a different Q2D artifact.",
    )
    return D3AuthorizedStage2LC(receipt, values, receipt.normalized.lc_readback)
end

function authorize_d3_stage2_lc_receipt(
    ::Nothing,
    candidate;
    q2d_artifact_sha256,
    expected_receipt_sha256=nothing,
)
    _fail("lc_receipt.missing", "Stage-2 candidate has no LC qualification receipt.")
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
    renewed.candidate == authorization.candidate &&
        renewed.lc_readback == authorization.lc_readback || _fail(
        "lc_receipt.stale",
        "Authorized LC evidence changed during revalidation.",
    )
    return renewed
end

function validate_d3_stage2_lc_authorization_match(
    left::D3AuthorizedStage2LC,
    right::D3AuthorizedStage2LC,
)
    d3_lc_qualification_receipt_identity(left) ==
        d3_lc_qualification_receipt_identity(right) &&
        left.candidate == right.candidate && left.lc_readback == right.lc_readback || _fail(
            "lc_receipt.foundation_mismatch",
            "Stage-2 foundation LC binding differs from the candidate authority.",
        )
    return left
end

end
