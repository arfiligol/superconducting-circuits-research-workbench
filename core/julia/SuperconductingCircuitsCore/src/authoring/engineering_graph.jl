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

struct SchematicLayoutGroup
    id::Symbol
    label::String
    role::Symbol
    members::Vector{Any}
    hints::Dict{Symbol,Any}
end

struct SchematicTrack
    id::Symbol
    line::Any
    orientation::Symbol
    relative_order::Symbol
    role::Symbol
    label::String
    hints::Dict{Symbol,Any}
end

struct SchematicSegment
    id::Symbol
    track::Symbol
    from_m::Float64
    to_m::Float64
    role::Symbol
    label::String
    hints::Dict{Symbol,Any}
end

struct SchematicCoupledSpan
    id::Symbol
    relation::Any
    track1::Symbol
    track2::Symbol
    from1_m::Union{Nothing,Float64}
    to1_m::Union{Nothing,Float64}
    from2_m::Union{Nothing,Float64}
    to2_m::Union{Nothing,Float64}
    align::Symbol
    label::String
    interface_nodes::Any
    render::Symbol
    hints::Dict{Symbol,Any}
end

struct SchematicTerminal
    id::Symbol
    endpoint::Any
    track::Union{Nothing,Symbol}
    side::Symbol
    kind::Symbol
    label::String
    hints::Dict{Symbol,Any}
end

struct SchematicNodeLabel
    id::Symbol
    target::Any
    label::String
    hints::Dict{Symbol,Any}
end

struct SchematicSegmentLabel
    id::Symbol
    line::Any
    track::Union{Nothing,Symbol}
    from_m::Float64
    to_m::Float64
    label::String
    hints::Dict{Symbol,Any}
end

struct SchematicAnchor
    id::Symbol
    target::Any
    role::Symbol
    label::String
    hints::Dict{Symbol,Any}
end

mutable struct SchematicLayoutIntent
    id::Symbol
    groups::Dict{Symbol,SchematicLayoutGroup}
    tracks::Dict{Symbol,SchematicTrack}
    segments::Dict{Symbol,SchematicSegment}
    coupled_spans::Dict{Symbol,SchematicCoupledSpan}
    terminals::Dict{Symbol,SchematicTerminal}
    node_labels::Dict{Symbol,SchematicNodeLabel}
    segment_labels::Dict{Symbol,SchematicSegmentLabel}
    anchors::Dict{Symbol,SchematicAnchor}
    layout_hints::Dict{Symbol,Any}
    render_hints::Dict{Symbol,Any}
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

struct SchematicExportSpec
    engineering_graph::EngineeringGraph
    layout_intent::SchematicLayoutIntent
    components::Vector{Any}
    relations::Vector{Any}
    ports::Vector{Any}
    groups::Vector{Any}
    tracks::Vector{Any}
    segments::Vector{Any}
    coupled_spans::Vector{Any}
    terminals::Vector{Any}
    node_labels::Vector{Any}
    segment_labels::Vector{Any}
    anchors::Vector{Any}
    layout_hints::Dict{Symbol,Any}
    render_hints::Dict{Symbol,Any}
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

function SchematicLayoutIntent(;
    id=:default,
    groups=Dict{Symbol,SchematicLayoutGroup}(),
    tracks=Dict{Symbol,SchematicTrack}(),
    segments=Dict{Symbol,SchematicSegment}(),
    coupled_spans=Dict{Symbol,SchematicCoupledSpan}(),
    terminals=Dict{Symbol,SchematicTerminal}(),
    node_labels=Dict{Symbol,SchematicNodeLabel}(),
    segment_labels=Dict{Symbol,SchematicSegmentLabel}(),
    anchors=Dict{Symbol,SchematicAnchor}(),
    layout_hints=Dict{Symbol,Any}(),
    render_hints=Dict{Symbol,Any}(),
)
    return SchematicLayoutIntent(
        _engineering_symbol(id),
        Dict{Symbol,SchematicLayoutGroup}(groups),
        Dict{Symbol,SchematicTrack}(tracks),
        Dict{Symbol,SchematicSegment}(segments),
        Dict{Symbol,SchematicCoupledSpan}(coupled_spans),
        Dict{Symbol,SchematicTerminal}(terminals),
        Dict{Symbol,SchematicNodeLabel}(node_labels),
        Dict{Symbol,SchematicSegmentLabel}(segment_labels),
        Dict{Symbol,SchematicAnchor}(anchors),
        Dict{Symbol,Any}(layout_hints),
        Dict{Symbol,Any}(render_hints),
    )
end

engineering_graph(plan) = plan.engineering_graph
schematic_layout_intent(plan) = plan.schematic_layout_intent

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

function record_schematic_group!(
    target;
    id,
    label=nothing,
    role=:group,
    members=Any[],
    hints=Dict{Symbol,Any}(),
    kwargs...,
)
    layout = _layout_intent(target)
    group_id = _engineering_symbol(id)
    group = SchematicLayoutGroup(
        group_id,
        isnothing(label) ? String(group_id) : string(label),
        _engineering_symbol(role),
        Any[members...],
        _merge_hints(hints, kwargs),
    )
    layout.groups[group_id] = group
    return group
end

function record_schematic_track!(
    target;
    id,
    line,
    orientation=:left_to_right,
    relative_order=:unspecified,
    role=:track,
    label=nothing,
    hints=Dict{Symbol,Any}(),
    kwargs...,
)
    layout = _layout_intent(target)
    track_id = _engineering_symbol(id)
    track = SchematicTrack(
        track_id,
        line,
        _engineering_symbol(orientation),
        _engineering_symbol(relative_order),
        _engineering_symbol(role),
        isnothing(label) ? String(track_id) : string(label),
        _merge_hints(hints, kwargs),
    )
    layout.tracks[track_id] = track
    return track
end

function record_schematic_segment!(
    target;
    id,
    track,
    from,
    to,
    role=:segment,
    label="",
    hints=Dict{Symbol,Any}(),
    kwargs...,
)
    layout = _layout_intent(target)
    track_id = _require_track(layout, track, "segment '$(id)'")
    from_value = Float64(from)
    to_value = Float64(to)
    _validate_interval(from_value, to_value, "segment '$(id)'")
    segment_id = _engineering_symbol(id)
    segment = SchematicSegment(
        segment_id,
        track_id,
        from_value,
        to_value,
        _engineering_symbol(role),
        string(label),
        _merge_hints(hints, kwargs),
    )
    layout.segments[segment_id] = segment
    return segment
end

function record_schematic_coupled_span!(
    target;
    id,
    relation,
    track1,
    track2,
    from1=nothing,
    to1=nothing,
    from2=nothing,
    to2=nothing,
    align=:start_and_end,
    label="",
    interface_nodes=nothing,
    render=:coupled_span,
    hints=Dict{Symbol,Any}(),
    kwargs...,
)
    layout = _layout_intent(target)
    track1_id = _require_track(layout, track1, "coupled span '$(id)' track1")
    track2_id = _require_track(layout, track2, "coupled span '$(id)' track2")
    track1_id == track2_id && _validation_error("Schematic coupled span '$(id)' requires two distinct tracks.")
    from1_value = _optional_float(from1)
    to1_value = _optional_float(to1)
    from2_value = _optional_float(from2)
    to2_value = _optional_float(to2)
    _validate_interval(from1_value, to1_value, "coupled span '$(id)' track1 interval")
    _validate_interval(from2_value, to2_value, "coupled span '$(id)' track2 interval")
    span_id = _engineering_symbol(id)
    span = SchematicCoupledSpan(
        span_id,
        relation,
        track1_id,
        track2_id,
        from1_value,
        to1_value,
        from2_value,
        to2_value,
        _engineering_symbol(align),
        string(label),
        interface_nodes,
        _engineering_symbol(render),
        _merge_hints(hints, kwargs),
    )
    layout.coupled_spans[span_id] = span
    return span
end

function record_schematic_terminal!(
    target;
    id,
    endpoint,
    track=nothing,
    side=:unspecified,
    kind=:terminal,
    label="",
    hints=Dict{Symbol,Any}(),
    kwargs...,
)
    layout = _layout_intent(target)
    terminal_id = _engineering_symbol(id)
    track_id = isnothing(track) ? nothing : _require_track(layout, track, "terminal '$(id)'")
    terminal = SchematicTerminal(
        terminal_id,
        endpoint,
        track_id,
        _engineering_symbol(side),
        _engineering_symbol(kind),
        string(label),
        _merge_hints(hints, kwargs),
    )
    layout.terminals[terminal_id] = terminal
    return terminal
end

function record_schematic_node_label!(
    owner;
    id,
    target,
    label,
    hints=Dict{Symbol,Any}(),
    kwargs...,
)
    layout = _layout_intent(owner)
    label_id = _engineering_symbol(id)
    node_label = SchematicNodeLabel(label_id, target, string(label), _merge_hints(hints, kwargs))
    layout.node_labels[label_id] = node_label
    return node_label
end

function record_schematic_segment_label!(
    target;
    id,
    line=nothing,
    track=nothing,
    from,
    to,
    label,
    hints=Dict{Symbol,Any}(),
    kwargs...,
)
    layout = _layout_intent(target)
    track_id = isnothing(track) ? nothing : _require_track(layout, track, "segment label '$(id)'")
    from_value = Float64(from)
    to_value = Float64(to)
    _validate_interval(from_value, to_value, "segment label '$(id)'")
    label_id = _engineering_symbol(id)
    segment_label = SchematicSegmentLabel(
        label_id,
        line,
        track_id,
        from_value,
        to_value,
        string(label),
        _merge_hints(hints, kwargs),
    )
    layout.segment_labels[label_id] = segment_label
    return segment_label
end

function record_schematic_anchor!(
    owner;
    id,
    target=nothing,
    role=:anchor,
    label=nothing,
    hints=Dict{Symbol,Any}(),
    kwargs...,
)
    layout = _layout_intent(owner)
    target isa AbstractCircuitEndpoint &&
        _validation_error("Schematic anchor '$(id)' is non-electrical; use a pin, tap, or probe for connectable endpoints.")
    anchor_id = _engineering_symbol(id)
    anchor = SchematicAnchor(
        anchor_id,
        target,
        _engineering_symbol(role),
        isnothing(label) ? String(anchor_id) : string(label),
        _merge_hints(hints, kwargs),
    )
    layout.anchors[anchor_id] = anchor
    return anchor
end

function schematic!(
    body::Function,
    plan;
    id=:default,
    layout_hints=Dict{Symbol,Any}(),
    render_hints=Dict{Symbol,Any}(),
)
    layout = schematic_layout_intent(plan)
    layout.id = _engineering_symbol(id)
    merge!(layout.layout_hints, _engineering_dict(layout_hints))
    merge!(layout.render_hints, _engineering_dict(render_hints))
    applicable(body, layout) ? body(layout) : body()
    return layout
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

function to_schematic_export_spec(plan)::SchematicExportSpec
    return to_schematic_export_spec(engineering_graph(plan), schematic_layout_intent(plan))
end

function to_schematic_export_spec(graph::EngineeringGraph, layout::SchematicLayoutIntent=SchematicLayoutIntent())::SchematicExportSpec
    components = Any[
        (
            id=component.id,
            label=component.display_name,
            component_type=component.component_type,
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
            relation_type=relation.relation_type,
            label=relation.label,
            role=relation.role,
            parameters=relation.parameters,
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
            source=:engineering_graph,
        ) for group in _sorted_values(graph.groups)
    ]
    append!(
        groups,
        Any[
            (
                id=group.id,
                label=group.label,
                role=group.role,
                members=group.members,
                hints=group.hints,
                source=:layout_intent,
            ) for group in _sorted_values(layout.groups)
        ],
    )

    tracks = Any[
        (
            id=track.id,
            line=_schematic_through_ref(track.line),
            orientation=track.orientation,
            relative_order=track.relative_order,
            role=track.role,
            label=track.label,
            hints=track.hints,
        ) for track in _sorted_values(layout.tracks)
    ]

    segments = Any[
        (
            id=segment.id,
            track=segment.track,
            from_m=segment.from_m,
            to_m=segment.to_m,
            role=segment.role,
            label=segment.label,
            hints=segment.hints,
        ) for segment in _sorted_values(layout.segments)
    ]

    coupled_spans = Any[
        (
            id=span.id,
            relation=_schematic_through_ref(span.relation),
            track1=span.track1,
            track2=span.track2,
            from1_m=span.from1_m,
            to1_m=span.to1_m,
            from2_m=span.from2_m,
            to2_m=span.to2_m,
            align=span.align,
            label=span.label,
            interface_nodes=span.interface_nodes,
            render=span.render,
            hints=span.hints,
        ) for span in _sorted_values(layout.coupled_spans)
    ]

    terminals = Any[
        (
            id=terminal.id,
            endpoint=_schematic_endpoint_ref(terminal.endpoint),
            track=terminal.track,
            side=terminal.side,
            kind=terminal.kind,
            label=terminal.label,
            hints=terminal.hints,
        ) for terminal in _sorted_values(layout.terminals)
    ]

    node_labels = Any[
        (
            id=label.id,
            target=_schematic_endpoint_ref(label.target),
            label=label.label,
            hints=label.hints,
        ) for label in _sorted_values(layout.node_labels)
    ]

    segment_labels = Any[
        (
            id=label.id,
            line=_schematic_through_ref(label.line),
            track=label.track,
            from_m=label.from_m,
            to_m=label.to_m,
            label=label.label,
            hints=label.hints,
        ) for label in _sorted_values(layout.segment_labels)
    ]

    anchors = Any[
        (
            id=anchor.id,
            target=_schematic_endpoint_ref(anchor.target),
            role=anchor.role,
            label=anchor.label,
            hints=anchor.hints,
        ) for anchor in _sorted_values(layout.anchors)
    ]

    return SchematicExportSpec(
        graph,
        layout,
        components,
        relations,
        ports,
        groups,
        tracks,
        segments,
        coupled_spans,
        terminals,
        node_labels,
        segment_labels,
        anchors,
        layout.layout_hints,
        layout.render_hints,
    )
end

function schematic_export_data(plan)
    return schematic_export_data(to_schematic_export_spec(plan))
end

function schematic_export_data(spec::SchematicExportSpec)
    return (
        schema_version=1,
        components=_json_safe(spec.components),
        relations=_json_safe(spec.relations),
        ports=_json_safe(spec.ports),
        groups=_json_safe(spec.groups),
        tracks=_json_safe(spec.tracks),
        segments=_json_safe(spec.segments),
        coupled_spans=_json_safe(spec.coupled_spans),
        terminals=_json_safe(spec.terminals),
        node_labels=_json_safe(spec.node_labels),
        segment_labels=_json_safe(spec.segment_labels),
        anchors=_json_safe(spec.anchors),
        layout_hints=_json_safe(spec.layout_hints),
        render_hints=_json_safe(spec.render_hints),
    )
end

function schematic_export_json(target)::String
    return sprint(JSON3.pretty, schematic_export_data(target)) * "\n"
end

function write_schematic_export_json(path, target)
    output_path = string(path)
    parent = dirname(output_path)
    isempty(parent) || mkpath(parent)
    open(output_path, "w") do io
        write(io, schematic_export_json(target))
    end
    return output_path
end

function _json_safe(value)
    isnothing(value) && return nothing
    value isa Bool && return value
    value isa Number && return value
    value isa AbstractString && return string(value)
    value isa Symbol && return string(value)
    value isa NamedTuple && return _json_safe_named_tuple(value)
    value isa AbstractDict && return _json_safe_dict(value)
    value isa AbstractVector && return Any[_json_safe(item) for item in value]
    value isa Tuple && return Any[_json_safe(item) for item in value]
    return string(value)
end

function _json_safe_named_tuple(value::NamedTuple)
    result = Dict{String,Any}()
    for key in keys(value)
        result[string(key)] = _json_safe(getfield(value, key))
    end
    return result
end

function _json_safe_dict(value::AbstractDict)
    result = Dict{String,Any}()
    for (key, item) in value
        result[string(key)] = _json_safe(item)
    end
    return result
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

function _merge_hints(hints, kwargs)
    merged = _engineering_dict(hints)
    for (key, value) in pairs(kwargs)
        merged[_engineering_symbol(key)] = value
    end
    return merged
end

function _layout_intent(target)
    target isa SchematicLayoutIntent && return target
    return schematic_layout_intent(target)
end

function _require_track(layout::SchematicLayoutIntent, track, context::AbstractString)
    track_id = _engineering_symbol(track)
    haskey(layout.tracks, track_id) ||
        _validation_error("Schematic $(context) references missing track '$(track_id)'.")
    return track_id
end

function _optional_float(value)
    isnothing(value) && return nothing
    return Float64(value)
end

function _validate_interval(from, to, context::AbstractString)
    if !isnothing(from) && !isnothing(to) && to <= from
        _validation_error("Schematic $(context) has invalid interval: to must be greater than from.")
    end
    return nothing
end

function _engineering_component_symbol(component, endpoint)
    !isnothing(component) && return _engineering_symbol(_component_id_value(component))
    endpoint isa PinEndpoint && return _engineering_symbol(endpoint.component_id)
    endpoint isa ProbeEndpoint && return _engineering_symbol(endpoint.component_id)
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
    value isa ProbeEndpoint && return Symbol(value.component_id)
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
    value isa ProbeEndpoint && return "$(value.component_id).$(value.probe)"
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
