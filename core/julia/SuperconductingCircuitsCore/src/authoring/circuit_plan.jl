abstract type AbstractCircuitRelation end

include("engineering_graph.jl")

mutable struct CircuitPlan
    id::String
    components::Dict{String,Any}
    endpoints::Vector{AbstractCircuitEndpoint}
    relations::Vector{AbstractCircuitRelation}
    parameters::Dict{Symbol,ParameterMetadata}
    engineering_graph::EngineeringGraph
    schematic_layout_intent::SchematicLayoutIntent
    metadata::Dict{Symbol,Any}
    duplicate_component_ids::Vector{String}
end

function CircuitPlan(; id::AbstractString, metadata=Dict{Symbol,Any}())
    return CircuitPlan(
        String(id),
        Dict{String,Any}(),
        AbstractCircuitEndpoint[],
        AbstractCircuitRelation[],
        Dict{Symbol,ParameterMetadata}(),
        EngineeringGraph(),
        SchematicLayoutIntent(),
        Dict{Symbol,Any}(metadata),
        String[],
    )
end

CircuitPlan(id::AbstractString) = CircuitPlan(; id=id)

function register_component!(
    plan::CircuitPlan,
    component;
    display_name=nothing,
    role=:component,
    component_type=nothing,
    source_location=nothing,
)
    id = _component_id_value(component)
    if haskey(plan.components, id)
        push!(plan.duplicate_component_ids, id)
    end
    plan.components[id] = component
    for meta in component_parameters(component)
        register_parameter!(plan, meta)
    end
    if !isnothing(display_name) || role != :component || !isnothing(component_type) || !isnothing(source_location)
        record_engineering_component!(
            plan;
            id=Symbol(id),
            display_name=isnothing(display_name) ? id : display_name,
            component_type=isnothing(component_type) ? Symbol(nameof(typeof(component))) : component_type,
            role=role,
            parameters=Dict(meta.name => meta for meta in component_parameters(component)),
            pins=component_pins(component),
            source_location=source_location,
        )
    end
    return component
end

function register_parameter!(plan::CircuitPlan, meta::ParameterMetadata)
    plan.parameters[meta.name] = meta
    return meta
end
