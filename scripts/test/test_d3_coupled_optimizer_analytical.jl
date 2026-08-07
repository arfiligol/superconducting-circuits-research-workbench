# This test exercises only the CMA-ES-only algorithm contract of the D3
# optimizer with a deterministic analytic objective. It does not load HB code
# or claim physical D3 evidence.

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
const INITIAL_CANDIDATE = (x=0.5, y=0.5)

function analytic_evaluator(candidate)
    candidate.x < 0.45 && return RejectedEvaluation(
        "analytic.rejected_region",
        "The analytic smoke domain excludes x below 0.45.",
        (x=candidate.x,),
    )
    return ValidEvaluation((
        x=candidate.x,
        y=candidate.y,
        sum_guard=candidate.x + candidate.y,
    ))
end

function run_generation_batch_optimizer(worker_count)
    result = optimize_d3(
        analytic_evaluator,
        VARIABLES,
        METRICS,
        INITIAL_CANDIDATE,
        CMASettings(
            seed=20260807,
            sigma=0.2,
            popsize=8,
            maxiter=5,
            maxfevals=40,
            ftol=1.0e-8,
            xtol=1.0e-5,
        ),
        nothing;
        condition_manifest_id="d3-deterministic-generation-batch-test",
        condition_manifest_sha256=repeat("d", 64),
        condition_manifest_approval_status="human_approved",
        worker_count=worker_count,
    )
    return result
end

@testset "D3 deterministic CMA generation batches" begin
    serial = run_generation_batch_optimizer(1)
    parallel = run_generation_batch_optimizer(4)
    repeated = run_generation_batch_optimizer(4)

    @test repr(serial) == repr(parallel) == repr(repeated)
    @test_throws ErrorException optimize_d3(
        analytic_evaluator,
        VARIABLES,
        METRICS,
        INITIAL_CANDIDATE,
        CMASettings(
            seed=1,
            sigma=0.2,
            popsize=4,
            maxiter=1,
            maxfevals=4,
            ftol=1.0e-6,
            xtol=1.0e-4,
        ),
        nothing;
        condition_manifest_id="d3-invalid-worker-count-test",
        condition_manifest_sha256=repeat("e", 64),
        condition_manifest_approval_status="human_approved",
        worker_count=0,
    )
end

@testset "D3 ordered batch cache and rejection replay" begin
    calls = Dict{Tuple,Int}()
    completion_order = Tuple[]
    calls_lock = ReentrantLock()
    evaluator = candidate -> begin
        key = Tuple(candidate)
        lock(calls_lock) do
            calls[key] = get(calls, key, 0) + 1
        end
        candidate.x == 0.75 && sleep(0.02)
        lock(calls_lock) do
            push!(completion_order, key)
        end
        candidate.x == 0.25 && return RejectedEvaluation(
            "analytic.batch_rejection",
            "The exact batch candidate is rejected.",
            candidate,
        )
        return ValidEvaluation((
            x=candidate.x,
            y=candidate.y,
            sum_guard=candidate.x + candidate.y,
        ))
    end
    context = D3CoupledOptimizer.ObjectiveContext(evaluator, VARIABLES, METRICS)
    D3CoupledOptimizer._evaluate!(context, :initial_seed, [0.5, 0.5])
    empty!(completion_order)
    costs = D3CoupledOptimizer._evaluate_batch!(
        context,
        :cma,
        ([0.5, 0.5], [0.75, 0.25], [0.75, 0.25], [0.25, 0.75], [0.25, 0.75], [0.5, 0.5]);
        worker_count=4,
    )

    records = context.history[2:end]
    @test completion_order == [(0.25, 0.75), (0.75, 0.25)]
    @test [Tuple(record.candidate) for record in records] ==
        [(0.5, 0.5), (0.75, 0.25), (0.75, 0.25), (0.25, 0.75), (0.25, 0.75), (0.5, 0.5)]
    @test [record.cache_hit for record in records] == [true, false, true, false, true, true]
    @test [record.evaluation isa RejectedEvaluation for record in records] ==
        [false, false, false, true, true, false]
    @test isfinite.(costs) == [true, true, true, false, false, true]
    @test calls == Dict((0.5, 0.5) => 1, (0.75, 0.25) => 1, (0.25, 0.75) => 1)
end

@testset "D3 batch exception replay uses original column order" begin
    calls = Tuple[]
    calls_lock = ReentrantLock()
    evaluator = candidate -> begin
        lock(calls_lock) do
            push!(calls, Tuple(candidate))
        end
        if candidate.x == 0.2
            sleep(0.02)
            error("earliest-column evaluator failure")
        elseif candidate.x == 0.3
            error("later-column evaluator failure")
        end
        return ValidEvaluation((
            x=candidate.x,
            y=candidate.y,
            sum_guard=candidate.x + candidate.y,
        ))
    end
    context = D3CoupledOptimizer.ObjectiveContext(evaluator, VARIABLES, METRICS)
    exception = try
        D3CoupledOptimizer._evaluate_batch!(
            context,
            :cma,
            ([0.1, 0.9], [0.2, 0.8], [0.3, 0.7], [0.4, 0.6]);
            worker_count=4,
        )
        nothing
    catch error
        error
    end

    @test exception isa ErrorException
    @test sprint(showerror, exception) == "earliest-column evaluator failure"
    @test Set(calls) == Set(((0.1, 0.9), (0.2, 0.8), (0.3, 0.7), (0.4, 0.6)))
    @test [Tuple(record.candidate) for record in context.history] == [(0.1, 0.9)]
    @test Set(keys(context.cache)) == Set(((0.1, 0.9),))
end

function run_analytic_optimizer(approval_status)
    seed_evaluator_calls = Ref(0)
    evaluator = candidate -> begin
        candidate == INITIAL_CANDIDATE && (seed_evaluator_calls[] += 1)
        analytic_evaluator(candidate)
    end
    result = optimize_d3(
        evaluator,
        VARIABLES,
        METRICS,
        INITIAL_CANDIDATE,
        CMASettings(
            seed=20260711,
            sigma=0.25,
            popsize=12,
            maxiter=40,
            maxfevals=480,
            ftol=1.0e-8,
            xtol=1.0e-5,
        ),
        PromotionSettings(max_cost=0.01, max_abs_normalized_residual=0.1);
        condition_manifest_id="d3-analytical-optimizer-test",
        condition_manifest_sha256=repeat("a", 64),
        condition_manifest_approval_status=approval_status,
    )
    return result, seed_evaluator_calls[]
end

@testset "D3 CMA-ES-only optimizer analytical contract" begin
    known = cost_breakdown(METRICS, analytic_evaluator((x=0.75, y=0.375)))
    @test known.total == 1.0
    @test [metric.contribution for metric in known.metrics] == [1.0, 0.0, 0.0]
    @test known.metrics[3].normalized_residual == 1.0

    proposed, proposed_seed_calls = run_analytic_optimizer("agent_proposed")
    approved, approved_seed_calls = run_analytic_optimizer("human_approved")
    @test proposed_seed_calls == approved_seed_calls == 1

    for result in (proposed, approved)
        seed_records = [record for record in result.history if record.stage === :initial_seed]
        cma_records = [record for record in result.history if record.stage === :cma]
        @test length(seed_records) == 1
        @test only(seed_records).record_id == result.initial_seed_record_id
        @test only(seed_records).candidate == INITIAL_CANDIDATE
        @test result.cma.observed_evaluations == length(cma_records)
        @test Set(record.stage for record in result.history) == Set((:initial_seed, :cma))
        @test result.cma.termination_reason == "maxiter"
        @test result.cma.state === :converged

        valid = [record for record in result.history if !isnothing(record.cost)]
        best = valid[argmin(record.cost for record in valid)]
        @test best.candidate.x ≈ 0.625 atol=0.05
        @test best.candidate.y ≈ 0.375 atol=0.05
        @test result.promotion.candidate_record_id == best.record_id
        @test any(record -> record.evaluation isa RejectedEvaluation, result.history)
        @test all(record -> isnothing(record.cost) || isfinite(record.cost), result.history)
        @test all(
            record -> !(record.evaluation isa RejectedEvaluation) ||
                (isnothing(record.cost) && isnothing(record.breakdown)),
            result.history,
        )
        @test result.cache_summary.hit_count + result.cache_summary.miss_count ==
            length(result.history)
        @test result.cache_summary.unique_candidate_count ==
            result.cache_summary.miss_count

        convergence = only(filter(
            condition -> condition.condition_id == "promotion.cma_es_converged",
            result.promotion.conditions,
        ))
        @test convergence.observed_value ==
            (result.cma.state === :converged ? 1.0 : 0.0)
        guard = only(filter(
            condition ->
                condition.condition_id ==
                    "promotion.metric.sum_guard.max_abs_normalized_residual",
            result.promotion.conditions,
        ))
        @test guard.observed_value ≈
            abs(best.breakdown.metrics[3].normalized_residual)
    end

    @test proposed.promotion.state === :not_evaluable
    @test approved.promotion.state === :met

    diagnostic = optimize_d3(
        analytic_evaluator,
        VARIABLES,
        METRICS,
        INITIAL_CANDIDATE,
        CMASettings(
            seed=11,
            sigma=0.2,
            popsize=4,
            maxiter=2,
            maxfevals=8,
            ftol=1.0e-6,
            xtol=1.0e-4,
        ),
        nothing;
        condition_manifest_id="d3-diagnostic-no-promotion-test",
        condition_manifest_sha256=repeat("c", 64),
        condition_manifest_approval_status="human_approved",
    )
    @test diagnostic.promotion.state === :not_evaluable
    @test isempty(diagnostic.promotion.conditions)
    @test isempty(diagnostic.promotion.unmet_condition_ids)
    @test occursin("did not declare", diagnostic.promotion.reason)
    @test diagnostic.promotion.candidate_record_id !== nothing

    seed_only_evaluator = candidate -> candidate == INITIAL_CANDIDATE ?
        ValidEvaluation((
            x=candidate.x,
            y=candidate.y,
            sum_guard=candidate.x + candidate.y,
        )) :
        RejectedEvaluation(
            "analytic.seed_only",
            "Only the exact seed is valid in this smoke test.",
            candidate,
        )
    seed_only = optimize_d3(
        seed_only_evaluator,
        VARIABLES,
        METRICS,
        INITIAL_CANDIDATE,
        CMASettings(
            seed=7,
            sigma=0.2,
            popsize=4,
            maxiter=2,
            maxfevals=8,
            ftol=1.0e-6,
            xtol=1.0e-4,
        ),
        PromotionSettings(max_cost=10.0, max_abs_normalized_residual=10.0);
        condition_manifest_id="d3-seed-incumbent-test",
        condition_manifest_sha256=repeat("b", 64),
        condition_manifest_approval_status="agent_proposed",
    )
    @test seed_only.cma.state === :no_valid_candidate
    @test seed_only.promotion.candidate_record_id ==
        seed_only.initial_seed_record_id
    @test Set(record.stage for record in seed_only.history) ==
        Set((:initial_seed, :cma))
end
