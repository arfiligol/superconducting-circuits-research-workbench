function inspect_plan(plan::CircuitPlan)
    return (
        id=plan.id,
        component_count=length(plan.components),
        relation_count=length(plan.relations),
        endpoint_count=length(plan.endpoints),
        parameter_count=length(plan.parameters),
        metadata_keys=sort(collect(keys(plan.metadata))),
    )
end

function inspect_parameters(plan::CircuitPlan)
    return [
        (
            name=meta.name,
            role=string(typeof(meta.role)),
            owner=meta.owner,
            targets=copy(meta.targets),
            sweep_name=meta.sweep_name,
            units=meta.units,
            assumptions=copy(meta.assumptions),
        )
        for meta in values(plan.parameters)
    ]
end

function inspect_endpoints(plan::CircuitPlan)
    endpoints = copy(plan.endpoints)
    for relation in plan.relations
        append!(endpoints, _relation_endpoints(relation))
    end
    return [_endpoint_summary(endpoint) for endpoint in endpoints]
end

function inspect_topology_key(compiled::JosephsonCompiledCircuit)
    key = topology_key(compiled)
    return (digest=key.digest, summary=key.summary)
end

function inspect_sweep_preflight(plan::SweepExecutionPlan)
    return (
        axis_count=length(plan.axes),
        estimated_compiles=plan.estimated_compiles,
        estimated_simulations=plan.estimated_simulations,
        topology_group_count=length(plan.topology_groups),
        executor=string(typeof(plan.executor)),
        compile_policy=string(typeof(plan.compile_policy)),
        warnings=copy(plan.warnings),
    )
end

function summarize_sweep_result(result::SweepResult)
    return (
        point_count=length(result.point_statuses),
        success_count=count(==(:success), result.point_statuses),
        compile_failed_count=count(==(:compile_failed), result.point_statuses),
        simulation_failed_count=count(==(:simulation_failed), result.point_statuses),
        warnings=copy(result.warnings),
    )
end

