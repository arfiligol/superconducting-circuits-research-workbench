using Test
using SHA
using SuperconductingCircuitsCore

const WORKBENCH_ROOT = normpath(joinpath(@__DIR__, "..", ".."))
const D3_SOURCE = joinpath(
    WORKBENCH_ROOT,
    "notebooks",
    "pluto",
    "D3 Intrinsic Purcell Filter Design",
)
const JSON3 = SuperconductingCircuitsCore.JSON3

include(joinpath(D3_SOURCE, "d3_stage_models.jl"))
include(joinpath(D3_SOURCE, "d3_stage_objectives.jl"))
include(joinpath(D3_SOURCE, "d3_direct_hybridized_spatial_receipt.jl"))
using .D3DirectHybridizedSpatialReceipt

const HASH_A = repeat("a", 64)
const HASH_B = repeat("b", 64)
const HASH_C = repeat("c", 64)
const HASH_D = repeat("d", 64)

candidate(u_idc=60.0e-6) = (
    lr_open_m=1.0e-3,
    lr_short_m=1.0e-3,
    lc_m=0.32e-3,
    lp_open_m=1.0e-3,
    lp_short_m=1.0e-3,
    u_IDC=Float64(u_idc),
)

gate_policy() = (
    maximum_elimination_condition_number=1.0e12,
    maximum_relative_elimination_solve_residual=1.0e-8,
    maximum_relative_reciprocity_error=1.0e-10,
    maximum_relative_passivity_violation=1.0e-10,
    maximum_relative_root_residual=1.0e-8,
    maximum_root_growth_rate_hz=1.0,
    minimum_normalized_residue_slope=1.0e-15,
    maximum_relative_coupling_spread=1.0e-3,
    maximum_relative_determinant_closure_error=1.0e-8,
)

extraction_profile() = (
    readout_effective_root_band_hz=(5.55e9, 5.65e9),
    filter_effective_root_band_hz=(5.55e9, 5.65e9),
    effective_operator_gate_policy=gate_policy(),
    notch_frequency_bracket_hz=(4.75e9, 5.25e9),
    minimum_q_reference_overlap=0.50,
    minimum_each_rp_subspace_overlap=0.50,
    minimum_unordered_set_assignment_margin=0.05,
    complement=:complete_hybridized_complement,
)

objective_authority() = d3_direct_hybridized_objective_authority(
    D3_HUMAN_APPROVED_OBJECTIVE_AUTHORITY,
)

function fixed_input_identity()
    core = (
        contract_id="d3-rev10-direct-hybridized-fixed-input.v1",
        q2d=(
            artifact_id="d3-q2d-v4",
            artifact_sha256=HASH_A,
            topology_id="d3-continuous-ground",
            geometry_um=(gap=8.0,),
            section_length_m=50.0e-6,
            mtl_section_length_m=10.0e-6,
        ),
        q3d=(input_sha256=HASH_B, model_id="q3d", capacitance_source_id="q3d-source"),
        idc=(mapping_id="idc", mapping_sha256=HASH_C, source_artifact="idc.json"),
        feedline=(
            feedline_length_m=2.0e-3,
            feedline_n_sections=64,
            feedline_l_per_m_h=4.0e-7,
            feedline_c_per_m_f=1.6e-10,
            port_resistance_ohm=50.0,
        ),
    )
    return merge(core, (canonical_sha256=bytes2hex(SHA.sha256(codeunits(JSON3.write(core)))),))
end

function grid_parts(level; malformed_count=false)
    multiplier = 1 << level
    counts = (
        readout_resonator=64 * multiplier,
        filter_resonator=64 * multiplier,
        mtl=(malformed_count ? 32 * multiplier + 1 : 32 * multiplier),
        feedline_left=32 * multiplier,
        feedline_right=32 * multiplier,
    )
    boundaries = (
        readout_resonator_boundaries_m=collect(range(0.0, 2.32e-3; length=counts.readout_resonator + 1)),
        filter_resonator_boundaries_m=collect(range(0.0, 2.32e-3; length=counts.filter_resonator + 1)),
        feedline_left_boundaries_m=collect(range(0.0, 1.0e-3; length=counts.feedline_left + 1)),
        feedline_right_boundaries_m=collect(range(0.0, 1.0e-3; length=counts.feedline_right + 1)),
    )
    return (counts=counts, boundaries_m=boundaries)
end

function grid_plan_sha256(level, parts)
    payload = (
        contract_id="d3-rev10-direct-hybridized-grid-plan.v1",
        refinement_level=level,
        candidate=candidate(),
        fixed_input_canonical_sha256=fixed_input_identity().canonical_sha256,
        counts=parts.counts,
        boundaries_m=parts.boundaries_m,
    )
    return bytes2hex(SHA.sha256(codeunits(JSON3.write(payload))))
end

function grid_identity(level; malformed_count=false)
    parts = grid_parts(level; malformed_count=malformed_count)
    return (
        counts=parts.counts,
        boundaries_m=parts.boundaries_m,
        canonical_sha256=bytes2hex(SHA.sha256(codeunits(JSON3.write(parts)))),
        refinement_level=level,
        requested_plan_sha256=grid_plan_sha256(level, parts),
    )
end

direct_inputs() = D3DirectHybridizedInputs(
    nothing,
    nothing,
    nothing,
    nothing,
    fixed_input_identity(),
)

function grid_plan(level; malformed_count=false)
    parts = grid_parts(level; malformed_count=malformed_count)
    return D3DirectHybridizedGridPlan(
        "d3-rev10-direct-hybridized-grid-plan.v1",
        level,
        candidate(),
        fixed_input_identity().canonical_sha256,
        parts.counts,
        parts.boundaries_m,
        grid_plan_sha256(level, parts),
    )
end

function source_profile(level)
    digit = string(level + 1)
    return (
        model_identity=(
            circuit_plan_sha256=repeat(digit, 64),
            capacitance_sha256=HASH_A,
            inverse_inductance_sha256=HASH_B,
            selector_sha256=HASH_C,
        ),
        q2d_artifact_id="d3-q2d-v4",
        q2d_artifact_sha256=HASH_A,
        q2d_topology_id=:d3_continuous_ground,
        q2d_geometry_um=(gap=8.0,),
        fixed_line_input_sha256=HASH_B,
        fixed_line_input_identity=(profile="w7-s6-d3-h8-v4",),
        fixed_input_identity=fixed_input_identity(),
        idc_mapping_id="d3-idc-gap8",
        idc_mapping_sha256=HASH_C,
        feedline_contract=(model=:split_distributed_cpw, length_m=2.0e-3, n_sections=64 * (1 << level)),
    )
end

function cared_output(level; change=5.0e-4, malformed_count=false)
    scale = (1 + change)^level
    first_frequency = 5.6e9 * scale
    second_frequency = 5.8e9 * scale
    swapped = isodd(level)
    fraction_min = 0.40 * scale
    return D3DirectHybridizedCaredOutput(
        D3_DIRECT_HYBRIDIZED_CARED_OUTPUT_CONTRACT,
        :stage2_direct_hybridized,
        :hybridized_distributed_lumped,
        5.6e9,
        candidate(),
        swapped ? second_frequency : first_frequency,
        swapped ? first_frequency : second_frequency,
        5.0e9 * scale,
        10.0e6 * scale,
        2.0e6 * scale,
        fraction_min,
        1 - fraction_min,
        source_profile(level),
        grid_identity(level; malformed_count=malformed_count),
        extraction_profile(),
        (
            status=:pass,
            source_identity=:pass,
            passivity=(
                capacitance_reciprocity_error=0.0,
                stiffness_reciprocity_error=0.0,
                conductance_reciprocity_error=0.0,
                stiffness_relative_passivity_violation=0.0,
                conductance_relative_passivity_violation=0.0,
            ),
            rp_root_and_operator=:pass,
            distributed_rp_on_notch=:pass,
            exact_open_poles=:pass,
            unordered_rp_assignment=:pass,
        ),
    )
end

function request(level; malformed_count=false)
    return d3_direct_hybridized_spatial_level_request(
        direct_inputs(),
        grid_plan(level; malformed_count=malformed_count),
        extraction_profile(),
    )
end

function exception_code(f)
    try
        f()
    catch exception
        exception isa D3DirectHybridizedSpatialNotEvaluable || rethrow()
        return exception.code, exception
    end
    error("Expected D3DirectHybridizedSpatialNotEvaluable.")
end

@testset "D3 direct-Hybridized spatial receipt" begin
    cache = Dict{String,Any}()
    evaluated = Int[]
    evidence = produce_d3_direct_hybridized_spatial_evidence(
        candidate();
        slot_hz=5.6e9,
        objective_authority=objective_authority(),
        level_request=(candidate, slot, level) -> request(level),
        cared_output_evaluator=(candidate, slot, input) -> begin
            level = input.grid_plan.refinement_level
            push!(evaluated, level)
            cared_output(level)
        end,
        cache=cache,
    )
    @test evaluated == [0, 1, 2]
    @test evidence["qualified_level"] == 2
    @test length(evidence["levels"]) == 3
    @test all(comparison["passed"] for comparison in evidence["adjacent_comparisons"])
    @test validate_d3_direct_hybridized_spatial_evidence(evidence).cared_output ==
        validate_d3_direct_hybridized_cared_output(cared_output(2))
    mismatched_objective_authority = copy(objective_authority())
    mismatched_objective_authority["target_contract_sha256"] = repeat("f", 64)
    @test exception_code(() -> validate_d3_direct_hybridized_objective_authority(
        mismatched_objective_authority,
    ))[1] == "direct_spatial.objective_authority_mismatch"

    empty!(evaluated)
    cached_evidence = produce_d3_direct_hybridized_spatial_evidence(
        candidate();
        slot_hz=5.6e9,
        objective_authority=objective_authority(),
        level_request=(candidate, slot, level) -> request(level),
        cared_output_evaluator=(candidate, slot, input) -> begin
            level = input.grid_plan.refinement_level
            push!(evaluated, level)
            cared_output(level)
        end,
        cache=cache,
    )
    @test isempty(evaluated)
    @test cached_evidence == evidence

    mktempdir() do directory
        path = joinpath(directory, "receipt.json")
        receipt = write_d3_direct_hybridized_spatial_receipt(path, evidence)
        identity = d3_direct_hybridized_spatial_receipt_identity(receipt)
        authorization = authorize_d3_direct_hybridized_spatial_receipt(
            receipt,
            candidate();
            slot_hz=5.6e9,
            objective_authority=objective_authority(),
            expected_receipt_sha256=identity.receipt_sha256,
        )
        objective_calls = Ref(0)
        result = evaluate_d3_direct_hybridized_objective_with_spatial_evidence(
            authorization,
            candidate(),
            cared_output(2);
            slot_hz=5.6e9,
            objective_authority=objective_authority(),
            objective_evaluator=authorization -> begin
                objective_calls[] += 1
                (status=:evaluated, candidate=authorization.candidate)
            end,
        )
        @test result.status == :evaluated
        @test objective_calls[] == 1
        @test exception_code(() -> authorize_d3_direct_hybridized_spatial_receipt(
            receipt,
            candidate(61.0e-6);
            slot_hz=5.6e9,
            objective_authority=objective_authority(),
        ))[1] == "direct_spatial.candidate_mismatch"
        @test exception_code(() -> authorize_d3_direct_hybridized_spatial_receipt(
            receipt,
            candidate();
            slot_hz=5.7e9,
            objective_authority=objective_authority(),
        ))[1] == "direct_spatial.slot_mismatch"
        @test exception_code(() -> write_d3_direct_hybridized_spatial_receipt(path, evidence))[1] ==
            "direct_spatial.exists"

        open(path, "a") do io
            write(io, " ")
        end
        @test exception_code(() -> revalidate_d3_direct_hybridized_spatial_receipt(
            authorization,
            candidate();
            slot_hz=5.6e9,
            objective_authority=objective_authority(),
        ))[1] == "direct_spatial.stale"
    end

    @testset "fail closed" begin
        code, exception = exception_code(() -> produce_d3_direct_hybridized_spatial_evidence(
            candidate();
            slot_hz=5.6e9,
            objective_authority=objective_authority(),
            level_request=(candidate, slot, level) -> request(level),
            cared_output_evaluator=(candidate, slot, input) -> cared_output(
                input.grid_plan.refinement_level;
                change=0.01,
            ),
        ))
        @test code == "spatial_grid_not_eligible"
        @test exception.details["cost"] === nothing
        @test length(exception.details["records"]) == 4

        @test exception_code(() -> produce_d3_direct_hybridized_spatial_evidence(
            candidate();
            slot_hz=5.6e9,
            objective_authority=objective_authority(),
            level_request=(candidate, slot, level) -> request(level; malformed_count=level == 1),
            cared_output_evaluator=(candidate, slot, input) -> cared_output(
                input.grid_plan.refinement_level;
                malformed_count=input.grid_plan.refinement_level == 1,
            ),
        ))[1] == "direct_spatial.grid_mismatch"

        @test exception_code(() -> produce_d3_direct_hybridized_spatial_evidence(
            candidate();
            slot_hz=5.6e9,
            objective_authority=objective_authority(),
            level_request=(candidate, slot, level) -> request(level),
            cared_output_evaluator=(candidate, slot, input) -> error("circuit failure"),
        ))[1] == "direct_spatial.cared_output_not_evaluable"

        record = cared_output(0)
        nonfinite = NamedTuple{propertynames(record)}(Tuple(
            name === :f_n_hz ? Inf : getproperty(record, name)
            for name in propertynames(record)
        ))
        @test exception_code(() -> validate_d3_direct_hybridized_cared_output(nonfinite))[1] ==
            "direct_spatial.nonfinite"

        poisoned_cache = deepcopy(cache)
        first_key = first(keys(poisoned_cache))
        poisoned_cache[first_key]["cared_output"]["f_n_hz"] *= 1.01
        @test exception_code(() -> produce_d3_direct_hybridized_spatial_evidence(
            candidate();
            slot_hz=5.6e9,
            objective_authority=objective_authority(),
            level_request=(candidate, slot, level) -> request(level),
            cared_output_evaluator=(candidate, slot, input) ->
                cared_output(input.grid_plan.refinement_level),
            cache=poisoned_cache,
        ))[1] == "direct_spatial.cache_mismatch"
    end
end
