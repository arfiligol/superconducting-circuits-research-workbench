Base.@kwdef struct ValidationIssue
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

function ValidationIssue(severity::Symbol, code::Symbol, message::AbstractString, path::Vector{Symbol})
    return ValidationIssue(severity=severity, code=code, message=String(message), path=copy(path))
end

struct ValidationReport
    issues::Vector{ValidationIssue}
end

ValidationReport() = ValidationReport(ValidationIssue[])

errors(report::ValidationReport) = [issue for issue in report.issues if issue.severity == :error]
warnings(report::ValidationReport) = [issue for issue in report.issues if issue.severity == :warning]
has_errors(report::ValidationReport) = !isempty(errors(report))

function _issue!(
    issues,
    severity::Symbol,
    code::Symbol,
    message::AbstractString,
    path=Symbol[];
    stage::Symbol=:unknown,
    object_id::Union{Nothing,String}=nothing,
    expected=nothing,
    actual=nothing,
    hint::Union{Nothing,String}=nothing,
    related_ids=String[],
    metadata=Dict{Symbol,Any}(),
)
    push!(
        issues,
        ValidationIssue(
            severity=severity,
            code=code,
            message=String(message),
            path=Symbol[path...],
            stage=stage,
            object_id=object_id,
            expected=expected,
            actual=actual,
            hint=hint,
            related_ids=String[string(id) for id in related_ids],
            metadata=Dict{Symbol,Any}(metadata),
        ),
    )
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
    relation isa ShuntInductor && return AbstractCircuitEndpoint[relation.at, ground()]
    relation isa SeriesInductor && return AbstractCircuitEndpoint[relation.from, relation.to]
    relation isa SeriesResistor && return AbstractCircuitEndpoint[relation.from, relation.to]
    relation isa InductiveCoupling && return AbstractCircuitEndpoint[relation.from, relation.to]
    relation isa CoupledWindowRelation && return AbstractCircuitEndpoint[relation.line_a, relation.line_b]
    return AbstractCircuitEndpoint[]
end

function _validate_endpoint_reference!(issues, plan::CircuitPlan, endpoint::AbstractCircuitEndpoint)
    for id in _endpoint_component_ids(endpoint)
        haskey(plan.components, id) ||
            _issue!(
                issues,
                :error,
                :unresolved_endpoint,
                "Endpoint references missing component '$(id)'.",
                [:relations];
                stage=:endpoint_resolution,
                object_id=id,
                expected="registered component id",
                actual="missing component reference",
                hint="Register component '$(id)' in the CircuitPlan before connecting or coupling its endpoints.",
                related_ids=[id],
                metadata=Dict{Symbol,Any}(:endpoint => _endpoint_summary(endpoint)),
            )
    end
end

function _validate_parameter_metadata!(issues, meta::ParameterMetadata, path)
    isempty(meta.owner) &&
        _issue!(
            issues,
            :error,
            :missing_parameter_owner,
            "Parameter '$(meta.name)' is missing an owner.",
            path;
            stage=:parameter_classification,
            object_id=String(meta.name),
            expected="non-empty parameter owner",
            actual=meta.owner,
            hint="Declare the component, relation, or plan builder that introduced this parameter.",
            metadata=Dict{Symbol,Any}(:sweep_name => meta.sweep_name, :role => string(typeof(meta.role))),
        )
end

function validate_authoring(plan::CircuitPlan)::ValidationReport
    issues = ValidationIssue[]

    for id in plan.duplicate_component_ids
        _issue!(
            issues,
            :error,
            :duplicate_component_id,
            "Duplicate component id '$(id)'.",
            [:components];
            stage=:authoring,
            object_id=id,
            expected="unique component id",
            actual="duplicate component id",
            hint="Use unique component IDs before registering components in the CircuitPlan.",
            related_ids=[id],
        )
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
            _issue!(
                issues,
                :error,
                :duplicate_relation_id,
                "Duplicate relation id '$(id)'.",
                [:relations];
                stage=:relation_validation,
                object_id=id,
                expected="unique relation id",
                actual="duplicate relation id",
                hint="Use unique relation IDs for couplings and named relations.",
                related_ids=[id],
            )
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
                [:components];
                stage=:compile_validation,
                object_id=id,
                expected="component_id, component_pins, component_lines, default_line, and component_parameters methods",
                actual=sprint(showerror, err),
                hint="Implement the Julia Core component interface for this component-library object.",
                related_ids=[id],
            )
        end
    end

    return ValidationReport(issues)
end
