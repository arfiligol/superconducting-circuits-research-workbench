struct SweepResult
    execution_plan::SweepExecutionPlan
    point_results::Vector{Any}
    point_statuses::Vector{Symbol}
    warnings::Vector{String}
    provenance::Dict{Symbol,Any}
end

function _compile_points(build_plan, sweep::SweepSpec, plan::SweepExecutionPlan, points)
    compiled = Vector{Union{Nothing,JosephsonCompiledCircuit}}(undef, length(points))
    errors_by_point = Vector{Union{Nothing,String}}(undef, length(points))
    fill!(compiled, nothing)
    fill!(errors_by_point, nothing)

    if sweep.compile_policy isa CompileOnce
        try
            first_compiled = compile_to_josephson(_build_plan_for_point(build_plan, first(points)))
            for idx in eachindex(points)
                compiled[idx] = first_compiled
            end
        catch err
            message = sprint(showerror, err)
            for idx in eachindex(points)
                errors_by_point[idx] = message
            end
        end
        return compiled, errors_by_point
    end

    if sweep.compile_policy isa CompileByTopologyKey
        for indices in values(plan.topology_groups)
            try
                representative = first(indices)
                group_compiled = compile_to_josephson(_build_plan_for_point(build_plan, points[representative]))
                for idx in indices
                    compiled[idx] = group_compiled
                end
            catch err
                message = sprint(showerror, err)
                for idx in indices
                    errors_by_point[idx] = message
                end
            end
        end
        return compiled, errors_by_point
    end

    for idx in eachindex(points)
        try
            compiled[idx] = compile_to_josephson(_build_plan_for_point(build_plan, points[idx]))
        catch err
            errors_by_point[idx] = sprint(showerror, err)
        end
    end
    return compiled, errors_by_point
end

function run_parameter_sweep(build_plan, sweep::SweepSpec; simulate=(compiled, _point) -> compiled)::SweepResult
    plan = preflight_sweep(build_plan, sweep)
    points = _sweep_points(sweep)
    compiled, compile_errors = _compile_points(build_plan, sweep, plan, points)
    results = Vector{Any}(undef, length(points))
    statuses = Vector{Symbol}(undef, length(points))

    function run_point!(idx)
        if !isnothing(compile_errors[idx])
            statuses[idx] = :compile_failed
            results[idx] = compile_errors[idx]
            return
        end
        try
            results[idx] = simulate(compiled[idx], points[idx])
            statuses[idx] = :success
        catch err
            results[idx] = sprint(showerror, err)
            statuses[idx] = :simulation_failed
        end
    end

    if sweep.executor isa ThreadedExecutor && Threads.nthreads() > 1 && length(points) > 1
        Threads.@threads for idx in eachindex(points)
            run_point!(idx)
        end
    else
        for idx in eachindex(points)
            run_point!(idx)
        end
    end

    return SweepResult(
        plan,
        results,
        statuses,
        copy(plan.warnings),
        Dict{Symbol,Any}(
            :points => points,
            :compile_policy => string(typeof(sweep.compile_policy)),
            :executor => string(typeof(sweep.executor)),
        ),
    )
end
