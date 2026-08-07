# This module owns the algorithm-only D3 tuning loop: explicit optimization
# contracts, evaluator caching, cost accounting, and bounded CMA-ES search.
# It does not own HB physics, D3 targets, geometry bounds, approval, restart
# orchestration, or artifact persistence; callers provide those decisions
# through a hash-bound condition manifest and the evaluator.
# Canonical D3 target:
# https://github.com/arfiligol/SCQ_Design/blob/main/docs/design-targets/d3-intrinsic-interferometric-purcell-filter.qmd
# Canonical optimization semantics:
# https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/numerical-methods/auditable-scientific-optimization.qmd

module D3CoupledOptimizer

import CMAEvolutionStrategy
import SHA

export CMASettings,
    CacheSummary,
    ConditionOutcome,
    CostBreakdown,
    EvaluationRecord,
    GateOutcome,
    MetricCost,
    MetricSpec,
    OptimizationResult,
    PromotionSettings,
    RejectedEvaluation,
    SearchStageOutcome,
    ValidEvaluation,
    VariableSpec,
    cost_breakdown,
    optimize_d3

"""One physical optimization variable with explicit closed bounds."""
struct VariableSpec
    name::Symbol
    unit::String
    lower::Float64
    upper::Float64

    function VariableSpec(name::Symbol, unit::AbstractString, lower::Real, upper::Real)
        isempty(String(name)) && error("Variable name must not be empty.")
        isempty(strip(String(unit))) && error("Variable $(name) must declare a unit.")
        bounds = Float64(lower), Float64(upper)
        all(isfinite, bounds) || error("Variable $(name) bounds must be finite.")
        bounds[1] < bounds[2] || error("Variable $(name) lower bound must be below its upper bound.")
        return new(name, String(unit), bounds...)
    end
end

"""One required evaluator metric; zero weight keeps it as a promotion-only condition."""
struct MetricSpec
    name::Symbol
    target::Float64
    scale::Float64
    weight::Float64

    function MetricSpec(name::Symbol, target::Real, scale::Real, weight::Real)
        isempty(String(name)) && error("Metric name must not be empty.")
        values = Float64(target), Float64(scale), Float64(weight)
        all(isfinite, values) || error("Metric $(name) values must be finite.")
        values[2] > 0 || error("Metric $(name) scale must be positive.")
        values[3] >= 0 || error("Metric $(name) weight must be non-negative.")
        return new(name, values...)
    end
end

"""A physically valid evaluation with finite real-valued metrics."""
struct ValidEvaluation{M<:NamedTuple}
    metrics::M

    function ValidEvaluation(metrics::M) where {M<:NamedTuple}
        isempty(propertynames(metrics)) && error("A valid evaluation must contain metrics.")
        for (name, value) in pairs(metrics)
            value isa Real || error("Metric $(name) must be real-valued.")
            isfinite(value) || error("Metric $(name) must be finite.")
        end
        return new{M}(metrics)
    end
end

"""
    RejectedEvaluation(code, reason, details)

Represent an expected candidate-level physics or evidence rejection. `code` is
stable for machine aggregation, `reason` is readable, and `details` retains the
observed evidence. Rejection is not an execution exception.
"""
struct RejectedEvaluation
    code::String
    reason::String
    details

    function RejectedEvaluation(code::AbstractString, reason::AbstractString, details)
        code_value = strip(String(code))
        reason_value = strip(String(reason))
        isempty(code_value) && error("Evaluation rejection must include a stable code.")
        isempty(reason_value) && error("Evaluation rejection must include a reason.")
        occursin(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$", code_value) || error(
            "Evaluation rejection code must be stable lowercase machine text; received $(repr(code_value)).",
        )
        return new(code_value, reason_value, details)
    end
end

const Evaluation = Union{ValidEvaluation,RejectedEvaluation}

"""One metric's normalized residual and finite weighted contribution."""
struct MetricCost
    name::Symbol
    observed::Float64
    target::Float64
    scale::Float64
    weight::Float64
    normalized_residual::Float64
    contribution::Float64
end

"""A finite total cost and its ordered per-metric contributions."""
struct CostBreakdown
    total::Float64
    metrics::Vector{MetricCost}
end

"""
    cost_breakdown(specs, evaluation)

Require the exact metric set and calculate the weighted normalized squared
cost. Missing, extra, duplicate, non-finite, or overflowing metrics fail fast.
"""
function cost_breakdown(specs::AbstractVector{MetricSpec}, evaluation::ValidEvaluation)
    _require_unique_names(specs, "metric")
    expected = Tuple(spec.name for spec in specs)
    actual = propertynames(evaluation.metrics)
    _same_names(actual, expected) || error(
        "Evaluator metric names must exactly match $(expected); received $(actual).",
    )

    total = 0.0
    metric_costs = MetricCost[]
    for spec in specs
        observed = Float64(getproperty(evaluation.metrics, spec.name))
        residual = (observed - spec.target) / spec.scale
        contribution = spec.weight * residual^2
        all(isfinite, (residual, contribution)) || error(
            "Metric $(spec.name) produced a non-finite normalized cost.",
        )
        total += contribution
        isfinite(total) || error("Total metric cost overflowed.")
        push!(metric_costs, MetricCost(
            spec.name,
            observed,
            spec.target,
            spec.scale,
            spec.weight,
            residual,
            contribution,
        ))
    end
    return CostBreakdown(total, metric_costs)
end

"""Explicit bounded CMA-ES settings supplied by the condition manifest."""
struct CMASettings
    seed::UInt
    sigma::Float64
    popsize::Int
    maxiter::Int
    maxfevals::Int
    ftol::Float64
    xtol::Float64

    function CMASettings(
        seed::Integer,
        sigma::Real,
        popsize::Integer,
        maxiter::Integer,
        maxfevals::Integer,
        ftol::Real,
        xtol::Real,
    )
        seed >= 0 || error("CMA seed must be non-negative.")
        seed <= typemax(UInt) || error("CMA seed exceeds UInt range.")
        counts = Int(popsize), Int(maxiter), Int(maxfevals)
        counts[1] >= 2 || error("CMA popsize must be at least two.")
        counts[2] > 0 || error("CMA maxiter must be positive.")
        counts[3] >= counts[1] || error("CMA maxfevals must cover at least one population.")
        values = Float64(sigma), Float64(ftol), Float64(xtol)
        all(isfinite, values) || error("CMA numeric settings must be finite.")
        values[1] > 0 || error("CMA sigma must be positive.")
        values[2] > 0 || error("CMA ftol must be positive.")
        values[3] > 0 || error("CMA xtol must be positive.")
        return new(UInt(seed), values[1], counts..., values[2], values[3])
    end
end

function CMASettings(; seed, sigma, popsize, maxiter, maxfevals, ftol, xtol)
    return CMASettings(seed, sigma, popsize, maxiter, maxfevals, ftol, xtol)
end

"""
    PromotionSettings(; max_cost, max_abs_normalized_residual)

Define Human-owned promotion limits independently of the local search
algorithm. Aggregate cost controls the joint weighted objective, while the
per-metric residual limit prevents one objective from compensating for another.
"""
struct PromotionSettings
    max_cost::Float64
    max_abs_normalized_residual::Float64

    function PromotionSettings(max_cost::Real, max_abs_normalized_residual::Real)
        values = Float64(max_cost), Float64(max_abs_normalized_residual)
        all(isfinite, values) || error("Promotion thresholds must be finite.")
        all(value -> value >= 0, values) || error("Promotion thresholds must be non-negative.")
        return new(values...)
    end
end

function PromotionSettings(; max_cost, max_abs_normalized_residual)
    return PromotionSettings(max_cost, max_abs_normalized_residual)
end

"""One explicit comparator observation used by a convergence or decision gate."""
struct ConditionOutcome
    condition_id::String
    observed_value::Union{Nothing,Float64}
    comparator::String
    threshold::Float64
    unit::String
    met::Union{Nothing,Bool}

    function ConditionOutcome(
        condition_id::AbstractString,
        observed_value::Union{Nothing,Real},
        comparator::AbstractString,
        threshold::Real,
        unit::AbstractString,
        met::Union{Nothing,Bool},
    )
        id = strip(String(condition_id))
        isempty(id) && error("Condition outcome id must not be empty.")
        comparator_value = String(comparator)
        comparator_value in ("<", "<=", ">", ">=", "==") || error(
            "Unsupported condition comparator $(repr(comparator_value)).",
        )
        observed = isnothing(observed_value) ? nothing : Float64(observed_value)
        isnothing(observed) || isfinite(observed) || error("Condition observed value must be finite or nothing.")
        threshold_value = Float64(threshold)
        isfinite(threshold_value) || error("Condition threshold must be finite.")
        isempty(strip(String(unit))) && error("Condition outcome must declare a unit.")
        return new(id, observed, comparator_value, threshold_value, String(unit), met)
    end
end

"""One objective call, retaining exact candidate state and cache provenance."""
struct EvaluationRecord
    record_id::String
    candidate_id::String
    stage::Symbol
    candidate::NamedTuple
    cache_hit::Bool
    evaluation::Evaluation
    cost::Union{Nothing,Float64}
    breakdown::Union{Nothing,CostBreakdown}
end

"""
A structured search-stage result; expected nonconvergence is not an exception.
`observed_evaluations` counts objective calls including cache hits, while valid
and rejected candidate counts each count unique exact candidate IDs.
"""
struct SearchStageOutcome
    state::Symbol
    termination_reason::String
    declared_iteration_budget::Int
    declared_evaluation_budget::Int
    observed_iterations::Int
    observed_evaluations::Int
    best_valid_record_id::Union{Nothing,String}
    valid_candidate_count::Int
    rejected_candidate_count::Int
    convergence_conditions::Vector{ConditionOutcome}
end

"""A structured handoff or promotion decision over one candidate record."""
struct GateOutcome
    state::Symbol
    reason::String
    candidate_record_id::Union{Nothing,String}
    conditions::Vector{ConditionOutcome}
    unmet_condition_ids::Vector{String}
end

"""Exact-cache accounting over all objective calls."""
struct CacheSummary
    unique_candidate_count::Int
    hit_count::Int
    miss_count::Int
end

"""Hash-bound bounded-CMA-ES result with an independent promotion gate."""
struct OptimizationResult
    condition_manifest_id::String
    condition_manifest_sha256::String
    condition_manifest_approval_status::String
    initial_seed_record_id::String
    cma::SearchStageOutcome
    promotion::GateOutcome
    history::Vector{EvaluationRecord}
    cache_summary::CacheSummary
end

mutable struct ObjectiveContext{F}
    evaluator::F
    variables::Vector{VariableSpec}
    metrics::Vector{MetricSpec}
    cache::Dict{Tuple,Evaluation}
    history::Vector{EvaluationRecord}
end

function ObjectiveContext(evaluator, variables, metrics)
    return ObjectiveContext(
        evaluator,
        collect(variables),
        collect(metrics),
        Dict{Tuple,Evaluation}(),
        EvaluationRecord[],
    )
end

function _require_unique_names(specs, kind)
    names = [spec.name for spec in specs]
    isempty(names) && error("At least one $(kind) specification is required.")
    length(unique(names)) == length(names) || error("$(uppercasefirst(kind)) names must be unique.")
    return nothing
end

_same_names(left, right) = length(left) == length(right) && Set(left) == Set(right)

function _candidate(variables, values)
    length(values) == length(variables) || error("Candidate dimension does not match variable specifications.")
    floats = Float64.(values)
    all(isfinite, floats) || error("Candidate values must be finite.")
    for (spec, value) in zip(variables, floats)
        spec.lower <= value <= spec.upper || error(
            "Candidate $(spec.name)=$(value) is outside [$(spec.lower), $(spec.upper)].",
        )
    end
    names = Tuple(spec.name for spec in variables)
    return NamedTuple{names}(Tuple(floats))
end

function _candidate_id(candidate::NamedTuple)
    payload = join(
        (string(name, "=", bitstring(Float64(value))) for (name, value) in pairs(candidate)),
        ";",
    )
    return bytes2hex(SHA.sha256(payload))
end

function _evaluate!(context::ObjectiveContext, stage::Symbol, values)
    candidate = _candidate(context.variables, values)
    key = Tuple(candidate)
    cache_hit = haskey(context.cache, key)
    evaluation = if cache_hit
        context.cache[key]
    else
        result = context.evaluator(candidate)
        result isa Evaluation || error(
            "Evaluator must return ValidEvaluation or RejectedEvaluation; received $(typeof(result)).",
        )
        context.cache[key] = result
        result
    end

    breakdown = evaluation isa ValidEvaluation ? cost_breakdown(context.metrics, evaluation) : nothing
    external_cost = isnothing(breakdown) ? nothing : breakdown.total
    record_id = string(stage, "-", lpad(length(context.history) + 1, 6, '0'))
    push!(context.history, EvaluationRecord(
        record_id,
        _candidate_id(candidate),
        stage,
        candidate,
        cache_hit,
        evaluation,
        external_cost,
        breakdown,
    ))
    return isnothing(external_cost) ? Inf : external_cost
end

function _initial_values(variables, initial_candidate::NamedTuple)
    expected = Tuple(spec.name for spec in variables)
    actual = propertynames(initial_candidate)
    _same_names(actual, expected) || error(
        "Initial candidate names must exactly match $(expected); received $(actual).",
    )
    return [getproperty(initial_candidate, spec.name) for spec in variables]
end

function _to_unit_box(variables, values)
    candidate = _candidate(variables, values)
    return [
        (getproperty(candidate, spec.name) - spec.lower) / (spec.upper - spec.lower)
        for spec in variables
    ]
end

function _from_unit_box(variables, values)
    length(values) == length(variables) || error("Normalized candidate dimension mismatch.")
    normalized = Float64.(values)
    all(isfinite, normalized) || error("Normalized candidate values must be finite.")
    all(value -> 0.0 <= value <= 1.0, normalized) || error(
        "CMA produced a candidate outside its declared unit-box bounds.",
    )
    return [
        spec.lower + value * (spec.upper - spec.lower)
        for (spec, value) in zip(variables, normalized)
    ]
end

function _condition(id, observed, comparator, threshold, unit)
    met = if isnothing(observed)
        nothing
    elseif comparator == "<"
        observed < threshold
    elseif comparator == "<="
        observed <= threshold
    elseif comparator == ">"
        observed > threshold
    elseif comparator == ">="
        observed >= threshold
    elseif comparator == "=="
        observed == threshold
    else
        error("Unsupported condition comparator $(repr(comparator)).")
    end
    return ConditionOutcome(id, observed, comparator, threshold, unit, met)
end

function _stage_records(context, stage)
    return [record for record in context.history if record.stage === stage]
end

function _best_valid_record(records)
    valid = [record for record in records if !isnothing(record.cost)]
    isempty(valid) && return nothing
    return valid[argmin(record.cost for record in valid)]
end

function _stage_counts(records)
    valid_candidate_ids = Set(
        record.candidate_id
        for record in records
        if record.evaluation isa ValidEvaluation
    )
    rejected_candidate_ids = Set(
        record.candidate_id
        for record in records
        if record.evaluation isa RejectedEvaluation
    )
    isempty(intersect(valid_candidate_ids, rejected_candidate_ids)) || error(
        "One exact cached candidate has inconsistent valid and rejected states.",
    )
    return length(valid_candidate_ids), length(rejected_candidate_ids)
end

function _gate(state, reason, record, conditions)
    state in (:met, :not_met, :not_evaluable) || error("Invalid gate state $(state).")
    unmet = [condition.condition_id for condition in conditions if condition.met !== true]
    return GateOutcome(
        state,
        String(reason),
        isnothing(record) ? nothing : record.record_id,
        conditions,
        unmet,
    )
end

function _promotion_conditions(
    record,
    cma_state::Symbol,
    metrics::AbstractVector{MetricSpec},
    promotion::PromotionSettings;
    stage_ran::Bool,
)
    convergence_observed = stage_ran ? (cma_state === :converged ? 1.0 : 0.0) : nothing
    conditions = ConditionOutcome[
        _condition(
            "promotion.cma_es_converged",
            convergence_observed,
            "==",
            1.0,
            "boolean",
        ),
        _condition(
            "promotion.max_cost",
            isnothing(record) ? nothing : record.cost,
            "<=",
            promotion.max_cost,
            "weighted_normalized_squared_cost",
        ),
    ]

    metric_costs = if isnothing(record)
        Dict{Symbol,MetricCost}()
    else
        isnothing(record.breakdown) && error("A valid promotion candidate must retain its cost breakdown.")
        Dict(metric.name => metric for metric in record.breakdown.metrics)
    end
    for spec in metrics
        observed = if isnothing(record)
            nothing
        else
            haskey(metric_costs, spec.name) || error(
                "Promotion candidate cost breakdown is missing metric $(spec.name).",
            )
            abs(metric_costs[spec.name].normalized_residual)
        end
        push!(conditions, _condition(
            "promotion.metric.$(spec.name).max_abs_normalized_residual",
            observed,
            "<=",
            promotion.max_abs_normalized_residual,
            "dimensionless_normalized_residual",
        ))
    end
    return conditions
end

function _cache_summary(context)
    hits = count(record -> record.cache_hit, context.history)
    return CacheSummary(length(context.cache), hits, length(context.history) - hits)
end

function _validate_manifest_identity(id, hash, approval_status)
    id_value = strip(String(id))
    isempty(id_value) && error("Condition manifest id must not be empty.")
    hash_value = lowercase(strip(String(hash)))
    occursin(r"^[0-9a-f]{64}$", hash_value) || error(
        "Condition manifest SHA-256 must be 64 lowercase hexadecimal characters.",
    )
    status_value = String(approval_status)
    status_value in ("agent_proposed", "sol_reviewed", "human_approved") || error(
        "Unsupported condition manifest approval status $(repr(status_value)).",
    )
    return id_value, hash_value, status_value
end

"""
    optimize_d3(evaluator, variables, metrics, initial_candidate, cma,
                promotion_or_nothing; condition_manifest_id,
                condition_manifest_sha256,
                condition_manifest_approval_status)

Evaluate the exact seed once and run real bounded CMA-ES. Candidate rejection,
search limits, nonconvergence, and promotion failure are returned as structured
outcomes. Malformed contracts, evaluator bugs, nonfinite data, and
optimizer-library failures remain execution errors. The function performs no
artifact writes. Independent CMA-ES restarts are deliberately owned by the
caller so their seeds and budgets remain explicit in the Run manifest.

`promotion_or_nothing=nothing` records a diagnostic `:not_evaluable`
promotion outcome with no synthetic thresholds. It does not change CMA-ES,
the incumbent, cost calculation, or history.

An `agent_proposed` or `sol_reviewed` manifest may drive an explicitly
requested exploration, but its promotion outcome is always `:not_evaluable`
even when all numerical comparisons pass. Only `human_approved` can evaluate
promotion.
"""
function optimize_d3(
    evaluator,
    variables::AbstractVector{VariableSpec},
    metrics::AbstractVector{MetricSpec},
    initial_candidate::NamedTuple,
    cma::CMASettings,
    promotion_settings::Union{Nothing,PromotionSettings};
    condition_manifest_id,
    condition_manifest_sha256,
    condition_manifest_approval_status,
)
    manifest_id, manifest_hash, approval_status = _validate_manifest_identity(
        condition_manifest_id,
        condition_manifest_sha256,
        condition_manifest_approval_status,
    )
    _require_unique_names(variables, "variable")
    _require_unique_names(metrics, "metric")
    any(spec -> spec.weight > 0, metrics) || error("At least one metric must have positive weight.")

    initial_values = _initial_values(variables, initial_candidate)
    initial_unit = _to_unit_box(variables, initial_values)
    context = ObjectiveContext(evaluator, variables, metrics)
    _evaluate!(context, :initial_seed, initial_values)
    initial_seed_records = _stage_records(context, :initial_seed)
    length(initial_seed_records) == 1 || error("The exact initial seed must produce exactly one history record.")
    initial_seed_record = only(initial_seed_records)
    cma_objective = normalized -> _evaluate!(
        context,
        :cma,
        _from_unit_box(variables, normalized),
    )

    cma_result = CMAEvolutionStrategy.minimize(
        cma_objective,
        initial_unit,
        cma.sigma;
        lower = zeros(length(variables)),
        upper = ones(length(variables)),
        popsize = cma.popsize,
        seed = cma.seed,
        maxiter = cma.maxiter,
        maxfevals = cma.maxfevals,
        # Run the declared fixed budget. The package stops on its first scalar
        # tolerance and its built-in xtol is sign-sensitive; D3 instead
        # evaluates the declared joint absolute ftol/xtol contract below.
        ftol = nothing,
        xtol = nothing,
        parallel_evaluation = false,
        multi_threading = false,
        noise_handling = nothing,
        verbosity = 0,
    )

    cma_records = _stage_records(context, :cma)
    cma_best = _best_valid_record(cma_records)
    cma_valid_count, cma_rejected_count = _stage_counts(cma_records)
    cma_reason_symbol = cma_result.stop.reason
    cma_reason = String(cma_reason_symbol)
    cma_iterations = Int(cma_result.stop.it)
    generation_count = length(cma_records) ÷ cma.popsize
    recent_generation_ranges = Float64[]
    for generation in max(1, generation_count - 2):generation_count
        first_index = (generation - 1) * cma.popsize + 1
        last_index = generation * cma.popsize
        finite_costs = Float64[
            record.cost for record in cma_records[first_index:last_index]
            if !isnothing(record.cost) && isfinite(record.cost)
        ]
        length(finite_costs) >= 2 || continue
        push!(recent_generation_ranges, maximum(finite_costs) - minimum(finite_costs))
    end
    cma_ftol_observed = isempty(recent_generation_ranges) ?
        nothing : maximum(recent_generation_ranges)
    raw_cma_xtol = maximum(abs.(CMAEvolutionStrategy.sigma(cma_result.p) .* cma_result.p.cov.p))
    cma_xtol_observed = if isfinite(raw_cma_xtol)
        raw_cma_xtol
    elseif isnothing(cma_best)
        nothing
    else
        error("CMA-ES produced a non-finite xtol observation despite retaining a valid candidate.")
    end
    cma_conditions = [
        _condition("cma.ftol", cma_ftol_observed, "<=", cma.ftol, "cost"),
        _condition("cma.xtol", cma_xtol_observed, "<=", cma.xtol, "normalized_fraction"),
    ]
    cma_state = if isnothing(cma_best)
        :no_valid_candidate
    elseif all(condition -> condition.met === true, cma_conditions)
        :converged
    else
        :not_converged
    end
    cma_outcome = SearchStageOutcome(
        cma_state,
        cma_reason,
        cma.maxiter,
        cma.maxfevals,
        cma_iterations,
        length(cma_records),
        isnothing(cma_best) ? nothing : cma_best.record_id,
        cma_valid_count,
        cma_rejected_count,
        cma_conditions,
    )

    incumbent = _best_valid_record(vcat(initial_seed_records, cma_records))
    promotion_conditions = isnothing(promotion_settings) ? ConditionOutcome[] :
        _promotion_conditions(
            incumbent,
            cma_state,
            metrics,
            promotion_settings;
            stage_ran=true,
        )
    promotion_outcome = if isnothing(promotion_settings)
        _gate(
            :not_evaluable,
            "Diagnostic search did not declare Human-owned promotion limits.",
            incumbent,
            promotion_conditions,
        )
    elseif approval_status != "human_approved"
        _gate(
            :not_evaluable,
            "Manifest state $(approval_status) may produce exploration evidence but cannot evaluate promotion.",
            incumbent,
            promotion_conditions,
        )
    elseif isnothing(incumbent)
        _gate(:not_evaluable, "CMA-ES produced no valid candidate.", nothing, promotion_conditions)
    elseif all(condition -> condition.met === true, promotion_conditions)
        _gate(:met, "Human-approved promotion conditions are met.", incumbent, promotion_conditions)
    else
        _gate(:not_met, "Human-approved promotion conditions are not all met.", incumbent, promotion_conditions)
    end

    return OptimizationResult(
        manifest_id,
        manifest_hash,
        approval_status,
        initial_seed_record.record_id,
        cma_outcome,
        promotion_outcome,
        copy(context.history),
        _cache_summary(context),
    )
end

end
