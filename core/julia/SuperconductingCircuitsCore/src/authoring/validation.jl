struct ValidationIssue
    severity::Symbol
    code::Symbol
    message::String
    path::Vector{Symbol}
end

struct ValidationReport
    issues::Vector{ValidationIssue}
end

ValidationReport() = ValidationReport(ValidationIssue[])

errors(report::ValidationReport) = [issue for issue in report.issues if issue.severity == :error]
warnings(report::ValidationReport) = [issue for issue in report.issues if issue.severity == :warning]
has_errors(report::ValidationReport) = !isempty(errors(report))

function _issue!(issues, severity::Symbol, code::Symbol, message::AbstractString, path=Symbol[])
    push!(issues, ValidationIssue(severity, code, String(message), Symbol[path...]))
end

function _endpoint_component_ids(endpoint::AbstractCircuitEndpoint)
    endpoint isa PinEndpoint && return [endpoint.component_id]
    endpoint isa LineTapEndpoint && return [endpoint.line_ref.component_id]
    endpoint isa LineSpanEndpoint && return [endpoint.line_ref.component_id]
    endpoint isa LoopEndpoint && return [endpoint.component_id]
    return String[]
end

function _relation_endpoints(relation::AbstractCircuitRelation)
    relation isa NodeConnection && return AbstractCircuitEndpoint[relation.a, relation.b]
    relation isa CapacitiveCoupling && return AbstractCircuitEndpoint[relation.from, relation.to]
    relation isa ShuntCapacitor && return AbstractCircuitEndpoint[relation.at, ground()]
    relation isa InductiveCoupling && return AbstractCircuitEndpoint[relation.from, relation.to]
    relation isa CoupledWindowRelation && return AbstractCircuitEndpoint[relation.line_a, relation.line_b]
    return AbstractCircuitEndpoint[]
end

function _validate_endpoint_reference!(issues, plan::CircuitPlan, endpoint::AbstractCircuitEndpoint)
    for id in _endpoint_component_ids(endpoint)
        haskey(plan.components, id) ||
            _issue!(issues, :error, :unresolved_endpoint, "Endpoint references missing component '$(id)'.", [:relations])
    end
end

function _validate_parameter_metadata!(issues, meta::ParameterMetadata, path)
    isempty(meta.owner) && _issue!(issues, :error, :missing_parameter_owner, "Parameter '$(meta.name)' is missing an owner.", path)
end

function validate_authoring(plan::CircuitPlan)::ValidationReport
    issues = ValidationIssue[]

    for id in plan.duplicate_component_ids
        _issue!(issues, :error, :duplicate_component_id, "Duplicate component id '$(id)'.", [:components])
    end

    relation_ids = String[]
    for relation in plan.relations
        id = _relation_id(relation)
        !isnothing(id) && push!(relation_ids, id)
        for endpoint in _relation_endpoints(relation)
            _validate_endpoint_reference!(issues, plan, endpoint)
        end
        for meta in relation_parameters(relation)
            _validate_parameter_metadata!(issues, meta, [:relations])
        end
    end

    seen = Set{String}()
    for id in relation_ids
        if id in seen
            _issue!(issues, :error, :duplicate_relation_id, "Duplicate relation id '$(id)'.", [:relations])
        end
        push!(seen, id)
    end

    for meta in values(plan.parameters)
        _validate_parameter_metadata!(issues, meta, [:parameters])
    end

    return ValidationReport(issues)
end

function validate_compile_ready(plan::CircuitPlan)::ValidationReport
    report = validate_authoring(plan)
    issues = copy(report.issues)

    for (id, component) in plan.components
        try
            component_id(component)
            component_pins(component)
            component_lines(component)
            default_line(component)
            component_parameters(component)
        catch err
            _issue!(
                issues,
                :error,
                :missing_component_interface,
                "Component '$(id)' does not satisfy the Julia Core component interface: $(sprint(showerror, err))",
                [:components],
            )
        end
    end

    return ValidationReport(issues)
end

