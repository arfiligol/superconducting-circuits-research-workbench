using Test

const WORKBENCH_ROOT = normpath(joinpath(@__DIR__, "..", ".."))
const D3_SOURCE = joinpath(
    WORKBENCH_ROOT,
    "notebooks",
    "pluto",
    "D3 Intrinsic Purcell Filter Design",
)

include(joinpath(D3_SOURCE, "d3_lc_qualification_receipt.jl"))
using .D3CandidateLCProducer
using .D3LCQualificationReceipt

const HASH_A = repeat("a", 64)
const HASH_B = repeat("b", 64)
const HASH_C = repeat("c", 64)
const HASH_D = repeat("d", 64)

candidate(u_idc=50.0) = (
    lr_open_m=1.90530e-3,
    lr_short_m=3.04226e-3,
    lc_m=0.17605e-3,
    lp_open_m=2.58184e-3,
    lp_short_m=2.20526e-3,
    u_IDC=Float64(u_idc),
)

source_identity() = Dict{String,Any}(
    "workbench_revision" => repeat("1", 40),
    "orpen_revision" => "80576910d596dbf4720335188e66b6a520cc2e36",
    "q2d_artifact_sha256" =>
        "301d3501a30614b994cf3f28d46eb75b545620a164bbb346fa557120d643fe6c",
    "q2d_payload_sha256" => HASH_A,
    "q2d_result_sha256" => HASH_B,
    "material_profile_id" => "w7-s6-d3-h8-v4",
    "material_profile_sha256" => HASH_C,
    "material_authority_sha256" => HASH_D,
    "extractor_sha256" => HASH_A,
    "discretizer_sha256" => HASH_B,
    "state_evaluator_sha256" => HASH_C,
)

const STATE_CHECKS = (
    finite_values=true,
    root_existence=true,
    unique_signed_branches=true,
    pole_exclusion=true,
    matrix_passivity_positive_energy=true,
    breakpoint_basis_terminal_identity=true,
    schur_full_node_formulation=true,
)
const LC_CHECKS = (
    identity=true,
    anchor_and_derivative=true,
    diagonal_poles=true,
    physical_pole=true,
    physical_formulations=true,
    y_r_at_notch_purity=true,
    y_p_at_notch_purity=true,
    c_n_star_purity=true,
    z21_real_residual=true,
    z21_imag_residual=true,
    z21_abs_residual=true,
    positive_finite_lc=true,
    no_free_fit=true,
)

function state_evaluator(candidate, state)
    hasproperty(candidate, :u_IDC) &&
        error("Local state evaluator must not receive the wrapper-only u_IDC coordinate.")
    return (
        status="PASS",
        values_hz=(f_r=6.0e9, f_p=6.0e9, f_n=5.0e9),
        checks=STATE_CHECKS,
        evidence=(state_id=state.id,),
    )
end
function lc_evaluator(candidate, state)
    hasproperty(candidate, :u_IDC) &&
        error("Local LC evaluator must not receive the wrapper-only u_IDC coordinate.")
    root(name, frequency) = (
        frequency_hz=frequency,
        absolute_error_hz=1.25,
        normalized_residual=2.0e-3,
        derivative_step_relative_change=name == :f_n ? 5.0e-2 : 1.0e-3,
    )
    return (
        status="PASS",
        roots=(f_r=root(:f_r, 6.0e9), f_p=root(:f_p, 6.0e9), f_n=root(:f_n, 5.0e9)),
        derivatives=(
            dY_r_domega=1.0 + 0im,
            dY_p_domega=2.0 + 0im,
            dZ21_domega=3.0 + 0im,
            Cn_star=4.0 + 0im,
        ),
        lc_readback=(Cr_f=1.0, Lr_h=2.0, Cp_f=3.0, Lp_h=4.0, Cn_f=5.0, Ln_h=6.0),
        checks=LC_CHECKS,
        evidence=(state_id=state.state.id,),
    )
end

function worst_case_state_evaluator(candidate, state)
    frequency = if occursin("joint-reference", state.origin)
        6.3e9
    else
        matched = match(r"-(\d+)$", state.origin)
        isnothing(matched) && error("Missing refinement level in test state origin.")
        level = parse(Int, only(matched.captures))
        6.0e9 * (1 + 0.01 * min(level, 8))
    end
    return (
        status="PASS",
        values_hz=(f_r=frequency, f_p=frequency, f_n=5.0e9),
        checks=STATE_CHECKS,
        evidence=(state_id=state.id,),
    )
end

function rejection_code(f, expected_type)
    try
        f()
    catch exception
        @test exception isa expected_type
        return exception.code
    end
    return nothing
end

@testset "D3 exact-candidate LC producer and cache" begin
    policy = d3_candidate_lc_policy()
    @test policy["schema_version"] == "d3-root-derivative-lc-readback.v2"
    @test policy["accepted_envelope"] === nothing
    @test policy["controller"]["maximum_level_index"] == 10
    @test policy["controller"]["maximum_rounds"] == 3
    @test policy["controller"]["maximum_state_requests"] == 102

    first = d3_candidate_wrapper_identity(candidate(50.0))
    second = d3_candidate_wrapper_identity(candidate(51.0))
    @test first.sha256 != second.sha256
    @test d3_local_lc_physics_identity(candidate(50.0), source_identity()).sha256 ==
        d3_local_lc_physics_identity(candidate(51.0), source_identity()).sha256

    cache = Dict{String,Any}()
    evidence_50 = produce_d3_candidate_lc_evidence(
        candidate(50.0),
        source_identity();
        state_evaluator=state_evaluator,
        lc_evaluator=lc_evaluator,
        cache=cache,
    )
    @test evidence_50["final_status"] == "PASS"
    @test evidence_50["controller"]["state_requests"] == 10
    @test evidence_50["controller"]["state_solves"] == 8
    @test evidence_50["controller"]["cache_hits"] == 2
    @test evidence_50["controller"]["rounds"][1]["round"] == 1
    @test evidence_50["operational_lc_tuple"]["Ln_h"] == 6.0

    evidence_51 = produce_d3_candidate_lc_evidence(
        candidate(51.0),
        source_identity();
        state_evaluator=state_evaluator,
        lc_evaluator=lc_evaluator,
        cache=cache,
    )
    @test evidence_50["physics_sha256"] == evidence_51["physics_sha256"]
    @test evidence_50["candidate"]["candidate_sha256"] !=
        evidence_51["candidate"]["candidate_sha256"]
    @test evidence_51["controller"]["state_solves"] == 0
    @test evidence_51["controller"]["cache_hits"] == 10

    changed_source = source_identity()
    changed_source["state_evaluator_sha256"] = HASH_D
    changed_evidence = produce_d3_candidate_lc_evidence(
        candidate(51.0),
        changed_source;
        state_evaluator=state_evaluator,
        lc_evaluator=lc_evaluator,
        cache=cache,
    )
    @test changed_evidence["physics_sha256"] != evidence_51["physics_sha256"]
    @test changed_evidence["controller"]["state_solves"] == 8
    @test changed_evidence["controller"]["cache_hits"] == 2

    @test rejection_code(
        () -> produce_d3_candidate_lc_evidence(
            candidate(),
            source_identity();
            state_evaluator=worst_case_state_evaluator,
            lc_evaluator=lc_evaluator,
        ),
        D3CandidateLCNotEvaluable,
    ) == "lc_producer.round_cap"

    @test rejection_code(
        () -> produce_d3_candidate_lc_evidence(
            candidate(),
            source_identity();
            state_evaluator=state_evaluator,
            lc_evaluator=(candidate, state) -> error("LC backend unavailable"),
        ),
        D3CandidateLCNotEvaluable,
    ) == "lc_producer.lc_evaluator"
end

@testset "D3 LC receipt strict current authority" begin
    evidence = produce_d3_candidate_lc_evidence(
        candidate(),
        source_identity();
        state_evaluator=state_evaluator,
        lc_evaluator=lc_evaluator,
    )
    mktempdir() do directory
        path = joinpath(directory, "lc.json")
        receipt = write_d3_lc_qualification_receipt(path, evidence)
        @test receipt.normalized.schema_version == D3_LC_QUALIFICATION_SCHEMA
        @test receipt.normalized.candidate.u_IDC == 50.0
        authorization = authorize_d3_stage2_lc_receipt(
            receipt,
            candidate();
            q2d_artifact_sha256=source_identity()["q2d_artifact_sha256"],
        )
        @test authorization.lc_readback.Ln_h == 6.0
        @test d3_lc_qualification_receipt_identity(authorization).receipt_sha256 ==
            receipt.sha256
        @test rejection_code(
            () -> authorize_d3_stage2_lc_receipt(
                receipt,
                candidate(51.0);
                q2d_artifact_sha256=source_identity()["q2d_artifact_sha256"],
            ),
            D3LCReceiptNotEvaluable,
        ) == "lc_receipt.candidate_mismatch"

        open(path, "a") do io
            write(io, " ")
        end
        @test rejection_code(
            () -> revalidate_d3_stage2_lc_receipt(
                authorization,
                candidate();
                q2d_artifact_sha256=source_identity()["q2d_artifact_sha256"],
            ),
            D3LCReceiptNotEvaluable,
        ) == "lc_receipt.stale"
    end

    mktempdir() do directory
        historical = joinpath(directory, "v1.json")
        open(historical, "w") do io
            write(io, "{\"schema_version\":\"d3-root-derivative-lc-readback.v1\"}")
        end
        @test rejection_code(
            () -> load_d3_lc_qualification_receipt(historical),
            D3LCReceiptNotEvaluable,
        ) == "lc_receipt.superseded_schema"
    end

    tampered = deepcopy(evidence)
    tampered["candidate"]["u_IDC"] = 52.0
    @test rejection_code(
        () -> validate_d3_candidate_lc_evidence(tampered),
        D3CandidateLCNotEvaluable,
    ) == "lc_producer.stale"

    rescheduled = deepcopy(evidence)
    records = rescheduled["controller"]["rounds"][1]["mtl"]["records"]
    records[1] = deepcopy(records[2])
    core = copy(rescheduled)
    delete!(core, "semantic_receipt_sha256")
    rescheduled["semantic_receipt_sha256"] =
        D3CandidateLCProducer.semantic_value_sha256(core)
    @test rejection_code(
        () -> validate_d3_candidate_lc_evidence(rescheduled),
        D3CandidateLCNotEvaluable,
    ) == "lc_producer.controller"
end
