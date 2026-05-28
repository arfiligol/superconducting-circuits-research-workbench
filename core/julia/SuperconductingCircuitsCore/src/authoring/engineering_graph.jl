struct EngineeringComponent
    id::Symbol
    display_name::String
    component_type::Symbol
    role::Symbol
    parameters::Dict{Symbol,Any}
    pins::Vector{Symbol}
    source_location::Any
end

struct EngineeringRelation
    id::Symbol
    relation_type::Symbol
    from::Any
    to::Any
    through::Any
    role::Symbol
    label::String
    parameters::Dict{Symbol,Any}
    source_location::Any
end

struct EngineeringPort
    id::Symbol
    component::Union{Nothing,Symbol}
    endpoint::Any
    port_index::Int
    role::Symbol
    resistance::Float64
    source_location::Any
end

struct EngineeringGroup
    id::Symbol
    label::String
    role::Symbol
    members::Vector{Any}
end

Base.@kwdef struct ExternalPort
    id::Symbol
    index::Int
    endpoint::AbstractCircuitEndpoint
    resistance::Float64
    role::Symbol
end

mutable struct EngineeringGraph
    components::Dict{Symbol,EngineeringComponent}
    relations::Vector{EngineeringRelation}
    ports::Dict{Symbol,EngineeringPort}
    groups::Dict{Symbol,EngineeringGroup}
    hb_overlay::Any
    metadata::Dict{Symbol,Any}
end

function external_port!(
    plan;
    id,
    index,
    endpoint,
    resistance=50.0,
    role=:mixed,
    source_location=nothing,
)
    endpoint isa AbstractCircuitEndpoint ||
        _validation_error("external_port! endpoint must be an AbstractCircuitEndpoint.")
    external = ExternalPort(
        id=Symbol(id),
        index=Int(index),
        endpoint=endpoint,
        resistance=Float64(resistance),
        role=Symbol(role),
    )
    port = record_engineering_port!(
        plan;
        id=external.id,
        endpoint=external.endpoint,
        index=external.index,
        role=external.role,
        resistance=external.resistance,
        source_location=source_location,
    )
    ports = get!(plan.metadata, :external_ports) do
        Dict{Symbol,ExternalPort}()
    end
    ports isa Dict{Symbol,ExternalPort} ||
        _validation_error("CircuitPlan metadata[:external_ports] is reserved for ExternalPort declarations.")
    haskey(ports, external.id) && _validation_error("Duplicate external port id '$(external.id)'.")
    ports[external.id] = external
    connect!(plan, external_node(string(port.id)), endpoint)
    return port
end

struct SchematicExportSpec
    components::Vector{Any}
    relations::Vector{Any}
    ports::Vector{Any}
    groups::Vector{Any}
    layout_hints::Dict{Symbol,Any}
    render_hints::Dict{Symbol,Any}
end

function EngineeringGraph(;
    components=Dict{Symbol,EngineeringComponent}(),
    relations=EngineeringRelation[],
    ports=Dict{Symbol,EngineeringPort}(),
    groups=Dict{Symbol,EngineeringGroup}(),
    hb_overlay=nothing,
    metadata=Dict{Symbol,Any}(),
)
    return EngineeringGraph(
        Dict{Symbol,EngineeringComponent}(components),
        EngineeringRelation[relations...],
        Dict{Symbol,EngineeringPort}(ports),
        Dict{Symbol,EngineeringGroup}(groups),
        hb_overlay,
        Dict{Symbol,Any}(metadata),
    )
end

engineering_graph(plan) = plan.engineering_graph

function record_engineering_component!(
    plan;
    id,
    display_name=nothing,
    component_type=:unknown,
    role=:component,
    parameters=Dict{Symbol,Any}(),
    pins=Symbol[],
    source_location=nothing,
)
    component_id = _engineering_symbol(id)
    component = EngineeringComponent(
        component_id,
        isnothing(display_name) ? String(component_id) : string(display_name),
        _engineering_symbol(component_type),
        _engineering_symbol(role),
        _engineering_dict(parameters),
        _engineering_symbol_vector(pins),
        source_location,
    )
    engineering_graph(plan).components[component_id] = component
    return component
end

function record_engineering_relation!(
    plan;
    id=nothing,
    relation_type,
    from,
    to,
    through=nothing,
    role=:relation,
    label="",
    parameters=Dict{Symbol,Any}(),
    source_location=nothing,
)
    relation_id = isnothing(id) ? _generated_relation_id(plan, relation_type) : _engineering_symbol(id)
    relation = EngineeringRelation(
        relation_id,
        _engineering_symbol(relation_type),
        from,
        to,
        through,
        _engineering_symbol(role),
        string(label),
        _engineering_dict(parameters),
        source_location,
    )
    push!(engineering_graph(plan).relations, relation)
    return relation
end

function record_engineering_port!(
    plan;
    id,
    component=nothing,
    endpoint=nothing,
    port_index=nothing,
    index=nothing,
    role=:mixed,
    resistance,
    source_location=nothing,
)
    selected_index = isnothing(port_index) ? index : port_index
    !isnothing(selected_index) || _validation_error("EngineeringPort '$(id)' requires port_index or index.")

    port_id = _engineering_symbol(id)
    port = EngineeringPort(
        port_id,
        _engineering_component_symbol(component, endpoint),
        endpoint,
        Int(selected_index),
        _engineering_symbol(role),
        Float64(resistance),
        source_location,
    )
    engineering_graph(plan).ports[port_id] = port
    return port
end

function record_engineering_group!(
    plan;
    id,
    label=nothing,
    role=:group,
    members=Any[],
)
    group_id = _engineering_symbol(id)
    group = EngineeringGroup(
        group_id,
        isnothing(label) ? String(group_id) : string(label),
        _engineering_symbol(role),
        Any[members...],
    )
    engineering_graph(plan).groups[group_id] = group
    return group
end

function to_dot(graph::EngineeringGraph)::String
    lines = String[
        "digraph EngineeringGraph {",
        "    rankdir=LR;",
    ]

    for id in sort!(collect(keys(graph.components)); by=string)
        component = graph.components[id]
        push!(
            lines,
            "    \"$(_dot_escape(id))\" [label=\"$(_dot_escape(component.display_name))\", shape=\"box\"];",
        )
    end

    for id in sort!(collect(keys(graph.ports)); by=string)
        port = graph.ports[id]
        push!(
            lines,
            "    \"$(_dot_escape(id))\" [label=\"$(_dot_escape(port.id))\", shape=\"oval\"];",
        )
        if !isnothing(port.component)
            push!(
                lines,
                "    \"$(_dot_escape(id))\" -> \"$(_dot_escape(port.component))\" [label=\"$(_dot_escape(port.role))\"];",
            )
        end
    end

    for relation in graph.relations
        from_id = _engineering_graph_node_id(relation.from)
        to_id = _engineering_graph_node_id(relation.to)
        label = isempty(relation.label) ? string(relation.relation_type) : relation.label
        push!(
            lines,
            "    \"$(_dot_escape(from_id))\" -> \"$(_dot_escape(to_id))\" [label=\"$(_dot_escape(label))\"];",
        )
    end

    push!(lines, "}")
    return join(lines, "\n")
end

function to_schemdraw_spec(graph::EngineeringGraph)::SchematicExportSpec
    components = Any[
        (
            id=component.id,
            label=component.display_name,
            schematic_kind=component.component_type,
            parameters=component.parameters,
            pins=component.pins,
            role=component.role,
        ) for component in _sorted_values(graph.components)
    ]

    relations = Any[
        (
            id=relation.id,
            from=_schematic_endpoint_ref(relation.from),
            to=_schematic_endpoint_ref(relation.to),
            through=_schematic_through_ref(relation.through),
            schematic_kind=relation.relation_type,
            label=relation.label,
            role=relation.role,
            parameters=relation.parameters,
            direction_hint=:right,
        ) for relation in graph.relations
    ]

    ports = Any[
        (
            id=port.id,
            component=port.component,
            endpoint=_schematic_endpoint_ref(port.endpoint),
            port_index=port.port_index,
            role=port.role,
            resistance=port.resistance,
        ) for port in _sorted_values(graph.ports)
    ]

    groups = Any[
        (
            id=group.id,
            label=group.label,
            role=group.role,
            members=group.members,
        ) for group in _sorted_values(graph.groups)
    ]

    return SchematicExportSpec(
        components,
        relations,
        ports,
        groups,
        Dict{Symbol,Any}(:layout => :auto),
        Dict{Symbol,Any}(:renderer => :schemdraw, :format => :renderer_neutral),
    )
end

function _engineering_symbol(value)
    value isa Symbol && return value
    value isa AbstractString && return Symbol(value)
    return Symbol(string(value))
end

function _engineering_symbol_vector(values)
    return Symbol[_engineering_symbol(value) for value in values]
end

function _engineering_dict(values)
    result = Dict{Symbol,Any}()
    for (key, value) in pairs(values)
        result[_engineering_symbol(key)] = value
    end
    return result
end

function _engineering_component_symbol(component, endpoint)
    !isnothing(component) && return _engineering_symbol(_component_id_value(component))
    endpoint isa PinEndpoint && return _engineering_symbol(endpoint.component_id)
    endpoint isa LineTapEndpoint && return _engineering_symbol(endpoint.line_ref.component_id)
    endpoint isa LineSpanEndpoint && return _engineering_symbol(endpoint.line_ref.component_id)
    endpoint isa LoopEndpoint && return _engineering_symbol(endpoint.component_id)
    return nothing
end

function _generated_relation_id(plan, relation_type)
    relation_count = length(engineering_graph(plan).relations) + 1
    return Symbol(_engineering_symbol(relation_type), "_", relation_count)
end

function _engineering_graph_node_id(value)
    value isa EngineeringPort && return value.id
    value isa EngineeringComponent && return value.id
    value isa Symbol && return value
    value isa AbstractString && return Symbol(value)
    value isa PinEndpoint && return Symbol(value.component_id)
    value isa LineTapEndpoint && return Symbol(value.line_ref.component_id)
    value isa LineSpanEndpoint && return Symbol(value.line_ref.component_id)
    value isa LoopEndpoint && return Symbol(value.component_id)
    value isa GroundEndpoint && return :ground
    value isa ExternalNodeEndpoint && return Symbol(value.name)
    return Symbol(string(value))
end

function _schematic_endpoint_ref(value)
    isnothing(value) && return nothing
    value isa PinEndpoint && return "$(value.component_id).$(value.pin)"
    value isa LineTapEndpoint && return "$(value.line_ref.component_id).$(value.line_ref.line)@$(value.at_m)"
    value isa LineSpanEndpoint && return "$(value.line_ref.component_id).$(value.line_ref.line):$(value.from_m)-$(value.to_m)"
    value isa LoopEndpoint && return "$(value.component_id).$(value.loop)"
    value isa GroundEndpoint && return "ground"
    value isa ExternalNodeEndpoint && return value.name
    value isa Symbol && return string(value)
    value isa AbstractString && return String(value)
    return string(value)
end

function _schematic_through_ref(value)
    isnothing(value) && return nothing
    value isa Symbol && return string(value)
    value isa AbstractString && return String(value)
    try
        return _component_id_value(value)
    catch
        return string(typeof(value))
    end
end

function _sorted_values(dict)
    return [dict[key] for key in sort!(collect(keys(dict)); by=string)]
end

_dot_escape(value) = replace(string(value), "\\" => "\\\\", "\"" => "\\\"")
