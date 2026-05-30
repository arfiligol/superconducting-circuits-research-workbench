struct TopologyKey
    digest::String
    summary::Dict{Symbol,Any}
end

function _endpoint_summary(endpoint::AbstractCircuitEndpoint)
    endpoint isa PinEndpoint && return (:pin, endpoint.component_id, endpoint.pin)
    endpoint isa ProbeEndpoint && return (:probe, endpoint.component_id, endpoint.probe)
    endpoint isa LineTapEndpoint && return (:line_tap, endpoint.line_ref.component_id, endpoint.line_ref.line, endpoint.at_m)
    endpoint isa LineSpanEndpoint && return (:line_span, endpoint.line_ref.component_id, endpoint.line_ref.line, endpoint.from_m, endpoint.to_m)
    endpoint isa GroundEndpoint && return (:ground,)
    endpoint isa ExternalNodeEndpoint && return (:external_node, endpoint.name)
    endpoint isa LoopEndpoint && return (:loop, endpoint.component_id, endpoint.loop)
    return (:unknown_endpoint, string(typeof(endpoint)))
end

function _relation_summary(relation::AbstractCircuitRelation)
    relation isa NodeConnection && return (:connect, _endpoint_summary(relation.a), _endpoint_summary(relation.b))
    relation isa CapacitiveCoupling &&
        return (:capacitive, relation.id, _endpoint_summary(relation.from), _endpoint_summary(relation.to))
    relation isa ShuntCapacitor && return (:shunt_capacitor, relation.id, _endpoint_summary(relation.at))
    relation isa ShuntInductor && return (:shunt_inductor, relation.id, _endpoint_summary(relation.at))
    relation isa SeriesInductor &&
        return (:series_inductor, relation.id, _endpoint_summary(relation.from), _endpoint_summary(relation.to))
    relation isa SeriesResistor &&
        return (:series_resistor, relation.id, _endpoint_summary(relation.from), _endpoint_summary(relation.to))
    relation isa JosephsonJunction &&
        return (:josephson_junction, relation.id, _endpoint_summary(relation.from), _endpoint_summary(relation.to))
    relation isa InductiveCoupling &&
        return (:inductive, relation.id, _endpoint_summary(relation.from), _endpoint_summary(relation.to))
    relation isa MutualInductiveCoupling &&
        return (:mutual_inductive, relation.id, relation.inductor_a.id, relation.inductor_b.id)
    relation isa CoupledWindowRelation &&
        return (:coupled_window, relation.id, _endpoint_summary(relation.line_a), _endpoint_summary(relation.line_b), string(typeof(relation.spec)))
    return (:unknown_relation, string(typeof(relation)))
end

function _component_summary(plan::CircuitPlan)
    ids = sort(collect(keys(plan.components)))
    return [(id=id, type=string(typeof(plan.components[id]))) for id in ids]
end

function _structural_parameter_summary(parameters::Dict{Symbol,ParameterMetadata})
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
        if meta.role isa StructuralParameter
    ]
end

function _topology_summary(plan::CircuitPlan)
    ordered = (
        components=_component_summary(plan),
        relations=sort([_relation_summary(relation) for relation in plan.relations]; by=repr),
        structural_parameters=_structural_parameter_summary(plan.parameters),
    )
    return ordered
end

function topology_key(plan::CircuitPlan)::TopologyKey
    ordered = _topology_summary(plan)
    digest = bytes2hex(sha1(repr(ordered)))
    return TopologyKey(
        digest,
        Dict{Symbol,Any}(
            :plan_id => plan.id,
            :component_count => length(plan.components),
            :relation_count => length(plan.relations),
            :structural_parameters => [item.name for item in ordered.structural_parameters],
            :components => collect(ordered.components),
            :relations => collect(ordered.relations),
            :structural_parameter_details => collect(ordered.structural_parameters),
        ),
    )
end

function topology_key(compiled::JosephsonCompiledCircuit)::TopologyKey
    value = get(compiled.metadata, :topology_key, nothing)
    value isa TopologyKey && return value
    digest = bytes2hex(sha1(repr((netlist_length=length(compiled.netlist), metadata=compiled.metadata))))
    return TopologyKey(digest, Dict{Symbol,Any}(:compiled => true))
end
