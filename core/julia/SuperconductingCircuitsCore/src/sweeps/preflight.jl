function _role_report(sweep::SweepSpec)
    return Dict{Symbol,Any}(
        name => Dict{Symbol,Any}(
            :declared_role => _axis_role_symbol(axis),
            :effective_role => _axis_role_symbol(axis),
            :declaration_source => :SweepSpec,
        )
        for (name, axis) in sweep.axes
    )
end

function _has_structural_axis(sweep::SweepSpec)
    return any(axis -> axis isa StructuralAxis, values(sweep.axes))
end

function _build_plan_for_point(build_plan, point)
    plan = build_plan(point)
    plan isa CircuitPlan || _validation_error("build_plan must return a CircuitPlan, got $(typeof(plan)).")
    return plan
end

function preflight_sweep(build_plan, sweep::SweepSpec)::SweepExecutionPlan
    points = _sweep_points(sweep)
    warnings = String[]
    topology_groups = Dict{String,Vector{Int}}()

    if sweep.compile_policy isa CompileOnce
        plan = _build_plan_for_point(build_plan, first(points))
        key = topology_key(plan)
        topology_groups[key.digest] = collect(eachindex(points))
        estimated_compiles = 1
        _has_structural_axis(sweep) &&
            push!(warnings, "CompileOnce was requested with structural axes; compile reuse must be validated carefully.")
    elseif sweep.compile_policy isa CompileEveryPoint
        for idx in eachindex(points)
            plan = _build_plan_for_point(build_plan, points[idx])
            key = topology_key(plan)
            topology_groups["$(key.digest)#$(idx)"] = [idx]
        end
        estimated_compiles = length(points)
    else
        for idx in eachindex(points)
            plan = _build_plan_for_point(build_plan, points[idx])
            key = topology_key(plan)
            push!(get!(topology_groups, key.digest, Int[]), idx)
        end
        estimated_compiles = length(topology_groups)
    end

    sweep.executor isa RunnerExecutor &&
        push!(warnings, "RunnerExecutor is an interface placeholder in Core v1; Runner task integration is not implemented.")

    return SweepExecutionPlan(
        sweep,
        sweep.compile_policy,
        sweep.executor,
        sweep.acceleration_policy,
        sweep.axes,
        _role_report(sweep),
        topology_groups,
        estimated_compiles,
        length(points),
        warnings,
    )
end

