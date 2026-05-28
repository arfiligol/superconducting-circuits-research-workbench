function _validation_message(report::ValidationReport)
    return join([string(issue.code, ": ", issue.message) for issue in errors(report)], "; ")
end

function compile_to_josephson(plan::CircuitPlan)::JosephsonCompiledCircuit
    report = validate_compile_ready(plan)
    if has_errors(report)
        _validation_error("CircuitPlan '$(plan.id)' is not compile-ready: $(_validation_message(report))")
    end

    key = topology_key(plan)
    warning_messages = [
        "compile_to_josephson skeleton emitted an empty target netlist; full lowering is not implemented yet.",
    ]

    return JosephsonCompiledCircuit(
        netlist=Any[],
        component_values=Dict{Symbol,Any}(),
        node_map=Dict{Any,String}(),
        component_map=Dict{String,Vector{Int}}(),
        line_tap_map=Dict{Any,Any}(),
        warnings=warning_messages,
        provenance=Dict{Symbol,Any}(
            :plan_id => plan.id,
            :compiler => :josephson_skeleton,
            :topology_key => key.digest,
        ),
        metadata=Dict{Symbol,Any}(
            :topology_key => key,
            :validation_issue_count => length(report.issues),
        ),
    )
end

