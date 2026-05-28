Base.@kwdef struct DiagnosticIssue
    severity::Symbol
    code::Symbol
    message::String
    path::Vector{Symbol} = Symbol[]
    stage::Symbol = :unknown
    object_id::Union{Nothing,String} = nothing
    expected::Any = nothing
    actual::Any = nothing
    hint::Union{Nothing,String} = nothing
    related_ids::Vector{String} = String[]
    metadata::Dict{Symbol,Any} = Dict{Symbol,Any}()
end

struct DiagnosticReport
    issues::Vector{DiagnosticIssue}
    summary::Dict{Symbol,Any}
end

DiagnosticReport(issues::Vector{DiagnosticIssue}) =
    DiagnosticReport(issues, _diagnostic_summary(issues))

diagnostic_errors(report::DiagnosticReport) = [issue for issue in report.issues if issue.severity == :error]
diagnostic_warnings(report::DiagnosticReport) = [issue for issue in report.issues if issue.severity == :warning]
has_diagnostic_errors(report::DiagnosticReport) = !isempty(diagnostic_errors(report))

function _diagnostic_summary(issues; extra=Dict{Symbol,Any}())
    summary = Dict{Symbol,Any}(
        :issue_count => length(issues),
        :error_count => count(issue -> issue.severity == :error, issues),
        :warning_count => count(issue -> issue.severity == :warning, issues),
    )
    merge!(summary, Dict{Symbol,Any}(extra))
    return summary
end

function _diagnostic_issue(issue::ValidationIssue)
    return DiagnosticIssue(
        severity=issue.severity,
        code=issue.code,
        message=issue.message,
        path=copy(issue.path),
        stage=issue.stage,
        object_id=issue.object_id,
        expected=issue.expected,
        actual=issue.actual,
        hint=issue.hint,
        related_ids=copy(issue.related_ids),
        metadata=Dict{Symbol,Any}(issue.metadata),
    )
end

function _diagnostic_report(report::ValidationReport; summary=Dict{Symbol,Any}())
    issues = [_diagnostic_issue(issue) for issue in report.issues]
    return DiagnosticReport(issues, _diagnostic_summary(issues; extra=summary))
end

function _endpoint_summaries(plan::CircuitPlan)
    endpoint_summaries = Any[_endpoint_summary(endpoint) for endpoint in plan.endpoints]
    for relation in plan.relations
        append!(endpoint_summaries, [_endpoint_summary(endpoint) for endpoint in _relation_endpoints(relation)])
    end
    return endpoint_summaries
end

function _endpoint_summaries_by_kind(plan::CircuitPlan, kind::Symbol)
    return [summary for summary in _endpoint_summaries(plan) if summary isa Tuple && !isempty(summary) && first(summary) == kind]
end

function _runtime_parameter_summary(parameters::Dict{Symbol,ParameterMetadata})
    names = sort(collect(keys(parameters)))
    return [
        (
            name=meta.name,
            owner=meta.owner,
            targets=sort(copy(meta.targets)),
            sweep_name=meta.sweep_name,
            role=string(typeof(meta.role)),
        )
        for name in names
        for meta in (parameters[name],)
        if !(meta.role isa StructuralParameter)
    ]
end

function diagnose_plan(plan::CircuitPlan)::DiagnosticReport
    report = validate_authoring(plan)
    relation_endpoint_count = sum(relation -> length(_relation_endpoints(relation)), plan.relations; init=0)
    summary = Dict{Symbol,Any}(
        :stage => :authoring,
        :plan_id => plan.id,
        :component_count => length(plan.components),
        :relation_count => length(plan.relations),
        :endpoint_count => length(plan.endpoints),
        :relation_endpoint_count => relation_endpoint_count,
        :parameter_count => length(plan.parameters),
        :duplicate_component_ids => copy(plan.duplicate_component_ids),
        :unresolved_endpoint_count => count(issue -> issue.code == :unresolved_endpoint, report.issues),
        :duplicate_relation_count => count(issue -> issue.code == :duplicate_relation_id, report.issues),
        :missing_parameter_owner_count => count(issue -> issue.code == :missing_parameter_owner, report.issues),
    )
    return _diagnostic_report(report; summary=summary)
end

function diagnose_compile(plan::CircuitPlan)::DiagnosticReport
    validation = validate_compile_ready(plan)
    issues = [_diagnostic_issue(issue) for issue in validation.issues]
    key = nothing
    compiled = nothing
    compile_ready = !has_errors(validation)

    if !compile_ready
        push!(
            issues,
            DiagnosticIssue(
                severity=:error,
                code=:compile_not_ready,
                message="CircuitPlan '$(plan.id)' is not compile-ready.",
                path=[:compiler],
                stage=:compile_validation,
                object_id=plan.id,
                expected="plan with no compile-ready validation errors",
                actual="$(length(errors(validation))) validation error(s)",
                hint="Resolve compile validation issues before target lowering.",
                metadata=Dict{Symbol,Any}(:validation_error_count => length(errors(validation))),
            ),
        )
    else
        try
            key = topology_key(plan)
            compiled = compile_to_josephson(plan)
            for (idx, warning) in enumerate(compiled.warnings)
                push!(
                    issues,
                    DiagnosticIssue(
                        severity=:warning,
                        code=:compiler_warning,
                        message=warning,
                        path=[:compiler],
                        stage=:compile_lowering,
                        object_id=plan.id,
                        hint="Inspect JosephsonCompiledCircuit.warnings and compiler provenance.",
                        metadata=Dict{Symbol,Any}(:warning_index => idx),
                    ),
                )
            end
        catch err
            compile_ready = false
            push!(
                issues,
                DiagnosticIssue(
                    severity=:error,
                    code=:compile_failed,
                    message="compile_to_josephson failed for CircuitPlan '$(plan.id)': $(sprint(showerror, err))",
                    path=[:compiler],
                    stage=:compile_lowering,
                    object_id=plan.id,
                    expected="JosephsonCompiledCircuit",
                    actual=sprint(showerror, err),
                    hint="Inspect compile-ready validation issues, endpoint resolution, and topology key inputs.",
                    metadata=Dict{Symbol,Any}(:error_type => string(typeof(err))),
                ),
            )
        end
    end

    summary = Dict{Symbol,Any}(
        :stage => :compile_validation,
        :plan_id => plan.id,
        :compile_ready => compile_ready,
        :topology_key => isnothing(key) ? nothing : key.digest,
        :topology_summary => isnothing(key) ? nothing : key.summary,
        :compiled_warning_count => isnothing(compiled) ? 0 : length(compiled.warnings),
    )
    return DiagnosticReport(issues, _diagnostic_summary(issues; extra=summary))
end

function diagnose_sweep(build_plan, sweep::SweepSpec)::DiagnosticReport
    issues = DiagnosticIssue[]
    preflight = nothing

    try
        preflight = preflight_sweep(build_plan, sweep)
        for (idx, warning) in enumerate(preflight.warnings)
            push!(
                issues,
                DiagnosticIssue(
                    severity=:warning,
                    code=:sweep_preflight_warning,
                    message=warning,
                    path=[:sweep],
                    stage=:sweep_preflight,
                    hint="Inspect SweepExecutionPlan warnings before running the sweep.",
                    metadata=Dict{Symbol,Any}(:warning_index => idx),
                ),
            )
        end
    catch err
        push!(
            issues,
            DiagnosticIssue(
                severity=:error,
                code=:sweep_preflight_failed,
                message="preflight_sweep failed: $(sprint(showerror, err))",
                path=[:sweep],
                stage=:sweep_preflight,
                expected="SweepExecutionPlan",
                actual=sprint(showerror, err),
                hint="Check build_plan output, sweep axes, parameter classification, and topology-key grouping inputs.",
                metadata=Dict{Symbol,Any}(:error_type => string(typeof(err))),
            ),
        )
    end

    summary = Dict{Symbol,Any}(
        :stage => :sweep_preflight,
        :axis_count => length(sweep.axes),
        :executor => string(typeof(sweep.executor)),
        :compile_policy => string(typeof(sweep.compile_policy)),
        :classification_policy => string(typeof(sweep.classification_policy)),
        :topology_group_count => isnothing(preflight) ? nothing : length(preflight.topology_groups),
        :estimated_compiles => isnothing(preflight) ? nothing : preflight.estimated_compiles,
        :estimated_simulations => isnothing(preflight) ? nothing : preflight.estimated_simulations,
    )
    return DiagnosticReport(issues, _diagnostic_summary(issues; extra=summary))
end

function explain_topology_key(plan::CircuitPlan)
    key = topology_key(plan)
    ordered = _topology_summary(plan)
    return (
        digest=key.digest,
        components_included=collect(ordered.components),
        relations_included=collect(ordered.relations),
        line_taps_included=_endpoint_summaries_by_kind(plan, :line_tap),
        line_spans_included=_endpoint_summaries_by_kind(plan, :line_span),
        structural_parameters_included=collect(ordered.structural_parameters),
        numeric_parameters_excluded=_runtime_parameter_summary(plan.parameters),
        summary=key.summary,
    )
end

function _collect_tuple_kind!(matches, value, kind::Symbol)
    if value isa Tuple
        if !isempty(value) && first(value) == kind
            push!(matches, value)
        end
        for item in value
            _collect_tuple_kind!(matches, item, kind)
        end
    elseif value isa NamedTuple
        for item in values(value)
            _collect_tuple_kind!(matches, item, kind)
        end
    elseif value isa AbstractVector
        for item in value
            _collect_tuple_kind!(matches, item, kind)
        end
    end
    return matches
end

function explain_topology_key(compiled::JosephsonCompiledCircuit)
    key = topology_key(compiled)
    relations = get(key.summary, :relations, Any[])
    return (
        digest=key.digest,
        components_included=get(key.summary, :components, Any[]),
        relations_included=relations,
        line_taps_included=_collect_tuple_kind!(Any[], relations, :line_tap),
        line_spans_included=_collect_tuple_kind!(Any[], relations, :line_span),
        structural_parameters_included=get(key.summary, :structural_parameter_details, Any[]),
        numeric_parameters_excluded=Any[],
        summary=key.summary,
    )
end

function _component_ids_from_explanation(explanation)
    return Set(String(item.id) for item in explanation.components_included)
end

function _repr_set(values)
    return Set(repr(value) for value in values)
end

function diff_topology_keys(plan_a::CircuitPlan, plan_b::CircuitPlan)
    explanation_a = explain_topology_key(plan_a)
    explanation_b = explain_topology_key(plan_b)
    components_a = _component_ids_from_explanation(explanation_a)
    components_b = _component_ids_from_explanation(explanation_b)
    relations_a = _repr_set(explanation_a.relations_included)
    relations_b = _repr_set(explanation_b.relations_included)
    structural_a = _repr_set(explanation_a.structural_parameters_included)
    structural_b = _repr_set(explanation_b.structural_parameters_included)
    same_digest = explanation_a.digest == explanation_b.digest

    return (
        same_digest=same_digest,
        digest_a=explanation_a.digest,
        digest_b=explanation_b.digest,
        added_components=sort(collect(setdiff(components_b, components_a))),
        removed_components=sort(collect(setdiff(components_a, components_b))),
        added_relations=sort(collect(setdiff(relations_b, relations_a))),
        removed_relations=sort(collect(setdiff(relations_a, relations_b))),
        changed_relations=sort(collect(symdiff(relations_a, relations_b))),
        changed_structural_parameters=sort(collect(symdiff(structural_a, structural_b))),
        hint=same_digest ? "Topology keys match; compiled output can be reused if validation also passes." :
             "Topology keys differ; inspect components, relation endpoints, line taps/spans, and structural parameters.",
    )
end

function _compiled_summary(compiled::JosephsonCompiledCircuit)
    return (
        netlist_row_count=length(compiled.netlist),
        component_value_count=length(compiled.component_values),
        node_map_count=length(compiled.node_map),
        component_map_count=length(compiled.component_map),
        line_tap_map_count=length(compiled.line_tap_map),
        warning_count=length(compiled.warnings),
        provenance_keys=sort(collect(keys(compiled.provenance))),
        metadata_keys=sort(collect(keys(compiled.metadata))),
    )
end

function _recommended_next_checks(authoring_report::DiagnosticReport, compile_report::DiagnosticReport, preflight, result)
    checks = String[]
    has_diagnostic_errors(authoring_report) &&
        push!(checks, "Fix authoring diagnostics first: duplicate IDs, unresolved endpoints, and parameter metadata.")
    has_diagnostic_errors(compile_report) &&
        push!(checks, "Inspect compile diagnostics, endpoint resolution, component interface methods, and topology-key inputs.")
    !isnothing(preflight) && !isempty(preflight.warnings) &&
        push!(checks, "Review SweepExecutionPlan warnings before running an expensive sweep.")
    !isnothing(result) && any(status -> status != :success, result.point_statuses) &&
        push!(checks, "Inspect failed sweep point statuses and point-level results.")
    isempty(checks) && push!(checks, "No blocking diagnostics found; inspect topology explanation, compiler warnings, or sweep preflight next.")
    return checks
end

function debug_bundle(plan::CircuitPlan; compiled=nothing, preflight=nothing, result=nothing)
    authoring_diagnostics = diagnose_plan(plan)
    compile_diagnostics = diagnose_compile(plan)
    topology_source = isnothing(compiled) ? plan : compiled

    return (
        plan_summary=inspect_plan(plan),
        parameter_summary=inspect_parameters(plan),
        endpoint_summary=inspect_endpoints(plan),
        authoring_diagnostics=authoring_diagnostics,
        compile_diagnostics=compile_diagnostics,
        topology_explanation=explain_topology_key(topology_source),
        compiled_summary=isnothing(compiled) ? nothing : _compiled_summary(compiled),
        preflight_summary=isnothing(preflight) ? nothing : inspect_sweep_preflight(preflight),
        sweep_result_summary=isnothing(result) ? nothing : summarize_sweep_result(result),
        recommended_next_checks=_recommended_next_checks(authoring_diagnostics, compile_diagnostics, preflight, result),
    )
end
