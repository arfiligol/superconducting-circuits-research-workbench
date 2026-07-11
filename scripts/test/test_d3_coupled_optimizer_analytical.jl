# This test exercises only the algorithm contract of the D3 optimizer with a
# deterministic analytic objective. It does not load HB code or claim physical
# D3 evidence. Canonical semantics:
# https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/numerical-methods/auditable-scientific-optimization.qmd

using Test

include(joinpath(
    @__DIR__,
    "..",
    "..",
    "notebooks",
    "pluto",
    "D3 Intrinsic Purcell Filter Design",
    "d3_coupled_optimizer.jl",
))
using .D3CoupledOptimizer

const VARIABLES = [
    VariableSpec(:x, "fraction", 0.0, 1.0),
    VariableSpec(:y, "fraction", 0.0, 1.0),
]
const METRICS = [
    MetricSpec(:x, 0.625, 0.125, 1.0),
    MetricSpec(:y, 0.375, 0.125, 2.0),
    MetricSpec(:sum_guard, 1.0, 0.125, 0.0),
]
const INITIAL_CANDIDATE = (x = 0.5, y = 0.5)
const REJECTION_CARRIER_COST = 1.0e12

function analytic_evaluator(candidate)
    candidate.x < 0.45 && return RejectedEvaluation(
        "analytic.rejected_region",
        "The analytic smoke domain excludes x below 0.45.",
        (x = candidate.x,),
    )
    return ValidEvaluation((
        x = candidate.x,
        y = candidate.y,
        sum_guard = candidate.x + candidate.y,
    ))
end

function run_analytic_optimizer(approval_status)
    seed_evaluator_calls = Ref(0)
    evaluator = candidate -> begin
        candidate == INITIAL_CANDIDATE && (seed_evaluator_calls[] += 1)
        return analytic_evaluator(candidate)
    end
    result = optimize_d3(
        evaluator,
        VARIABLES,
        METRICS,
        INITIAL_CANDIDATE,
        CMASettings(
            seed = 20260711,
            sigma = 0.25,
            popsize = 10,
            maxiter = 12,
            maxfevals = 120,
            ftol = 1.0e-8,
            xtol = 1.0e-6,
        ),
        NelderMeadSettings(
            maxiter = 100,
            maxfevals = 220,
            ftol = 1.0e-8,
            xtol = 5.0e-5,
            rejection_carrier_cost = REJECTION_CARRIER_COST,
            simplex_logit_offset = 0.05,
            simplex_logit_multiplier = 0.1,
        ),
        PromotionSettings(max_cost = 0.01, max_abs_normalized_residual = 0.1);
        condition_manifest_id = "d3-analytical-optimizer-test",
        condition_manifest_sha256 = repeat("a", 64),
        condition_manifest_approval_status = approval_status,
    )
    return result, seed_evaluator_calls[]
end

function best_nelder_mead_record(result)
    record_id = result.nelder_mead.best_valid_record_id
    @test !isnothing(record_id)
    return only(record for record in result.history if record.record_id == record_id)
end

@testset "D3 optimizer analytical contract" begin
    @test_throws ErrorException NelderMeadSettings(
        maxiter = 3,
        maxfevals = 10,
        ftol = 1.0e-6,
        xtol = 1.0e-4,
        rejection_carrier_cost = 0.0,
        simplex_logit_offset = 0.05,
        simplex_logit_multiplier = 0.1,
    )

    known = cost_breakdown(METRICS, analytic_evaluator((x = 0.75, y = 0.375)))
    @test known.total == 1.0
    @test [metric.contribution for metric in known.metrics] == [1.0, 0.0, 0.0]
    @test known.metrics[3].normalized_residual == 1.0

    proposed, proposed_seed_calls = run_analytic_optimizer("agent_proposed")
    approved, approved_seed_calls = run_analytic_optimizer("human_approved")
    @test proposed_seed_calls == approved_seed_calls == 1

    for result in (proposed, approved)
        seed_records = [record for record in result.history if record.stage === :initial_seed]
        @test length(seed_records) == 1
        @test only(seed_records).record_id == result.initial_seed_record_id == "initial_seed-000001"
        @test only(seed_records).candidate == INITIAL_CANDIDATE
        @test only(seed_records).cache_hit === false

        cma_records = [record for record in result.history if record.stage === :cma]
        @test result.cma.observed_evaluations == length(cma_records)
        cma_valid_ids = Set(record.candidate_id for record in cma_records if record.evaluation isa ValidEvaluation)
        cma_rejected_ids = Set(record.candidate_id for record in cma_records if record.evaluation isa RejectedEvaluation)
        @test result.cma.valid_candidate_count == length(cma_valid_ids)
        @test result.cma.rejected_candidate_count == length(cma_rejected_ids)
        expected_cma_state = isempty(cma_valid_ids) ? :no_valid_candidate :
            all(condition -> condition.met === true, result.cma.convergence_conditions) ? :converged : :not_converged
        @test result.cma.state === expected_cma_state
        @test result.cma.termination_reason == "xtol"
        @test result.cma.state === :not_converged
        @test any(condition -> condition.met !== true, result.cma.convergence_conditions)

        handoff_pool = vcat(seed_records, cma_records)
        valid_handoff_pool = [record for record in handoff_pool if !isnothing(record.cost)]
        expected_incumbent = valid_handoff_pool[argmin(record.cost for record in valid_handoff_pool)]
        @test result.handoff.candidate_record_id == expected_incumbent.record_id
        best = best_nelder_mead_record(result)
        @test best.candidate.x ≈ 0.625 atol = 0.005
        @test best.candidate.y ≈ 0.375 atol = 0.005
        @test result.handoff.state === :met
        @test result.nelder_mead.state === :converged
        @test any(
            record -> record.evaluation isa RejectedEvaluation &&
                record.evaluation.code == "analytic.rejected_region",
            result.history,
        )
        @test any(record -> record.evaluation isa ValidEvaluation, result.history)
        @test all(record -> isnothing(record.cost) || isfinite(record.cost), result.history)
        @test all(record -> isnothing(record.cost) || record.cost != REJECTION_CARRIER_COST, result.history)
        @test all(
            record -> !(record.evaluation isa RejectedEvaluation) ||
                (isnothing(record.cost) && isnothing(record.breakdown)),
            result.history,
        )
        @test result.cache_summary.hit_count + result.cache_summary.miss_count == length(result.history)
        @test result.cache_summary.unique_candidate_count == result.cache_summary.miss_count
        @test result.cache_summary.unique_candidate_count == length(unique(record.candidate_id for record in result.history))
        @test length(unique(record.record_id for record in result.history)) == length(result.history)
        global_valid = [record for record in result.history if !isnothing(record.cost)]
        global_best = global_valid[argmin(record.cost for record in global_valid)]
        @test global_best.cost <= best.cost
        guard = only(filter(
            condition -> condition.condition_id == "promotion.metric.sum_guard.max_abs_normalized_residual",
            result.promotion.conditions,
        ))
        @test guard.met === true
    end

    @test proposed.promotion.state === :not_evaluable
    @test approved.promotion.state === :met

    seed_only_evaluator = candidate -> candidate == INITIAL_CANDIDATE ?
        ValidEvaluation((x = candidate.x, y = candidate.y, sum_guard = candidate.x + candidate.y)) :
        RejectedEvaluation("analytic.seed_only", "Only the exact seed is valid in this handoff smoke.", candidate)
    seed_only = optimize_d3(
        seed_only_evaluator,
        VARIABLES,
        METRICS,
        INITIAL_CANDIDATE,
        CMASettings(seed = 7, sigma = 0.2, popsize = 4, maxiter = 2, maxfevals = 8, ftol = 1.0e-6, xtol = 1.0e-4),
        NelderMeadSettings(
            maxiter = 3,
            maxfevals = 10,
            ftol = 1.0e-6,
            xtol = 1.0e-4,
            rejection_carrier_cost = REJECTION_CARRIER_COST,
            simplex_logit_offset = 0.05,
            simplex_logit_multiplier = 0.1,
        ),
        PromotionSettings(max_cost = 10.0, max_abs_normalized_residual = 10.0);
        condition_manifest_id = "d3-seed-incumbent-test",
        condition_manifest_sha256 = repeat("b", 64),
        condition_manifest_approval_status = "agent_proposed",
    )
    @test seed_only.cma.state === :no_valid_candidate
    @test seed_only.handoff.state === :met
    @test seed_only.handoff.candidate_record_id == seed_only.initial_seed_record_id
    @test seed_only.nelder_mead.state !== :not_run
    @test seed_only.cma.observed_evaluations == count(record -> record.stage === :cma, seed_only.history)
    seed_only_nm_records = [record for record in seed_only.history if record.stage === :nelder_mead]
    @test seed_only.nelder_mead.observed_iterations > 0
    @test seed_only.nelder_mead.observed_evaluations > length(VARIABLES) + 1
    @test any(record -> record.evaluation isa RejectedEvaluation, seed_only_nm_records[1:(length(VARIABLES) + 1)])
    @test all(
        record -> !(record.evaluation isa RejectedEvaluation) ||
            (isnothing(record.cost) && isnothing(record.breakdown)),
        seed_only.history,
    )
    @test all(record -> isnothing(record.cost) || record.cost != REJECTION_CARRIER_COST, seed_only.history)
    seed_only_global_valid = [record for record in seed_only.history if !isnothing(record.cost)]
    @test seed_only_global_valid[argmin(record.cost for record in seed_only_global_valid)].record_id ==
        seed_only.initial_seed_record_id
    @test isnothing(seed_only.promotion.candidate_record_id) ||
        seed_only.promotion.candidate_record_id in Set(record.record_id for record in seed_only_global_valid)

    valid_above_carrier = candidate -> ValidEvaluation((
        x = candidate.x,
        y = candidate.y,
        sum_guard = candidate.x + candidate.y,
    ))
    carrier_failure = try
        optimize_d3(
            valid_above_carrier,
            VARIABLES,
            METRICS,
            INITIAL_CANDIDATE,
            CMASettings(seed = 9, sigma = 0.2, popsize = 4, maxiter = 2, maxfevals = 8, ftol = 1.0e-6, xtol = 1.0e-4),
            NelderMeadSettings(
                maxiter = 3,
                maxfevals = 10,
                ftol = 1.0e-6,
                xtol = 1.0e-4,
                rejection_carrier_cost = 1.0,
                simplex_logit_offset = 0.05,
                simplex_logit_multiplier = 0.1,
            ),
            PromotionSettings(max_cost = 10.0, max_abs_normalized_residual = 10.0);
            condition_manifest_id = "d3-carrier-bound-test",
            condition_manifest_sha256 = repeat("c", 64),
            condition_manifest_approval_status = "agent_proposed",
        )
        nothing
    catch error
        error
    end
    @test carrier_failure isa ErrorException
    @test occursin("must remain below rejection carrier", sprint(showerror, carrier_failure))
end
