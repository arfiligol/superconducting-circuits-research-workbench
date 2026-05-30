abstract type AbstractCircuitComponent end

struct CircuitComponentInstance <: AbstractCircuitComponent
    id::String
    template_id::Symbol
    pins::Dict{Symbol,Any}
    lines::Dict{Symbol,Any}
    probes::Dict{Symbol,Any}
    anchors::Dict{Symbol,Any}
    parameters::Vector{ParameterMetadata}
    metadata::Dict{Symbol,Any}
end

function component_id(component)
    throw(MethodError(component_id, (component,)))
end

function component_pins(component)
    throw(MethodError(component_pins, (component,)))
end

function component_lines(component)
    throw(MethodError(component_lines, (component,)))
end

function default_line(component)
    throw(MethodError(default_line, (component,)))
end

function component_parameters(component)
    throw(MethodError(component_parameters, (component,)))
end

component_id(component::CircuitComponentInstance) = component.id
component_pins(component::CircuitComponentInstance) = sort!(collect(keys(component.pins)); by=string)
component_lines(component::CircuitComponentInstance) = sort!(collect(keys(component.lines)); by=string)
default_line(component::CircuitComponentInstance) = length(component.lines) == 1 ? only(keys(component.lines)) : nothing
component_parameters(component::CircuitComponentInstance) = component.parameters

function _component_instance(
    id;
    template_id,
    pins=Dict{Symbol,Any}(),
    lines=Dict{Symbol,Any}(),
    probes=Dict{Symbol,Any}(),
    anchors=Dict{Symbol,Any}(),
    parameters=ParameterMetadata[],
    metadata=Dict{Symbol,Any}(),
)
    return CircuitComponentInstance(
        String(id),
        Symbol(template_id),
        Dict{Symbol,Any}(pins),
        Dict{Symbol,Any}(lines),
        Dict{Symbol,Any}(probes),
        Dict{Symbol,Any}(anchors),
        ParameterMetadata[parameters...],
        Dict{Symbol,Any}(metadata),
    )
end

function component_local_id(component_id, local_id)
    return "$(String(component_id))_$(String(Symbol(local_id)))"
end

function component_private_node(component_id, name)
    return external_node("$(String(component_id))_$(String(name))")
end

function _component_id_value(component)
    component isa AbstractString && return String(component)
    return String(component_id(component))
end
