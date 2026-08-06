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
include(joinpath(D3_SOURCE, "d3_full_qrp_qualification_receipt.jl"))
using .D3FullQRPQualificationReceipt
include(joinpath(D3_SOURCE, "d3_stage_models.jl"))
include(joinpath(D3_SOURCE, "d3_coupled_optimizer.jl"))
include(joinpath(D3_SOURCE, "d3_stage2_result.jl"))

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

function full_qrp_foundation(candidate_value, lc_authorization)
    model_identity = (
        circuit_plan_sha256=HASH_A,
        capacitance_sha256=HASH_B,
        inverse_inductance_sha256=HASH_C,
        selector_sha256=HASH_D,
    )
    gate_policy = (
        maximum_elimination_condition_number=1.0e12,
        maximum_relative_elimination_solve_residual=1.0e-9,
        maximum_relative_reciprocity_error=1.0e-9,
        maximum_relative_passivity_violation=1.0e-12,
        maximum_relative_root_residual=1.0e-9,
        maximum_root_growth_rate_hz=0.0,
        minimum_normalized_residue_slope=1.0e-9,
        maximum_relative_coupling_spread=0.1,
        maximum_relative_determinant_closure_error=1.0e-9,
    )
    effective = (
        contract_id="d3-q-feedline-downfolded-rp-effective-operator.v1",
        coupling_state=:qrp_on,
        external_port_state=:matched_open,
        retained_coordinates=[:r, :p],
        eliminated_coordinates=[:q, :f1, :fc, :f2],
        gate_policy=gate_policy,
        source_model_identity=model_identity,
        context_validation=(passed=true,),
        readout=(frequency_hz=6.0e9,),
        filter=(frequency_hz=6.0e9,),
        coherent_exchange_hz=5.0e6,
        determinant_closure=(relative_error=0.0,),
        provenance=(contract=:existing,),
    )
    notch = (
        quantity=:f_n_rp_on,
        frequency_hz=5.0e9,
        frequency_bracket_hz=[4.9e9, 5.1e9],
        frequency_tolerance_hz=1.0e3,
        residual_tolerances_ohm=(real=0.01, imag=0.01, complex=0.01),
        residual_gates=(real=true, imag=true, complex=true),
        provenance=(
            contract_id="d3-intrinsic-pair-rp-on-z21-zero.v1",
            circuit_plan_sha256=HASH_A,
            coupling_state=:rp_on,
        ),
    )
    identity = (
        contract_id="d3-exact-open-qrp-identity-continuation.v1",
        identities=(:q, :r, :p),
        assignment=(
            minimum_selected_overlap=0.9,
            minimum_overlap=0.8,
            assignment_margin=0.2,
            minimum_assignment_margin=0.1,
        ),
        energy_metric=(matrix_sha256=HASH_A,),
        references=(construction="bare",),
        provenance=(
            identity_rule=:global_normalized_stored_energy_overlap,
            frequency_rank_assignment=:forbidden,
            source_model_identity=model_identity,
            exact_open_generator_sha256=HASH_B,
        ),
    )
    linewidth = (
        linewidth_hz=20.0e6,
        per_identity_linewidth_hz=(q=0.0, r=10.0e6, p=10.0e6),
        eta_r=0.5,
        eta_p=0.5,
        provenance=(
            contract_id="d3-linewidth-lc-identity-continued-qrp-sum.v1",
            pole_scope=:qrp_three,
            frequency_rank_assignment=:forbidden,
        ),
    )
    metrics = merge(model_identity, (
        fr_eff_q_feedline_downfolded_qrp_on_ext_on_hz=6.0e9,
        fp_eff_q_feedline_downfolded_qrp_on_ext_on_hz=6.0e9,
        J_rp_eff_q_feedline_downfolded_coherent_hz=5.0e6,
        notch_rp_on_hz=5.0e9,
        kappa_sum_qrp_on_ext_on_hz=20.0e6,
        eta_r_qrp_on=0.5,
        eta_p_qrp_on=0.5,
        effective_diagonal_frequency_extraction=
            :q_feedline_downfolded_rp_complex_operator,
        effective_exchange_extraction=
            :q_feedline_downfolded_rp_complex_midpoint_residue,
        notch_authority=:rp_on,
        linewidth_pole_scope=:qrp_three,
        primary_linewidth_extraction=:L_C,
    ))
    return (
        contract_id="d3-stage2-candidate-foundation.v5",
        stage_id=:stage2_equivalent,
        model_family=:equivalent_exact_n,
        objective_ready=true,
        stage=(candidate=candidate_value, lc_qualification=lc_authorization),
        cqed_handoff=(source_model_identity=model_identity,),
        metrics=metrics,
        extractions=(
            effective_rp=effective,
            notch=notch,
            identity_continuation=identity,
            linewidth_lc=linewidth,
        ),
    )
end

@testset "D3 Full-QRP qualification before objective" begin
    lc_evidence = produce_d3_candidate_lc_evidence(
        candidate(), source_identity(); state_evaluator=state_evaluator,
        lc_evaluator=lc_evaluator,
    )
    mktempdir() do directory
        lc_receipt = write_d3_lc_qualification_receipt(
            joinpath(directory, "lc.json"),
            lc_evidence,
        )
        lc_authorization = authorize_d3_stage2_lc_receipt(
            lc_receipt,
            candidate();
            q2d_artifact_sha256=source_identity()["q2d_artifact_sha256"],
        )
        foundation = full_qrp_foundation(candidate(), lc_authorization)
        full_evidence = produce_d3_full_qrp_qualification_evidence(
            foundation,
            candidate(),
            lc_authorization;
            q2d_artifact_sha256=source_identity()["q2d_artifact_sha256"],
        )
        @test full_evidence["objective_target_gates_evaluated"] === false
        full_receipt = write_d3_full_qrp_qualification_receipt(
            joinpath(directory, "full-qrp.json"),
            full_evidence,
        )
        full_authorization = authorize_d3_stage2_full_qrp_receipt(
            full_receipt,
            foundation,
            candidate(),
            lc_authorization;
            q2d_artifact_sha256=source_identity()["q2d_artifact_sha256"],
        )
        calls = Ref(0)
        objective = evaluate_d3_stage2_objective_with_evidence(
            full_authorization,
            foundation,
            candidate(),
            lc_authorization;
            q2d_artifact_sha256=source_identity()["q2d_artifact_sha256"],
            objective_evaluator=(foundation, qualification) -> begin
                calls[] += 1
                (cost=0.0, receipt=d3_full_qrp_qualification_receipt_identity(qualification))
            end,
        )
        @test calls[] == 1
        @test objective.cost == 0.0
        @test objective.receipt.receipt_sha256 == full_receipt.sha256

        changed_foundation = merge(foundation, (
            metrics=merge(foundation.metrics, (notch_rp_on_hz=5.1e9,)),
        ))
        @test rejection_code(
            () -> evaluate_d3_stage2_objective_with_evidence(
                full_authorization,
                changed_foundation,
                candidate(),
                lc_authorization;
                q2d_artifact_sha256=source_identity()["q2d_artifact_sha256"],
                objective_evaluator=(foundation, qualification) -> begin
                    calls[] += 1
                    nothing
                end,
            ),
            D3FullQRPReceiptNotEvaluable,
        ) == "full_qrp_receipt.operand_mismatch"
        @test calls[] == 1

        mismatched_notch = merge(foundation.extractions.notch, (
            provenance=merge(
                foundation.extractions.notch.provenance,
                (circuit_plan_sha256=HASH_B,),
            ),
        ))
        mismatched_foundation = merge(foundation, (
            extractions=merge(foundation.extractions, (notch=mismatched_notch,)),
        ))
        @test rejection_code(
            () -> produce_d3_full_qrp_qualification_evidence(
                mismatched_foundation,
                candidate(),
                lc_authorization;
                q2d_artifact_sha256=source_identity()["q2d_artifact_sha256"],
            ),
            D3FullQRPReceiptNotEvaluable,
        ) == "full_qrp_receipt.model_mismatch"

        @test rejection_code(
            () -> authorize_d3_stage2_full_qrp_receipt(
                nothing,
                foundation,
                candidate(),
                lc_authorization;
                q2d_artifact_sha256=source_identity()["q2d_artifact_sha256"],
            ),
            D3FullQRPReceiptNotEvaluable,
        ) == "full_qrp_receipt.missing"
    end
end

@testset "D3 Stage-2 current evidence policies" begin
    @test rejection_code(
        () -> authorize_d3_stage2_lc_receipt(
            nothing,
            candidate();
            q2d_artifact_sha256=source_identity()["q2d_artifact_sha256"],
        ),
        D3LCReceiptNotEvaluable,
    ) == "lc_receipt.missing"

    resonator_mapping = D3Stage2ResonatorMapping(
        nothing,
        nothing,
        (q2d_artifact_sha256=source_identity()["q2d_artifact_sha256"],),
        HASH_A,
    )
    idc_mapping = D3IDCInput.D3IDCMapping(
        0.0,
        (0.0, 0.0),
        (0.0, 0.0),
        0.0,
        0.0,
        Dict{String,Vector{Float64}}(),
        Dict{Tuple{Float64,Float64},NamedTuple}(),
        "invalid-test-mapping",
        HASH_A,
        Dict{String,Any}(),
        Dict{String,Any}(),
    )
    @test rejection_code(
        () -> d3_stage2_equivalent_model(
            candidate(),
            nothing,
            resonator_mapping,
            idc_mapping;
            lc_qualification_receipt=nothing,
        ),
        D3LCReceiptNotEvaluable,
    ) == "lc_receipt.missing"

    @test_throws ErrorException D3Stage2Result.Stage2RunSpec(
        "policy-gate",
        6.0e9,
        [6.0e9],
        [6.0e9],
        Dict{String,Any}(),
        HASH_A,
        D3_FULL_QRP_QUALIFICATION_POLICY_SHA256,
        Dict{String,Any}(),
        Dict{String,Any}(),
    )
end
