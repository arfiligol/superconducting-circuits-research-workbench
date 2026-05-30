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
    endpoint isa ProbeEndpoint && return [endpoint.component_id]
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
    relation isa JosephsonJunction && return AbstractCircuitEndpoint[relation.from, relation.to]
    relation isa InductiveCoupling && return AbstractCircuitEndpoint[relation.from, relation.to]
    relation isa MutualInductiveCoupling && return AbstractCircuitEndpoint[
        relation.inductor_a.from,
        relation.inductor_a.to,
        relation.inductor_b.from,
        relation.inductor_b.to,
    ]
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

function _relation_is_generated_by_owner(relation::AbstractCircuitRelation, owner::AbstractString)
    id = _relation_id(relation)
    isnothing(id) && return false
    return startswith(String(id), "$(owner)_")
end

function _external_terminal_satisfied(plan::CircuitPlan, requirement)
    endpoint = requirement.endpoint
    ports = get(plan.metadata, :external_ports, Dict{Symbol,ExternalPort}())
    if ports isa Dict
        any(port -> port.endpoint == endpoint, values(ports)) && return true
    end
    for relation in plan.relations
        _relation_is_generated_by_owner(relation, requirement.owner) && continue
        endpoint in _relation_endpoints(relation) && return true
    end
    return false
end

function _validate_external_terminations!(issues, plan::CircuitPlan)
    requirements = get(plan.metadata, :external_terminal_requirements, Any[])
    requirements isa Vector || return
    for requirement in requirements
        _external_terminal_satisfied(plan, requirement) && continue
        _issue!(
            issues,
            :error,
            :dangling_external_endpoint,
            "Transmission-line $(requirement.side) endpoint for '$(requirement.owner)' is declared :external but has no enclosing connection.",
            [:terminations];
            stage=:authoring,
            object_id=requirement.owner,
            expected="external port, component connection, or declared relation",
            actual="dangling external endpoint",
            hint="Use :open for an intentional open boundary, or connect the :external endpoint explicitly.",
            metadata=Dict{Symbol,Any}(:side => requirement.side, :endpoint => _endpoint_summary(requirement.endpoint)),
        )
    end
end

function _validate_schematic_layout!(issues, plan::CircuitPlan)
    layout = schematic_layout_intent(plan)
    track_ids = Set(keys(layout.tracks))

    for segment in values(layout.segments)
        segment.track in track_ids || _issue!(
            issues,
            :error,
            :unknown_schematic_track,
            "Schematic segment '$(segment.id)' references unknown track '$(segment.track)'.",
            [:schematic_layout, :segments];
            stage=:layout_validation,
            object_id=String(segment.id),
        )
    end

    for span in values(layout.coupled_spans)
        span.track1 in track_ids || _issue!(
            issues,
            :error,
            :unknown_schematic_track,
            "Schematic coupled span '$(span.id)' references unknown track '$(span.track1)'.",
            [:schematic_layout, :coupled_spans];
            stage=:layout_validation,
            object_id=String(span.id),
        )
        span.track2 in track_ids || _issue!(
            issues,
            :error,
            :unknown_schematic_track,
            "Schematic coupled span '$(span.id)' references unknown track '$(span.track2)'.",
            [:schematic_layout, :coupled_spans];
            stage=:layout_validation,
            object_id=String(span.id),
        )
        span.track1 != span.track2 || _issue!(
            issues,
            :error,
            :invalid_coupled_span_tracks,
            "Schematic coupled span '$(span.id)' must reference two distinct tracks.",
            [:schematic_layout, :coupled_spans];
            stage=:layout_validation,
            object_id=String(span.id),
        )
    end

    for terminal in values(layout.terminals)
        if !isnothing(terminal.track) && !(terminal.track in track_ids)
            _issue!(
                issues,
                :error,
                :unknown_schematic_track,
                "Schematic terminal '$(terminal.id)' references unknown track '$(terminal.track)'.",
                [:schematic_layout, :terminals];
                stage=:layout_validation,
                object_id=String(terminal.id),
            )
        end
    end

    for label in values(layout.segment_labels)
        if !isnothing(label.track) && !(label.track in track_ids)
            _issue!(
                issues,
                :error,
                :unknown_schematic_track,
                "Schematic segment label '$(label.id)' references unknown track '$(label.track)'.",
                [:schematic_layout, :segment_labels];
                stage=:layout_validation,
                object_id=String(label.id),
            )
        end
    end

    for anchor in values(layout.anchors)
        if anchor.target isa AbstractCircuitEndpoint
            _issue!(
                issues,
                :error,
                :electrical_anchor_target,
                "Schematic anchor '$(anchor.id)' targets an electrical endpoint.",
                [:schematic_layout, :anchors];
                stage=:layout_validation,
                object_id=String(anchor.id),
                hint="Use a pin, tap, probe, or terminal for connectable electrical points; anchors are non-electrical.",
            )
        end
    end
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

    _validate_external_terminations!(issues, plan)
    _validate_schematic_layout!(issues, plan)

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
