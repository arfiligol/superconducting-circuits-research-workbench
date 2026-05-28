abstract type AbstractCircuitRelation end

mutable struct CircuitPlan
    id::String
    components::Dict{String,Any}
    endpoints::Vector{AbstractCircuitEndpoint}
    relations::Vector{AbstractCircuitRelation}
    parameters::Dict{Symbol,ParameterMetadata}
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
        Dict{Symbol,Any}(metadata),
        String[],
    )
end

CircuitPlan(id::AbstractString) = CircuitPlan(; id=id)

function register_component!(plan::CircuitPlan, component)
    id = _component_id_value(component)
    if haskey(plan.components, id)
        push!(plan.duplicate_component_ids, id)
    end
    plan.components[id] = component
    for meta in component_parameters(component)
        register_parameter!(plan, meta)
    end
    return component
end

function register_parameter!(plan::CircuitPlan, meta::ParameterMetadata)
    plan.parameters[meta.name] = meta
    return meta
end

