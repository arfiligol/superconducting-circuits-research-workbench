using Test

const WORKBENCH_ROOT = normpath(joinpath(@__DIR__, "..", ".."))
include(joinpath(
    WORKBENCH_ROOT,
    "notebooks",
    "pluto",
    "D3 Intrinsic Purcell Filter Design",
    "d3_lc_qualification_receipt.jl",
))
using .D3LCQualificationReceipt
include(joinpath(
    WORKBENCH_ROOT,
    "notebooks",
    "pluto",
    "D3 Intrinsic Purcell Filter Design",
    "d3_stage_models.jl",
))
include(joinpath(
    WORKBENCH_ROOT,
    "notebooks",
    "pluto",
    "D3 Intrinsic Purcell Filter Design",
    "d3_coupled_optimizer.jl",
))
include(joinpath(
    WORKBENCH_ROOT,
    "notebooks",
    "pluto",
    "D3 Intrinsic Purcell Filter Design",
    "d3_stage2_result.jl",
))

function rejection_code(f)
    try
        f()
    catch exception
        @test exception isa D3LCReceiptNotEvaluable
        return exception.code
    end
    return nothing
end

function anchor_payload(observable, frequency_hz; step_change, residual=2.0e-3)
    root_rad_s = 2π * frequency_hz
    return Dict{String,Any}(
        "observable" => observable,
        "authoritative_midpoint_receipt" => Dict{String,Any}(),
        "construction_anchor_frequency_hz" => frequency_hz,
        "bracket_hz" => [frequency_hz - 10.0, frequency_hz + 10.0],
        "h_rad_s" => 1.0e-6 * root_rad_s,
        "samples" => Dict{String,Any}(),
        "root_value" => Dict{String,Any}(),
        "derivative_h" => Dict{String,Any}(),
        "derivative_h2" => Dict{String,Any}(),
        "derivative_step_relative_change" => step_change,
        "derivative_step_tolerance" => observable == "f_n" ? 5.0e-2 : 1.0e-3,
        "reactive_purity_relative" => 1.0e-7,
        "normalized_root_residual" => residual,
        "checks" => Dict(
            name => true for name in (
                "same_bracket",
                "midpoint_distance_hz",
                "stencil_inside_bracket",
                "finite_samples",
                "derivative_step_convergence",
                "reactive_purity",
                "normalized_root_residual",
            )
        ),
        "passed" => true,
        "root_rad_s" => root_rad_s,
        "derivative" => Dict{String,Any}(),
    )
end

function state_payload(frequencies)
    lc = Dict(
        "Cr_f" => 1.0,
        "Lr_h" => 2.0,
        "Cp_f" => 3.0,
        "Lp_h" => 4.0,
        "Cn_f" => 5.0,
        "Ln_h" => 6.0,
    )
    return Dict{String,Any}(
        "status" => "PASS",
        "state" => Dict{String,Any}(),
        "actual_grid" => Dict{String,Any}(),
        "identity_checks" => Dict{String,Any}(),
        "midpoint_receipts" => Dict{String,Any}(),
        "anchors" => Dict(
            "f_r" => anchor_payload("f_r", frequencies.f_r; step_change=1.0e-3),
            "f_p" => anchor_payload("f_p", frequencies.f_p; step_change=1.0e-3),
            "f_n" => anchor_payload("f_n", frequencies.f_n; step_change=5.0e-2),
        ),
        "pole_certificates" => Dict{String,Any}(),
        "physical_formulation" => Dict{String,Any}(),
        "bridge_inputs" => Dict{String,Any}(),
        "lc_readback" => lc,
        "checks" => Dict(
            name => true for name in (
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
        ),
    )
end

function comparison_payload(; diagonal=1.0e-3, notch=5.0e-2)
    derivative = Dict(
        "dY_r_domega" => diagonal,
        "dY_p_domega" => diagonal,
        "dZ21_domega" => notch,
        "Cn_star" => notch,
    )
    lc = Dict(
        "Cr_f" => diagonal,
        "Lr_h" => diagonal,
        "Cp_f" => diagonal,
        "Lp_h" => diagonal,
        "Cn_f" => notch,
        "Ln_h" => notch,
    )
    return Dict{String,Any}(
        "derivative_and_c_n_star_deltas_fraction" => derivative,
        "derivative_and_c_n_star_deltas_percent" => Dict{String,Any}(),
        "derivative_and_c_n_star_checks" => Dict(name => true for name in keys(derivative)),
        "lc_deltas_fraction" => lc,
        "lc_deltas_percent" => Dict{String,Any}(),
        "diagonal_lc_checks" => Dict(
            name => true for name in ("Cr_f", "Lr_h", "Cp_f", "Lp_h")
        ),
        "notch_lc_checks" => Dict(name => true for name in ("Cn_f", "Ln_h")),
        "passed" => true,
    )
end

@testset "D3 LC qualification receipt authority" begin
    policy = d3_lc_qualification_policy()
    @test policy["contract_id"] == D3_LC_QUALIFICATION_CONTRACT
    @test policy["schema_version"] == D3_LC_QUALIFICATION_SCHEMA
    @test policy["authority_mode"] == "exact_receipt_only"
    @test policy["accepted_receipt_sha256"] == D3_ACCEPTED_LC_RECEIPT_SHA256
    @test policy["accepted_receipt_candidate_scope"] ==
        "exact_historical_lengths_only"
    @test policy["accepted_receipt_numeric_u_idc_authority"] === false
    @test isnothing(policy["accepted_envelope"])
    @test policy["policy_sha256"] == D3_LC_QUALIFICATION_POLICY_SHA256

    thresholds = policy["thresholds"]
    @test thresholds["root_absolute_tolerance_hz"] == 1.25
    @test thresholds["normalized_root_residual"] == 2.0e-3
    @test thresholds["readout_frequency_relative"] == 1.0e-3
    @test thresholds["filter_frequency_relative"] == 1.0e-3
    @test thresholds["notch_frequency_relative"] == 1.0e-2
    @test thresholds["diagonal_derivative_step_relative"] == 1.0e-3
    @test thresholds["notch_derivative_step_relative"] == 5.0e-2
    @test thresholds["diagonal_extraction_relative"] == 1.0e-3
    @test thresholds["notch_extraction_relative"] == 5.0e-2

    thresholds["notch_frequency_relative"] = 1.0
    @test d3_lc_qualification_policy()["thresholds"]["notch_frequency_relative"] ==
        1.0e-2
    @test rejection_code(() -> validate_d3_lc_qualification_policy(policy)) ==
        "lc_receipt.stale"

    @test validate_d3_lc_qualification_receipt_identity(
        D3_ACCEPTED_LC_RECEIPT_SHA256,
    ) == D3_ACCEPTED_LC_RECEIPT_SHA256
    @test rejection_code(() -> validate_d3_lc_qualification_receipt_identity(
        nothing,
    )) == "lc_receipt.missing"
    @test rejection_code(() -> validate_d3_lc_qualification_receipt_identity(
        repeat("a", 64),
    )) == "lc_receipt.unaccepted_authority"
    @test rejection_code(() -> validate_d3_lc_qualification_receipt_identity(
        uppercase(D3_ACCEPTED_LC_RECEIPT_SHA256),
    )) == "lc_receipt.malformed"

    mktempdir() do directory
        missing_path = joinpath(directory, "missing.json")
        @test rejection_code(() -> load_d3_lc_qualification_receipt(missing_path)) ==
            "lc_receipt.missing"
    end

    mktemp() do path, io
        write(io, "{}")
        flush(io)
        @test rejection_code(() -> load_d3_lc_qualification_receipt(path)) ==
            "lc_receipt.unaccepted_authority"
    end

    candidate = (
        lr_open_m=1.0,
        lr_short_m=1.0,
        lc_m=1.0,
        lp_open_m=1.0,
        lp_short_m=1.0,
        u_IDC=1.0,
    )
    @test rejection_code(() -> authorize_d3_stage2_lc_receipt(
        nothing,
        candidate;
        q2d_artifact_sha256=repeat("a", 64),
    )) == "lc_receipt.missing"

    resonator_mapping = D3Stage2ResonatorMapping(
        nothing,
        nothing,
        (q2d_artifact_sha256=repeat("a", 64),),
        repeat("b", 64),
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
        repeat("c", 64),
        Dict{String,Any}(),
        Dict{String,Any}(),
    )
    @test rejection_code(() -> d3_stage2_equivalent_model(
        candidate,
        nothing,
        resonator_mapping,
        idc_mapping;
        lc_qualification_receipt=nothing,
    )) == "lc_receipt.missing"
    @test rejection_code(() -> D3Stage2Result.Stage2RunSpec(
        "receipt-gate-test",
        1.0,
        [1.0],
        [1.0],
        Dict{String,Any}(),
        repeat("a", 64),
        Dict{String,Any}(),
        Dict{String,Any}(),
    )) == "lc_receipt.unaccepted_authority"
end

@testset "D3 LC qualification hard gates" begin
    @test D3LCQualificationReceipt._anchor(
        anchor_payload("f_r", 6.0e9; step_change=1.0e-3),
        "f_r",
        1.0e-3,
    ).normalized_root_residual == 2.0e-3
    @test D3LCQualificationReceipt._anchor(
        anchor_payload("f_n", 5.0e9; step_change=5.0e-2),
        "f_n",
        5.0e-2,
    ).derivative_step_relative_change == 5.0e-2
    @test rejection_code(() -> D3LCQualificationReceipt._anchor(
        anchor_payload("f_r", 6.0e9; step_change=1.0001e-3),
        "f_r",
        1.0e-3,
    )) == "lc_receipt.failed_gate"
    @test rejection_code(() -> D3LCQualificationReceipt._anchor(
        anchor_payload("f_n", 5.0e9; step_change=5.0001e-2),
        "f_n",
        5.0e-2,
    )) == "lc_receipt.failed_gate"
    @test rejection_code(() -> D3LCQualificationReceipt._anchor(
        anchor_payload("f_r", 6.0e9; step_change=1.0e-3, residual=2.0001e-3),
        "f_r",
        1.0e-3,
    )) == "lc_receipt.failed_gate"

    operational = D3LCQualificationReceipt._state(
        state_payload((f_r=6.0e9, f_p=6.1e9, f_n=5.0e9)),
        "operational",
    )
    reference = D3LCQualificationReceipt._state(
        state_payload((f_r=6.006e9, f_p=6.1061e9, f_n=5.05e9)),
        "reference",
    )
    deltas = D3LCQualificationReceipt._comparison(
        comparison_payload(),
        operational,
        reference,
    )
    @test deltas.f_r ≈ 1.0e-3
    @test deltas.f_p ≈ 1.0e-3
    @test deltas.f_n ≈ 1.0e-2

    reference_outside = D3LCQualificationReceipt._state(
        state_payload((f_r=6.0061e9, f_p=6.1e9, f_n=5.0e9)),
        "reference",
    )
    @test rejection_code(() -> D3LCQualificationReceipt._comparison(
        comparison_payload(),
        operational,
        reference_outside,
    )) == "lc_receipt.failed_gate"
    @test rejection_code(() -> D3LCQualificationReceipt._comparison(
        comparison_payload(; diagonal=1.0001e-3),
        operational,
        operational,
    )) == "lc_receipt.failed_gate"
    @test rejection_code(() -> D3LCQualificationReceipt._comparison(
        comparison_payload(; notch=5.0001e-2),
        operational,
        operational,
    )) == "lc_receipt.failed_gate"
end
